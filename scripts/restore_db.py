from __future__ import annotations

import subprocess
from pathlib import Path

try:
    from scripts.backup_db import PROJECT_ROOT, compose_database_command
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from backup_db import PROJECT_ROOT, compose_database_command


def restore_db(backup_path: Path, *, confirm: bool = False) -> bool:
    """Restaura um dump SQL no banco do Compose somente com confirmação explícita."""

    if not confirm:
        print("❌ Restauração bloqueada: informe --confirm explicitamente")
        return False

    if not backup_path.is_file():
        print(f"❌ Backup não encontrado: {backup_path}")
        return False

    if backup_path.stat().st_size == 0:
        print(f"❌ Backup vazio: {backup_path}")
        return False

    print(f"⚠️ Restaurando {backup_path} no banco do serviço Compose")
    try:
        with backup_path.open("rb") as dump_file:
            subprocess.run(
                compose_database_command("psql", "-v", "ON_ERROR_STOP=1"),
                cwd=PROJECT_ROOT,
                stdin=dump_file,
                stderr=subprocess.PIPE,
                check=True,
            )
        print("✅ Restauração concluída")
        return True
    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", None)
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace").strip()
        print(f"❌ Erro ao restaurar backup: {stderr or error}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Restaura um dump SQL no PostgreSQL do Compose")
    parser.add_argument("backup", type=Path, help="caminho do arquivo .sql")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="confirma que o banco configurado no Compose será sobrescrito",
    )
    arguments = parser.parse_args()
    raise SystemExit(0 if restore_db(arguments.backup, confirm=arguments.confirm) else 1)
