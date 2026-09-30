import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from src.ai import chat_service
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

    def test_tabelas_do_chat_sao_inicializadas_no_lifespan(self) -> None:
        async def executar_lifespan() -> None:
            async with chat_service.lifespan(None):
                pass

        with patch.object(chat_service, "criar_tabela_feedback") as feedback, patch.object(
            chat_service, "criar_tabelas_historico"
        ) as historico:
            asyncio.run(executar_lifespan())

        feedback.assert_called_once_with()
        historico.assert_called_once_with()

    def test_health_informa_modelo_configurado(self) -> None:
        self.assertEqual(chat_service.health_check()["model"], chat_service.CHAT_MODEL)

    def test_ready_rejeita_armazenamento_indisponivel(self) -> None:
        with patch.object(chat_service, "chat_storage_ready", False):
            with self.assertRaises(HTTPException) as raised:
                chat_service.ready_check()

        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
