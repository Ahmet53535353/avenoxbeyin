#!/usr/bin/env python3
"""Read a session's transcript from the OpenCode SQLite database.

Usage: read_transcript.py --session <session_id> [--db <path>]
Prints one JSON object per message (newline separated) with the shape:
  {"info": {"role": "user"|"assistant"}, "parts": [{"type": ..., "text": ...}, ...]}
"""
import argparse
import json
import os
import sqlite3
import sys


def find_db():
    candidates = []
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        candidates.append(os.path.join(xdg, "opencode", "opencode.db"))
    candidates.append(os.path.expanduser("~/.local/share/opencode/opencode.db"))
    candidates.append(os.path.expanduser("~/.opencode/data/opencode.db"))
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()

    db = args.db or find_db()
    if not db:
        sys.stderr.write("opencode.db not found\n")
        sys.exit(2)

    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, data FROM message WHERE session_id=? ORDER BY time_created",
            (args.session,),
        )
        messages = [(row[0], json.loads(row[1])) for row in cur.fetchall()]
        for mid, m in messages:
            cur.execute(
                "SELECT data FROM part WHERE message_id=? ORDER BY time_created",
                (mid,),
            )
            parts = [json.loads(row[0]) for row in cur.fetchall()]
            out = {
                "info": {"role": m.get("role")},
                "parts": [
                    {"type": p.get("type"), "text": p.get("text") or ""}
                    for p in parts
                ],
            }
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        conn.close()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"read_transcript error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
