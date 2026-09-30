from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.ai import ai_service
from src import database
from src.etl import etl_ai_consumo


class SqlSafetyTests(unittest.TestCase):
    def test_id_da_simulacao_e_parametrizado(self) -> None:
        malicious_id = "A' OR '1'='1"
        with patch.object(ai_service.pd, "read_sql", return_value=None) as read_sql:
            ai_service._buscar_consumo_mensal(object(), malicious_id, 1)

        query = str(read_sql.call_args.args[0])
        self.assertIn(":id_alvo", query)
        self.assertNotIn(malicious_id, query)
        self.assertEqual(read_sql.call_args.kwargs["params"], {"id_alvo": malicious_id})

    def test_mes_invalido_e_rejeitado_antes_da_consulta(self) -> None:
        with self.assertRaises(ValueError):
            ai_service._buscar_consumo_mensal(object(), "A", 13)

    def test_id_do_etl_e_parametrizado(self) -> None:
        malicious_id = "B' OR '1'='1"
        with patch.object(etl_ai_consumo.pd, "read_sql", return_value=None) as read_sql:
            etl_ai_consumo._buscar_consumo_por_classe(object(), malicious_id)

        query = str(read_sql.call_args.args[0])
        self.assertIn(":id_sub", query)
        self.assertNotIn(malicious_id, query)
        self.assertEqual(read_sql.call_args.kwargs["params"], {"id_sub": malicious_id})

    def test_coluna_nao_permitida_e_rejeitada(self) -> None:
        with self.assertRaises(ValueError):
            database._select_columns("consumidores", ["PN_CON; DROP TABLE consumidores"])

    def test_salvadores_de_derivados_usam_schema_configurado(self) -> None:
        engine = MagicMock()
        gdf = MagicMock()
        gdf.crs = None

        with patch.object(database, "DATABASE_SCHEMA", "staging_teste"), patch.object(
            database, "get_engine", return_value=engine
        ), patch.object(database, "_avisar_publicacao_direta"):
            database.salvar_voronoi(gdf)
            with patch.object(database, "criar_tabela_cache"):
                database.salvar_cache_mercado([{"id_tecnico": "SUB-1"}])

        self.assertEqual(gdf.to_postgis.call_args.kwargs["schema"], "staging_teste")
        sqls = [str(call.args[0]) for call in engine.connect.return_value.__enter__.return_value.execute.call_args_list]
        self.assertTrue(any('"staging_teste"."cache_mercado"' in sql for sql in sqls))

if __name__ == "__main__":
    unittest.main()
