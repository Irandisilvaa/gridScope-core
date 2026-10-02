import asyncio
import unittest
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.ai import chat_service
from src.ai.chat_service import ChatRequest, _validar_limites_chat
from src.auth.store import UserRecord


class ChatLimitsTests(unittest.TestCase):
    def test_historico_rejeita_papel_desconhecido(self) -> None:
        request = ChatRequest(
            mensagem="Quais são os indicadores?",
            historico=[{"role": "tool", "content": "resultado"}],
        )

        with self.assertRaises(HTTPException) as raised:
            _validar_limites_chat(request)

        self.assertEqual(raised.exception.status_code, 422)

    def test_request_nao_aceita_identidade_do_cliente(self) -> None:
        with self.assertRaises(ValidationError):
            ChatRequest(mensagem="Resumo", usuario_id="hostname-local")

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

        with patch.object(chat_service, "ensure_auth_tables") as auth_tables, patch.object(
            chat_service, "criar_tabela_feedback"
        ) as feedback, patch.object(chat_service, "criar_tabelas_historico") as historico:
            asyncio.run(executar_lifespan())

        auth_tables.assert_called_once_with()
        feedback.assert_called_once_with()
        historico.assert_called_once_with()

    def test_health_informa_modelo_configurado(self) -> None:
        self.assertEqual(chat_service.health_check()["model"], chat_service.CHAT_MODEL)

    def test_ready_rejeita_armazenamento_indisponivel(self) -> None:
        with patch.object(chat_service, "chat_storage_ready", False):
            with self.assertRaises(HTTPException) as raised:
                chat_service.ready_check()

        self.assertEqual(raised.exception.status_code, 503)

    def test_conversa_usa_uuid_do_usuario_autenticado(self) -> None:
        user = UserRecord(
            id=uuid4(),
            email="owner@example.test",
            name="Owner",
            role="user",
            is_active=True,
        )
        chat_service.app.dependency_overrides[chat_service.current_user] = lambda: user
        self.addCleanup(chat_service.app.dependency_overrides.clear)

        with patch.object(chat_service, "chat_storage_ready", True), patch.object(
            chat_service, "carregar_mensagens", return_value=None
        ) as carregar:
            response = TestClient(chat_service.app).get("/chat/conversa/42")

        self.assertEqual(response.status_code, 404)
        carregar.assert_called_once_with(42, str(user.id))


if __name__ == "__main__":
    unittest.main()
