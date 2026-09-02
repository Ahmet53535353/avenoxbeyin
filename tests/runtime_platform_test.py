"""Unit tests for runtime_platform module."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "template" / ".claude" / "scripts"))
sys.dont_write_bytecode = True

import runtime_platform


class DetachedProcessOptionsTest(unittest.TestCase):
    def test_returns_dict(self) -> None:
        result = runtime_platform.detached_process_options()
        self.assertIsInstance(result, dict)

    def test_posix_uses_new_session(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX-only")
        result = runtime_platform.detached_process_options()
        self.assertTrue(result.get("start_new_session"))
        self.assertNotIn("creationflags", result)

    def test_windows_uses_creationflags(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows-only")
        result = runtime_platform.detached_process_options()
        self.assertIn("creationflags", result)
        self.assertIsInstance(result["creationflags"], int)


class ExclusiveLockTest(unittest.TestCase):
    def test_lock_acquired_and_released(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with tmp_path.open("r+") as handle:
                with runtime_platform.exclusive_lock(handle, blocking=False) as held:
                    self.assertTrue(held)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_lock_nonblocking_already_locked(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with tmp_path.open("r+") as handle_a:
                with runtime_platform.exclusive_lock(handle_a, blocking=False) as held_a:
                    self.assertTrue(held_a)
                    with tmp_path.open("r+") as handle_b:
                        with runtime_platform.exclusive_lock(handle_b, blocking=False) as held_b:
                            self.assertFalse(held_b)
        finally:
            tmp_path.unlink(missing_ok=True)


class ExclusiveClaimTest(unittest.TestCase):
    def test_first_claim_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claim_path = Path(tmp) / "claim.lock"
            result = runtime_platform.create_exclusive_claim(claim_path)
            self.assertTrue(result)
            self.assertTrue(claim_path.exists())

    def test_second_claim_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claim_path = Path(tmp) / "claim.lock"
            self.assertTrue(runtime_platform.create_exclusive_claim(claim_path))
            self.assertFalse(runtime_platform.create_exclusive_claim(claim_path))

    def test_claim_file_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claim_path = Path(tmp) / "claim.lock"
            runtime_platform.create_exclusive_claim(claim_path, mode=0o600)
            mode = claim_path.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)


class IsLinkOrReparseTest(unittest.TestCase):
    def test_regular_file(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            self.assertFalse(runtime_platform._is_link_or_reparse(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_symlink(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlink not available")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.txt"
            target.write_text("x")
            link = Path(tmp) / "link"
            link.symlink_to(target)
            self.assertTrue(runtime_platform._is_link_or_reparse(link))

    def test_nonexistent(self) -> None:
        self.assertFalse(runtime_platform._is_link_or_reparse(Path("/nonexistent/path/xyz")))


class PathWithinVaultTest(unittest.TestCase):
    def test_path_inside_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            inner = vault / "inner.txt"
            inner.write_text("x")
            self.assertTrue(runtime_platform.path_within_vault(inner, vault))

    def test_path_outside_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("x")
            self.assertFalse(runtime_platform.path_within_vault(outside, vault))

    def test_symlink_inside_vault_pointing_outside(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlink not available")
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("x")
            link = vault / "link"
            link.symlink_to(outside)
            self.assertFalse(runtime_platform.path_within_vault(link, vault))


if __name__ == "__main__":
    unittest.main(verbosity=2)
