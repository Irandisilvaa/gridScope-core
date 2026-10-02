from __future__ import annotations

import argparse
import getpass

from .store import create_user, ensure_auth_tables, count_active_admins


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria o primeiro administrador GridScope")
    parser.add_argument("--email", required=True, help="e-mail do administrador")
    parser.add_argument("--name", required=True, help="nome exibido do administrador")
    args = parser.parse_args()

    ensure_auth_tables()
    if count_active_admins() > 0:
        print("Já existe um administrador ativo; criação inicial bloqueada.")
        return 1

    password = getpass.getpass("Senha do administrador: ")
    confirmation = getpass.getpass("Repita a senha: ")
    if password != confirmation:
        print("As senhas não coincidem.")
        return 1

    user = create_user(args.email, args.name, password, role="admin")
    print(f"Administrador criado: {user.email} ({user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
