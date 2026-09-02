"""Unit tests for bridge module."""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "template" / ".claude" / "scripts"))
sys.dont_write_bytecode = True

import bridge


class FirstStringTest(unittest.TestCase):
    def test_returns_first_matching_key(self) -> None:
        payload = {"a": "value-a", "b": "value-b"}
        self.assertEqual(bridge.first_string(payload, "a", "b"), "value-a")

    def test_skips_missing_keys(self) -> None:
        payload = {"c": "value-c"}
        self.assertEqual(bridge.first_string(payload, "a", "b", "c"), "value-c")

    def test_returns_empty_for_no_match(self) -> None:
        payload = {"x": "value-x"}
        self.assertEqual(bridge.first_string(payload, "a", "b"), "")

    def test_skips_empty_string(self) -> None:
        payload = {"a": "", "b": "value-b"}
        self.assertEqual(bridge.first_string(payload, "a", "b"), "value-b")

    def test_skips_non_string_values(self) -> None:
        payload = {"a": 123, "b": "value-b"}
        self.assertEqual(bridge.first_string(payload, "a", "b"), "value-b")


class WslPathTest(unittest.TestCase):
    def test_passthrough_posix_path(self) -> None:
        self.assertEqual(bridge.wsl_path("/home/user/file.txt"), "/home/user/file.txt")

    def test_passthrough_relative_path(self) -> None:
        self.assertEqual(bridge.wsl_path("relative/path"), "relative/path")

    def test_passthrough_empty_string(self) -> None:
        self.assertEqual(bridge.wsl_path(""), "")

    def test_passthrough_none(self) -> None:
        self.assertEqual(bridge.wsl_path(None) if None else "", "")

    def test_windows_path_non_wsl(self) -> None:
        if os.name == "nt":
            self.skipTest("Cannot test WSL detection on Windows")
        result = bridge.wsl_path("C:\\Users\\test\\file.txt")
        self.assertEqual(result, "C:\\Users\\test\\file.txt")


class NormalizeTest(unittest.TestCase):
    def test_adds_session_id(self) -> None:
        payload = {}
        result = bridge.normalize("opencode", payload)
        self.assertIn("session_id", result)
        self.assertTrue(result["session_id"].endswith("-unknown"))

    def test_uses_provided_session_id(self) -> None:
        payload = {"session_id": "my-session-123"}
        result = bridge.normalize("claude", payload)
        self.assertEqual(result["session_id"], "my-session-123")

    def test_falls_back_to_conversation_id(self) -> None:
        payload = {"conversation_id": "conv-456"}
        result = bridge.normalize("codex", payload)
        self.assertEqual(result["session_id"], "conv-456")

    def test_uses_cwd_from_payload(self) -> None:
        payload = {"cwd": "/path/to/vault"}
        result = bridge.normalize("cursor", payload)
        self.assertEqual(result["cwd"], "/path/to/vault")

    def test_uses_workspace_paths_fallback(self) -> None:
        payload = {"workspacePaths": ["/path/to/workspace"]}
        result = bridge.normalize("antigravity", payload)
        self.assertEqual(result["cwd"], "/path/to/workspace")

    def test_sets_beyin_provider(self) -> None:
        payload = {}
        result = bridge.normalize("opencode", payload)
        self.assertEqual(result["beyin_provider"], "opencode")

    def test_normalizes_transcript_path(self) -> None:
        payload = {"transcript_path": "C:\\Users\\test\\transcript.jsonl"}
        result = bridge.normalize("opencode", payload)
        self.assertIn("transcript_path", result)

    def test_preserves_extra_fields(self) -> None:
        payload = {"session_id": "s1", "model": "gpt-4", "extra_field": "keep"}
        result = bridge.normalize("claude", payload)
        self.assertEqual(result["extra_field"], "keep")


class ExtractContextTest(unittest.TestCase):
    def test_extracts_from_hook_specific_output(self) -> None:
        stdout = json.dumps({
            "hookSpecificOutput": {
                "additionalContext": "Test context content"
            }
        })
        result = bridge.extract_context(stdout)
        self.assertEqual(result, "Test context content")

    def test_returns_empty_for_no_match(self) -> None:
        stdout = json.dumps({"other": "data"})
        result = bridge.extract_context(stdout)
        self.assertEqual(result, "")

    def test_returns_empty_for_empty_json(self) -> None:
        result = bridge.extract_context("")
        self.assertEqual(result, "")

    def test_returns_empty_for_non_dict(self) -> None:
        stdout = '"just a string"'
        result = bridge.extract_context(stdout)
        self.assertEqual(result, "")

    def test_returns_last_matching_line(self) -> None:
        line1 = json.dumps({"hookSpecificOutput": {"additionalContext": "first"}})
        line2 = json.dumps({"hookSpecificOutput": {"additionalContext": "last"}})
        stdout = f"{line1}\n{line2}\n"
        result = bridge.extract_context(stdout)
        self.assertEqual(result, "last")


class InsideVaultTest(unittest.TestCase):
    def test_posix_path_inside(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            with patch.object(bridge, "ROOT", vault):
                self.assertTrue(bridge.inside_vault(str(vault / "subdir")))

    def test_posix_path_outside(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            with patch.object(bridge, "ROOT", vault):
                self.assertFalse(bridge.inside_vault(str(outside)))

    def test_relative_path_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            with patch.object(bridge, "ROOT", vault):
                self.assertFalse(bridge.inside_vault("relative/path"))


class OutputTest(unittest.TestCase):
    def test_opencode_start_with_context(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            bridge.output("opencode", "start", "Test context")
            self.assertEqual(mock_out.getvalue(), "Test context")

    def test_opencode_other_events(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            bridge.output("opencode", "end", "Some context")
            self.assertEqual(mock_out.getvalue(), "{}\n")

    def test_cursor_start_with_context(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            bridge.output("cursor", "start", "Cursor context")
            value = mock_out.getvalue()
            self.assertIn("additional_context", value)
            self.assertIn("Cursor context", value)

    def test_antigravity_start_with_context(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            bridge.output("antigravity", "start", "Agy context")
            value = mock_out.getvalue()
            self.assertIn("injectSteps", value)
            self.assertIn("Agy context", value)

    def test_antigravity_other_events(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            bridge.output("antigravity", "end", "Some context")
            value = mock_out.getvalue()
            self.assertIn("decision", value)
            self.assertIn("stop", value)

    def test_claude_format(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            bridge.output("claude", "start", "Claude context")
            value = mock_out.getvalue()
            self.assertIn("hookSpecificOutput", value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
