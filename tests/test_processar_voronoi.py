import unittest

import geopandas as gpd
from shapely.geometry import Point, Polygon

from src.modelos.processar_voronoi import (
    gerar_recortes_municipais,
    gerar_territorios_por_transformadores,
)


class ProcessarVoronoiTests(unittest.TestCase):
    def _limite(self) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {
                "municipio_codigo": ["2800308"],
                "nome": ["Aracaju"],
                "uf": ["28"],
                "fonte": ["teste"],
                "qualidade": ["teste"],
            },
            geometry=[
                Polygon(
                    [
                        (-37.30, -11.30),
                        (-36.90, -11.30),
                        (-36.90, -10.90),
                        (-37.30, -10.90),
                    ]
                )
            ],
            crs="EPSG:4326",
        )

    def test_territorio_usa_todos_os_transformadores_e_nao_o_centro_da_subestacao(self):
        transformadores = gpd.GeoDataFrame(
            {
                "COD_ID": ["T-A1", "T-A2", "T-B1", "T-B2"],
                "SUB": ["SUB-A", "SUB-A", "SUB-B", "SUB-B"],
                "MUN": ["2800308"] * 4,
            },
            geometry=[
                Point(-37.25, -11.15),
                Point(-36.95, -11.15),
                Point(-37.29, -11.05),
                Point(-37.05, -11.05),
            ],
            crs="EPSG:4326",
        )
        subestacoes = gpd.GeoDataFrame(
            {"COD_ID": ["SUB-A", "SUB-B"], "NOME": ["A", "B"]},
            geometry=[Point(-37.10, -11.15), Point(-37.17, -11.05)],
            crs="EPSG:4326",
        )

        territorios = gerar_territorios_por_transformadores(
            transformadores,
            subestacoes,
            self._limite(),
        )

        self.assertEqual(set(territorios["COD_ID"]), {"SUB-A", "SUB-B"})
        self.assertTrue(territorios["SITE_LON"].notna().all())
        self.assertTrue(territorios["SITE_LAT"].notna().all())
        self.assertTrue(territorios["LABEL_LON"].notna().all())
        self.assertTrue(territorios["LABEL_LAT"].notna().all())
        for row in territorios.itertuples():
            label = Point(row.LABEL_LON, row.LABEL_LAT)
            self.assertTrue(row.geometry.covers(label))
        joined = gpd.sjoin(
            transformadores.to_crs(territorios.crs),
            territorios[["COD_ID", "geometry"]],
            how="left",
            predicate="within",
            lsuffix="trafo",
            rsuffix="territorio",
        )
        self.assertTrue((joined["SUB"] == joined["COD_ID_territorio"]).all())

    def test_recorta_territorios_globais_por_municipio(self):
        territorios = gpd.GeoDataFrame(
            {"COD_ID": ["SUB-A"], "NOM": ["A"]},
            geometry=[
                Polygon(
                    [
                        (-37.30, -11.30),
                        (-36.90, -11.30),
                        (-36.90, -10.90),
                        (-37.30, -10.90),
                    ]
                )
            ],
            crs="EPSG:4326",
        )
        limites = self._limite().copy()
        limites["municipio_codigo"] = "2800308"

        recortes = gerar_recortes_municipais(territorios, limites)

        self.assertEqual(len(recortes), 1)
        self.assertEqual(recortes.iloc[0]["municipio_codigo"], "2800308")
        self.assertTrue(recortes.geometry.iloc[0].is_valid)
        label = Point(recortes.iloc[0]["LABEL_LON"], recortes.iloc[0]["LABEL_LAT"])
        self.assertTrue(recortes.geometry.iloc[0].covers(label))

    def test_ponto_dentro_da_tolerancia_nao_expande_a_area_oficial(self):
        transformadores = gpd.GeoDataFrame(
            {
                "SUB": ["SUB-FORA", "SUB-DENTRO"],
                "MUN": ["2800308", "2800308"],
            },
            geometry=[Point(-37.301, -11.10), Point(-37.10, -11.10)],
            crs="EPSG:4326",
        )
        subestacoes = gpd.GeoDataFrame(
            {"COD_ID": ["SUB-FORA", "SUB-DENTRO"], "NOME": ["Fora", "Dentro"]},
            geometry=[Point(-37.301, -11.10), Point(-37.10, -11.10)],
            crs="EPSG:4326",
        )

        territorios_wgs = gerar_territorios_por_transformadores(
            transformadores,
            subestacoes,
            self._limite(),
        )
        report = territorios_wgs.attrs["geospatial_quality_report"]
        territorios = territorios_wgs.to_crs(epsg=31984)
        limite = self._limite().to_crs(epsg=31984).geometry.iloc[0]

        self.assertTrue(all(limite.covers(geometry) for geometry in territorios.geometry))
        self.assertEqual(report["outside_official_boundary_count"], 1)
        self.assertEqual(report["outside_official_boundary"][0]["subestacao_id"], "SUB-FORA")

    def test_rejeita_coordenada_compartilhada_por_subestacoes_diferentes(self):
        transformadores = gpd.GeoDataFrame(
            {
                "SUB": ["SUB-A", "SUB-B"],
                "MUN": ["2800308", "2800308"],
            },
            geometry=[Point(-37.10, -11.10), Point(-37.10, -11.10)],
            crs="EPSG:4326",
        )
        subestacoes = gpd.GeoDataFrame(
            {"COD_ID": ["SUB-A", "SUB-B"], "NOME": ["A", "B"]},
            geometry=[Point(-37.10, -11.10), Point(-37.10, -11.10)],
            crs="EPSG:4326",
        )

        with self.assertRaisesRegex(RuntimeError, "compartilham coordenadas"):
            gerar_territorios_por_transformadores(
                transformadores,
                subestacoes,
                self._limite(),
            )


if __name__ == "__main__":
    unittest.main()
