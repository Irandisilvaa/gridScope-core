import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.etl import pipeline


class PipelineTests(unittest.TestCase):
    @patch("src.etl.pipeline._invalidate_runtime_cache")
    @patch("src.etl.pipeline._write_metadata")
    @patch("src.etl.pipeline.SnapshotImporter")
    @patch("src.etl.pipeline.create_data_source")
    def test_publicacao_invalida_cache_apos_o_corte(
        self,
        create_data_source,
        snapshot_importer,
        write_metadata,
        invalidate_cache,
    ):
        delivery = Mock(
            local_path=Path("/tmp/entrega.gdb"),
            delivery_id="entrega-b",
            cleanup=Mock(),
        )
        create_data_source.return_value.fetch.return_value = delivery
        resultado = Mock(row_counts={"subestacoes": 1})
        snapshot_importer.return_value.run.return_value = resultado

        pipeline.ingest_current_delivery()

        write_metadata.assert_called_once_with(delivery, resultado)
        invalidate_cache.assert_called_once_with()
        delivery.cleanup.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
