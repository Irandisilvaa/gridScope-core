import unittest
from unittest.mock import MagicMock, patch

from src.etl import atualizar_banco, migracao_db


class PublicationPathTests(unittest.TestCase):
    @patch("src.etl.migracao_db.SnapshotImporter")
    @patch("src.etl.migracao_db._invalidate_runtime_cache")
    def test_migracao_legada_publica_derivados_no_mesmo_corte(self, invalidate_cache, importer_type):
        importer_type.return_value.run.return_value = MagicMock(
            delivery_id="delivery-b", publication_id="publication-b"
        )

        migracao_db.migrar_gdb_para_sql("/tmp/snapshot.gdb", delivery_id="delivery-b")

        importer_type.return_value.run.assert_called_once_with(
            prepare_publish=migracao_db._build_derived_tables
        )
        self.assertEqual(
            importer_type.call_args.kwargs["publication_metadata"],
            {"source": "local_file", "city_target": migracao_db.get_cidade_alvo()},
        )
        invalidate_cache.assert_called_once_with("publication-b")

    @patch("src.etl.atualizar_banco.ingest_current_delivery")
    def test_atualizacao_manual_delega_ao_pipeline_canonico(self, ingest):
        ingest.return_value = {"delivery_id": "delivery-b", "row_counts": {"subestacoes": 1}}

        result = atualizar_banco.atualizar_banco_completo()

        ingest.assert_called_once_with()
        self.assertEqual(result["delivery_id"], "delivery-b")


if __name__ == "__main__":
    unittest.main()
