import unittest
from pathlib import Path


class ComposeSecurityTests(unittest.TestCase):
    def test_compose_padrao_nao_monta_repositorio_ou_env(self) -> None:
        compose = Path("docker-compose.yml").read_text(encoding="utf-8")

        self.assertNotIn("- .:/app", compose)
        self.assertNotIn("./.env:/app/.env", compose)
        self.assertIn('user: "${GRID_SCOPE_UID:-1000}:${GRID_SCOPE_GID:-1000}"', compose)

    def test_override_de_desenvolvimento_e_explicito(self) -> None:
        dev_compose = Path("docker-compose.dev.yml").read_text(encoding="utf-8")

        self.assertIn("- .:/app", dev_compose)
        self.assertIn("./.env:/app/.env:ro", dev_compose)


if __name__ == "__main__":
    unittest.main()
