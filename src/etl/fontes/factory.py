"""Composição dos adaptadores de fonte."""

from __future__ import annotations

from pathlib import Path

from src.config import (
    DATA_MAX_ARCHIVE_ENTRIES,
    DATA_MAX_DOWNLOAD_BYTES,
    DATA_SOURCE,
    DATA_SOURCE_TIMEOUT_SECONDS,
    DIR_DADOS,
    DISTRIBUTOR_API_TOKEN,
    DISTRIBUTOR_SOURCE_URL,
    FILE_GDB,
)

from .contratos import DataSource
from .exceptions import UnsupportedDataSourceError
from .http import HttpFileSource
from .local import LocalFileSource


def create_data_source() -> DataSource:
    """Cria a fonte configurada sem acoplar o pipeline ao transporte."""

    if DATA_SOURCE == "local_file":
        if not FILE_GDB:
            raise UnsupportedDataSourceError("FILE_GDB é obrigatório para DATA_SOURCE=local_file")
        return LocalFileSource(Path(DIR_DADOS) / FILE_GDB)

    if DATA_SOURCE in {"distributor_http", "http"}:
        return HttpFileSource(
            DISTRIBUTOR_SOURCE_URL or "",
            token=DISTRIBUTOR_API_TOKEN,
            timeout_seconds=DATA_SOURCE_TIMEOUT_SECONDS,
            max_download_bytes=DATA_MAX_DOWNLOAD_BYTES,
            max_archive_entries=DATA_MAX_ARCHIVE_ENTRIES,
        )

    raise UnsupportedDataSourceError(f"DATA_SOURCE não suportado: {DATA_SOURCE}")
