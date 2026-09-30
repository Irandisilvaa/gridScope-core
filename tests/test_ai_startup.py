import unittest

from src.ai import ai_service


class AiStartupTests(unittest.TestCase):
    def test_importacao_nao_carrega_banco_antecipadamente(self) -> None:
        self.assertIsNone(ai_service.gdf_subs)


if __name__ == "__main__":
    unittest.main()
