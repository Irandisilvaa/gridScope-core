"""Fonte de arquivo local para desenvolvimento e homologação."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .contratos import DataDelivery
from .exceptions import DataSourceError


def _fingerprint(path: Path) -> str:
    """Gera um identificador estável sem carregar um GDB inteiro em memória."""

    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    if path.is_dir():
        for child in sorted(path.rglob("*")):
            relative = child.relative_to(path).as_posix().encode("utf-8")
            stat = child.stat()
            digest.update(relative)
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
        return digest.hexdigest()

    raise DataSourceError(f"Arquivo de dados não encontrado: {path}")


class LocalFileSource:
    """Entrega um arquivo configurado localmente sem alterar o banco."""

    def __init__(self, path: Path, *, source_name: str = "local_file") -> None:
        self._path = path
        self._source_name = source_name

    def fetch(self) -> DataDelivery:
        if not self._path.exists():
            raise DataSourceError(f"Arquivo de dados não encontrado: {self._path}")

        return DataDelivery(
            local_path=self._path,
            source=self._source_name,
            delivery_id=_fingerprint(self._path),
            format=self._path.suffix.lstrip(".") or "directory",
        )
