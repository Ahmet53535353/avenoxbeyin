#!/usr/bin/env python3
"""Compile changed daily logs into knowledge base articles, connections, and index."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Sequence

sys.dont_write_bytecode = True

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import _portalock

SCRIPT_DIR = Path(__file__).resolve().parent
VAULT_ROOT = SCRIPT_DIR.parent.parent
STATE_DIR = SCRIPT_DIR / ".state"
DEFAULT_MAX_CALLS = 5

DATE_IN_NAME = re.compile(
    r"(?<!\d)(?P<year>\d{4})-(?P<month>\d{2})"
    r"(?:-(?P<day>\d{2}))?(?!\d)"
)


def _iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def write_health(state_dir: Path, error: str, warning: bool = False) -> None:
    try:
        payload: dict[str, Any] = {}
        health_path = state_dir / "health.json"
        if health_path.exists():
            try:
                loaded = json.loads(health_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload.update(loaded)
            except Exception:
                pass
        payload.update(
            {
                "ts": int(time.time()),
                "component": "compile",
                "error": error,
            }
        )
        if warning:
            warnings = payload.get("warnings", [])
            if not isinstance(warnings, list):
                warnings = []
            if error not in warnings:
                warnings.append(error)
            payload["warnings"] = warnings[-20:]
        _atomic_write_json(health_path, payload)
    except OSError:
        pass


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ingested": {}, "last_run": "", "last_status": "init", "runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"ingested": {}, "last_run": "", "last_status": "corrupt", "runs": []}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    _atomic_write_json(path, state)


def changed_daily_logs(vault_root: Path, state: dict[str, Any]) -> list[Path]:
    daily_dir = vault_root / "daily"
    if not daily_dir.is_dir():
        return []
    ingested = state.get("ingested", {})
    changed = []
    for path in sorted(daily_dir.glob("*.md")):
        if not path.is_file():
            continue
        if DATE_IN_NAME.search(path.name) is None:
            continue
        current_digest = _sha256(path)
        if ingested.get(path.name) != current_digest:
            changed.append(path)
    return changed


def _run_gemini_compile(prompt: str, api_key: str) -> tuple[dict[str, Any] | None, str | None]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
    schema = {
        "type": "OBJECT",
        "properties": {
            "concepts": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "slug": {"type": "STRING", "description": "ASCII kebab-case filename (without .md)"},
                        "content": {"type": "STRING", "description": "Full Markdown article text with YAML frontmatter"}
                    },
                    "required": ["slug", "content"]
                }
            },
            "connections": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "slug": {"type": "STRING", "description": "format: a--b (without .md)"},
                        "content": {"type": "STRING", "description": "Full Markdown connection text with YAML frontmatter"}
                    },
                    "required": ["slug", "content"]
                }
            },
            "index_content": {
                "type": "STRING",
                "description": "Updated full Markdown table content for knowledge/index.md"
            },
            "log_entry": {
                "type": "STRING",
                "description": "Log entry to append to knowledge/log.md"
            }
        },
        "required": ["concepts", "index_content", "log_entry"]
    }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8")
            res_json = json.loads(body)
            candidates = res_json.get("candidates", [])
            if not candidates:
                return None, "gemini-empty-candidates"
            text = candidates[0]["content"]["parts"][0]["text"]
            return json.loads(text), None
    except urllib.error.HTTPError as err:
        # Fallback to flash if 2.5-pro has rate issues
        if err.code in (404, 429, 503):
            url_flash = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            try:
                req_flash = urllib.request.Request(url_flash, data=data, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req_flash, timeout=120) as resp_flash:
                    body_flash = resp_flash.read().decode("utf-8")
                    res_flash = json.loads(body_flash)
                    text_flash = res_flash["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text_flash), None
            except Exception as exc2:
                return None, f"gemini-flash-error-{exc2}"
        return None, f"gemini-http-{err.code}"
    except Exception as exc:
        return None, f"gemini-error-{exc}"


def _find_agy_executable() -> str | None:
    found = shutil.which("agy") or shutil.which("agy.exe")
    if found:
        return found
    candidates = [
        Path(os.path.expanduser(r"~\AppData\Local\agy\bin\agy.exe")),
        Path(os.path.expanduser(r"~\AppData\Local\Programs\agy\bin\agy.exe")),
        Path(os.path.expanduser(r"~/.local/bin/agy")),
        Path("/usr/local/bin/agy"),
        Path("/opt/homebrew/bin/agy"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def _run_agy_compile(prompt: str) -> tuple[dict[str, Any] | None, str | None]:
    agy = _find_agy_executable()
    if agy is None:
        return None, "agy-cli-missing"

    environment = os.environ.copy()
    environment["BEYIN_INVOKED_BY"] = "beyin-scripts"
    try:
        with tempfile.TemporaryDirectory(prefix="beyin-compile-") as temporary:
            compile_instruction = (
                prompt + "\n\n"
                "ÖNEMLİ: Çıktıyı SADECE geçerli bir JSON nesnesi olarak döndür. "
                "Markdown kod bloğu (```json), selamlama veya açıklama yazma. "
                "JSON formatı:\n"
                "{\n"
                '  "concepts": [{"slug": "...", "content": "..."}],\n'
                '  "connections": [{"slug": "...", "content": "..."}],\n'
                '  "index_content": "...",\n'
                '  "log_entry": "..."\n'
                "}"
            )
            result = subprocess.run(
                [
                    agy,
                    "-p",
                    compile_instruction,
                    "--disable-slash-commands",
                    "--effort",
                    "low",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=temporary,
                env=environment,
                timeout=300,
                check=False,
            )
    except subprocess.TimeoutExpired:
        return None, "agy-timeout"
    except Exception as exc:
        return None, f"agy-exec-error:{exc}"

    if result.returncode != 0:
        return None, f"agy-exit-{result.returncode}"

    raw_text = result.stdout.strip()
    if not raw_text:
        return None, "agy-empty-output"

    if "```" in raw_text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
        if match:
            raw_text = match.group(1).strip()

    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed, None
        return None, "agy-output-not-dict"
    except json.JSONDecodeError as exc:
        return None, f"agy-json-decode-error:{exc}"


def build_compile_prompt(index_text: str, daily_name: str, daily_body: str, timestamp: str) -> str:
    return f"""BELLEK ŞEMASI KURALLARI
