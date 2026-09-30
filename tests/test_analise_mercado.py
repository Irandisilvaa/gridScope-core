import unittest

import pandas as pd

from src.modelos.analise_mercado import _classificar_geracao_por_classe


class AnaliseMercadoTests(unittest.TestCase):
    def test_geracao_sem_consumidores_recebe_classe_outros(self) -> None:
        geracao = pd.DataFrame({"PN_CON": ["PN-1"]})
        classificada = _classificar_geracao_por_classe(geracao, pd.Series(dtype="object"))
        self.assertEqual(classificada.loc[0, "TIPO"], "Outros")


if __name__ == "__main__":
    unittest.main()
