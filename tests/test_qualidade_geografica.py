import json
import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from src.qualidade_geografica import analisar_cobertura_geografica, persistir_diagnostico_geografico


class QualidadeGeograficaTests(unittest.TestCase):
    def _limites(self):
        return gpd.GeoDataFrame(
            {"municipio_codigo": ["3304557"]},
            geometry=[Polygon([(-43.3, -23.1), (-43.0, -23.1), (-43.0, -22.9), (-43.3, -22.9)])],
            crs="EPSG:4326",
        )

    def test_classifica_transformador_e_mantem_ids_auditaveis(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["TRAFO-DENTRO", "TRAFO-FORA"], "SUB": ["SUB-A", "SUB-B"], "MUN": ["3304557", "3304557"]},
            geometry=[Point(-43.2, -23.0), Point(-43.4, -23.0)],
            crs="EPSG:4326",
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())

        self.assertEqual(report["inside_count"], 1)
        self.assertEqual(report["outside_above_tolerance_count"], 1)
        self.assertEqual(occurrences.iloc[0]["transformador_id"], "TRAFO-FORA")
        self.assertEqual(occurrences.iloc[0]["subestacao_id"], "SUB-B")
        self.assertGreater(occurrences.iloc[0]["distance_to_study_boundary_m"], 250)

    def test_persiste_resumo_csv_e_geojson(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["TRAFO-FORA"], "SUB": ["SUB-B"], "MUN": ["3304557"]},
            geometry=[Point(-43.4, -23.0)], crs="EPSG:4326",
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())
        with tempfile.TemporaryDirectory() as temporary:
            directory = persistir_diagnostico_geografico(Path(temporary), report, occurrences)
            self.assertTrue((directory / "resumo.json").exists())
            self.assertTrue((directory / "transformadores_fora.csv").exists())
            self.assertTrue((directory / "transformadores_fora.geojson").exists())
            self.assertEqual(json.loads((directory / "resumo.json").read_text())["status"], "blocked")

    def test_geometria_nao_pontual_bloqueia_sem_ser_ignorada(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["INVALIDO"], "SUB": ["SUB-A"], "MUN": ["3304557"]},
            geometry=[Polygon([(-43.2, -23.0), (-43.1, -23.0), (-43.1, -22.95), (-43.2, -23.0)])],
            crs="EPSG:4326",
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["invalid_or_ineligible_count"], 1)
        self.assertEqual(report["unique_seed_count"], 0)
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences.iloc[0]["transformador_id"], "INVALIDO")
        self.assertEqual(occurrences.iloc[0]["subestacao_id"], "SUB-A")
        self.assertEqual(occurrences.iloc[0]["classification"], "invalid_geometry_or_identifier")

    def test_sem_subestacao_e_descartado_sem_bloquear_outro_transformador(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["VALIDO", "DESCARTADO"], "SUB": ["SUB-A", ""], "MUN": ["3304557", "3304557"]},
            geometry=[Point(-43.2, -23.0), Point(-43.2, -23.0)], crs="EPSG:4326",
        )
        report, _ = analisar_cobertura_geografica(transformadores, self._limites())

        self.assertEqual(report["status"], "approved")
        self.assertEqual(report["ineligible_counts"]["discarded_missing_substation_count"], 1)

    def test_substitui_geojson_antigo_por_colecao_vazia(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["VALIDO"], "SUB": ["SUB-A"], "MUN": ["3304557"]},
            geometry=[Point(-43.2, -23.0)], crs="EPSG:4326",
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "transformadores_fora.geojson").write_text('{"old":true}')
            persistir_diagnostico_geografico(directory, report, occurrences)

            geojson = json.loads((directory / "transformadores_fora.geojson").read_text())
            self.assertEqual(geojson, {"type": "FeatureCollection", "features": []})

    def test_coordenada_infinita_bloqueia_sem_quebrar_crs_ou_geojson(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["VALIDO", "INFINITO"], "SUB": ["SUB-A", "SUB-B"], "MUN": ["3304557", "3304557"]},
            geometry=[Point(-43.2, -23.0), Point(float("inf"), -23.0)], crs="EPSG:4326",
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())

        self.assertEqual(report["status"], "blocked")
        invalid = occurrences.loc[occurrences["transformador_id"] == "INFINITO"].iloc[0]
        self.assertEqual(invalid["classification"], "non_finite_coordinate")
        self.assertIsNone(invalid["longitude"])
        self.assertIsNone(invalid["latitude"])
        with tempfile.TemporaryDirectory() as temporary:
            directory = persistir_diagnostico_geografico(Path(temporary), report, occurrences)
            rows = (directory / "transformadores_fora.csv").read_text()
            self.assertIn("INFINITO", rows)
            self.assertEqual(json.loads((directory / "transformadores_fora.geojson").read_text())["type"], "FeatureCollection")

    def test_poligono_e_coordenada_infinita_sao_auditaveis_sem_crs_misto(self):
        transformadores = gpd.GeoDataFrame(
            {
                "COD_ID": ["VALIDO", "POLIGONO", "INFINITO"],
                "SUB": ["SUB-A", "SUB-B", "SUB-C"],
                "MUN": ["3304557", "3304557", "3304557"],
            },
            geometry=[
                Point(-43.2, -23.0),
                Polygon([(-43.2, -23.0), (-43.1, -23.0), (-43.1, -22.95), (-43.2, -23.0)]),
                Point(float("inf"), -23.0),
            ],
            crs="EPSG:4326",
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(set(occurrences["transformador_id"]), {"POLIGONO", "INFINITO"})
        self.assertEqual(occurrences.crs.to_epsg(), 31983)
        with tempfile.TemporaryDirectory() as temporary:
            directory = persistir_diagnostico_geografico(Path(temporary), report, occurrences)
            geojson = json.loads((directory / "transformadores_fora.geojson").read_text())
            self.assertTrue(all(feature["geometry"] is not None for feature in geojson["features"]))

    def test_sem_invalidos_nao_cria_conflito_de_crs(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["VALIDO"], "SUB": ["SUB-A"], "MUN": ["3304557"]},
            geometry=[Point(-43.2, -23.0)], crs="EPSG:4326",
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())

        self.assertEqual(report["status"], "approved")
        self.assertTrue(occurrences.empty)

    def test_distancia_do_municipio_declarado_e_numerica_e_preserva_geometria(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["DENTRO", "FORA"], "SUB": ["SUB-A", "SUB-B"], "MUN": ["3304557", "3304557"]},
            geometry=[Point(-43.2, -23.0), Point(-43.4, -23.0)],
            crs="EPSG:4326",
            index=[10, 30],
        )
        original = transformadores.geometry.copy()
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())

        self.assertTrue(transformadores.geometry.equals(original))
        self.assertEqual(report["declared_municipality_distance_statistics_m"]["min"], 0.0)
        self.assertTrue(pd.api.types.is_float_dtype(occurrences["distance_to_declared_municipality_m"]))
        self.assertGreater(occurrences.iloc[0]["distance_to_declared_municipality_m"], 0)

    def test_geometria_nula_permanece_no_csv_e_fora_do_geojson(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": ["VALIDO", "NULO"], "SUB": ["SUB-A", "SUB-B"], "MUN": ["3304557", "3304557"]},
            geometry=[Point(-43.2, -23.0), None], crs="EPSG:4326",
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())
        with tempfile.TemporaryDirectory() as temporary:
            directory = persistir_diagnostico_geografico(Path(temporary), report, occurrences)
            self.assertIn("NULO", (directory / "transformadores_fora.csv").read_text())
            geojson = json.loads((directory / "transformadores_fora.geojson").read_text())
            self.assertEqual(geojson["features"], [])

    def test_entrada_vazia_bloqueia_sem_perder_tipo_numerico(self):
        transformadores = gpd.GeoDataFrame(
            {"COD_ID": [], "SUB": [], "MUN": []}, geometry=[], crs="EPSG:4326"
        )
        report, occurrences = analisar_cobertura_geografica(transformadores, self._limites())

        self.assertEqual(report["status"], "blocked")
        self.assertTrue(occurrences.empty)


if __name__ == "__main__":
    unittest.main()
