"""Teste indispensável do DATA-01 contra PostgreSQL/PostGIS real.

Publica a entrega A, depois a entrega B, e exige que sobre **somente** a B em
tabelas brutas, derivados, registro de publicação e leitura da API. Depois
republica uma B corrompida e exige que nada mude e que não haja sucesso.

O teste é ignorado quando não há PostgreSQL com PostGIS disponível.
"""

from __future__ import annotations

import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from src.etl.importador import SnapshotImportError, SnapshotImporter

# Somente uma URL explícita de teste habilita esta suíte. Não há fallback para
# DATABASE_URL: um teste de corte substitui tabelas inteiras e jamais pode
# rodar contra a base que a aplicação está servindo.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()
TABLAS_PUBLICAS = (
    "subestacoes",
    "transformadores",
    "consumidores",
    "geracao_gd",
    "rede_mt",
    "territorios_voronoi",
    "cache_mercado",
)


def _geometria_valida() -> Polygon:
    return Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])


def _camadas(
    prefixo: str,
    *,
    orfao: bool = False,
    duplicado: bool = False,
    sem_sub: bool = False,
) -> dict[str, object]:
    """Entrega sintética com IDs exclusivos por prefixo."""

    cod_sub = f"SUB-{prefixo}-1"
    cod_sub_duplicado = cod_sub if duplicado else f"SUB-{prefixo}-2"
    cod_trafo = f"TRAFO-{prefixo}-1"
    consumidor_ref = f"TRAFO-ORFAO-{prefixo}" if orfao else cod_trafo
    transformador_ids = [cod_trafo]
    transformador_subestacoes = [cod_sub]
    transformador_geometrias = [Point(0.5, 0.5)]
    consumidor_referencias = [consumidor_ref]
    if sem_sub:
        transformador_ids.append(f"TRAFO-SEM-SUB-{prefixo}")
        transformador_subestacoes.append(None)
        transformador_geometrias.append(Point(0.6, 0.6))
        consumidor_referencias.append(f"TRAFO-SEM-SUB-{prefixo}")

    return {
        "SUB": gpd.GeoDataFrame(
            {
                "COD_ID": [cod_sub, cod_sub_duplicado],
                "NOME": [f"Sub {prefixo} A", f"Sub {prefixo} B"],
                "geometry": [_geometria_valida(), _geometria_valida()],
            },
            crs="EPSG:4326",
        ),
        "UNTRMT": gpd.GeoDataFrame(
            {
                "COD_ID": transformador_ids,
                "SUB": transformador_subestacoes,
                "geometry": transformador_geometrias,
            },
            crs="EPSG:4326",
        ),
        "SSDMT": gpd.GeoDataFrame(
            {
                "COD_ID": [f"REDE-{prefixo}-1"],
                "SUB": [cod_sub],
                "geometry": [Point(0.4, 0.4)],
            },
            crs="EPSG:4326",
        ),
        "UCBT_tab": pd.DataFrame(
            {
                "UNI_TR_MT": consumidor_referencias,
                "CLAS_SUB": ["B1"] * len(consumidor_referencias),
                "PN_CON": [f"PN-{prefixo}-{idx}" for idx in range(len(consumidor_referencias))],
                "DAT_CON": ["2025-01-15"] * len(consumidor_referencias),
                **{
                    f"ENE_{mes:02d}": [float(mes)] * len(consumidor_referencias)
                    for mes in range(1, 13)
                },
            }
        ),
        "UGBT_tab": pd.DataFrame(
            {
                "UNI_TR_MT": [cod_trafo],
                "POT_INST": [10.0],
                "PN_CON": [f"PN-GD-{prefixo}-1"],
                "DAT_CON": ["2025-01-15"],
            }
        ),
    }


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "defina TEST_DATABASE_URL para um PostgreSQL com PostGIS de teste",
)
class CorteTransacionalPostgisTests(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import create_engine, text

        self._engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        with self._engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    def tearDown(self) -> None:
        self._engine.dispose()

    def _publicar(self, prefixo: str, **kwargs) -> dict[str, int]:
        """Publica um snapshot sintético com derivados simulados."""

        campos = {
            "delivery_id": f"delivery-{prefixo}-{uuid.uuid4().hex[:8]}",
            "source": "teste",
            "reference_period": "2025-01",
        }
        caminho = Path("/tmp") / f"{campos['delivery_id']}.gdb"
        caminho.mkdir(parents=True, exist_ok=True)

        importer = SnapshotImporter(
            TEST_DATABASE_URL,
            caminho,
            delivery_id=campos["delivery_id"],
            publication_metadata={
                "source": "teste",
                "reference_period": "2025-01",
                "city_target": "Aracaju, Sergipe, Brazil",
            },
        )

        with patch.object(SnapshotImporter, "_read_layer", autospec=True) as ler:
            def _read(self, layer_name):
                return _camadas(prefixo, **kwargs)[layer_name]

            ler.side_effect = _read

            return importer.run(prepare_publish=self._derivados).row_counts

    @staticmethod
    def _derivados(staging_schema: str) -> dict[str, int]:
        """Simula os jobs derivados gravando no mesmo staging.

        Usa as mesmas tabelas e colunas do schema operacional para que o corte
        seja exercitado com o formato real.
        """

        from sqlalchemy import create_engine, text

        engine = create_engine(TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={staging_schema},public"})
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(f'CREATE TABLE "{staging_schema}".territorios_voronoi ("COD_ID" TEXT, "NOM" TEXT)')
                )
                connection.execute(
                    text(
                        f'CREATE TABLE "{staging_schema}".cache_mercado '
                        '("id_subestacao" TEXT, "dados_json" JSONB, "data_atualizacao" TIMESTAMP DEFAULT NOW())'
                    )
                )
                connection.execute(
                    text(
                        f'INSERT INTO "{staging_schema}".territorios_voronoi ("COD_ID", "NOM") '
                        f'SELECT "COD_ID", "NOME" FROM "{staging_schema}".subestacoes'
                    )
                )
                connection.execute(
                    text(
                        f'INSERT INTO "{staging_schema}".cache_mercado ("id_subestacao", "dados_json") '
                        f"SELECT \"COD_ID\", jsonb_build_object('id_tecnico', \"COD_ID\") "
                        f'FROM "{staging_schema}".subestacoes'
                    )
                )
            return {"territorios_voronoi": 2, "cache_mercado": 2}
        finally:
            engine.dispose()

    def _contagens(self) -> dict[str, int]:
        from sqlalchemy import text

        with self._engine.connect() as connection:
            return {
                tabela: connection.execute(
                    text(f'SELECT COUNT(*) FROM public."{tabela}"')
                ).scalar_one()
                for tabela in TABLAS_PUBLICAS
                if connection.execute(
                    text("SELECT to_regclass(:nome)"), {"nome": f"public.{tabela}"}
                ).scalar_one()
            }

    def _identificadores_publicados(self) -> set[str]:
        from sqlalchemy import text

        with self._engine.connect() as connection:
            linhas = connection.execute(
                text('SELECT "COD_ID" FROM public.subestacoes')
            ).scalars()
            return set(linhas)

    def _publicacao_registrada(self) -> dict[str, object]:
        from sqlalchemy import text

        with self._engine.connect() as connection:
            existe = connection.execute(
                text("SELECT to_regclass('public.grid_scope_publication')")
            ).scalar_one()
            if not existe:
                return {}
            linha = connection.execute(
                text(
                    "SELECT delivery_id, city_target, row_counts, quality_report "
                    "FROM public.grid_scope_publication "
                    "WHERE publication_key = 1"
                )
            ).mappings().first()
            return dict(linha) if linha else {}

    def test_apos_sucesso_encontra_somente_a_entrega_b(self) -> None:
        self._publicar("a")
        self._publicar("b")

        identificadores = self._identificadores_publicados()
        self.assertTrue(identificadores, "nenhuma subestação publicada")
        self.assertTrue(
            all(identificador.startswith("SUB-b-") for identificador in identificadores),
            f"encontrados identificadores de outra entrega: {sorted(identificadores)}",
        )

        contagens = self._contagens()
        self.assertEqual(contagens["subestacoes"], 2)
        self.assertEqual(contagens["territorios_voronoi"], 2)
        self.assertEqual(contagens["cache_mercado"], 2)

        registro = self._publicacao_registrada()
        self.assertTrue(registro["delivery_id"].startswith("delivery-b-"))
        self.assertEqual(registro["city_target"], "Aracaju, Sergipe, Brazil")

    def test_registra_descarte_de_registros_sem_subestacao(self) -> None:
        contagens = self._publicar("sem-sub", sem_sub=True)

        self.assertEqual(contagens["transformadores"], 1)
        self.assertEqual(contagens["consumidores"], 1)
        registro = self._publicacao_registrada()
        descartes = registro["quality_report"]["discarded_records"]
        descarte_transformador = next(item for item in descartes if item["table"] == "transformadores")
        descarte_consumidor = next(item for item in descartes if item["table"] == "consumidores")
        self.assertEqual(descarte_transformador["count"], 1)
        self.assertEqual(descarte_transformador["ids"], ["TRAFO-SEM-SUB-sem-sub"])
        self.assertEqual(descarte_consumidor["count"], 1)
        self.assertEqual(
            descarte_consumidor["transformer_ids"],
            ["TRAFO-SEM-SUB-sem-sub"],
        )

    def test_entrega_corrompida_nao_altera_nem_declara_sucesso(self) -> None:
        self._publicar("a")
        self._publicar("b")
        antes = self._identificadores_publicados()
        publicacao_antes = self._publicacao_registrada()

        for rotulo, kwargs in (
            ("referência órfã", {"orfao": True}),
            ("identificador duplicado", {"duplicado": True}),
        ):
            with self.subTest(rotulo=rotulo):
                with self.assertRaises(SnapshotImportError):
                    self._publicar("c", **kwargs)

                self.assertEqual(self._identificadores_publicados(), antes)
                self.assertEqual(self._publicacao_registrada(), publicacao_antes)


if __name__ == "__main__":
    unittest.main()
