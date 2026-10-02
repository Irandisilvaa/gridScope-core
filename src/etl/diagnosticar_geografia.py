"""Diagnostica a cobertura municipal de uma BDGD sem publicar dados."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import geopandas as gpd
import pyogrio

from src.limites_municipais import carregar_limites_para_territorio
from src.municipalities import normalizar_codigo_municipio
from src.qualidade_geografica import (
    analisar_cobertura_geografica,
    preparar_transformadores_eligiveis,
    persistir_diagnostico_geografico,
    relatorio_sem_transformadores_elegiveis,
)

logger = logging.getLogger(__name__)


def diagnosticar(gdb_path: Path, output_dir: Path) -> int:
    """Lê exclusivamente UNTRMT e grava um relatório reproduzível."""

    layers = {str(row[0]).casefold(): str(row[0]) for row in pyogrio.list_layers(gdb_path)}
    layer = layers.get("untrmt")
    if not layer:
        raise RuntimeError("Camada UNTRMT não encontrada")
    logger.info("[GEO] Lendo UNTRMT para diagnóstico: %s", gdb_path)
    transformadores = gpd.read_file(
        gdb_path, layer=layer, engine="pyogrio", use_arrow=True, columns=["COD_ID", "SUB", "MUN"]
    )
    elegiveis, invalidos, rejected = preparar_transformadores_eligiveis(transformadores)
    if elegiveis.empty:
        report, occurrences = relatorio_sem_transformadores_elegiveis(
            transformadores, rejected, invalidos
        )
        persistir_diagnostico_geografico(output_dir, report, occurrences)
        return 2
    codigos = elegiveis["MUN"].map(normalizar_codigo_municipio).dropna().unique()
    limites = carregar_limites_para_territorio(codigos)
    report, occurrences = analisar_cobertura_geografica(transformadores, limites)
    persistir_diagnostico_geografico(output_dir, report, occurrences)
    logger.info("[GEO] Diagnóstico salvo em %s", output_dir)
    return 2 if report["status"] == "blocked" else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gdb", required=True, type=Path)
    parser.add_argument("--saida", required=True, type=Path)
    args = parser.parse_args(argv)
    return diagnosticar(args.gdb, args.saida)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
