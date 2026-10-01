import subprocess
import unittest
from unittest.mock import MagicMock, Mock, patch

import run_all


class StartupTests(unittest.TestCase):
    def test_processos_sao_encerrados_e_forcados_se_necessario(self) -> None:
        processo_normal = Mock()
        processo_normal.poll.return_value = None

        processo_travado = Mock()
        processo_travado.poll.return_value = None
        processo_travado.wait.side_effect = [subprocess.TimeoutExpired("uvicorn", 5), None]

        run_all._stop_api_processes(
            [("API normal", processo_normal), ("API travada", processo_travado)]
        )

        processo_normal.terminate.assert_called_once_with()
        processo_travado.terminate.assert_called_once_with()
        processo_travado.kill.assert_called_once_with()

    @patch("run_all.urllib.request.urlopen")
    def test_aguarda_healthcheck_dos_servicos(self, urlopen):
        response = MagicMock(status=200)
        urlopen.return_value.__enter__.return_value = response
        processo = MagicMock()
        processo.poll.return_value = None

        run_all.aguardar_servicos(
            [("API", processo)],
            {"API": "http://127.0.0.1:8000/health"},
            timeout_seconds=1,
            interval_seconds=0,
        )

        urlopen.assert_called_once()

    def test_healthcheck_falha_se_processo_morrer(self):
        processo = MagicMock()
        processo.poll.return_value = 1

        with self.assertRaisesRegex(RuntimeError, "encerrou"):
            run_all.aguardar_servicos(
                [("API", processo)],
                {"API": "http://127.0.0.1:8000/health"},
                timeout_seconds=1,
                interval_seconds=0,
            )

    def test_startup_da_api_principal_exige_readiness(self):
        self.assertEqual(
            run_all.API_STARTUP_ENDPOINTS["API Principal"],
            "http://127.0.0.1:8000/ready",
        )

    @patch("src.database.get_engine")
    def test_verificacao_do_banco_reutiliza_engine_com_schema_configurado(self, get_engine):
        engine = MagicMock()
        connection = engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.scalar.return_value = 1
        get_engine.return_value = engine

        self.assertTrue(run_all.verificar_banco_populado())

        get_engine.assert_called_once_with()
        self.assertEqual(connection.execute.call_count, 3)
        engine.dispose.assert_called_once_with()

    @patch("src.database.get_engine")
    def test_verificacao_do_banco_falha_se_tabela_esta_vazia(self, get_engine):
        engine = MagicMock()
        connection = engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.scalar.side_effect = [1, 0]
        get_engine.return_value = engine

        self.assertFalse(run_all.verificar_banco_populado())

    @patch("run_all.modelo_artefato_compativel", return_value=True)
    @patch("run_all.run_script")
    @patch("run_all.verificar_banco_populado", return_value=False)
    @patch("run_all.run_module")
    @patch("src.config.DATA_INGEST_ON_STARTUP", False)
    def test_banco_vazio_dispara_ingestao_no_boot(
        self,
        run_module,
        _verificar_banco,
        _run_script,
        _modelo_compativel,
    ):
        run_module.return_value = True

        run_all.run_pipeline()

        run_module.assert_called_once_with(
            "src.etl.pipeline", "Ingestão e publicação do snapshot"
        )

    @patch("run_all.modelo_artefato_compativel", return_value=True)
    @patch("run_all.run_script")
    @patch("run_all.verificar_banco_populado", return_value=True)
    @patch("run_all.run_module")
    @patch("src.config.DATA_INGEST_ON_STARTUP", False)
    def test_banco_populado_pula_ingestao_no_boot(
        self,
        run_module,
        _verificar_banco,
        _run_script,
        _modelo_compativel,
    ):
        run_all.run_pipeline()

        run_module.assert_not_called()
