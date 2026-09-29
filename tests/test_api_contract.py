from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api as api_module


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(api_module.app)
        self.snapshot = [
            {
                "subestacao": "SE-A (ID: A)",
                "id_tecnico": "A",
                "metricas_rede": {
                    "total_clientes": 12,
                    "consumo_anual_mwh": 34.5,
                    "nivel_criticidade_gd": "NORMAL",
                },
                "geracao_distribuida": {
                    "total_unidades": 2,
                    "potencia_total_kw": 18.0,
                    "detalhe_por_classe": {
                        "Residencial": {"potencia_kw": 18.0, "qtd": 2}
                    },
                },
                "perfil_consumo": {},
                "evolucao_temporal": [],
                "geometry": None,
            }
        ]

    def test_ranking_aceita_o_schema_aninhado_do_etl(self) -> None:
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=self.snapshot
        ):
            response = self.client.get("/mercado/ranking")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[0]["id_tecnico"], "A")
        self.assertEqual(body[0]["geracao_distribuida"]["detalhe_por_classe"]["Residencial"]["qtd"], 2)

    def test_status_lê_somente_metadados_da_carga(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            metadata_path = Path(temporary) / "metadata_carga_atual.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "status": "published",
                        "source": "local_file",
                        "delivery_id": "delivery-a",
                        "row_counts": {"subestacoes": 1},
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(api_module, "DIR_DADOS", temporary):
                response = self.client.get("/data/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["delivery_id"], "delivery-a")
        self.assertEqual(response.json()["row_counts"], {"subestacoes": 1})


if __name__ == "__main__":
    unittest.main()
