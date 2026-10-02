import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src import quarentena_geografica as quarentena


def _ocorrencias(classificacoes: dict[str, str]) -> pd.DataFrame:
    registros = []
    for transformador_id, classification in classificacoes.items():
        registros.append(
            {
                "transformador_id": transformador_id,
                "subestacao_id": "SUB1",
                "municipio_codigo": "3300308",
                "classification": classification,
                "distance_to_study_boundary_m": 1200.0,
            }
        )
    return pd.DataFrame(registros)


def _relatorio(elegiveis: int, invalidos: int = 0, status: str = "blocked") -> dict:
    return {
        "status": status,
        "eligible_transformer_count": elegiveis,
        "invalid_or_ineligible_count": invalidos,
        "tolerance_m": 250,
    }


class QuarentenaGeograficaTests(unittest.TestCase):
    def test_aplica_quarentena_dentro_do_limite(self) -> None:
        ocorrencias = _ocorrencias(
            {
                "T2": "outside_above_tolerance",
                "T1": "outside_above_tolerance",
                "T3": "inside",
            }
        )
        resultado = quarentena.avaliar_quarentena(
            _relatorio(1000), ocorrencias, fracao_maxima=0.01
        )
        self.assertEqual(resultado.transformador_ids, ("T1", "T2"))
        self.assertEqual(resultado.count, 2)
        self.assertEqual(resultado.resumo["quarantined_count"], 2)
        self.assertAlmostEqual(resultado.resumo["quarantined_fraction_of_eligible"], 0.002)
        self.assertEqual(resultado.resumo["max_distance_m"], 1200.0)
        self.assertEqual(resultado.resumo["by_declared_municipality"], {"3300308": 2})

    def test_ids_sao_unicos_e_ordenados(self) -> None:
        ocorrencias = _ocorrencias(
            {
                "T9": "outside_above_tolerance",
                "T3": "outside_above_tolerance",
                "T3 ": "outside_above_tolerance",
            }
        )
        resultado = quarentena.avaliar_quarentena(
            _relatorio(100), ocorrencias, fracao_maxima=0.5
        )
        self.assertEqual(resultado.transformador_ids, ("T3", "T9"))

    def test_acima_do_limite_bloqueia_como_falha_sistemica(self) -> None:
        ocorrencias = _ocorrencias(
            {f"T{indice}": "outside_above_tolerance" for indice in range(20)}
        )
        with self.assertRaisesRegex(
            quarentena.QuarentenaRecusadaError, "falha sistêmica"
        ):
            quarentena.avaliar_quarentena(
                _relatorio(100), ocorrencias, fracao_maxima=0.05
            )

    def test_nao_quarentena_outros_tipos_de_falha(self) -> None:
        ocorrencias = _ocorrencias(
            {
                "T1": "invalid_geometry_or_identifier",
                "T2": "non_finite_coordinate",
                "T3": "invalid_municipality",
                "T4": "outside_within_tolerance",
            }
        )
        with self.assertRaisesRegex(
            quarentena.QuarentenaRecusadaError, "integridade"
        ):
            quarentena.avaliar_quarentena(
                _relatorio(100, invalidos=3), ocorrencias
            )

    def test_recusa_quarentena_quando_ha_falha_de_integridade(self) -> None:
        ocorrencias = _ocorrencias(
            {"T1": "outside_above_tolerance", "T2": "invalid_geometry_or_identifier"}
        )
        with self.assertRaisesRegex(
            quarentena.QuarentenaRecusadaError, "falha de integridade"
        ):
            quarentena.avaliar_quarentena(
                _relatorio(100, invalidos=1), ocorrencias
            )

    def test_recusa_quarentena_sem_identificador_auditavel(self) -> None:
        ocorrencias = _ocorrencias({"T1": "outside_above_tolerance"})
        ocorrencias.loc[0, "transformador_id"] = "  "
        with self.assertRaisesRegex(
            quarentena.QuarentenaRecusadaError, "sem transformador_id"
        ):
            quarentena.avaliar_quarentena(
                _relatorio(100), ocorrencias, fracao_maxima=0.5
            )

    def test_sem_bloqueio_nao_faz_nada(self) -> None:
        ocorrencias = _ocorrencias({"T1": "outside_above_tolerance"})
        self.assertIsNone(
            quarentena.avaliar_quarentena(
                _relatorio(100, status="approved"), ocorrencias
            )
        )

    def test_bloqueio_sem_outlier_quarentenavel_nao_e_perdoado(self) -> None:
        ocorrencias = _ocorrencias({"T1": "outside_within_tolerance"})
        with self.assertRaisesRegex(
            quarentena.QuarentenaRecusadaError, "nenhum outlier geométrico"
        ):
            quarentena.avaliar_quarentena(_relatorio(100), ocorrencias)

    def test_bloqueio_sem_ocorrencias_nunca_vira_aprovacao(self) -> None:
        with self.assertRaisesRegex(
            quarentena.QuarentenaRecusadaError, "não há ocorrências"
        ):
            quarentena.avaliar_quarentena(
                _relatorio(100), pd.DataFrame()
            )

    def test_exige_fracao_maxima_positiva(self) -> None:
        ocorrencias = _ocorrencias({"T1": "outside_above_tolerance"})
        with self.assertRaisesRegex(ValueError, "fração máxima"):
            quarentena.avaliar_quarentena(
                _relatorio(100), ocorrencias, fracao_maxima=0
            )

    def test_exige_coluna_de_classificacao(self) -> None:
        with self.assertRaisesRegex(
            quarentena.QuarentenaRecusadaError, "coluna de classificação"
        ):
            quarentena.avaliar_quarentena(
                _relatorio(100), pd.DataFrame({"transformador_id": ["T1"]})
            )

    def test_artefato_reproduz_todos_os_registros_excluidos(self) -> None:
        ocorrencias = _ocorrencias(
            {
                "T1": "outside_above_tolerance",
                "T2": "outside_above_tolerance",
                "T3": "inside",
            }
        )
        resultado = quarentena.avaliar_quarentena(
            _relatorio(1000), ocorrencias, fracao_maxima=0.01
        )
        with tempfile.TemporaryDirectory() as temporaria:
            destino = quarentena.persistir_quarentena(
                Path(temporaria), resultado, ocorrencias
            )
            gravado = pd.read_csv(destino, dtype={"transformador_id": "string"})
        self.assertEqual(destino.name, quarentena.ARQUIVO_QUARENTENA)
        self.assertEqual(sorted(gravado["transformador_id"]), ["T1", "T2"])
        self.assertEqual(
            set(gravado["quarantine_reason"]),
            {quarentena.RAZAO_QUARENTENA},
        )

    def test_artefato_incompleto_e_recusado(self) -> None:
        ocorrencias = _ocorrencias(
            {"T1": "outside_above_tolerance", "T2": "outside_above_tolerance"}
        )
        resultado = quarentena.avaliar_quarentena(
            _relatorio(1000), ocorrencias, fracao_maxima=0.01
        )
        with tempfile.TemporaryDirectory() as temporaria, self.assertRaisesRegex(
            quarentena.QuarentenaRecusadaError, "não reproduz"
        ):
            quarentena.persistir_quarentena(
                Path(temporaria), resultado, ocorrencias.iloc[:1]
            )


if __name__ == "__main__":
    unittest.main()
