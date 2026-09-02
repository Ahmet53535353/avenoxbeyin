"""Unit tests for lifecycle module."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "template" / ".claude" / "scripts"))
sys.dont_write_bytecode = True

import lifecycle


class SessionKeyTest(unittest.TestCase):
    def test_returns_sha256_hex(self) -> None:
        result = lifecycle.session_key("test-session-1")
        expected = hashlib.sha256(b"test-session-1").hexdigest()
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 64)

    def test_same_input_same_output(self) -> None:
        a = lifecycle.session_key("session-abc")
        b = lifecycle.session_key("session-abc")
        self.assertEqual(a, b)

    def test_different_input_different_output(self) -> None:
        a = lifecycle.session_key("session-a")
        b = lifecycle.session_key("session-b")
        self.assertNotEqual(a, b)

    def test_unicode_session_id(self) -> None:
        result = lifecycle.session_key("oturum-123")
        self.assertEqual(len(result), 64)


class StateDirTest(unittest.TestCase):
    def test_state_dir_under_beyin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            state = lifecycle._state_dir(vault)
            self.assertEqual(state, vault / ".beyin" / ".state")


class AtomicWriteTest(unittest.TestCase):
    def test_writes_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "file.txt"
            lifecycle._atomic_write(target, "hello world")
            self.assertEqual(target.read_text(encoding="utf-8"), "hello world")

    def test_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "dir" / "file.txt"
            lifecycle._atomic_write(target, "content")
            self.assertTrue(target.exists())

    def test_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "file.txt"
            target.write_text("old", encoding="utf-8")
            lifecycle._atomic_write(target, "new")
            self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_file_mode_is_0o600(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "file.txt"
            lifecycle._atomic_write(target, "content", mode=0o600)
            mode = target.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)


class ReadLinesTest(unittest.TestCase):
    def test_reads_all_lines(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tmp:
            tmp.write("a\nb\nc\n")
            tmp_path = Path(tmp.name)
        try:
            self.assertEqual(lifecycle._read_lines(tmp_path), ["a", "b", "c"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_returns_empty_for_missing_file(self) -> None:
        result = lifecycle._read_lines(Path("/nonexistent/xyz/abc"))
        self.assertEqual(result, [])

    def test_limit_caps_lines(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tmp:
            for i in range(10):
                tmp.write(f"line{i}\n")
            tmp_path = Path(tmp.name)
        try:
            self.assertEqual(lifecycle._read_lines(tmp_path, limit=3), ["line0", "line1", "line2"])
        finally:
            tmp_path.unlink(missing_ok=True)


class ReadIntegerTest(unittest.TestCase):
    def test_reads_positive_integer(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("42\n")
            tmp_path = Path(tmp.name)
        try:
            self.assertEqual(lifecycle._read_integer(tmp_path), 42)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_reads_zero(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("0\n")
            tmp_path = Path(tmp.name)
        try:
            self.assertEqual(lifecycle._read_integer(tmp_path), 0)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_returns_zero_for_missing(self) -> None:
        self.assertEqual(lifecycle._read_integer(Path("/nonexistent/xyz")), 0)

    def test_returns_zero_for_non_digit(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("not-a-number\n")
            tmp_path = Path(tmp.name)
        try:
            self.assertEqual(lifecycle._read_integer(tmp_path), 0)
        finally:
            tmp_path.unlink(missing_ok=True)


class CapTest(unittest.TestCase):
    def test_under_limit_unchanged(self) -> None:
        result = lifecycle._cap("hello", 100, "[truncated]")
        self.assertEqual(result, "hello")

    def test_over_limit_truncated_with_note(self) -> None:
        text = "x" * 100
        result = lifecycle._cap(text, 50, "[truncated]")
        self.assertTrue(result.endswith("[truncated]"))
        self.assertLessEqual(len(result), 50)

    def test_zero_limit(self) -> None:
        result = lifecycle._cap("hello", 0, "[truncated]")
        self.assertIn("[truncated]", result)


class CleanupSessionStateTest(unittest.TestCase):
    def test_removes_old_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            old = state / "session_start_time.old"
            old.write_text("12345")
            eight_days_ago = (datetime.now() - timedelta(days=8)).timestamp()
            import os
            os.utime(old, (eight_days_ago, eight_days_ago))
            lifecycle._cleanup_session_state(state, datetime.now())
            self.assertFalse(old.exists())

    def test_keeps_recent_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            recent = state / "session_start_time.recent"
            recent.write_text("12345")
            lifecycle._cleanup_session_state(state, datetime.now())
            self.assertTrue(recent.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
