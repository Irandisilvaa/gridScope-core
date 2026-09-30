import unittest

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


if __name__ == "__main__":
    unittest.main()
