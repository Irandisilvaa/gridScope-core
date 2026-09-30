from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

import src.pdf_report as pdf_report


class PdfReportDataTests(unittest.TestCase):
    def _cache(self) -> list[dict]:
        return [
            {
                "subestacao": "SE-A (ID: A)",
                "id_tecnico": "A",
                "regiao": "Aracaju",
                "metricas_rede": {"total_clientes": 10, "consumo_anual_mwh": 100.0},
                "geracao_distribuida": {
                    "total_unidades": 2,
                    "potencia_total_kw": 20.0,
                    "detalhe_por_classe": {"Residencial": {"potencia_kw": 20.0, "qtd": 2}},
                },
                "perfil_consumo": {
                    "Residencial": {"qtd_clientes": 10, "consumo_anual_mwh": 100.0},
                },
            }
        ]

    def test_cache_vazio_nao_fabrica_dados(self) -> None:
        with patch.object(pdf_report, "carregar_cache_mercado", return_value=[]):
            with self.assertRaises(pdf_report.ReportDataError):
                pdf_report.get_bulk_data()

    def test_id_inexistente_nao_seleciona_primeiro_ativo(self) -> None:
        with patch.object(pdf_report, "carregar_cache_mercado", return_value=self._cache()):
            with self.assertRaises(pdf_report.ReportDataError):
                pdf_report.get_pdf_data(["Residencial"], ["clientes"], substation_id="missing")

    def test_data_escolhida_e_preservada_no_cabecalho(self) -> None:
        with patch.object(pdf_report, "carregar_cache_mercado", return_value=self._cache()), patch.object(
            pdf_report, "_get_neighborhood_from_coords", return_value="Aracaju"
        ), patch.object(pdf_report, "_get_substation_area_km2", return_value="N/D"):
            result = pdf_report.get_pdf_data(
                ["Residencial"],
                ["clientes"],
                substation_id="A",
                report_date=date(2025, 3, 15),
            )

        self.assertEqual(result["pdf_data"]["header"]["report_date"], "15/03/2025")


if __name__ == "__main__":
    unittest.main()
