import unittest

import pandas as pd

from src.ai.model_contract import FEATURE_COLUMNS, TARGET_COLUMN, annotate_model, model_is_compatible
from src.ai.train_model import gerar_dados_treino_inteligente


class ModelContractTests(unittest.TestCase):
    def test_dataset_sintetico_e_reproduzivel(self) -> None:
        primeira = gerar_dados_treino_inteligente(seed=7, quantidade_perfis=2)
        segunda = gerar_dados_treino_inteligente(seed=7, quantidade_perfis=2)

        pd.testing.assert_frame_equal(primeira, segunda)
        self.assertEqual(list(primeira.columns), [*FEATURE_COLUMNS, TARGET_COLUMN])

    def test_modelo_annotado_respeita_contrato(self) -> None:
        class Modelo:
            feature_names_in_ = FEATURE_COLUMNS

        modelo = annotate_model(Modelo())

        self.assertTrue(model_is_compatible(modelo))

    def test_modelo_sem_versao_e_incompativel(self) -> None:
        class Modelo:
            feature_names_in_ = FEATURE_COLUMNS

        self.assertFalse(model_is_compatible(Modelo()))


if __name__ == "__main__":
    unittest.main()
