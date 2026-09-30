from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.backup_db as backup_db


class BackupDatabaseTests(unittest.TestCase):
    def test_cria_backup_atomico_usando_servico_db(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backup_dir = Path(temporary)

            def fake_run(*args, **kwargs):
                kwargs["stdout"].write(b"-- dump de teste\n")

            with patch.object(backup_db, "BACKUP_DIR", backup_dir), patch.object(
                backup_db.subprocess, "run", side_effect=fake_run
            ) as run:
                self.assertTrue(backup_db.backup_db())

            backups = list(backup_dir.glob("backup_gridscope_*.sql"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b"-- dump de teste\n")
            command = run.call_args.args[0]
            self.assertEqual(command[:7], ["docker", "compose", "exec", "-T", "db", "sh", "-eu"])
            self.assertIn("pg_dump --no-password", command[-1])
            self.assertNotIn("1234", command[-1])

    def test_falha_remove_temporario_e_retorna_false(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backup_dir = Path(temporary)

            def fake_run(*args, **kwargs):
                kwargs["stdout"].write(b"parcial")
                raise subprocess.CalledProcessError(1, args[0], stderr=b"falha do pg_dump")

            with patch.object(backup_db, "BACKUP_DIR", backup_dir), patch.object(
                backup_db.subprocess, "run", side_effect=fake_run
            ):
                self.assertFalse(backup_db.backup_db())

            self.assertEqual(list(backup_dir.glob("*.tmp")), [])
            self.assertEqual(list(backup_dir.glob("*.sql")), [])


if __name__ == "__main__":
    unittest.main()
