import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from src.utils import fundir_dados_geo_mercado, sanitizar_dados


class SanitizarDadosTests(unittest.TestCase):
    def test_lista_de_dicts_preserva_a_estrutura(self) -> None:
        """pd.isna em lista devolve array; o resultado não pode virar string."""

        dados = [{"id_tecnico": "A"}, {"id_tecnico": "B"}]

        resultado = sanitizar_dados(dados)

        self.assertIsInstance(resultado, list)
        self.assertEqual(resultado, dados)

    def test_escalares_nulos_continuam_normalizados(self) -> None:
        self.assertIsNone(sanitizar_dados(None))
        self.assertIsNone(sanitizar_dados(float("nan")))

    def test_geometria_vira_mapeamento(self) -> None:
        resultado = sanitizar_dados({"geometry": Point(-37.07, -10.94)})

        self.assertEqual(resultado["geometry"]["type"], "Point")


class FundirDadosTests(unittest.TestCase):
    def test_fusao_devolve_lista_de_dicts_com_geometria(self) -> None:
        territories = gpd.GeoDataFrame(
            {"COD_ID": ["A"], "NOME": ["SE-A"]},
            geometry=[Point(-37.0731, -10.9472)],
            crs="EPSG:4326",
        )
        mercado = [{"id_tecnico": "A", "subestacao": "SE-A (ID: A)"}]

        resultado = fundir_dados_geo_mercado(territories, mercado)

        self.assertIsInstance(resultado, list)
        self.assertEqual(resultado[0]["id_tecnico"], "A")
        self.assertEqual(resultado[0]["geometry"]["type"], "Point")

    def test_fusao_aceita_dataframe(self) -> None:
        territories = gpd.GeoDataFrame(
            {"COD_ID": ["A"], "NOME": ["SE-A"]},
            geometry=[Point(-37.0731, -10.9472)],
            crs="EPSG:4326",
        )
        mercado = pd.DataFrame([{"id_tecnico": "A", "subestacao": "SE-A"}])

        resultado = fundir_dados_geo_mercado(territories, mercado)

        self.assertIsInstance(resultado, list)
        self.assertEqual(len(resultado), 1)


if __name__ == "__main__":
    unittest.main()
