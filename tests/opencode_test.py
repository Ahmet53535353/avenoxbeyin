"""Tests for OpenCode brain integration."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "template"


class OpenCodeIntegrationTest(unittest.TestCase):
    def test_preflight(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import install_opencode

        report = install_opencode.check_preflight()
        self.assertTrue(report["ok"])
        self.assertTrue(report["plugin_source_exists"])

    def test_clean_install_copies_all_dependencies(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import install_opencode

        with tempfile.TemporaryDirectory(prefix="test-opencode-vault-") as temp_dir:
            vault = Path(temp_dir) / "vault"
            vault.mkdir()
            (vault / ".claude" / "scripts").mkdir(parents=True)

            for script in ["bridge.py", "read_transcript.py", "lifecycle.py", "runtime_platform.py"]:
                src = TEMPLATE_DIR / ".claude" / "scripts" / script
                dst = vault / ".claude" / "scripts" / script
                if src.exists():
                    shutil.copy2(src, dst)

            fake_home = Path(temp_dir) / "home"
            fake_home.mkdir()
            config_dir = fake_home / ".config" / "opencode"
            config_dir.mkdir(parents=True)
            (config_dir / "opencode.jsonc").write_text("{}\n", encoding="utf-8")

            old_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = str(fake_home)
                result = install_opencode.install_plugin(vault)
            finally:
                if old_home:
                    os.environ["HOME"] = old_home

            self.assertTrue(result)
            hooks_dir = vault / ".beyin" / "hooks"
            self.assertTrue(hooks_dir.exists())

            for script in ["bridge.py", "read_transcript.py", "lifecycle.py", "runtime_platform.py"]:
                self.assertTrue(
                    (hooks_dir / script).exists(),
                    f"{script} not copied to hooks directory",
                )

    def test_template_scripts_importable(self):
        sys.path.insert(0, str(TEMPLATE_DIR / ".claude" / "scripts"))

        import runtime_platform
        self.assertTrue(hasattr(runtime_platform, "exclusive_lock"))
        self.assertTrue(hasattr(runtime_platform, "detached_process_options"))

        import lifecycle
        self.assertTrue(hasattr(lifecycle, "handle"))

        import bridge
        self.assertTrue(hasattr(bridge, "normalize"))
        self.assertTrue(hasattr(bridge, "dispatch"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
