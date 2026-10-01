from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
import tempfile

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = PROJECT_ROOT / "backups"
MAX_BACKUPS = 5
DATABASE_SERVICE = "db"


def _database_setting(name: str, default: str) -> str:
    """Replica a precedência do Compose: ambiente do processo sobre .env."""

    values = dotenv_values(PROJECT_ROOT / ".env")
    return str(os.getenv(name) or values.get(name) or default)


def compose_database_command(program: str, *extra_args: str) -> list[str]:
    """Monta um comando direto para o PostgreSQL do serviço Compose."""

    if program not in {"pg_dump", "psql"}:
        raise ValueError(f"Programa PostgreSQL não permitido: {program}")

    return [
        "docker",
        "compose",
        "exec",
        "-T",
        DATABASE_SERVICE,
        program,
        *extra_args,
        "--no-password",
        "-U",
        _database_setting("POSTGRES_USER", "postgres"),
        "--dbname",
        _database_setting("POSTGRES_DB", "gridscope_local"),
    ]


def _error_message(error: Exception) -> str:
    if isinstance(error, subprocess.CalledProcessError) and error.stderr:
        stderr = error.stderr
        if isinstance(stderr, bytes):
            return stderr.decode("utf-8", errors="replace").strip()
        return str(stderr).strip()
    return str(error)


def _prune_backups() -> None:
    backups = sorted(BACKUP_DIR.glob("backup_gridscope_*.sql"))
    for old_backup in backups[:-MAX_BACKUPS]:
        old_backup.unlink()
        print(f"♻️ Removido backup antigo: {old_backup.name}")


def backup_db() -> bool:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / f"backup_gridscope_{timestamp}.sql"
    temporary_path: Path | None = None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    print(f"📦 Iniciando backup: {destination}")
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            dir=BACKUP_DIR,
            prefix=f"{destination.stem}-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            subprocess.run(
                compose_database_command("pg_dump"),
                cwd=PROJECT_ROOT,
                stdout=temporary,
                stderr=subprocess.PIPE,
                check=True,
            )

        if temporary_path.stat().st_size == 0:
            raise RuntimeError("pg_dump produziu um arquivo vazio")

        temporary_path.replace(destination)
        print(f"✅ Backup concluído com sucesso: {destination}")
        _prune_backups()
        return True
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
        print(f"❌ Erro ao realizar backup: {_error_message(error)}")
        return False

if __name__ == "__main__":
    raise SystemExit(0 if backup_db() else 1)
