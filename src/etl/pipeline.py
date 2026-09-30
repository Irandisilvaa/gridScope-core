"""Orquestra aquisição, importação e publicação de uma entrega completa."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.config import DATABASE_URL, DIR_DADOS, atualizar_cidade_alvo, get_cidade_alvo
from src.etl.fontes import create_data_source
from src.etl.importador import SnapshotImporter

logger = logging.getLogger(__name__)
DATA_DIRECTORY = Path(DIR_DADOS)
METADATA_PATH = DATA_DIRECTORY / "metadata_carga_atual.json"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DERIVED_JOBS = (
    PROJECT_ROOT / "src" / "modelos" / "processar_voronoi.py",
    PROJECT_ROOT / "src" / "modelos" / "analise_mercado.py",
)


def _write_metadata(delivery, result) -> None:
    metadata = {
        "status": "published",
        "source": delivery.source,
        "delivery_id": delivery.delivery_id,
        "format": delivery.format,
        "reference_period": delivery.reference_period,
        "received_at": delivery.received_at.isoformat(),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "row_counts": result.row_counts,
        "quality_report": result.quality_report,
    }
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=DATA_DIRECTORY,
        prefix="metadata-",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump(metadata, temporary, ensure_ascii=False, indent=2)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    temporary_path.replace(METADATA_PATH)


def _invalidate_runtime_cache(delivery_id: str | None = None) -> int:
    """Remove respostas Redis que poderiam refletir a carga anterior."""

    try:
        from src.cache_redis import definir_versao_publicacao, limpar_cache

        if delivery_id:
            definir_versao_publicacao(delivery_id)
        removidas = limpar_cache()
        logger.info("Cache Redis invalidado: %s chaves removidas", removidas)
        return int(removidas)
    except Exception:
        logger.exception("Falha ao invalidar cache Redis após publicação")
        return 0


def _build_derived_tables(staging_schema: str) -> dict[str, int]:
    """Gera os derivados usando o mesmo schema temporário do snapshot."""

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", staging_schema):
        raise RuntimeError(f"Schema de staging inválido: {staging_schema}")

    environment = os.environ.copy()
    environment["DATABASE_SCHEMA"] = staging_schema
    environment["GRIDSCOPE_DERIVED_STAGING"] = "1"
    python_path = environment.get("PYTHONPATH", "")
    source_path = str(PROJECT_ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (source_path, python_path) if part
    )

    for job in DERIVED_JOBS:
        completed = subprocess.run(
            [sys.executable, str(job)],
            cwd=PROJECT_ROOT,
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Job derivado falhou: {job.name}")

    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL, connect_args={"options": f"-csearch_path={staging_schema},public"})
    try:
        counts: dict[str, int] = {}
        with engine.connect() as connection:
            for table_name in ("territorios_voronoi", "cache_mercado"):
                count = connection.execute(
                    text(f'SELECT COUNT(*) FROM "{staging_schema}"."{table_name}"')
                ).scalar_one()
                counts[table_name] = int(count)
        return counts
    finally:
        engine.dispose()


def ingest_current_delivery() -> dict:
    """Executa o fluxo completo; só grava metadados após o corte bem-sucedido."""

    source = create_data_source()
    delivery = source.fetch()
    try:
        result = SnapshotImporter(
            DATABASE_URL,
            delivery.local_path,
            delivery_id=delivery.delivery_id,
            publication_metadata={
                "source": delivery.source,
                "reference_period": delivery.reference_period,
            },
        ).run(prepare_publish=_build_derived_tables)
        try:
            _write_metadata(delivery, result)
        except Exception:
            logger.exception(
                "Falha ao atualizar espelho de metadados; o registro transacional do banco permanece vigente"
            )
        _invalidate_runtime_cache(delivery.delivery_id)
        logger.info("Entrega %s publicada: %s", delivery.delivery_id, result.row_counts)
        return {
            "delivery_id": delivery.delivery_id,
            "row_counts": result.row_counts,
            "quality_report": result.quality_report,
        }
    finally:
        delivery.cleanup()


def ingest_city(cidade: str) -> dict:
    """Publica a entrega atual para uma cidade e restaura a anterior em falha."""

    cidade_anterior = get_cidade_alvo()
    atualizar_cidade_alvo(cidade)
    try:
        return ingest_current_delivery()
    except Exception:
        atualizar_cidade_alvo(cidade_anterior)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ingest_current_delivery()
