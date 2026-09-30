from __future__ import annotations

import unittest
from unittest.mock import patch

import src.reports.data as report_data


class ReportsDataTests(unittest.TestCase):
    def test_cache_vazio_bloqueia_relatorio(self) -> None:
        with patch.object(report_data, "carregar_dados_cache", return_value=(None, [])):
            with self.assertRaises(report_data.ReportDataError):
                report_data.get_report_data("A")

    def test_falha_de_carga_bloqueia_relatorio(self) -> None:
        with patch.object(
            report_data,
            "carregar_dados_cache",
            side_effect=report_data.DataCacheError("banco indisponível"),
        ):
            with self.assertRaises(report_data.ReportDataError):
                report_data.get_report_data("A")

    def test_id_inexistente_nao_escolhe_primeira_subestacao(self) -> None:
        with patch.object(
            report_data,
            "carregar_dados_cache",
            return_value=(None, [{"id_tecnico": "A", "subestacao": "SE-A"}]),
        ):
            with self.assertRaises(report_data.ReportDataError):
                report_data.get_report_data("missing")

    def test_id_duplicado_bloqueia_relatorio_ambiguo(self) -> None:
        rows = [{"id_tecnico": "A"}, {"id_tecnico": "A"}]
        with patch.object(report_data, "carregar_dados_cache", return_value=(None, rows)):
            with self.assertRaises(report_data.ReportDataError):
                report_data.get_report_data("A")

    def test_literal_malicioso_nao_e_executado(self) -> None:
        rows = [
            {
                "id_tecnico": "A",
                "metricas_rede": "__import__('os').system('touch /tmp/nao-executar')",
            }
        ]
        with patch.object(report_data, "carregar_dados_cache", return_value=(None, rows)):
            with self.assertRaises(report_data.ReportDataError):
                report_data.get_report_data("A")


if __name__ == "__main__":
    unittest.main()
