"""Compatibilidade para o importador de snapshots completos."""

from __future__ import annotations

import os
from pathlib import Path

from src.config import DATABASE_URL, DIR_DADOS, FILE_GDB
from src.etl.importador import CAMADAS_ALVO, SnapshotImportResult, SnapshotImporter


def migrar_gdb_para_sql(
    path_gdb: str | os.PathLike[str] | None = None,
    *,
    limpar_antes: bool | None = None,
    delivery_id: str | None = None,
) -> SnapshotImportResult:
    """Publica um snapshot completo.

    ``limpar_antes`` é aceito somente para compatibilidade com chamadas antigas.
    A limpeza agora ocorre no corte da publicação, depois da validação de todas
    as camadas; nunca antes da carga temporária.
    """

    del limpar_antes
    source = Path(path_gdb) if path_gdb else Path(DIR_DADOS) / FILE_GDB
    resolved_delivery_id = delivery_id or source.name
    return SnapshotImporter(
        DATABASE_URL,
        source,
        delivery_id=resolved_delivery_id,
    ).run()


if __name__ == "__main__":
    result = migrar_gdb_para_sql()
    print(f"Snapshot publicado: {result.delivery_id} ({result.row_counts})")
