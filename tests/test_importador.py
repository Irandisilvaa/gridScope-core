from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from src.etl.importador import SnapshotImportError, SnapshotImporter


class SnapshotImporterTests(unittest.TestCase):
    def _make_importer(self) -> SnapshotImporter:
        return SnapshotImporter(
            "postgresql://unused",
            Path("/tmp/snapshot.gdb"),
            delivery_id="delivery-a",
        )

    def test_publica_derivados_somente_depois_da_preparacao(self) -> None:
        importer = self._make_importer()
        engine = MagicMock()
        publish = MagicMock()
        prepare = MagicMock(return_value={"territorios_voronoi": 3, "cache_mercado": 2})

        with patch("src.etl.importador.create_engine", return_value=engine), patch.object(
            importer, "_validate_source"
        ), patch.object(importer, "_create_schema"), patch.object(
            importer, "_load_layers", return_value={"subestacoes": 3}
        ), patch.object(importer, "_publish", publish), patch.object(
            importer, "_drop_schema"
        ):
            result = importer.run(prepare_publish=prepare)

        prepare.assert_called_once()
        publish.assert_called_once()
        published_tables = set(publish.call_args.args[2])
        self.assertEqual(
            published_tables,
            {"subestacoes", "territorios_voronoi", "cache_mercado"},
        )
        self.assertEqual(result.row_counts["cache_mercado"], 2)

    def test_falha_na_preparacao_nao_publica_nada(self) -> None:
        importer = self._make_importer()
        engine = MagicMock()
        publish = MagicMock()

        with patch("src.etl.importador.create_engine", return_value=engine), patch.object(
            importer, "_validate_source"
        ), patch.object(importer, "_create_schema"), patch.object(
            importer, "_load_layers", return_value={"subestacoes": 3}
        ), patch.object(importer, "_publish", publish), patch.object(
            importer, "_drop_schema"
        ), self.assertRaises(SnapshotImportError):
            importer.run(prepare_publish=MagicMock(side_effect=RuntimeError("falha de derivação")))

        publish.assert_not_called()
        engine.dispose.assert_called_once()

    def test_camada_vazia_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()
        engine = MagicMock()
        publish = MagicMock()
        prepare = MagicMock()

        with patch("src.etl.importador.create_engine", return_value=engine), patch.object(
            importer, "_validate_source"
        ), patch.object(importer, "_create_schema"), patch.object(
            importer, "_load_layers", return_value={"subestacoes": 0}
        ), patch.object(importer, "_publish", publish), patch.object(
            importer, "_drop_schema"
        ), self.assertRaises(SnapshotImportError):
            importer.run(prepare_publish=prepare)

        prepare.assert_not_called()
        publish.assert_not_called()

    def test_schema_sem_coluna_obrigatoria_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()

        with self.assertRaisesRegex(SnapshotImportError, "colunas obrigatórias"):
            importer._validate_layer_schema(
                "SUB",
                gpd.GeoDataFrame(
                    {"COD_ID": ["A"], "geometry": [Point(-37.0, -10.0)]},
                    crs="EPSG:4326",
                ),
            )

    def test_camada_espacial_sem_crs_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()

        with self.assertRaisesRegex(SnapshotImportError, "sem CRS"):
            importer._validate_layer_schema(
                "SUB",
                gpd.GeoDataFrame(
                    {"COD_ID": ["A"], "NOME": ["SE-A"], "geometry": [Point(-37.0, -10.0)]},
                ),
            )

    def test_identificador_duplicado_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()

        with self.assertRaisesRegex(SnapshotImportError, "duplicad"):
            importer._validate_layer_schema(
                "SUB",
                gpd.GeoDataFrame(
                    {
                        "COD_ID": ["A", "A"],
                        "NOME": ["SE-A", "SE-A duplicada"],
                        "geometry": [Point(-37.0, -10.0), Point(-37.1, -10.1)],
                    },
                    crs="EPSG:4326",
                ),
            )

    def test_identificador_nulo_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()

        with self.assertRaisesRegex(SnapshotImportError, "nulo"):
            importer._validate_layer_schema(
                "SUB",
                gpd.GeoDataFrame(
                    {"COD_ID": [None], "NOME": ["SE-A"], "geometry": [Point(-37.0, -10.0)]},
                    crs="EPSG:4326",
                ),
            )

    def test_geometria_invalida_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()

        with self.assertRaisesRegex(SnapshotImportError, "inválid"):
            importer._validate_layer_schema(
                "SUB",
                gpd.GeoDataFrame(
                    {"COD_ID": ["A"], "NOME": ["SE-A"], "geometry": [Point(-37.0, -10.0)]},
                    crs="EPSG:4326",
                ).set_geometry(
                    [Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])], crs="EPSG:4326"
                ),
            )

    def test_integridade_referencial_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()
        tabelas = {
            "transformadores": pd.DataFrame({"COD_ID": ["TRAFO-1"], "SUB": ["SUB-1"]}),
            "consumidores": pd.DataFrame({"UNI_TR_MT": ["TRAFO-999"]}),
            "subestacoes": pd.DataFrame({"COD_ID": ["SUB-1"]}),
            "geracao_gd": pd.DataFrame({"UNI_TR_MT": ["TRAFO-1"]}),
            "rede_mt": pd.DataFrame({"COD_ID": ["REDE-1"], "SUB": ["SUB-1"]}),
        }

        with self.assertRaisesRegex(SnapshotImportError, "consumidores"):
            importer._validate_references(tabelas)

    def test_integridade_referencial_aceita_snapshot_coerente(self) -> None:
        importer = self._make_importer()
        tabelas = {
            "transformadores": pd.DataFrame({"COD_ID": ["TRAFO-1"], "SUB": ["SUB-1"]}),
            "consumidores": pd.DataFrame({"UNI_TR_MT": ["TRAFO-1"]}),
            "subestacoes": pd.DataFrame({"COD_ID": ["SUB-1"]}),
            "geracao_gd": pd.DataFrame({"UNI_TR_MT": ["TRAFO-1"]}),
            "rede_mt": pd.DataFrame({"COD_ID": ["REDE-1"], "SUB": ["SUB-1"]}),
        }

        importer._validate_references(tabelas)


if __name__ == "__main__":
    unittest.main()
