import unittest

import pandas as pd

from src.ai.model_contract import FEATURE_COLUMNS, TARGET_COLUMN
from src.ai.train_model import gerar_dados_treino_inteligente


class ModelContractTests(unittest.TestCase):
    def test_dataset_sintetico_e_reproduzivel(self) -> None:
        primeira = gerar_dados_treino_inteligente(seed=7, quantidade_perfis=2)
        segunda = gerar_dados_treino_inteligente(seed=7, quantidade_perfis=2)

        pd.testing.assert_frame_equal(primeira, segunda)
        self.assertEqual(list(primeira.columns), [*FEATURE_COLUMNS, TARGET_COLUMN])


if __name__ == "__main__":
    unittest.main()
