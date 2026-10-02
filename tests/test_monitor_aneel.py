import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

from src.etl import monitor_aneel


class MonitorAneelTests(unittest.TestCase):
    def test_file_geodatabase_usa_endpoint_de_download_do_arcgis(self):
        url = monitor_aneel._url_de_referencia(
            {
                "title": "Light_382_2025-12-31_V11_20260824-0926",
                "id": "snapshot-light",
            }
        )

        self.assertEqual(
            url,
            "https://www.arcgis.com/sharing/rest/content/items/snapshot-light/data",
        )

    @patch("src.etl.monitor_aneel.requests.get")
    def test_consulta_nao_baixa_nem_altera_dados(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {
            "features": [
                {
                    "properties": {
                        "title": "Energisa SE BDGD 2025 - Link",
                        "id": "entrega-2025",
                        "updated": "2025-12-01",
                        "url": "https://example.test/documents/entrega-2025",
                    }
                }
            ]
        }
        get.return_value = response

        with patch.object(monitor_aneel, "DISTRIBUIDORA_ALVO", "Energisa SE"):
            with patch("builtins.open", mock_open()) as opened:
                referencia = monitor_aneel.verificar_aneel()

        self.assertEqual(referencia["id"], "entrega-2025")
        opened.assert_not_called()
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs["params"]["limit"], 100)

    @patch("src.etl.monitor_aneel.requests.get")
    def test_falha_na_consulta_nao_indica_publicacao(self, get):
        get.return_value = Mock(status_code=503)

        self.assertIsNone(monitor_aneel.verificar_aneel())

    @patch("src.etl.monitor_aneel.requests.get")
    def test_refaz_busca_com_bdgd_quando_resultado_e_generico(self, get):
        generic = Mock(status_code=200)
        generic.json.return_value = {
            "features": [
                {"properties": {"title": "light_posts", "id": "generic"}}
            ]
        }
        bdgd = Mock(status_code=200)
        bdgd.json.return_value = {
            "features": [
                {
                    "properties": {
                        "title": "Light_382_2025-12-31_V11_20260824-0926",
                        "id": "snapshot",
                    }
                }
            ]
        }
        get.side_effect = [generic, bdgd]

        referencia = monitor_aneel.verificar_aneel("Light")

        self.assertEqual(referencia["id"], "snapshot")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["q"], "Light BDGD")

    def test_resolve_link_arcgis_para_url_de_download(self):
        response = Mock(headers={"Content-Type": "application/json"})
        response.json.return_value = {
            "sourceUrl": "https://dados.example.test/light-bdgd.zip"
        }
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        url = monitor_aneel.resolver_url_download(
            {
                "name": "Light BDGD 2025 - Link",
                "url": "https://www.arcgis.com/items/light/data",
            },
            session=session,
        )

        self.assertEqual(url, "https://dados.example.test/light-bdgd.zip")

    @patch("src.etl.monitor_aneel.HttpFileSource")
    @patch("src.etl.monitor_aneel.resolver_url_download", return_value="https://example.test/base.zip")
    @patch("src.etl.monitor_aneel.verificar_aneel", return_value={"name": "Light", "url": "https://ref.test"})
    def test_baixa_qualquer_distribuidora_para_destino_local(
        self, _verificar, _resolver, source_type
    ):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as destination:
            gdb = Path(source_dir) / "delivery.gdb"
            gdb.mkdir()
            (gdb / "a.gdbtable").write_bytes(b"data")
            delivery = Mock(
                local_path=gdb,
                delivery_id="a" * 64,
                cleanup=Mock(),
            )
            source_type.return_value.fetch.return_value = delivery

            result = monitor_aneel.adquirir_aneel("Light", destino=destination)

            self.assertTrue(Path(result["local_path"]).is_dir())
            self.assertTrue((Path(result["local_path"]) / "a.gdbtable").exists())
            delivery.cleanup.assert_called_once_with()
            self.assertEqual(source_type.call_args.kwargs["source_name"], "aneel")

    @patch("src.etl.pipeline.ingest_delivery", return_value={"publication_id": "pub-1"})
    @patch("src.etl.monitor_aneel.HttpFileSource")
    @patch("src.etl.monitor_aneel.resolver_url_download", return_value="https://example.test/base.zip")
    @patch("src.etl.monitor_aneel.verificar_aneel", return_value={"name": "Light", "url": "https://ref.test"})
    def test_publica_entrega_somente_quando_solicitado(
        self, _verificar, _resolver, source_type, ingest_delivery
    ):
        delivery = Mock(cleanup=Mock())
        source_type.return_value.fetch.return_value = delivery

        result = monitor_aneel.adquirir_aneel("Light", publicar=True)

        self.assertEqual(result["publication_id"], "pub-1")
        ingest_delivery.assert_called_once_with(delivery)
        delivery.cleanup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
