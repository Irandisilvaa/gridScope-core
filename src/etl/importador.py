"""Importação segura de um snapshot completo em PostgreSQL/PostGIS."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Callable, Iterable, Mapping

import geopandas as gpd
import pandas as pd
import pyogrio
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
# Colunas que não podem vir nulas: nelas se apoiam junções e agregações.
_KEY_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "UNTRMT": ("COD_ID",),
    "UCBT_tab": ("UNI_TR_MT", "PN_CON"),
    "UGBT_tab": ("UNI_TR_MT", "PN_CON"),
    "SUB": ("COD_ID",),
    "SSDMT": ("COD_ID",),
}
# Unicidade só é exigida onde a entrega realmente garante. Contra o GDB real,
# consumidores e geração repetem o mesmo transformador e o mesmo PN_CON de forma
# legítima (1.066.358 linhas para 182.855 PN_CON distintos), então exigir chave
# única rejeitaria a entrega sem evitar defeito algum.
_UNIQUE_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "UNTRMT": ("COD_ID",),
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
_OPTIONAL_COLUMNS: Mapping[str, set[str]] = {
    "UNTRMT": {"MUN"},
    "UCBT_tab": {"MUN"},
    "UGBT_tab": {"MUN"},
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
    publication_id: str
    delivery_id: str
    source_path: Path
    row_counts: dict[str, int]
    quality_report: dict[str, object] = field(default_factory=dict)


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
        prepare_publish: Callable[
            [str], Mapping[str, int] | tuple[Mapping[str, int], Mapping[str, object]]
        ] | None = None,
    ) -> SnapshotImportResult:
        self._validate_source()
        engine = create_engine(self._database_url, pool_pre_ping=True)
        staging_schema = f"staging_{uuid.uuid4().hex}"

        try:
            self._create_schema(engine, staging_schema)
            counts, quality_report = self._load_layers(engine, staging_schema)
            self._validate_counts(counts)
            if prepare_publish:
                prepared = prepare_publish(staging_schema)
                if isinstance(prepared, tuple):
                    derived_counts = dict(prepared[0])
                    quality_report.update(dict(prepared[1]))
                else:
                    derived_counts = dict(prepared)
                self._validate_counts(derived_counts)
                counts.update(derived_counts)
            publication_id = str(uuid.uuid4())
            self._publish(
                engine,
                staging_schema,
                counts.keys(),
                counts,
                quality_report,
                publication_id,
            )
            return SnapshotImportResult(
                publication_id,
                self._delivery_id,
                self._source_path,
                counts,
                quality_report,
            )
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

    def _load_layers(self, engine: Engine, schema: str) -> tuple[dict[str, int], dict[str, object]]:
        counts: dict[str, int] = {}
        loaded: dict[str, pd.DataFrame] = {}
        discarded_records: list[dict[str, object]] = []
        excluded_transformer_ids: set[str] = set()
        for layer_name, table_name in self._layers.items():
            if not _IDENTIFIER.match(table_name):
                raise SnapshotImportError(f"Nome de tabela inválido: {table_name}")
            dataframe = self._read_layer(layer_name)
            self._validate_layer_schema(layer_name, dataframe)
            if layer_name == "UNTRMT":
                dataframe, reports = self._discard_transformers_without_substation(dataframe)
                for report in reports:
                    discarded_records.append({"table": table_name, **report})
                    if report["reason"] == "missing_substation":
                        excluded_transformer_ids.update(report["ids"])
            elif layer_name in {"UCBT_tab", "UGBT_tab"}:
                dataframe, reports = self._discard_transformer_dependents(
                    dataframe,
                    excluded_transformer_ids,
                    table_name,
                )
                discarded_records.extend(
                    {"table": table_name, **report} for report in reports
                )
            if dataframe.empty:
                raise SnapshotImportError(f"Camada obrigatória vazia: {layer_name}")
            self._write_layer(dataframe, table_name, schema, engine)
            counts[table_name] = len(dataframe)
            loaded[table_name] = dataframe
            logger.info("Camada %s carregada em staging: %s registros", layer_name, len(dataframe))
        self._validate_references(loaded)
        quality_report: dict[str, object] = {}
        if discarded_records:
            quality_report["discarded_records"] = discarded_records
        return counts, quality_report

    @staticmethod
    def _discard_transformers_without_substation(
        dataframe: gpd.GeoDataFrame | pd.DataFrame,
    ) -> tuple[gpd.GeoDataFrame | pd.DataFrame, list[dict[str, object]]]:
        substation = dataframe["SUB"].astype("string").str.strip()
        discarded = dataframe["SUB"].isna() | substation.eq("")
        if not bool(discarded.any()):
            return dataframe, []

        ids = sorted({str(value).strip() for value in dataframe.loc[discarded, "COD_ID"]})
        logger.warning(
            "Transformadores sem subestação utilizável serão descartados: %s",
            ", ".join(ids),
        )
        return dataframe.loc[~discarded].copy(), [
            {
                "reason": "missing_substation",
                "count": len(ids),
                "ids": ids,
            }
        ]

    @staticmethod
    def _discard_transformer_dependents(
        dataframe: gpd.GeoDataFrame | pd.DataFrame,
        excluded_transformer_ids: set[str],
        table_name: str,
    ) -> tuple[gpd.GeoDataFrame | pd.DataFrame, list[dict[str, object]]]:

        transformer_ids = dataframe["UNI_TR_MT"].astype("string").str.strip()
        missing_transformer = transformer_ids.isna() | transformer_ids.eq("")
        discarded_transformer = transformer_ids.isin(excluded_transformer_ids)
        discarded = missing_transformer | discarded_transformer
        if not bool(discarded.any()):
            return dataframe, []

        reports: list[dict[str, object]] = []
        if bool(discarded_transformer.any()):
            dependent_ids = sorted(set(transformer_ids[discarded_transformer].tolist()))
            logger.warning(
                "Registros de %s ligados a transformadores descartados: %s",
                table_name,
                int(discarded_transformer.sum()),
            )
            reports.append(
                {
                    "reason": "discarded_transformer",
                    "count": int(discarded_transformer.sum()),
                    "transformer_ids": dependent_ids,
                }
            )
        if bool(missing_transformer.any()):
            logger.warning(
                "Registros de %s sem transformador serão descartados: %s",
                table_name,
                int(missing_transformer.sum()),
            )
            reports.append(
                {
                    "reason": "missing_transformer",
                    "count": int(missing_transformer.sum()),
                }
            )
        return dataframe.loc[~discarded].copy(), reports

    def _read_layer(self, layer_name: str) -> gpd.GeoDataFrame | pd.DataFrame:
        columns = self._colunas_utiles(layer_name)
        try:
            return gpd.read_file(
                self._source_path,
                layer=layer_name,
                engine="pyogrio",
                use_arrow=True,
                columns=columns,
            )
        except Exception as pyogrio_error:
            logger.warning("Fallback de leitura para %s: %s", layer_name, pyogrio_error)
            try:
                return gpd.read_file(
                    self._source_path,
                    layer=layer_name,
                    engine="pyogrio",
                    columns=columns,
                )
            except Exception as exc:
                raise SnapshotImportError(f"Falha ao ler camada {layer_name}: {exc}") from exc

    def _colunas_utiles(self, layer_name: str) -> list[str] | None:
        """Projeta a camada nas colunas que o resto do sistema efetivamente le.

        A entrega traz dezenas de colunas que ninguém consome: em uma camada
        de mais de um milhão de registros, ler tudo elevou o pico de memória
        de 566 MB para 1731 MB sem nenhum ganho. Colunas ausentes ficam de
        fora da projeção para que a validação de esquema continue reportando
        o que falta, em vez de estourar no leitor.
        """
        desejadas = (
            _REQUIRED_COLUMNS.get(layer_name, set())
            | set(_KEY_COLUMNS.get(layer_name, ()))
            | set(_OPTIONAL_COLUMNS.get(layer_name, ()))
        )
        if not desejadas:
            return None
        try:
            info = pyogrio.read_info(self._source_path, layer=layer_name)
        except Exception:
            logger.warning("Sem metadados de %s; lendo todas as colunas", layer_name)
            return None
        # Só pede o que existe no arquivo: a validação de esquema precisa ver
        # a camada inteira para apontar o que falta.
        disponiveis = set(info["fields"])
        colunas = sorted(desejadas & disponiveis)
        # O pyogrio descreve a geometria fora de "fields".
        if info.get("geometry_type") and "geometry" in desejadas:
            colunas.append("geometry")
        return colunas or None

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

        for column in _UNIQUE_COLUMNS.get(layer_name, ()):
            if column not in dataframe.columns:
                continue
            keys = dataframe[column]
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
                    f"{len(orphans)} registro(s) de {table_name} referenciam "
                    f"{column} inexistente em {target_table}: {', '.join(exemplos)}"
                )

    def _publish(
        self,
        engine: Engine,
        staging_schema: str,
        table_names: Iterable[str],
        row_counts: Mapping[str, int],
        quality_report: Mapping[str, object],
        publication_id: str,
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
                        publication_id UUID NOT NULL,
                        delivery_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        reference_period TEXT,
                        city_target TEXT,
                        published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        row_counts JSONB NOT NULL,
                        quality_report JSONB NOT NULL DEFAULT '{}'::jsonb
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    ALTER TABLE public.grid_scope_publication
                    ADD COLUMN IF NOT EXISTS publication_id UUID
                    """
                )
            )
            connection.execute(
                text(
                    """
                    UPDATE public.grid_scope_publication
                    SET publication_id = gen_random_uuid()
                    WHERE publication_id IS NULL
                    """
                )
            )
            connection.execute(
                text(
                    """
                    ALTER TABLE public.grid_scope_publication
                    ADD COLUMN IF NOT EXISTS quality_report JSONB NOT NULL DEFAULT '{}'::jsonb
                    """
                )
            )
            connection.execute(
                text(
                    """
                    ALTER TABLE public.grid_scope_publication
                    ADD COLUMN IF NOT EXISTS city_target TEXT
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO public.grid_scope_publication
                        (
                            publication_key,
                            publication_id,
                            delivery_id,
                            source,
                            reference_period,
                            city_target,
                            published_at,
                            row_counts,
                            quality_report
                        )
                    VALUES (
                        1,
                        CAST(:publication_id AS uuid),
                        :delivery_id,
                        :source,
                        :reference_period,
                        :city_target,
                        NOW(),
                        CAST(:row_counts AS jsonb),
                        CAST(:quality_report AS jsonb)
                    )
                    ON CONFLICT (publication_key) DO UPDATE SET
                        delivery_id = EXCLUDED.delivery_id,
                        publication_id = EXCLUDED.publication_id,
                        source = EXCLUDED.source,
                        reference_period = EXCLUDED.reference_period,
                        city_target = EXCLUDED.city_target,
                        published_at = EXCLUDED.published_at,
                        row_counts = EXCLUDED.row_counts,
                        quality_report = EXCLUDED.quality_report
                    """
                ),
                {
                    "publication_id": publication_id,
                    "delivery_id": self._delivery_id,
                    "source": str(self._publication_metadata.get("source", "unknown")),
                    "reference_period": self._publication_metadata.get("reference_period"),
                    "city_target": self._publication_metadata.get("city_target"),
                    "row_counts": json.dumps(dict(row_counts), ensure_ascii=False),
                    "quality_report": json.dumps(dict(quality_report), ensure_ascii=False),
                },
            )
            connection.execute(
                text(
                    """
                    ALTER TABLE public.grid_scope_publication
                    ALTER COLUMN publication_id SET NOT NULL
                    """
                )
            )

    @staticmethod
    def _drop_schema(engine: Engine, schema: str) -> None:
        try:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        except Exception:
            logger.exception("Não foi possível remover staging %s", schema)
