"""Adaptador HTTP para uma entrega de arquivo da distribuidora.

O adaptador não presume o endpoint real. URL, token e limites são fornecidos
por configuração somente depois que o contrato com a distribuidora existir.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

import requests

from .contratos import DataDelivery
from .exceptions import DataSourceError, UnsafeArchiveError

logger = logging.getLogger(__name__)


class HttpFileSource:
    """Baixa uma entrega ZIP e expõe o GDB extraído em uma área temporária."""

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        timeout_seconds: int = 120,
        max_download_bytes: int = 2 * 1024 * 1024 * 1024,
        max_archive_entries: int = 100_000,
        source_name: str = "distributor_http",
        reference_period: str | None = None,
    ) -> None:
        if not url:
            raise DataSourceError("DISTRIBUTOR_SOURCE_URL não foi configurada")
        self._url = url
        self._token = token
        self._timeout = timeout_seconds
        self._max_download_bytes = max_download_bytes
        self._max_archive_entries = max_archive_entries
        self._source_name = source_name
        self._reference_period = reference_period

    def fetch(self) -> DataDelivery:
        temporary_root = Path(tempfile.mkdtemp(prefix="gridscope-delivery-"))
        archive_path = temporary_root / "delivery.zip"

        try:
            delivery_id = self._download(archive_path)
            gdb_path = self._extract_archive(archive_path, temporary_root / "extracted")
            return DataDelivery(
                local_path=gdb_path,
                source=self._source_name,
                delivery_id=delivery_id,
                reference_period=self._reference_period,
                format="gdb_zip",
                cleanup=lambda: shutil.rmtree(temporary_root, ignore_errors=True),
            )
        except Exception:
            shutil.rmtree(temporary_root, ignore_errors=True)
            raise

    def _download(self, destination: Path) -> str:
        headers = {"User-Agent": "GridScope/1.0", "Accept": "application/zip"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        digest = hashlib.sha256()
        downloaded = 0
        last_reported_percent = -10
        last_reported_bytes = 0
        try:
            with requests.get(
                self._url,
                headers=headers,
                stream=True,
                timeout=(10, self._timeout),
            ) as response:
                response.raise_for_status()
                content_length = response.headers.get("Content-Length")
                total_bytes = int(content_length) if content_length else None
                if total_bytes and total_bytes > self._max_download_bytes:
                    raise DataSourceError("Entrega excede o limite de download configurado")
                logger.info(
                    "Iniciando download de %s",
                    self._format_bytes(total_bytes) if total_bytes else "tamanho desconhecido",
                )

                with destination.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if downloaded > self._max_download_bytes:
                            raise DataSourceError("Entrega excede o limite de download configurado")
                        digest.update(chunk)
                        output.write(chunk)
                        if total_bytes:
                            percent = int(downloaded * 100 / total_bytes)
                            if percent >= last_reported_percent + 5:
                                logger.info(
                                    "Download: %s/%s (%s%%)",
                                    self._format_bytes(downloaded),
                                    self._format_bytes(total_bytes),
                                    percent,
                                )
                                last_reported_percent = percent
                        elif downloaded - last_reported_bytes >= 256 * 1024 * 1024:
                            logger.info("Download: %s", self._format_bytes(downloaded))
                            last_reported_bytes = downloaded
        except requests.RequestException as exc:
            raise DataSourceError(f"Falha ao obter entrega da distribuidora: {exc}") from exc

        if not zipfile.is_zipfile(destination):
            raise DataSourceError("A entrega HTTP não é um ZIP válido")
        logger.info("Download concluído: %s. Validando e extraindo GDB...", self._format_bytes(downloaded))
        return digest.hexdigest()

    def _extract_archive(self, archive: Path, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(archive) as zip_file:
                entries = zip_file.infolist()
                if len(entries) > self._max_archive_entries:
                    raise UnsafeArchiveError("ZIP contém entradas demais")

                expanded_size = sum(info.file_size for info in entries)
                if expanded_size > self._max_download_bytes:
                    raise UnsafeArchiveError("Conteúdo expandido excede o limite configurado")
                logger.info(
                    "Extraindo %s entradas (%s expandidos)",
                    len(entries),
                    self._format_bytes(expanded_size),
                )

                root = destination.resolve()
                report_every = max(1, len(entries) // 20)
                for index, info in enumerate(entries, start=1):
                    normalized_name = info.filename.replace("\\", "/")
                    member = PurePosixPath(normalized_name)
                    if member.is_absolute() or ".." in member.parts:
                        raise UnsafeArchiveError(f"Caminho inválido no ZIP: {info.filename}")
                    target = (destination.joinpath(*member.parts)).resolve()
                    if root != target and root not in target.parents:
                        raise UnsafeArchiveError(f"Caminho inválido no ZIP: {info.filename}")
                    if self._is_symlink(info):
                        raise UnsafeArchiveError(f"Symlink não permitido no ZIP: {info.filename}")
                    if not info.is_dir():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zip_file.open(info) as source, target.open("wb") as output:
                            shutil.copyfileobj(source, output, length=1024 * 1024)
                    if index % report_every == 0 or index == len(entries):
                        logger.info(
                            "Extração: %s/%s entradas (%s%%)",
                            index,
                            len(entries),
                            int(index * 100 / len(entries)),
                        )
        except zipfile.BadZipFile as exc:
            raise DataSourceError("ZIP inválido") from exc

        gdb_candidates = sorted(
            candidate
            for candidate in destination.rglob("*")
            if candidate.is_dir() and candidate.suffix.lower() == ".gdb"
        )
        if len(gdb_candidates) != 1:
            raise DataSourceError(
                f"A entrega deve conter exatamente um GDB; encontrados {len(gdb_candidates)}"
            )
        logger.info("GDB extraído e validado: %s", gdb_candidates[0].name)
        return gdb_candidates[0]

    @staticmethod
    def _format_bytes(value: int) -> str:
        amount = float(value)
        for unit in ("B", "KiB", "MiB", "GiB"):
            if amount < 1024 or unit == "GiB":
                return f"{amount:.1f} {unit}"
            amount /= 1024
        return f"{amount:.1f} GiB"

    @staticmethod
    def _is_symlink(info: zipfile.ZipInfo) -> bool:
        mode = (info.external_attr >> 16) & 0o170000
        return mode == 0o120000
