from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from src.etl.fontes.http import HttpFileSource
from src.etl.fontes.local import LocalFileSource
from src.etl.fontes.exceptions import UnsafeArchiveError


class LocalFileSourceTests(unittest.TestCase):
    def test_fetch_identifica_uma_entrega_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "snapshot.gdb"
            path.mkdir()
            (path / "layer.dat").write_bytes(b"snapshot")

            delivery = LocalFileSource(path).fetch()

            self.assertEqual(delivery.local_path, path)
            self.assertEqual(delivery.source, "local_file")
            self.assertEqual(delivery.format, "gdb")
            self.assertTrue(delivery.delivery_id)


class HttpFileSourceArchiveTests(unittest.TestCase):
    def test_formata_tamanhos_binarios_corretamente(self) -> None:
        self.assertEqual(HttpFileSource._format_bytes(1024**3), "1.0 GiB")
        self.assertEqual(HttpFileSource._format_bytes(5519 * 1024**2), "5.4 GiB")

    def test_extract_encontra_um_gdb(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "delivery.zip"
            destination = root / "extracted"
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr("snapshot.gdb/UNTRMT", "layer")

            result = HttpFileSource("https://example.invalid/data.zip")._extract_archive(
                archive, destination
            )

            self.assertEqual(result, destination / "snapshot.gdb")
            self.assertEqual((result / "UNTRMT").read_text(), "layer")

    def test_extract_rejeita_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr("../outside.txt", "blocked")

            with self.assertRaises(UnsafeArchiveError):
                HttpFileSource("https://example.invalid/data.zip")._extract_archive(
                    archive, root / "extracted"
                )

    def test_extract_rejeita_path_traversal_com_barra_invertida(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "unsafe-windows.zip"
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr(r"..\outside.txt", "blocked")

            with self.assertRaises(UnsafeArchiveError):
                HttpFileSource("https://example.invalid/data.zip")._extract_archive(
                    archive, root / "extracted"
                )


if __name__ == "__main__":
    unittest.main()