- Her kavram dosyası knowledge/concepts/<ascii-kebab-slug>.md yolunda olmalı.
- YAML frontmatter alanları: title, aliases, tags, sources, created, updated. sources günlük dosya adını ({daily_name}) içermeli.
- Kavram gövdesi: # Title, 2-4 cümlelik çekirdek açıklama, ## Önemli Noktalar, ## Detaylar, ## İlgili Kavramlar (wikilinklerle), ## Kaynaklar.
- Anlamlı kavram bağlantıları knowledge/connections/<a>--<b>.md yolunda olmalı.
- knowledge/index.md tablosunun sütunları: | Makale | Özet | Kaynak | Güncellendi |
- knowledge/log.md girdisi: `## [{timestamp}] compile | {daily_name}` başlığı ve oluşturulan/güncellenen listesi.

İNDEKSTEKİ MEVCUT DURUM:
{index_text}

GÜNLÜK LOG ({daily_name}):
{daily_body}

TALİMATLAR:
1. Bu günlükten kalıcı değeri olan 1-4 kavram çıkar veya mevcut makaleleri güncelle.
2. Bağlantı varsa connections altına ekle.
3. knowledge/index.md içeriğini güncelle (her makale için tek satır).
4. knowledge/log.md için özet log girdisi oluştur.
"""


MAX_DAILY_CHARS = 10_000


def _cap_daily(text: str, limit: int = MAX_DAILY_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def compile_daily(vault_root: Path, daily_path: Path) -> bool:
    knowledge_dir = vault_root / "knowledge"
    concepts_dir = knowledge_dir / "concepts"
    connections_dir = knowledge_dir / "connections"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    connections_dir.mkdir(parents=True, exist_ok=True)

    index_path = knowledge_dir / "index.md"
    log_path = knowledge_dir / "log.md"

    index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else "# Bilgi İndeksi\n\n| Makale | Özet | Kaynak | Güncellendi |\n| --- | --- | --- | --- |\n"
    daily_body = _cap_daily(daily_path.read_text(encoding="utf-8"))
    iso_ts = _iso_now()

    prompt = build_compile_prompt(index_text, daily_path.name, daily_body, iso_ts)

    result = None
    err = None

    # 1. Antigravity CLI native print mode (-p) (Zero API keys required!)
    agy = shutil.which("agy") or shutil.which("agy.exe")
    if agy is not None:
        result, err = _run_agy_compile(prompt)

    # 2. Check Gemini API
    if result is None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            result, err = _run_gemini_compile(prompt, api_key)

    if err or not result:
        write_health(vault_root / ".agents" / "scripts" / ".state", f"compile-llm-failed:{err or 'empty-result'}")
        return False

    # Apply concepts
    for concept in result.get("concepts", []):
        slug = re.sub(r"[^a-zA-Z0-9_\-]", "-", concept.get("slug", "").strip()).strip("-").lower()
        if not slug:
            continue
        content = concept.get("content", "").strip()
        if content:
            (concepts_dir / f"{slug}.md").write_text(content + "\n", encoding="utf-8")

    # Apply connections
    for conn in result.get("connections", []):
        slug = re.sub(r"[^a-zA-Z0-9_\-]", "-", conn.get("slug", "").strip()).strip("-").lower()
        if not slug:
            continue
        content = conn.get("content", "").strip()
        if content:
            (connections_dir / f"{slug}.md").write_text(content + "\n", encoding="utf-8")

    # Update index
    new_index = result.get("index_content", "").strip()
    if new_index:
        index_path.write_text(new_index + "\n", encoding="utf-8")

    # Update log
    log_entry = result.get("log_entry", "").strip()
    if log_entry:
        with log_path.open("a", encoding="utf-8") as lf:
            lf.write(f"\n{log_entry}\n")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state_path = STATE_DIR / "compile-state.json"
    state = _load_state(state_path)

    changed = changed_daily_logs(VAULT_ROOT, state)
    if not changed:
        print("Derlenecek yeni günlük log bulunamadı.")
        return

    print(f"{len(changed)} adet değişen günlük log bulundu.")
    for daily_path in changed:
        print(f"Derleniyor: {daily_path.name}...")
        if args.dry_run:
            continue
        success = compile_daily(VAULT_ROOT, daily_path)
        if success:
            state.setdefault("ingested", {})[daily_path.name] = _sha256(daily_path)
            state["last_run"] = _iso_now()
            state["last_status"] = "ok"
            _save_state(state_path, state)
            print(f"Tamamlandı: {daily_path.name}")
        else:
            print(f"Hata oluştu: {daily_path.name}")
            break


if __name__ == "__main__":
    main()
