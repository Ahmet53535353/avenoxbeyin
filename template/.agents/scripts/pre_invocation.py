#!/usr/bin/env python3
"""PreInvocation lifecycle hook for Google Antigravity.

Injects relational memory, rules, recent journal, knowledge index,
and daily log context into the agent's context window.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

sys.dont_write_bytecode = True

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _cap(text: str, limit: int, note: str = "[... kesildi]") -> str:
    if len(text) <= limit:
        return text
    keep = limit - len(note) - 1
    return text[:max(0, keep)] + "\n" + note


def _get_yesterday_str() -> str:
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def main() -> None:
    # Read stdin safely
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    conversation_id = payload.get("conversationId", "")
    workspace_paths = payload.get("workspacePaths", [])
    invocation_num = payload.get("invocationNum", 1)

    # Determine vault root
    if workspace_paths and os.path.isdir(workspace_paths[0]):
        vault_root = Path(workspace_paths[0]).resolve()
    else:
        vault_root = Path(__file__).resolve().parent.parent.parent

    memory_dir = vault_root / "🔮 850-Companion"
    state_dir = vault_root / ".agents" / "scripts" / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)

    session_hash = ""
    if conversation_id:
        session_hash = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()

    # If subsequent invocation, increment prompt count and return empty
    if invocation_num > 1:
        if session_hash:
            prompt_file = state_dir / f"prompt_count.{session_hash}"
            count = 0
            if prompt_file.exists():
                try:
                    count = int(prompt_file.read_text(encoding="utf-8").strip())
                except Exception:
                    count = 0
            try:
                prompt_file.write_text(str(count + 1), encoding="utf-8")
            except Exception:
                pass
        sys.stdout.write("{}\n")
        return

    # invocationNum == 1: Record session start
    if session_hash:
        try:
            (state_dir / f"session_start_time.{session_hash}").write_text(
                str(int(time.time())), encoding="utf-8"
            )
            (state_dir / f"prompt_count.{session_hash}").write_text(
                "0", encoding="utf-8"
            )
        except Exception:
            pass

    # 1. Last Session
    last_session_text = ""
    last_session_path = memory_dir / "Last-Session.md"
    if last_session_path.exists():
        try:
            lines = last_session_path.read_text(encoding="utf-8").splitlines()
            active_lines = []
            capturing = False
            for line in lines:
                if line.startswith("## Session:"):
                    capturing = True
                elif capturing and line.startswith("## Previous"):
                    break
                if capturing:
                    active_lines.append(line)
            last_session_text = "\n".join(active_lines[:50])
        except Exception:
            pass

    # 2. Threads
    threads_text = ""
    threads_path = memory_dir / "Threads.md"
    if threads_path.exists():
        try:
            lines = threads_path.read_text(encoding="utf-8").splitlines()
            active_lines = []
            capturing = False
            for line in lines:
                if line.startswith("## Active"):
                    capturing = True
                elif capturing and line.startswith("## Closed"):
                    break
                if capturing and (line.startswith("### ") or line.startswith("**Status:**")):
                    active_lines.append(line)
            threads_text = "\n".join(active_lines[:12])
        except Exception:
            pass

    # 3. Rules
    rules_text = ""
    rules_path = memory_dir / "Kurallar.md"
    if rules_path.exists():
        try:
            lines = rules_path.read_text(encoding="utf-8").splitlines()
            rules_text = "\n".join(lines[:60])
        except Exception:
            pass

    # 4. Journal
    journal_text = ""
    journal_path = memory_dir / "Journal.md"
    if journal_path.exists():
        try:
            lines = journal_path.read_text(encoding="utf-8").splitlines()
            h2_indices = [i for i, l in enumerate(lines) if l.startswith("## ")]
            if h2_indices:
                last_h2 = h2_indices[-1]
                journal_text = "\n".join(lines[last_h2:last_h2 + 10])
        except Exception:
            pass

    # 5. Knowledge Index
    index_text = ""
    index_path = vault_root / "knowledge" / "index.md"
    if index_path.exists():
        try:
            lines = index_path.read_text(encoding="utf-8").splitlines()
            index_text = "\n".join(lines[:150])
        except Exception:
            pass

    # 6. Daily Log
    daily_text = ""
    today_str = dt.date.today().strftime("%Y-%m-%d")
    daily_path = vault_root / "daily" / f"{today_str}.md"
    if not daily_path.exists():
        daily_path = vault_root / "daily" / f"{_get_yesterday_str()}.md"
    if daily_path.exists():
        try:
            lines = daily_path.read_text(encoding="utf-8").splitlines()
            daily_text = "\n".join(lines[-25:])
        except Exception:
            pass

    # 7. Reflection Debt
    reflection_warnings = []
    for ref_file in state_dir.glob("needs_reflection*"):
        if ref_file.is_file():
            try:
                detail = ref_file.read_text(encoding="utf-8").strip()
                if detail:
                    reflection_warnings.append(
                        f"⚠️ Önceki oturum hafıza güncellemeden bitti: {detail}. "
                        "Anlamlı bir şey olduysa 🔮 850-Companion dosyalarını güncelle."
                    )
                ref_file.unlink(missing_ok=True)
            except Exception:
                pass

    # Assemble sections
    sections = ["🧠 **AVENOXBEYIN HAFIZA KÖPRÜSÜ** (Antigravity)\n"]

    if last_session_text.strip():
        sections.append("### 🔮 Son Oturum\n" + _cap(last_session_text, 4000))
    if threads_text.strip():
        sections.append("### 🧵 Aktif Başlıklar (Threads)\n" + _cap(threads_text, 2000))
    if rules_text.strip():
        sections.append("### 📜 Kurallar (Kurallar.md)\n" + _cap(rules_text, 4000))
    if journal_text.strip():
        sections.append("### 📖 Son Journal Girişi\n" + _cap(journal_text, 1500))
    if index_text.strip():
        sections.append("### 📚 Bilgi İndeksi (knowledge/index.md)\n" + _cap(index_text, 6000))
    if daily_text.strip():
        sections.append("### 📅 Günlük Log\n" + _cap(daily_text, 2000))
    if reflection_warnings:
        sections.append("\n".join(reflection_warnings))

    ephemeral_content = "\n\n".join(sections).strip()

    output = {
        "injectSteps": [
            {
                "ephemeralMessage": ephemeral_content
            }
        ]
    }
    sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
