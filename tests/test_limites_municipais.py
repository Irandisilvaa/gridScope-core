import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src import limites_municipais


class LimitesMunicipaisTests(unittest.TestCase):
    def test_exige_edicao_oficial_explicita(self) -> None:
        with patch.object(limites_municipais, "IBGE_MALHA_REVISAO", ""):
            with self.assertRaisesRegex(
                limites_municipais.LimitesMunicipaisError,
                "IBGE_MALHA_REVISAO",
            ):
                limites_municipais._carregar_limite("2800308", Mock())

    def test_armazena_artefato_e_metadados_reproduziveis(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"codarea": "2800308"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-37.2, -11.2],
                                [-37.0, -11.2],
                                [-37.0, -11.0],
                                [-37.2, -11.0],
                                [-37.2, -11.2],
                            ]
                        ],
                    },
                }
            ],
        }
        content = json.dumps(payload).encode()
        response = Mock(content=content)
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            limites_municipais, "IBGE_MALHA_REVISAO", "edicao-oficial-teste"
        ), patch.object(
            limites_municipais, "IBGE_MALHA_CACHE_DIR", Path(temporary)
        ):
            result = limites_municipais._carregar_limite("2800308", session)
            artifact = (
                Path(temporary) / "edicao-oficial-teste" /
                limites_municipais.IBGE_MALHA_QUALIDADE / "2800308.geojson"
            )
            self.assertTrue(artifact.exists())
            self.assertEqual(artifact.read_bytes(), content)

        self.assertEqual(result.iloc[0]["revisao"], "edicao-oficial-teste")
        self.assertTrue(result.iloc[0]["checksum_sha256"])
        self.assertTrue(result.iloc[0]["obtido_em"])

    def test_rejeita_feature_sem_codigo_reconhecido(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[-37, -11], [-36, -11], [-36, -10], [-37, -11]]],
                    },
                }
            ],
        }
        response = Mock(content=json.dumps(payload).encode())
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            limites_municipais, "IBGE_MALHA_REVISAO", "edicao-oficial-teste"
        ), patch.object(
            limites_municipais, "IBGE_MALHA_CACHE_DIR", Path(temporary)
        ), self.assertRaisesRegex(
            limites_municipais.LimitesMunicipaisError,
            "sem código municipal",
        ):
            limites_municipais._carregar_limite("2800308", session)


def _feature(codigo: str, x0: float, y0: float, x1: float, y1: float) -> dict:
    return {
        "type": "Feature",
        "properties": {"codarea": codigo},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]],
            ],
        },
    }


def _payload(*codigos: str) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            _feature(codigo, -43.0 - indice, -22.0, -42.9 - indice, -21.9)
            for indice, codigo in enumerate(codigos)
        ],
    }


class EscopoMalhaTests(unittest.TestCase):
    """A malha de validação não pode ser derivada do atributo que ela audita."""

    def test_escopo_da_uf_cobre_todos_os_municipios(self) -> None:
        with patch.object(limites_municipais, "IBGE_MALHA_REVISAO", "edicao-oficial-teste"), patch.object(
            limites_municipais, "carregar_limites_municipais_ufs", Mock()
        ) as ufs:
            limites_municipais.carregar_limites_para_territorio(
                ["3302858", "3304557", "inválido", None]
            )

        ufs.assert_called_once_with(["33"], ["3302858", "3304557"])

    def test_exige_codigo_municipal_valido(self) -> None:
        with self.assertRaisesRegex(
            limites_municipais.LimitesMunicipaisError, "Nenhum código municipal"
        ):
            limites_municipais.carregar_limites_para_territorio([None, "abc"])

    def test_malha_estadual_traz_municipios_alem_do_declarado(self) -> None:
        payload = _payload("3300308", "3303203", "3304557")
        content = json.dumps(payload).encode()
        response = Mock(content=content)
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            limites_municipais, "IBGE_MALHA_REVISAO", "edicao-oficial-teste"
        ), patch.object(
            limites_municipais, "IBGE_MALHA_CACHE_DIR", Path(temporary)
        ), patch.object(
            limites_municipais, "_catalogo_nomes", Mock(return_value={})
        ):
            resultado = limites_municipais.carregar_limites_municipais_ufs(
                ["33"], ["3303203"], session=session
            )
            artifact = (
                Path(temporary) / "edicao-oficial-teste" /
                limites_municipais.IBGE_MALHA_QUALIDADE / "uf_33.geojson"
            )
            self.assertTrue(artifact.exists())
            self.assertEqual(session.get.call_count, 1)

        # O município não declarado entra na malha: é o que impede que erro de
        # atribuição de MUN vire bloqueio de publicação.
        self.assertEqual(
            sorted(resultado["municipio_codigo"]), ["3300308", "3303203", "3304557"]
        )
        self.assertEqual(set(resultado["uf"]), {"33"})
        self.assertEqual(set(resultado["qualidade"]), {limites_municipais.IBGE_MALHA_QUALIDADE})
        # Sem catálogo do IBGE o nome local continua sendo um fallback previsível.
        self.assertIn("Município 3303203", set(resultado["nome"]))

    def test_usa_nomes_oficiais_quando_o_catalogo_esta_disponivel(self) -> None:
        content = json.dumps(_payload("3303203")).encode()
        response = Mock(content=content)
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            limites_municipais, "IBGE_MALHA_REVISAO", "edicao-oficial-teste"
        ), patch.object(
            limites_municipais, "IBGE_MALHA_CACHE_DIR", Path(temporary)
        ), patch.object(
            limites_municipais,
            "_catalogo_nomes",
            Mock(return_value={"3303203": "Nilópolis"}),
        ):
            resultado = limites_municipais.carregar_limites_municipais_ufs(
                ["33"], session=session
            )

        self.assertEqual(list(resultado["nome"]), ["Nilópolis"])

    def test_rejeita_municipio_de_outra_uf_na_malha_estadual(self) -> None:
        payload = _payload("3300308", "2800308")
        response = Mock(content=json.dumps(payload).encode())
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            limites_municipais, "IBGE_MALHA_REVISAO", "edicao-oficial-teste"
        ), patch.object(
            limites_municipais, "IBGE_MALHA_CACHE_DIR", Path(temporary)
        ), patch.object(
            limites_municipais, "_catalogo_nomes", Mock(return_value={})
        ), self.assertRaisesRegex(
            limites_municipais.LimitesMunicipaisError,
            "malha do estado 33",
        ):
            limites_municipais.carregar_limites_municipais_ufs(["33"], session=session)

    def test_exige_uf_valida(self) -> None:
        with self.assertRaisesRegex(
            limites_municipais.LimitesMunicipaisError, "Nenhuma UF válida"
        ):
            limites_municipais.carregar_limites_municipais_ufs(["", None])


if __name__ == "__main__":
    unittest.main()
