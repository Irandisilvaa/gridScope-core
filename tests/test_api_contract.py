from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from shapely.geometry import Point

import geopandas as gpd

import src.api as api_module
from src.cache_redis import limpar_cache


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        limpar_cache()
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
                "geometry": Point(-37.0731, -10.9472),
            }
        ]

    def test_ranking_com_fusao_real_nao_quebra_a_geometria(self) -> None:
        """Cobre a fusão de verdade: o banco entrega lista de dicts sem geometria."""

        mercado = [
            {chave: valor for chave, valor in item.items() if chave != "geometry"}
            for item in self.snapshot
        ]
        territories = gpd.GeoDataFrame(
            {"COD_ID": ["A"], "NOME": ["SE-A"]},
            geometry=[Point(-37.0731, -10.9472)],
            crs="EPSG:4326",
        )

        with patch.object(api_module, "carregar_dados_cache", return_value=(territories, mercado)):
            response = self.client.get("/mercado/ranking")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertIsNotNone(payload[0]["geometry"])

    def test_ranking_aceita_o_schema_aninhado_do_etl(self) -> None:
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=self.snapshot
        ):
            response = self.client.get("/mercado/ranking")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[0]["id_tecnico"], "A")
        self.assertEqual(body[0]["geracao_distribuida"]["detalhe_por_classe"]["Residencial"]["qtd"], 2)

    def test_ranking_vazio_retorna_indisponibilidade(self) -> None:
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=[]
        ):
            response = self.client.get("/mercado/ranking")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("[]", response.text)

    def test_status_lê_somente_metadados_da_carga(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            metadata_path = Path(temporary) / "metadata_carga_atual.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "status": "published",
                        "source": "local_file",
                        "delivery_id": "delivery-a",
                        "city_target": "Aracaju, Sergipe, Brazil",
                        "row_counts": {"subestacoes": 1},
                        "quality_report": {"discarded_records": []},
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(api_module, "carregar_publication_metadata", return_value=None), patch.object(
                api_module, "DIR_DADOS", temporary
            ):
                response = self.client.get("/data/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["delivery_id"], "delivery-a")
        self.assertEqual(response.json()["city_target"], "Aracaju, Sergipe, Brazil")
        self.assertEqual(response.json()["row_counts"], {"subestacoes": 1})
        self.assertEqual(response.json()["quality_report"], {"discarded_records": []})

    def test_status_prioriza_metadados_transacionais_do_banco(self) -> None:
        with patch.object(
            api_module,
            "carregar_publication_metadata",
            return_value={
                "status": "published",
                "source": "local_file",
                "delivery_id": "delivery-db",
                "reference_period": None,
                "city_target": "Lagarto, Sergipe, Brazil",
                "published_at": "2026-09-30T12:00:00+00:00",
                "row_counts": {"subestacoes": 2},
                "quality_report": {
                    "discarded_records": [{"table": "transformadores", "count": 1}]
                },
            },
        ):
            response = self.client.get("/data/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["delivery_id"], "delivery-db")
        self.assertEqual(response.json()["city_target"], "Lagarto, Sergipe, Brazil")
        self.assertEqual(
            response.json()["quality_report"]["discarded_records"][0]["count"],
            1,
        )

    def test_health_nao_depende_do_banco(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(response.headers["X-Request-ID"])

    def test_request_id_fornecido_e_devolvido(self) -> None:
        response = self.client.get("/health", headers={"X-Request-ID": "teste-123"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-ID"], "teste-123")

    def test_readiness_retorna_indisponivel_quando_redis_falha(self) -> None:
        with patch.object(api_module, "get_engine", return_value=MagicMock()), patch.object(
            api_module, "is_redis_available", return_value=False
        ):
            response = self.client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["checks"]["redis"], "unavailable")

    def test_exportacao_csv_protege_texto_de_formula(self) -> None:
        snapshot = [dict(self.snapshot[0], subestacao="=SUM(1,1)")]
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=snapshot
        ):
            response = self.client.get("/mercado/ranking.csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=gridscope-ranking.csv", response.headers["content-disposition"])
        self.assertIn("'=SUM(1,1)", response.content.decode("utf-8-sig"))
        self.assertNotIn("geometry", response.content.decode("utf-8-sig"))

    def test_exportacao_csv_aplica_busca_e_situacao(self) -> None:
        attention = dict(
            self.snapshot[0],
            id_tecnico="B",
            subestacao="SE-B (ID: B)",
            metricas_rede={**self.snapshot[0]["metricas_rede"], "nivel_criticidade_gd": "ALTA"},
        )
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=[self.snapshot[0], attention]
        ):
            response = self.client.get("/mercado/ranking.csv?busca=SE-B&situacao=attention")

        body = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SE-B", body)
        self.assertNotIn("SE-A", body)

    def test_exportacao_csv_rejeita_situacao_invalida(self) -> None:
        response = self.client.get("/mercado/ranking.csv?situacao=unknown")

        self.assertEqual(response.status_code, 400)

    def test_ranking_nao_expõe_detalhe_da_excecao(self) -> None:
        with patch.object(api_module, "carregar_dados_cache", side_effect=RuntimeError("segredo interno")):
            response = self.client.get("/mercado/ranking")

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("segredo interno", response.text)

    def test_simulacao_nao_expõe_detalhe_da_excecao(self) -> None:
        with patch.object(
            api_module,
            "_carregar_alvo_simulacao",
            side_effect=RuntimeError("consulta interna inválida"),
        ):
            response = self.client.get("/simulacao/id/A")

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("consulta interna inválida", response.text)

    def test_simulacao_por_id_usa_identificador_estavel(self) -> None:
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=self.snapshot
        ), patch.object(
            api_module,
            "obter_clima_avancado",
            return_value=(5.0, 25.0, "Ceu Limpo", "Teste"),
        ):
            response = self.client.get("/simulacao/id/A?data=2026-09-29")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subestacao"], "SE-A (ID: A)")
        self.assertEqual(response.json()["data_referencia"], "29/09/2026")

    def test_simulacao_por_id_rejeita_id_ausente_e_ambiguo(self) -> None:
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=self.snapshot
        ):
            missing = self.client.get("/simulacao/id/inexistente")

        self.assertEqual(missing.status_code, 404)

        duplicate = [self.snapshot[0], dict(self.snapshot[0], subestacao="SE-B (ID: A)")]
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=duplicate
        ):
            ambiguous = self.client.get("/simulacao/id/A")

        self.assertEqual(ambiguous.status_code, 409)

    def test_simulacao_rejeita_localizacao_ausente(self) -> None:
        sem_geometria = dict(self.snapshot[0], geometry=None)
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=[sem_geometria]
        ), patch.object(api_module, "obter_clima_avancado") as clima:
            response = self.client.get("/simulacao/id/A")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Brasília", response.text)
        clima.assert_not_called()

    def test_simulacao_por_nome_nao_escolhe_primeiro_resultado_ambiguo(self) -> None:
        duplicate_names = [
            dict(self.snapshot[0], subestacao="SE-A - Norte"),
            dict(self.snapshot[0], id_tecnico="B", subestacao="SE-A - Sul"),
        ]
        with patch.object(api_module, "carregar_dados_cache", return_value=(None, [])), patch.object(
            api_module, "fundir_dados_geo_mercado", return_value=duplicate_names
        ):
            response = self.client.get("/simulacao/SE-A")

        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
