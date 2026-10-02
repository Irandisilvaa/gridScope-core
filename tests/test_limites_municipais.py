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
            artifact = Path(temporary) / "edicao-oficial-teste" / "2800308.geojson"
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


if __name__ == "__main__":
    unittest.main()
