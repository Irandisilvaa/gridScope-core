"""Importação segura de um snapshot completo em PostgreSQL/PostGIS."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Iterable, Mapping

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

CAMADAS_ALVO: Mapping[str, str] = {
    "UNTRMT": "transformadores",
    "UCBT_tab": "consumidores",
    "UGBT_tab": "geracao_gd",
    "SUB": "subestacoes",
    "SSDMT": "rede_mt",
}
_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class SnapshotImportError(RuntimeError):
    """Falha que impede a substituição da carga publicada."""


@dataclass(frozen=True)
class SnapshotImportResult:
    delivery_id: str
    source_path: Path
    row_counts: dict[str, int]


class SnapshotImporter:
    """Carrega e publica um snapshot sem expor tabelas parcialmente carregadas."""

    def __init__(
        self,
        database_url: str,
        source_path: Path,
        *,
        delivery_id: str,
        layers: Mapping[str, str] = CAMADAS_ALVO,
    ) -> None:
        self._database_url = database_url
        self._source_path = source_path
        self._delivery_id = delivery_id
        self._layers = layers

    def run(
        self,
        *,
        prepare_publish: Callable[[str], Mapping[str, int]] | None = None,
    ) -> SnapshotImportResult:
        self._validate_source()
        engine = create_engine(self._database_url, pool_pre_ping=True)
        staging_schema = f"staging_{uuid.uuid4().hex}"

        try:
            self._create_schema(engine, staging_schema)
            counts = self._load_layers(engine, staging_schema)
            self._validate_counts(counts)
            if prepare_publish:
                derived_counts = dict(prepare_publish(staging_schema))
                self._validate_counts(derived_counts)
                counts.update(derived_counts)
            self._publish(engine, staging_schema, counts.keys())
            return SnapshotImportResult(self._delivery_id, self._source_path, counts)
        except Exception as exc:
            logger.exception("Falha na importação do snapshot %s", self._delivery_id)
            raise SnapshotImportError(
                f"Snapshot {self._delivery_id} não foi publicado: {exc}"
            ) from exc
        finally:
            self._drop_schema(engine, staging_schema)
            engine.dispose()

    def _validate_source(self) -> None:
        if not self._source_path.exists():
            raise SnapshotImportError(f"Fonte não encontrada: {self._source_path}")
        if not self._source_path.is_dir() and self._source_path.suffix.lower() != ".gdb":
            raise SnapshotImportError(f"Formato de fonte não suportado: {self._source_path}")

    @staticmethod
    def _create_schema(engine: Engine, schema: str) -> None:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    def _load_layers(self, engine: Engine, schema: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for layer_name, table_name in self._layers.items():
            if not _IDENTIFIER.match(table_name):
                raise SnapshotImportError(f"Nome de tabela inválido: {table_name}")
            dataframe = self._read_layer(layer_name)
            if dataframe.empty:
                raise SnapshotImportError(f"Camada obrigatória vazia: {layer_name}")
            self._write_layer(dataframe, table_name, schema, engine)
            counts[table_name] = len(dataframe)
            logger.info("Camada %s carregada em staging: %s registros", layer_name, len(dataframe))
        return counts

    def _read_layer(self, layer_name: str) -> gpd.GeoDataFrame | pd.DataFrame:
        try:
            return gpd.read_file(
                self._source_path,
                layer=layer_name,
                engine="pyogrio",
                use_arrow=True,
            )
        except Exception as pyogrio_error:
            logger.warning("Fallback de leitura para %s: %s", layer_name, pyogrio_error)
            try:
                return gpd.read_file(self._source_path, layer=layer_name)
            except Exception as exc:
                raise SnapshotImportError(f"Falha ao ler camada {layer_name}: {exc}") from exc

    @staticmethod
    def _write_layer(
        dataframe: gpd.GeoDataFrame | pd.DataFrame,
        table_name: str,
        schema: str,
        engine: Engine,
    ) -> None:
        has_geometry = isinstance(dataframe, gpd.GeoDataFrame) and "geometry" in dataframe.columns
        if has_geometry:
            if dataframe.crs is None:
                raise SnapshotImportError(f"Camada espacial sem CRS: {table_name}")
            normalized = dataframe.to_crs("EPSG:4326")
            normalized.to_postgis(
                table_name,
                engine,
                schema=schema,
                if_exists="replace",
                index=False,
                chunksize=5000,
            )
            return

        dataframe.to_sql(
            table_name,
            engine,
            schema=schema,
            if_exists="replace",
            index=False,
            chunksize=5000,
            method="multi",
        )

    @staticmethod
    def _validate_counts(counts: Mapping[str, int]) -> None:
        missing = [table for table, count in counts.items() if count <= 0]
        if missing:
            raise SnapshotImportError(f"Camadas sem registros: {', '.join(missing)}")

    def _publish(
        self,
        engine: Engine,
        staging_schema: str,
        table_names: Iterable[str],
    ) -> None:
        old_suffix = uuid.uuid4().hex
        with engine.begin() as connection:
            for table_name in table_names:
                if not _IDENTIFIER.match(table_name):
                    raise SnapshotImportError(f"Nome de tabela inválido: {table_name}")
                old_name = f"__old_{old_suffix}_{table_name}"
                connection.execute(
                    text(
                        f'ALTER TABLE IF EXISTS public."{table_name}" '
                        f'RENAME TO "{old_name}"'
                    )
                )
                connection.execute(
                    text(
                        f'ALTER TABLE "{staging_schema}"."{table_name}" '
                        'SET SCHEMA public'
                    )
                )
                connection.execute(
                    text(f'DROP TABLE IF EXISTS public."{old_name}" CASCADE')
                )

    @staticmethod
    def _drop_schema(engine: Engine, schema: str) -> None:
        try:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        except Exception:
            logger.exception("Não foi possível remover staging %s", schema)
