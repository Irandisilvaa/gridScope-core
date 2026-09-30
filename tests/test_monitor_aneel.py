import unittest
from unittest.mock import Mock, mock_open, patch

from src.etl import monitor_aneel


class MonitorAneelTests(unittest.TestCase):
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

    @patch("src.etl.monitor_aneel.requests.get")
    def test_falha_na_consulta_nao_indica_publicacao(self, get):
        get.return_value = Mock(status_code=503)

        self.assertIsNone(monitor_aneel.verificar_aneel())


if __name__ == "__main__":
    unittest.main()
