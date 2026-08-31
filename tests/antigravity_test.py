"""Tests for Google Antigravity integration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "template" / ".agents" / "scripts"))

import install_antigravity
import flush


class AntigravityIntegrationTest(unittest.TestCase):
    def test_preflight(self):
        report = install_antigravity.check_preflight()
        self.assertTrue(report["ok"])
        self.assertTrue(report["template_exists"])

    def test_clean_install_and_placeholders(self):
        with tempfile.TemporaryDirectory(prefix="test-agy-vault-") as temp_dir:
            vault_path = Path(temp_dir) / "TestOS"
            success = install_antigravity.install_vault(
                vault_path=vault_path,
                user_name="TestUser",
                user_bio="AI Researcher",
                companion="Atlas",
                os_name="TestOS",
            )
            self.assertTrue(success)
            self.assertTrue(vault_path.is_dir())

            # Verify files exist
            gemini_md = vault_path / "GEMINI.md"
            self.assertTrue(gemini_md.is_file())
            content = gemini_md.read_text(encoding="utf-8")
            self.assertIn("TestOS", content)
            self.assertIn("Atlas", content)
            self.assertIn("TestUser", content)
            self.assertNotIn("{{COMPANION}}", content)
            self.assertNotIn("{{USER_NAME}}", content)

            # Verify hooks.json
            hooks_json = vault_path / ".agents" / "hooks.json"
            self.assertTrue(hooks_json.is_file())
            data = json.loads(hooks_json.read_text(encoding="utf-8"))
            self.assertIn("avenoxbeyin-context", data)
            self.assertIn("avenoxbeyin-flush", data)

    def test_pre_invocation_hook_output(self):
        with tempfile.TemporaryDirectory(prefix="test-agy-hook-") as temp_dir:
            vault_path = Path(temp_dir) / "TestOS"
            install_antigravity.install_vault(
                vault_path=vault_path,
                user_name="TestUser",
                user_bio="AI Researcher",
                companion="Atlas",
                os_name="TestOS",
            )
            pre_inv_script = vault_path / ".agents" / "scripts" / "pre_invocation.py"

            payload = {
                "conversationId": "test-conv-1",
                "workspacePaths": [str(vault_path)],
                "invocationNum": 1,
            }
            res = subprocess.run(
                [sys.executable, str(pre_inv_script)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
            out_json = json.loads(res.stdout)
            self.assertIn("injectSteps", out_json)
            ephemeral = out_json["injectSteps"][0]["ephemeralMessage"]
            self.assertIn("AVENOXBEYIN HAFIZA KÖPRÜSÜ", ephemeral)

    def test_antigravity_transcript_parsing(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as tf:
            lines = [
                {"step_index": 1, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "Merhaba!"},
                {"step_index": 2, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Selam, nasıl yardımcı olabilirim?"},
            ]
            for l in lines:
                tf.write(json.dumps(l) + "\n")
            tf_path = Path(tf.name)

        try:
            turns = flush.read_transcript(tf_path)
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0], ("user", "Merhaba!"))
            self.assertEqual(turns[1], ("assistant", "Selam, nasıl yardımcı olabilirim?"))
        finally:
            tf_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
