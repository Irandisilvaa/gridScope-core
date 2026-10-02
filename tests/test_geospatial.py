import unittest

import geopandas as gpd
from shapely.geometry import Point, box

from src.geospatial import GeospatialCrsError, crs_projetado_bdgd


class GeospatialCrsTests(unittest.TestCase):
    def test_seleciona_utm_24s_para_sergipe(self):
        frame = gpd.GeoDataFrame(geometry=[Point(-37.1, -11.0)], crs="EPSG:4326")
        self.assertEqual(crs_projetado_bdgd(frame).to_epsg(), 31984)

    def test_seleciona_utm_23s_para_rio(self):
        frame = gpd.GeoDataFrame(geometry=[Point(-43.2, -22.9)], crs="EPSG:4326")
        self.assertEqual(crs_projetado_bdgd(frame).to_epsg(), 31983)

    def test_usa_projecao_nacional_para_extensao_multizona(self):
        frame = gpd.GeoDataFrame(
            geometry=[box(-44.0, -23.0, -40.0, -21.0)], crs="EPSG:4326"
        )
        self.assertEqual(crs_projetado_bdgd(frame).to_epsg(), 5880)

    def test_rejeita_geometria_sem_crs(self):
        frame = gpd.GeoDataFrame(geometry=[Point(-43.2, -22.9)])
        with self.assertRaisesRegex(GeospatialCrsError, "sem CRS"):
            crs_projetado_bdgd(frame)

    def test_rejeita_geometria_vazia(self):
        frame = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        with self.assertRaisesRegex(GeospatialCrsError, "vazia"):
            crs_projetado_bdgd(frame)
