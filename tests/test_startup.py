import subprocess
import unittest
from unittest.mock import Mock

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
