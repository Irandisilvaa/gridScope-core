"""Importação segura de um snapshot completo em PostgreSQL/PostGIS."""

from __future__ import annotations

import json
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
# Chave estável de cada camada; usada para bloquear duplicatas e chaves nulas.
_KEY_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "UNTRMT": ("COD_ID",),
    "UCBT_tab": ("UNI_TR_MT", "PN_CON"),
    "UGBT_tab": ("UNI_TR_MT", "PN_CON"),
    "SUB": ("COD_ID",),
    "SSDMT": ("COD_ID",),
}
# Relações esperadas entre camadas; órfãos indicam entrega truncada.
_REFERENCES: Mapping[str, tuple[tuple[str, str, str], ...]] = {
    "transformadores": (("SUB", "subestacoes", "COD_ID"),),
    "rede_mt": (("SUB", "subestacoes", "COD_ID"),),
    "consumidores": (("UNI_TR_MT", "transformadores", "COD_ID"),),
    "geracao_gd": (("UNI_TR_MT", "transformadores", "COD_ID"),),
}
_REQUIRED_COLUMNS: Mapping[str, set[str]] = {
    "UNTRMT": {"COD_ID", "SUB", "geometry"},
    "UCBT_tab": {
        "UNI_TR_MT", "CLAS_SUB", "PN_CON", "DAT_CON",
        *(f"ENE_{month:02d}" for month in range(1, 13)),
    },
    "UGBT_tab": {"UNI_TR_MT", "POT_INST", "PN_CON", "DAT_CON"},
    "SUB": {"COD_ID", "NOME", "geometry"},
    "SSDMT": {"COD_ID", "SUB", "geometry"},
}


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
        publication_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self._database_url = database_url
        self._source_path = source_path
        self._delivery_id = delivery_id
        self._layers = layers
        self._publication_metadata = dict(publication_metadata or {})

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
            self._publish(engine, staging_schema, counts.keys(), counts)
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
        loaded: dict[str, pd.DataFrame] = {}
        for layer_name, table_name in self._layers.items():
            if not _IDENTIFIER.match(table_name):
                raise SnapshotImportError(f"Nome de tabela inválido: {table_name}")
            dataframe = self._read_layer(layer_name)
            self._validate_layer_schema(layer_name, dataframe)
            if dataframe.empty:
                raise SnapshotImportError(f"Camada obrigatória vazia: {layer_name}")
            self._write_layer(dataframe, table_name, schema, engine)
            counts[table_name] = len(dataframe)
            loaded[table_name] = dataframe
            logger.info("Camada %s carregada em staging: %s registros", layer_name, len(dataframe))
        self._validate_references(loaded)
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

    @staticmethod
    def _validate_layer_schema(layer_name: str, dataframe: gpd.GeoDataFrame | pd.DataFrame) -> None:
        required = _REQUIRED_COLUMNS.get(layer_name)
        if required is None:
            raise SnapshotImportError(f"Camada não reconhecida: {layer_name}")

        missing = sorted(required.difference(dataframe.columns))
        if missing:
            raise SnapshotImportError(
                f"Camada {layer_name} sem colunas obrigatórias: {', '.join(missing)}"
            )

        if "geometry" in required:
            if not isinstance(dataframe, gpd.GeoDataFrame) or dataframe.crs is None:
                raise SnapshotImportError(f"Camada espacial sem CRS: {layer_name}")
            invalid = ~dataframe.geometry.is_valid & ~dataframe.geometry.is_empty
            if bool(invalid.any()):
                raise SnapshotImportError(
                    f"Camada {layer_name} com geometria inválida: "
                    f"{int(invalid.sum())} registro(s)"
                )

        for column in _KEY_COLUMNS.get(layer_name, ()):
            if column not in dataframe.columns:
                continue
            keys = dataframe[column]
            if bool(keys.isna().any()):
                raise SnapshotImportError(
                    f"Camada {layer_name} com identificador nulo em {column}: "
                    f"{int(keys.isna().sum())} registro(s)"
                )
            duplicated = keys.duplicated()
            if bool(duplicated.any()):
                exemplos = sorted({str(valor) for valor in keys[duplicated][:5]})
                raise SnapshotImportError(
                    f"Camada {layer_name} com identificador duplicado em {column}: "
                    f"{int(duplicated.sum())} registro(s), exemplos {', '.join(exemplos)}"
                )

    @staticmethod
    def _validate_references(tabelas: Mapping[str, pd.DataFrame]) -> None:
        """Bloqueia entrega truncada: nenhuma camada pode referenciar órfãos."""

        for table_name, relations in _REFERENCES.items():
            dataframe = tabelas.get(table_name)
            if dataframe is None or dataframe.empty:
                continue

            for column, target_table, target_column in relations:
                target = tabelas.get(target_table)
                if target is None or target.empty or column not in dataframe.columns:
                    continue
                if target_column not in target.columns:
                    continue

                known = set(target[target_column].astype(str))
                referenced = dataframe[column].astype(str)
                orphans = referenced[~referenced.isin(known)]
                orphans = orphans[orphans != "nan"]
                if orphans.empty:
                    continue

                exemplos = sorted(set(orphans[:5]))
                raise SnapshotImportError(
                    f"{len(set(orphans))} registro(s) de {table_name} referenciam "
                    f"{column} inexistente em {target_table}: {', '.join(exemplos)}"
                )

    def _publish(
        self,
        engine: Engine,
        staging_schema: str,
        table_names: Iterable[str],
        row_counts: Mapping[str, int],
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
                        f'DROP TABLE IF EXISTS public."{old_name}" CASCADE'
                    )
                )
                connection.execute(
                    text(
                        f'ALTER TABLE "{staging_schema}"."{table_name}" '
                        'SET SCHEMA public'
                    )
                )

            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS public.grid_scope_publication (
                        publication_key SMALLINT PRIMARY KEY CHECK (publication_key = 1),
                        delivery_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        reference_period TEXT,
                        published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        row_counts JSONB NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO public.grid_scope_publication
                        (publication_key, delivery_id, source, reference_period, published_at, row_counts)
                    VALUES (1, :delivery_id, :source, :reference_period, NOW(), CAST(:row_counts AS jsonb))
                    ON CONFLICT (publication_key) DO UPDATE SET
                        delivery_id = EXCLUDED.delivery_id,
                        source = EXCLUDED.source,
                        reference_period = EXCLUDED.reference_period,
                        published_at = EXCLUDED.published_at,
                        row_counts = EXCLUDED.row_counts
                    """
                ),
                {
                    "delivery_id": self._delivery_id,
                    "source": str(self._publication_metadata.get("source", "unknown")),
                    "reference_period": self._publication_metadata.get("reference_period"),
                    "row_counts": json.dumps(dict(row_counts), ensure_ascii=False),
                },
            )

    @staticmethod
    def _drop_schema(engine: Engine, schema: str) -> None:
        try:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        except Exception:
            logger.exception("Não foi possível remover staging %s", schema)
