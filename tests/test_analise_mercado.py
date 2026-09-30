import unittest
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from src.modelos import analise_mercado


class AnaliseMercadoTests(unittest.TestCase):
    def test_geracao_sem_consumidores_recebe_classe_outros(self) -> None:
        geracao = pd.DataFrame({"PN_CON": ["PN-1"]})
        classificada = analise_mercado._classificar_geracao_por_classe(
            geracao, pd.Series(dtype="object")
        )
        self.assertEqual(classificada.loc[0, "TIPO"], "Outros")

    @patch.object(analise_mercado, "carregar_consumidores")
    @patch.object(analise_mercado.gpd, "sjoin")
    @patch.object(analise_mercado, "carregar_transformadores")
    @patch.object(analise_mercado, "carregar_voronoi")
    def test_falha_ao_carregar_consumidores_interrompe_publicacao(
        self,
        carregar_voronoi,
        carregar_transformadores,
        sjoin,
        carregar_consumidores,
    ) -> None:
        carregar_voronoi.return_value = gpd.GeoDataFrame(
            {"COD_ID": ["SUB-1"], "NOM": ["Sub 1"]},
            geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
            crs="EPSG:31984",
        )
        carregar_transformadores.return_value = gpd.GeoDataFrame(
            {"COD_ID": ["TRAFO-1"]},
            geometry=[Point(0.5, 0.5)],
            crs="EPSG:31984",
        )
        sjoin.return_value = pd.DataFrame(
            {
                "COD_ID_left": ["TRAFO-1"],
                "COD_ID_CLEAN_right": ["SUB-1"],
            }
        )
        carregar_consumidores.side_effect = RuntimeError("banco indisponível")

        with self.assertRaisesRegex(RuntimeError, "análise não publicada"):
            analise_mercado.analisar_mercado()

    @patch.object(analise_mercado.gpd, "sjoin")
    @patch.object(analise_mercado, "carregar_transformadores")
    @patch.object(analise_mercado, "carregar_voronoi")
    def test_transformador_ambiguo_interrompe_publicacao(
        self,
        carregar_voronoi,
        carregar_transformadores,
        sjoin,
    ) -> None:
        carregar_voronoi.return_value = gpd.GeoDataFrame(
            {"COD_ID": ["SUB-1", "SUB-2"], "NOM": ["Sub 1", "Sub 2"]},
            geometry=[
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
            ],
            crs="EPSG:31984",
        )
        carregar_transformadores.return_value = gpd.GeoDataFrame(
            {"COD_ID": ["TRAFO-1"]},
            geometry=[Point(1, 0.5)],
            crs="EPSG:31984",
        )
        sjoin.return_value = pd.DataFrame(
            {
                "COD_ID_left": ["TRAFO-1", "TRAFO-1"],
                "COD_ID_CLEAN_right": ["SUB-1", "SUB-2"],
            }
        )

        with self.assertRaisesRegex(RuntimeError, "vincular transformadores"):
            analise_mercado.analisar_mercado()


if __name__ == "__main__":
    unittest.main()
