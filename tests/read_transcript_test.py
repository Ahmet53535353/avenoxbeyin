"""Unit tests for read_transcript module."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "template" / ".claude" / "scripts"))
sys.dont_write_bytecode = True

SCRIPT_PATH = REPO_ROOT / "template" / ".claude" / "scripts" / "read_transcript.py"

import read_transcript


def create_test_db(db_path: Path, session_id: str, messages: list) -> None:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS part (message_id TEXT, time_created INTEGER, data TEXT)"
    )
    for i, msg in enumerate(messages):
        msg_id = f"msg-{session_id}-{i}"
        cur.execute(
            "INSERT INTO message (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
            (msg_id, session_id, i, json.dumps(msg["info"])),
        )
        for j, part in enumerate(msg.get("parts", [])):
            cur.execute(
                "INSERT INTO part (message_id, time_created, data) VALUES (?, ?, ?)",
                (msg_id, j, json.dumps(part)),
            )
    conn.commit()
    conn.close()


class FindDbTest(unittest.TestCase):
    def _patch_env(self, home: str, xdg: str) -> None:
        self._old_home = os.environ.get("HOME")
        self._old_xdg = os.environ.get("XDG_DATA_HOME")
        self._old_up = os.environ.get("USERPROFILE")
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = xdg
        os.environ["USERPROFILE"] = home

    def _restore_env(self) -> None:
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        if self._old_xdg is not None:
            os.environ["XDG_DATA_HOME"] = self._old_xdg
        if self._old_up is not None:
            os.environ["USERPROFILE"] = self._old_up

    def test_no_db_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._patch_env(tmp, tmp)
            try:
                result = read_transcript.find_db()
                self.assertIsNone(result)
            finally:
                self._restore_env()

    def test_finds_xdg_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_dir = Path(tmp) / "opencode"
            db_dir.mkdir()
            db_path = db_dir / "opencode.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT)"
            )
            conn.execute(
                "CREATE TABLE part (message_id TEXT, time_created INTEGER, data TEXT)"
            )
            conn.commit()
            conn.close()
            self._patch_env(tmp, tmp)
            try:
                result = read_transcript.find_db()
                self.assertEqual(result, str(db_path))
            finally:
                self._restore_env()

    def test_finds_home_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_dir = Path(tmp) / ".local" / "share" / "opencode"
            db_dir.mkdir(parents=True)
            db_path = db_dir / "opencode.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT)"
            )
            conn.execute(
                "CREATE TABLE part (message_id TEXT, time_created INTEGER, data TEXT)"
            )
            conn.commit()
            conn.close()
            self._patch_env(tmp, "")
            try:
                result = read_transcript.find_db()
                self.assertEqual(result, str(db_path))
            finally:
                self._restore_env()


class ScriptExecutionTest(unittest.TestCase):
    def test_missing_db_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--session", "abc"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": tmp,
                    "XDG_DATA_HOME": tmp,
                    "USERPROFILE": tmp,
                },
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("opencode.db not found", result.stderr)

    def test_reads_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "opencode.db"
            messages = [
                {
                    "info": {"role": "user"},
                    "parts": [{"type": "text", "text": "Merhaba"}],
                },
                {
                    "info": {"role": "assistant"},
                    "parts": [{"type": "text", "text": "Selam"}],
                },
            ]
            create_test_db(db_path, "session-1", messages)

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--session", "session-1", "--db", str(db_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            self.assertEqual(first["info"]["role"], "user")
            self.assertEqual(first["parts"][0]["text"], "Merhaba")
            second = json.loads(lines[1])
            self.assertEqual(second["info"]["role"], "assistant")
            self.assertEqual(second["parts"][0]["text"], "Selam")

    def test_empty_session_returns_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "opencode.db"
            create_test_db(db_path, "empty-session", [])

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--session", "empty-session", "--db", str(db_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
