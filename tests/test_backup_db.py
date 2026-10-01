from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.backup_db as backup_db
import scripts.restore_db as restore_db


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
            self.assertEqual(command[:6], ["docker", "compose", "exec", "-T", "db", "pg_dump"])
            self.assertIn("--no-password", command)
            self.assertNotIn("sh", command)
            self.assertNotIn("1234", command)

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

    def test_restore_exige_confirmacao(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backup_path = Path(temporary) / "backup.sql"
            backup_path.write_text("SELECT 1;", encoding="utf-8")

            with patch.object(restore_db.subprocess, "run") as run:
                self.assertFalse(restore_db.restore_db(backup_path))

            run.assert_not_called()

    def test_restore_envia_dump_para_psql_com_erro_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backup_path = Path(temporary) / "backup.sql"
            backup_path.write_text("SELECT 1;", encoding="utf-8")

            def fake_run(*args, **kwargs):
                self.assertEqual(kwargs["stdin"].read(), b"SELECT 1;")

            with patch.object(restore_db.subprocess, "run", side_effect=fake_run) as run:
                self.assertTrue(restore_db.restore_db(backup_path, confirm=True))

            command = run.call_args.args[0]
            self.assertEqual(command[:6], ["docker", "compose", "exec", "-T", "db", "psql"])
            self.assertIn("ON_ERROR_STOP=1", command)
            self.assertNotIn("sh", command)


if __name__ == "__main__":
    unittest.main()
