import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ai import ai_service


class AiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(ai_service.app)

    def test_rejeita_latitude_fora_do_intervalo(self) -> None:
        response = self.client.post(
            "/predict/duck-curve",
            json={
                "data_alvo": "2026-09-30",
                "potencia_gd_kw": 10,
                "consumo_mes_alvo_mwh": 100,
                "lat": 91,
                "lon": -37,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_health_indica_estado_do_modelo(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "gridscope-ai")
        self.assertIn("model_loaded", response.json())

    def test_rejeita_longitude_fora_do_intervalo(self) -> None:
        response = self.client.post(
            "/predict/duck-curve",
            json={
                "data_alvo": "2026-09-30",
                "potencia_gd_kw": 10,
                "consumo_mes_alvo_mwh": 100,
                "lat": -10,
                "lon": 181,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_nao_expoe_detalhe_de_excecao_interna(self) -> None:
        with patch.object(ai_service, "resolver_subestacao", side_effect=RuntimeError("segredo interno")):
            response = self.client.post(
                "/predict/duck-curve",
                json={
                    "data_alvo": "2026-09-30",
                    "potencia_gd_kw": 10,
                    "consumo_mes_alvo_mwh": 100,
                    "lat": -10,
                    "lon": -37,
                },
            )

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("segredo interno", response.text)


if __name__ == "__main__":
    unittest.main()
