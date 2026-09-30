import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.etl import pipeline


class PipelineTests(unittest.TestCase):
    @patch("src.etl.pipeline.subprocess.run")
    @patch("sqlalchemy.create_engine")
    def test_jobs_derivados_recebem_modo_staging(self, create_engine, run_job):
        engine = create_engine.return_value
        connection = engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.scalar_one.return_value = 1
        run_job.return_value.returncode = 0

        pipeline._build_derived_tables("staging_delivery")

        self.assertEqual(run_job.call_count, len(pipeline.DERIVED_JOBS))
        for call in run_job.call_args_list:
            self.assertEqual(call.kwargs["env"]["DATABASE_SCHEMA"], "staging_delivery")
            self.assertEqual(call.kwargs["env"]["GRIDSCOPE_DERIVED_STAGING"], "1")

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
        invalidate_cache.assert_called_once_with("entrega-b")
        delivery.cleanup.assert_called_once_with()

    @patch("src.etl.pipeline._invalidate_runtime_cache")
    @patch("src.etl.pipeline._write_metadata", side_effect=OSError("filesystem read-only"))
    @patch("src.etl.pipeline.SnapshotImporter")
    @patch("src.etl.pipeline.create_data_source")
    def test_falha_no_espelho_de_metadados_nao_desfaz_publicacao(
        self,
        create_data_source,
        snapshot_importer,
        _write_metadata,
        invalidate_cache,
    ):
        delivery = Mock(
            local_path=Path("/tmp/entrega.gdb"),
            delivery_id="entrega-c",
            source="local_file",
            reference_period=None,
            cleanup=Mock(),
        )
        create_data_source.return_value.fetch.return_value = delivery
        snapshot_importer.return_value.run.return_value = Mock(
            row_counts={"subestacoes": 1}
        )

        resultado = pipeline.ingest_current_delivery()

        self.assertEqual(resultado["delivery_id"], "entrega-c")
        invalidate_cache.assert_called_once_with("entrega-c")
        delivery.cleanup.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
