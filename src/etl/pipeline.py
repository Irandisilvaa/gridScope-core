"""Orquestra aquisição, importação e publicação de uma entrega completa."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import DATABASE_URL, DIR_DADOS, atualizar_cidade_alvo, get_cidade_alvo
from src.etl.fontes import create_data_source
from src.etl.importador import SnapshotImporter
from src.etl.fontes.contratos import DataDelivery
from src.limites_municipais import carregar_limites_para_territorio
from src.municipalities import normalizar_codigo_municipio
from src.qualidade_geografica import (
    GeospatialCoverageError,
    analisar_cobertura_geografica,
    preparar_transformadores_eligiveis,
    persistir_diagnostico_geografico,
    relatorio_sem_transformadores_elegiveis,
)
from src.quarentena_geografica import (
    QuarentenaRecusadaError,
    avaliar_quarentena,
    persistir_quarentena,
)

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
        "publication_id": result.publication_id,
        "format": delivery.format,
        "reference_period": delivery.reference_period,
        "city_target": get_cidade_alvo(),
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


def _invalidate_runtime_cache(publication_id: str | None = None) -> int:
    """Remove respostas Redis que poderiam refletir a carga anterior."""

    try:
        from src.cache_redis import definir_versao_publicacao, limpar_cache

        removidas = 0
        if publication_id:
            definir_versao_publicacao(publication_id)
        removidas += limpar_cache()
        removidas += limpar_cache("coverage_cache:*")
        logger.info("Cache Redis invalidado: %s chaves removidas", removidas)
        return int(removidas)
    except Exception:
        logger.exception("Falha ao invalidar cache Redis após publicação")
        return 0


def _build_derived_tables(
    staging_schema: str,
    diagnostic_dir: Path | None = None,
) -> tuple[dict[str, int], dict[str, object]]:
    """Gera os derivados usando o mesmo schema temporário do snapshot."""

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", staging_schema):
        raise RuntimeError(f"Schema de staging inválido: {staging_schema}")

    environment = os.environ.copy()
    environment["DATABASE_SCHEMA"] = staging_schema
    environment["GRIDSCOPE_DERIVED_STAGING"] = "1"
    quality_report_file = tempfile.NamedTemporaryFile(
        prefix="geospatial-quality-", suffix=".json", delete=False
    )
    quality_report_path = Path(quality_report_file.name)
    quality_report_file.close()
    environment["GRIDSCOPE_GEOSPATIAL_QUALITY_REPORT"] = str(quality_report_path)
    if diagnostic_dir is not None:
        environment["GRIDSCOPE_GEOSPATIAL_DIAGNOSTIC_DIR"] = str(diagnostic_dir / "voronoi")
        environment["GRIDSCOPE_GEOSPATIAL_MESH_MANIFEST"] = str(diagnostic_dir / "malhas.json")
    python_path = environment.get("PYTHONPATH", "")
    source_path = str(PROJECT_ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (source_path, python_path) if part
    )

    for job_index, job in enumerate(DERIVED_JOBS, start=1):
        started = time.monotonic()
        logger.info(
            "[DERIVADOS %s/%s] Iniciando %s...",
            job_index,
            len(DERIVED_JOBS),
            job.name,
        )
        completed = subprocess.run(
            [sys.executable, str(job)],
            cwd=PROJECT_ROOT,
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            quality_report_path.unlink(missing_ok=True)
            raise RuntimeError(f"Job derivado falhou: {job.name}")
        logger.info(
            "[DERIVADOS %s/%s] %s concluído em %.1fs",
            job_index,
            len(DERIVED_JOBS),
            job.name,
            time.monotonic() - started,
        )

    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL, connect_args={"options": f"-csearch_path={staging_schema},public"})
    try:
        counts: dict[str, int] = {}
        with engine.connect() as connection:
            for table_name in (
                "limites_municipais",
                "territorios_voronoi",
                "territorios_voronoi_municipais",
                "cache_mercado",
            ):
                count = connection.execute(
                    text(f'SELECT COUNT(*) FROM "{staging_schema}"."{table_name}"')
                ).scalar_one()
                counts[table_name] = int(count)
                logger.info(
                    "[DERIVADOS] %s validada: %s registros",
                    table_name,
                    f"{counts[table_name]:,}",
                )
        geospatial_quality = {}
        if quality_report_path.exists() and quality_report_path.stat().st_size:
            geospatial_quality = json.loads(quality_report_path.read_text(encoding="utf-8"))
        return counts, {"geospatial": geospatial_quality}
    finally:
        engine.dispose()
        quality_report_path.unlink(missing_ok=True)


def ingest_delivery(delivery: DataDelivery) -> dict:
    """Publica uma entrega adquirida; só grava metadados após o corte bem-sucedido."""

    started = time.monotonic()
    diagnostic_dir = (
        PROJECT_ROOT / "dados" / "diagnosticos" / delivery.delivery_id / uuid.uuid4().hex
    )

    def persist_diagnostic(report, occurrences) -> None:
        try:
            location = persistir_diagnostico_geografico(
                diagnostic_dir / "preflight", report, occurrences
            )
            logger.info("[GEO] Diagnóstico salvo em %s", location)
        except Exception as error:
            # Não esconda uma causa geográfica já conhecida atrás de um erro do
            # driver de exportação. KeyboardInterrupt não deriva de Exception.
            report["diagnostic_persistence_error"] = str(error)
            logger.exception("[GEO] Falha ao persistir diagnóstico em %s", diagnostic_dir)

    def persist_manifest(report) -> bool:
        try:
            diagnostic_dir.mkdir(parents=True, exist_ok=True)
            (diagnostic_dir / "malhas.json").write_text(
                json.dumps(report["boundary_provenance"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception as error:
            report["mesh_manifest_persistence_error"] = str(error)
            logger.exception("[GEO] Falha ao persistir manifesto de malhas em %s", diagnostic_dir)
            return False

    def validate_transformers(transformadores) -> frozenset[str]:
        elegiveis, invalidos, rejected = preparar_transformadores_eligiveis(transformadores)
        if elegiveis.empty:
            report, occurrences = relatorio_sem_transformadores_elegiveis(
                transformadores, rejected, invalidos
            )
            persist_diagnostic(report, occurrences)
            raise GeospatialCoverageError(report, occurrences)
        codigos = elegiveis["MUN"].map(normalizar_codigo_municipio).dropna().unique()
        limites = carregar_limites_para_territorio(codigos)
        report, occurrences = analisar_cobertura_geografica(transformadores, limites)
        manifest_saved = persist_manifest(report)
        persist_diagnostic(report, occurrences)
        if report["status"] == "blocked":
            try:
                quarentena = avaliar_quarentena(report, occurrences)
            except QuarentenaRecusadaError as recusada:
                report["quarantine_blocked_reason"] = str(recusada)
                persist_diagnostic(report, occurrences)
                raise GeospatialCoverageError(report, occurrences) from recusada
            if quarentena is None:
                raise GeospatialCoverageError(report, occurrences)
            persistir_quarentena(diagnostic_dir / "preflight", quarentena, occurrences)
            report["quarantine"] = quarentena.resumo
            report["status"] = "approved_with_quarantine"
            logger.warning(
                "[GEO] Publicação prosseguirá com %s sementes em quarentena auditada",
                f"{quarentena.count:,}",
            )
            persist_diagnostic(report, occurrences)
            return frozenset(quarentena.transformador_ids)
        if not manifest_saved:
            raise RuntimeError("Manifesto de malhas não pôde ser persistido")
        return frozenset()

    logger.info("[PUBLICAÇÃO 1/5] Validando e carregando camadas em staging...")
    try:
        try:
            result = SnapshotImporter(
                DATABASE_URL,
                delivery.local_path,
                delivery_id=delivery.delivery_id,
                publication_metadata={
                    "source": delivery.source,
                    "reference_period": delivery.reference_period,
                    "city_target": get_cidade_alvo(),
                },
                validate_transformers=validate_transformers,
            ).run(
                prepare_publish=lambda staging_schema: _build_derived_tables(
                    staging_schema, diagnostic_dir
                )
            )
        except GeospatialCoverageError as error:
            logger.error(
                "[PUBLICAÇÃO BLOQUEADA] %s; distância máxima %.1fm. Diagnóstico: %s",
                error,
                error.report["distance_statistics_m"]["max"],
                diagnostic_dir,
            )
            raise
        logger.info(
            "[PUBLICAÇÃO 2/5] Corte transacional confirmado: %s",
            result.publication_id,
        )
        try:
            logger.info("[PUBLICAÇÃO 3/5] Atualizando espelho de metadados...")
            _write_metadata(delivery, result)
        except Exception:
            logger.exception(
                "Falha ao atualizar espelho de metadados; o registro transacional do banco permanece vigente"
            )
        logger.info("[PUBLICAÇÃO 4/5] Atualizando namespace e limpando caches Redis...")
        _invalidate_runtime_cache(result.publication_id)
        logger.info("Entrega %s publicada: %s", delivery.delivery_id, result.row_counts)
        response = {
            "delivery_id": delivery.delivery_id,
            "publication_id": result.publication_id,
            "city_target": get_cidade_alvo(),
            "row_counts": result.row_counts,
            "quality_report": result.quality_report,
        }
        logger.info(
            "[PUBLICAÇÃO 5/5] Fluxo concluído em %.1fs",
            time.monotonic() - started,
        )
        return response
    finally:
        logger.info("[LIMPEZA] Removendo arquivos temporários da entrega...")
        delivery.cleanup()
        logger.info("[LIMPEZA] Arquivos temporários removidos")


def ingest_current_delivery() -> dict:
    """Adquire a fonte configurada e executa o fluxo completo."""

    return ingest_delivery(create_data_source().fetch())


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
