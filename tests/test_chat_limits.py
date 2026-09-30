import unittest

from fastapi import HTTPException

from src.ai.chat_service import ChatRequest, _validar_limites_chat


class ChatLimitsTests(unittest.TestCase):
    def test_historico_rejeita_papel_desconhecido(self) -> None:
        request = ChatRequest(
            mensagem="Quais são os indicadores?",
            historico=[{"role": "tool", "content": "resultado"}],
        )

        with self.assertRaises(HTTPException) as raised:
            _validar_limites_chat(request)

        self.assertEqual(raised.exception.status_code, 422)

    def test_historico_rejeita_excesso_de_mensagens(self) -> None:
        request = ChatRequest(
            mensagem="Resumo",
            historico=[{"role": "user", "content": "x"}] * 21,
        )

        with self.assertRaises(HTTPException) as raised:
            _validar_limites_chat(request)

        self.assertEqual(raised.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
