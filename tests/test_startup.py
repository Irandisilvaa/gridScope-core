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
