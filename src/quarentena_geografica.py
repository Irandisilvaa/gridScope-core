"""Quarentena auditada para sementes fora da área de operação.

Existe um caso em que nenhuma malha oficial resolve o problema: o atributo
``MUN`` da BDGD declara um município do estado, mas a coordenada cai fisicamente
em município de outra UF. A malha está certa; a entrega é que carrega um
registro incoerente. Ampliar a malha para acomodá-lo seria fabricar território
para uma coordenada errada, então a alternativa é excluir o registro da carga —
sempre de forma explícita, contável e auditável.

A quarentena cobre apenas falha de posição. Geometria inválida, coordenada não
finita, identificador ausente ou município inválido continuam bloqueando a
publicação, porque não são corrigíveis por decisão de escopo. E o volume
excluído é limitado: acima da fração máxima o volume indica falha sistêmica da
entrega, não outliers isolados, e a publicação permanece bloqueada.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

RAZAO_QUARENTENA = "geospatial_outlier_quarantine"
CLASSIFICACOES_QUARENAVEIS = frozenset({"outside_above_tolerance"})
FRACAO_MAXIMA_PADRAO = float(
    os.getenv("GRIDSCOPE_QUARENTENA_FRACAO_MAXIMA", "0.005")
)
ARQUIVO_QUARENTENA = "quarentena.csv"


class QuarentenaRecusadaError(RuntimeError):
    """A exclusão não é segura ou possível; a publicação deve ficar bloqueada."""


@dataclass(frozen=True)
class Quarentena:
    """Resultado aplicado: os ``transformador_ids`` saíram da carga."""

    transformador_ids: tuple[str, ...]
    resumo: dict

    @property
    def count(self) -> int:
        return len(self.transformador_ids)


def avaliar_quarentena(
    report: dict,
    occurrences: pd.DataFrame,
    *,
    fracao_maxima: float = FRACAO_MAXIMA_PADRAO,
) -> Quarentena | None:
    """Aplica a quarentena ou recusa; devolve ``None`` quando nada está bloqueado.

    A função nunca devolve uma quarentena vazia para "perdoar" um bloqueio: com o
    relatório bloqueado, o retorno é a quarentena aplicada ou uma exceção. O
    chamador só recebe ``None`` quando a publicação já está aprovada.
    """

    if fracao_maxima <= 0:
        raise ValueError("A fração máxima da quarentena deve ser positiva")
    if report.get("status") != "blocked":
        return None

    invalidos = int(report.get("invalid_or_ineligible_count") or 0)
    elegiveis = int(report.get("eligible_transformer_count") or 0)
    if occurrences is None or occurrences.empty:
        raise QuarentenaRecusadaError(
            "A publicação está bloqueada, mas não há ocorrências geográficas "
            f"auditáveis ({invalidos} sementes com falha de integridade); "
            "a quarentena exige um diagnóstico reproduzível"
        )
    if "classification" not in occurrences.columns:
        raise QuarentenaRecusadaError(
            "As ocorrências não têm a coluna de classificação geográfica; "
            "a quarentena exige um diagnóstico reproduzível"
        )

    candidatas = occurrences.loc[
        occurrences["classification"].isin(CLASSIFICACOES_QUARENAVEIS)
    ]
    if candidatas.empty:
        raise QuarentenaRecusadaError(
            "A publicação está bloqueada sem nenhum outlier geométrico "
            f"quarentenável ({invalidos} sementes com falha de integridade); "
            "corrija a origem da entrega"
        )
    if invalidos:
        raise QuarentenaRecusadaError(
            f"Quarentena não se aplica: há {invalidos} sementes com falha de "
            "integridade (geometria, identificador ou município) além dos "
            "outliers geométricos; corrija a origem da entrega"
        )

    if "transformador_id" not in candidatas.columns:
        raise QuarentenaRecusadaError(
            "Quarentena não aplicada: as ocorrências não têm transformador_id"
        )
    ids = candidatas["transformador_id"].astype("string").str.strip()
    if bool(ids.eq("").any()):
        raise QuarentenaRecusadaError(
            "Quarentena não aplicada: há outliers sem transformador_id auditável"
        )

    unicos = tuple(sorted(set(ids.tolist())))
    fracao = (len(unicos) / elegiveis) if elegiveis else 1.0
    if fracao > fracao_maxima:
        raise QuarentenaRecusadaError(
            f"{len(unicos)} sementes ({fracao:.2%}) excedem o limite de "
            f"{fracao_maxima:.2%} para quarentena. Esse volume indica falha "
            "sistêmica da entrega, não outliers isolados"
        )

    resumo = {
        "applied": True,
        "reason": RAZAO_QUARENTENA,
        "quarantined_count": len(unicos),
        "quarantined_record_count": len(candidatas),
        "quarantined_fraction_of_eligible": round(fracao, 8),
        "max_fraction_allowed": fracao_maxima,
        "eligible_transformer_count": elegiveis,
        "outside_tolerance_m": report.get("tolerance_m"),
        "max_distance_m": _max_distance(candidatas),
        "by_declared_municipality": _contagem(candidatas, "municipio_codigo"),
        "by_substation": _contagem(candidatas, "subestacao_id"),
        "artifact": ARQUIVO_QUARENTENA,
    }
    logger.warning(
        "[GEO] Quarentena auditada: %s sementes excluídas (%.3f%% das elegíveis, "
        "limite %.3f%%), cada ID registrado em %s. A malha publicada não foi ampliada.",
        f"{len(unicos):,}",
        fracao * 100,
        fracao_maxima * 100,
        ARQUIVO_QUARENTENA,
    )
    return Quarentena(unicos, resumo)


def _max_distance(candidatas: pd.DataFrame) -> float | None:
    coluna = "distance_to_study_boundary_m"
    if coluna not in candidatas.columns:
        return None
    valores = pd.to_numeric(candidatas[coluna], errors="coerce").dropna()
    return round(float(valores.max()), 3) if not valores.empty else None


def _contagem(candidatas: pd.DataFrame, coluna: str) -> dict[str, int]:
    if coluna not in candidatas.columns:
        return {}
    return {
        str(chave): int(valor)
        for chave, valor in candidatas[coluna].fillna("invalid_or_missing").value_counts().items()
    }


def persistir_quarentena(
    directory: Path,
    quarentena: Quarentena,
    occurrences: pd.DataFrame,
) -> Path:
    """Grava o artefato auditável e confirma que ele reproduz tudo que foi excluído."""

    esperado = int(quarentena.resumo["quarantined_record_count"])
    if occurrences is None or occurrences.empty or "transformador_id" not in occurrences.columns:
        raise QuarentenaRecusadaError(
            "Não foi possível gravar a quarentena: ocorrências sem transformador_id"
        )
    ids = pd.Index(quarentena.transformador_ids)
    linhas = occurrences.loc[
        occurrences["transformador_id"].astype("string").str.strip().isin(ids)
    ]
    if len(linhas) != esperado:
        raise QuarentenaRecusadaError(
            "Não foi possível gravar a quarentena: o artefato não reproduz "
            f"todos os registros excluídos ({len(linhas)} de {esperado})"
        )
    linhas = linhas.copy()
    linhas.insert(0, "quarantine_reason", RAZAO_QUARENTENA)
    directory.mkdir(parents=True, exist_ok=True)
    destino = directory / ARQUIVO_QUARENTENA
    linhas.to_csv(destino, index=False)
    logger.info("[GEO] Quarentena gravada em %s", destino)
    return destino