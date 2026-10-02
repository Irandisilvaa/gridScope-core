import unittest
from uuid import UUID

from src.auth.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    new_uuid,
    normalize_email,
    verify_password,
)


class AuthSecurityTests(unittest.TestCase):
    def test_password_is_hashed_and_verifies(self) -> None:
        password = "Senha-local-segura-123"
        encoded = hash_password(password)

        self.assertNotIn(password, encoded)
        self.assertTrue(verify_password(password, encoded))
        self.assertFalse(verify_password("senha-incorreta-123", encoded))

    def test_password_hashes_use_different_salts(self) -> None:
        password = "Senha-local-segura-123"
        self.assertNotEqual(hash_password(password), hash_password(password))

    def test_email_is_normalized(self) -> None:
        self.assertEqual(normalize_email("  Operador@GridScope.LOCAL "), "operador@gridscope.local")

    def test_user_and_session_identifiers_are_uuid_or_opaque(self) -> None:
        identifier = new_uuid()
        self.assertIsInstance(identifier, UUID)
        self.assertEqual(identifier.version, 4)

        token = new_session_token()
        self.assertGreaterEqual(len(token), 48)
        self.assertNotEqual(token, hash_session_token(token))


if __name__ == "__main__":
    unittest.main()
