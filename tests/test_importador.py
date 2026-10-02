from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd
import pyogrio
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
            importer, "_load_layers", return_value=({"subestacoes": 3}, {})
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
        self.assertTrue(result.publication_id)

    def test_combina_relatorio_da_ingestao_e_dos_derivados(self) -> None:
        importer = self._make_importer()
        engine = MagicMock()

        with patch("src.etl.importador.create_engine", return_value=engine), patch.object(
            importer, "_validate_source"
        ), patch.object(importer, "_create_schema"), patch.object(
            importer,
            "_load_layers",
            return_value=({"subestacoes": 3}, {"discarded_records": []}),
        ), patch.object(importer, "_publish"), patch.object(importer, "_drop_schema"):
            result = importer.run(
                prepare_publish=lambda _schema: (
                    {"territorios_voronoi": 2},
                    {"geospatial": {"outside_official_boundary_count": 1}},
                )
            )

        self.assertEqual(
            result.quality_report["geospatial"]["outside_official_boundary_count"],
            1,
        )

    def test_falha_na_preparacao_nao_publica_nada(self) -> None:
        importer = self._make_importer()
        engine = MagicMock()
        publish = MagicMock()

        with patch("src.etl.importador.create_engine", return_value=engine), patch.object(
            importer, "_validate_source"
        ), patch.object(importer, "_create_schema"), patch.object(
            importer, "_load_layers", return_value=({"subestacoes": 3}, {})
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
            importer, "_load_layers", return_value=({"subestacoes": 0}, {})
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

    def test_consumidor_repetido_nao_bloqueia_o_corte(self) -> None:
        """Vários consumidores legítimos apontam para o mesmo transformador.

        A entrega real repete UNI_TR_MT e PN_CON de forma normal, então exigir
        chave única aqui rejeitaria o único dado real disponível.
        """
        importer = self._make_importer()
        repetidos = pd.DataFrame(
            {
                "UNI_TR_MT": ["TRAFO-1", "TRAFO-1", "TRAFO-1"],
                "CLAS_SUB": ["R1", "R1", "R2"],
                "PN_CON": ["111", "111", "222"],
                "DAT_CON": [1, 1, 1],
                **{f"ENE_{mes:02d}": [0, 0, 0] for mes in range(1, 13)},
            }
        )

        importer._validate_layer_schema("UCBT_tab", repetidos)

    def test_consumidor_sem_identificador_bloqueia_o_corte(self) -> None:
        importer = self._make_importer()
        sem_transformador = pd.DataFrame(
            {
                "UNI_TR_MT": [None],
                "CLAS_SUB": ["R1"],
                "PN_CON": ["111"],
                "DAT_CON": [1],
                **{f"ENE_{mes:02d}": [0] for mes in range(1, 13)},
            }
        )

        with self.assertRaisesRegex(SnapshotImportError, "nulo"):
            importer._validate_layer_schema("UCBT_tab", sem_transformador)

    def test_transformador_sem_sub_e_dependentes_sao_auditados(self) -> None:
        importer = self._make_importer()
        transformadores = pd.DataFrame(
            {
                "COD_ID": ["TRAFO-1", "TRAFO-2", "TRAFO-3"],
                "SUB": ["SUB-1", None, "  "],
            }
        )
        consumidores = pd.DataFrame(
            {
                "UNI_TR_MT": ["TRAFO-1", "TRAFO-2", "TRAFO-3", "TRAFO-1"],
            }
        )

        restantes, descarte = importer._discard_transformers_without_substation(transformadores)
        consumidores_restantes, descarte_dependentes = importer._discard_transformer_dependents(
            consumidores,
            set(descarte[0]["ids"]),
            "consumidores",
        )

        self.assertEqual(restantes["COD_ID"].tolist(), ["TRAFO-1"])
        self.assertEqual(descarte[0]["count"], 2)
        self.assertEqual(descarte[0]["ids"], ["TRAFO-2", "TRAFO-3"])
        self.assertEqual(consumidores_restantes["UNI_TR_MT"].tolist(), ["TRAFO-1", "TRAFO-1"])
        self.assertEqual(descarte_dependentes[0]["count"], 2)
        self.assertEqual(
            descarte_dependentes[0]["transformer_ids"],
            ["TRAFO-2", "TRAFO-3"],
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

    def test_le_apenas_as_colunas_efetivamente_usadas(self) -> None:
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        entrega = pasta / "entrega.gpkg"

        gpd.GeoDataFrame(
            {
                "COD_ID": ["SUB-1"],
                "NOME": ["SE-A"],
                "DESCRICAO": ["texto que ninguem le"],
                "geometry": [Point(-37.0, -10.0)],
            },
            crs="EPSG:4326",
        ).to_file(entrega, layer="SUB", driver="GPKG")
        pd.DataFrame(
            {
                "UNI_TR_MT": ["TRAFO-1"],
                "CLAS_SUB": ["R1"],
                "PN_CON": ["12345"],
                "DAT_CON": [1],
                **{f"ENE_{mes:02d}": [0] for mes in range(1, 13)},
                "SEMRED": ["nao lido"],
                "DESCR": ["nao lido"],
            }
        ).rename_axis("fid").pipe(
            pyogrio.write_dataframe, entrega, layer="UCBT_tab", driver="GPKG"
        )

        importer = SnapshotImporter("postgresql://unused", entrega, delivery_id="delivery-a")

        subestacoes = importer._read_layer("SUB")
        consumidores = importer._read_layer("UCBT_tab")

        self.assertEqual(set(subestacoes.columns), {"COD_ID", "NOME", "geometry"})
        self.assertEqual("EPSG:4326", subestacoes.crs.to_string())
        self.assertNotIn("SEMRED", consumidores.columns)
        self.assertNotIn("DESCR", consumidores.columns)
        # A projeção não pode esconder coluna obrigatória que sumiu do arquivo.
        with self.assertRaisesRegex(SnapshotImportError, "colunas obrigatórias"):
            importer._validate_layer_schema(
                "UCBT_tab",
                consumidores.drop(columns=["CLAS_SUB"]),
            )


if __name__ == "__main__":
    unittest.main()
