#!/usr/bin/env python3
"""Stop lifecycle hook for Google Antigravity.

Detaches or runs the automatic session flush into the vault's daily log,
and verifies relational-memory debt.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add script directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    import flush
except ImportError:
    flush = None


def main() -> None:
    if os.environ.get("BEYIN_INVOKED_BY"):
        sys.stdout.write("{}\n")
        return

    # Read stdin safely
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    conversation_id = payload.get("conversationId", "")
    workspace_paths = payload.get("workspacePaths", [])
    transcript_path_str = payload.get("transcriptPath", "")

    # Determine vault root
    if workspace_paths and os.path.isdir(workspace_paths[0]):
        vault_root = Path(workspace_paths[0]).resolve()
    else:
        vault_root = SCRIPT_DIR.parent.parent

    memory_dir = vault_root / "🔮 850-Companion"
    state_dir = vault_root / ".agents" / "scripts" / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)

    session_hash = ""
    if conversation_id:
        session_hash = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()

    # 1. Check relational memory debt
    if session_hash:
        start_time_file = state_dir / f"session_start_time.{session_hash}"
        prompt_count_file = state_dir / f"prompt_count.{session_hash}"
        reflection_file = state_dir / f"needs_reflection.{session_hash}"

        start_time = 0
        prompt_count = 0
        if start_time_file.exists():
            try:
                start_time = int(start_time_file.read_text(encoding="utf-8").strip())
            except Exception:
                start_time = 0
        if prompt_count_file.exists():
            try:
                prompt_count = int(prompt_count_file.read_text(encoding="utf-8").strip())
            except Exception:
                prompt_count = 0

        last_session_path = memory_dir / "Last-Session.md"
        last_session_mtime = 0
        if last_session_path.exists():
            try:
                last_session_mtime = int(last_session_path.stat().st_mtime)
            except Exception:
                last_session_mtime = 0

        if prompt_count >= 5 and last_session_mtime < start_time:
            try:
                now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
                reflection_file.write_text(
                    f"Oturum hafıza güncellemeden bitti. Prompt sayısı: {prompt_count}. ({now_str})",
                    encoding="utf-8",
                )
            except Exception:
                pass

        # Cleanup ephemeral tracking files
        start_time_file.unlink(missing_ok=True)
        prompt_count_file.unlink(missing_ok=True)

    # 2. Flush transcript to daily log
    if transcript_path_str:
        transcript_path = Path(transcript_path_str)
        if transcript_path.exists():
            if flush is not None:
                try:
                    flush.flush_transcript(
                        transcript_path=transcript_path,
                        session_id=conversation_id or "default",
                        reason="stop",
                        vault_root=vault_root,
                    )
                except Exception:
                    pass
            else:
                # Fallback to subprocess
                try:
                    subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT_DIR / "flush.py"),
                            "--transcript",
                            str(transcript_path),
                            "--session-id",
                            conversation_id or "default",
                            "--reason",
                            "stop",
                        ],
                        capture_output=True,
                        timeout=120,
                        check=False,
                    )
                except Exception:
                    pass

    # Antigravity Stop hook contract expects an empty JSON object to let the agent stop normally
    sys.stdout.write("{}\n")


if __name__ == "__main__":
    main()
