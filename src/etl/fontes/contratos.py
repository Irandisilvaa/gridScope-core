"""Contratos estáveis entre aquisição de dados e o pipeline de publicação."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol


Cleanup = Callable[[], None]


@dataclass(frozen=True)
class DataDelivery:
    """Entrega pronta para validação e importação em staging."""

    local_path: Path
    source: str
    delivery_id: str
    reference_period: str | None = None
    format: str = "unknown"
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cleanup: Cleanup = field(default=lambda: None, repr=False, compare=False)


class DataSource(Protocol):
    """Porta de aquisição; o importador não conhece o transporte da fonte."""

    def fetch(self) -> DataDelivery:
        """Obtém uma entrega completa ou falha sem alterar o banco publicado."""
