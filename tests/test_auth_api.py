import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

import src.api as api_module
from src.auth.dependencies import admin_user
from src.auth.store import UserRecord


def user_record(role: str = "user") -> UserRecord:
    return UserRecord(
        id=uuid4(),
        email=f"{role}@gridscope.local",
        name=f"Usuário {role}",
        role=role,
        is_active=True,
    )


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = user_record("admin")
        api_module.app.dependency_overrides.clear()
        api_module.app.dependency_overrides[api_module.admin_user] = lambda: self.admin
        api_module.app.dependency_overrides[api_module.require_csrf] = lambda: None
        self.client = TestClient(api_module.app)
        self.addCleanup(api_module.app.dependency_overrides.clear)

    def test_login_creates_a_server_session_and_returns_public_user(self) -> None:
        with patch.object(api_module, "_ensure_auth_ready"), patch.object(
            api_module, "_enforce_auth_rate_limit"
        ), patch.object(api_module, "authenticate_user", return_value=self.admin), patch.object(
            api_module, "create_session", return_value="opaque-session"
        ) as create_session, patch.object(api_module, "mark_login") as mark_login, patch.object(
            api_module, "set_auth_cookies"
        ) as set_auth_cookies:
            response = self.client.post(
                "/auth/login",
                json={"email": self.admin.email, "password": "senha-segura-123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["id"], str(self.admin.id))
        create_session.assert_called_once()
        mark_login.assert_called_once_with(self.admin.id)
        set_auth_cookies.assert_called_once()

    def test_admin_creation_is_available_only_through_admin_dependency(self) -> None:
        created = user_record("user")
        with patch.object(api_module, "_ensure_auth_ready"), patch.object(
            api_module, "_enforce_admin_rate_limit"
        ), patch.object(api_module, "create_user", return_value=created) as create_user:
            response = self.client.post(
                "/auth/admin/users",
                json={
                    "email": created.email,
                    "name": created.name,
                    "password": "senha-segura-123",
                    "role": "user",
                },
            )

        self.assertEqual(response.status_code, 201)
        create_user.assert_called_once_with(created.email, created.name, "senha-segura-123", "user")

    def test_public_registration_route_does_not_exist(self) -> None:
        response = self.client.post(
            "/auth/register",
            json={"email": "novo@gridscope.local", "password": "senha-segura-123"},
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_dependency_rejects_regular_user(self) -> None:
        request_user = user_record("user")
        with patch("src.auth.dependencies.current_user", return_value=request_user):
            with self.assertRaises(HTTPException) as raised:
                admin_user(object())
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
