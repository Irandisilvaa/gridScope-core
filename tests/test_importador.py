from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.etl.importador import SnapshotImportError, SnapshotImporter


class SnapshotImporterTests(unittest.TestCase):
    def _make_importer(self) -> SnapshotImporter:
        return SnapshotImporter(
            "postgresql://unused",
            Path("/tmp/snapshot.gdb"),
            delivery_id="delivery-a",
        )

    def test_publica_derivados_somente_depois_da_preparacao(self) -> None:
        importer = self._make_importer()
        engine = MagicMock()
        publish = MagicMock()
        prepare = MagicMock(return_value={"territorios_voronoi": 3, "cache_mercado": 2})

        with patch("src.etl.importador.create_engine", return_value=engine), patch.object(
            importer, "_validate_source"
        ), patch.object(importer, "_create_schema"), patch.object(
            importer, "_load_layers", return_value={"subestacoes": 3}
        ), patch.object(importer, "_publish", publish), patch.object(
            importer, "_drop_schema"
        ):
            result = importer.run(prepare_publish=prepare)

        prepare.assert_called_once()
        publish.assert_called_once()
        published_tables = set(publish.call_args.args[2])
        self.assertEqual(
            published_tables,
            {"subestacoes", "territorios_voronoi", "cache_mercado"},
        )
        self.assertEqual(result.row_counts["cache_mercado"], 2)

    def test_falha_na_preparacao_nao_publica_nada(self) -> None:
        importer = self._make_importer()
        engine = MagicMock()
        publish = MagicMock()

        with patch("src.etl.importador.create_engine", return_value=engine), patch.object(
            importer, "_validate_source"
        ), patch.object(importer, "_create_schema"), patch.object(
            importer, "_load_layers", return_value={"subestacoes": 3}
        ), patch.object(importer, "_publish", publish), patch.object(
            importer, "_drop_schema"
        ), self.assertRaises(SnapshotImportError):
            importer.run(prepare_publish=MagicMock(side_effect=RuntimeError("falha de derivação")))

        publish.assert_not_called()
        engine.dispose.assert_called_once()

    def test_camada_vazia_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()
        engine = MagicMock()
        publish = MagicMock()
        prepare = MagicMock()

        with patch("src.etl.importador.create_engine", return_value=engine), patch.object(
            importer, "_validate_source"
        ), patch.object(importer, "_create_schema"), patch.object(
            importer, "_load_layers", return_value={"subestacoes": 0}
        ), patch.object(importer, "_publish", publish), patch.object(
            importer, "_drop_schema"
        ), self.assertRaises(SnapshotImportError):
            importer.run(prepare_publish=prepare)

        prepare.assert_not_called()
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
