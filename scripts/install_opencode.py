#!/usr/bin/env python3
"""OpenCode harness plugin installer for avenoxbeyin.

Installs the opencode-brain plugin to ~/.config/opencode/plugins/ and registers
it in opencode.jsonc. The plugin provides brain-memory integration for OpenCode
sessions within an avenoxbeyin vault.

Usage:
  python scripts/install_opencode.py --vault-path "/path/to/vault"
  python scripts/install_opencode.py --preflight-only
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SOURCE = REPO_ROOT / "plugins" / "opencode-brain"
OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
OPENCODE_PLUGINS = Path.home() / ".config" / "opencode" / "plugins"


def check_preflight() -> dict:
    """Verify environment readiness for OpenCode plugin installation."""
    report: dict = {
        "ok": True,
        "plugin_source_exists": PLUGIN_SOURCE.is_dir(),
        "opencode_config_exists": OPENCODE_CONFIG.exists(),
        "errors": [],
    }

    if not PLUGIN_SOURCE.is_dir():
        report["ok"] = False
        report["errors"].append(f"Plugin kaynağı bulunamadı: {PLUGIN_SOURCE}")

    return report


def _read_jsonc(path: Path) -> dict | None:
    """Read a JSONC file, stripping // comments."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = []
    for line in text.splitlines():
        stripped = line.split("//")[0]
        lines.append(stripped)
    try:
        return json.loads("\n".join(lines))
    except json.JSONDecodeError:
        return None


def _write_jsonc(path: Path, data: dict) -> None:
    """Write a JSONC file preserving a // plugins comment if the file existed."""
    existing_lines = []
    if path.exists():
        try:
            existing_lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            pass

    lines = [json.dumps(data, indent=2, ensure_ascii=False)]
    for original in reversed(existing_lines):
        stripped = original.split("//")[0].strip()
        if stripped.startswith("{"):
            break
        if "// plugins" in original:
            lines.append(original)
            break

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def install_plugin(vault_path: Path) -> bool:
    """Install opencode-brain plugin for a vault."""
    vault_path = vault_path.expanduser().resolve()

    beyin_dir = vault_path / ".beyin"
    hooks_dir = beyin_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    plugin_target = OPENCODE_PLUGINS / "opencode-brain"
    print(f"Eklenti kopyalanıyor: {plugin_target}")
    if plugin_target.exists():
        shutil.rmtree(plugin_target, ignore_errors=True)
    shutil.copytree(PLUGIN_SOURCE, plugin_target)

    bridge_source = vault_path / ".claude" / "scripts" / "bridge.py"
    bridge_target = hooks_dir / "bridge.py"
    if bridge_source.exists() and not bridge_target.exists():
        shutil.copy2(bridge_source, bridge_target)

    read_transcript_source = vault_path / ".claude" / "scripts" / "read_transcript.py"
    read_transcript_target = hooks_dir / "read_transcript.py"
    if read_transcript_source.exists() and not read_transcript_target.exists():
        shutil.copy2(read_transcript_source, read_transcript_target)

    lifecycle_source = vault_path / ".claude" / "scripts" / "lifecycle.py"
    lifecycle_target = hooks_dir / "lifecycle.py"
    if lifecycle_source.exists() and not lifecycle_target.exists():
        shutil.copy2(lifecycle_source, lifecycle_target)

    runtime_platform_source = vault_path / ".claude" / "scripts" / "runtime_platform.py"
    runtime_platform_target = hooks_dir / "runtime_platform.py"
    if runtime_platform_source.exists() and not runtime_platform_target.exists():
        shutil.copy2(runtime_platform_source, runtime_platform_target)

    if OPENCODE_CONFIG.exists():
        config = _read_jsonc(OPENCODE_CONFIG) or {}
    else:
        config = {}

    plugins = config.get("plugins", [])
    if not any(p.get("name") == "opencode-brain" for p in plugins):
        plugins.append({"name": "opencode-brain", "path": str(plugin_target)})
        config["plugins"] = plugins
        _write_jsonc(OPENCODE_CONFIG, config)
        print(f"opencode.jsonc güncellendi: opencode-brain eklentisi kaydedildi")
    else:
        print("opencode.jsonc: opencode-brain zaten kayıtlı")

    print("\n✅ opencode-brain eklentisi kuruldu!")
    print(f"📁 Vault: {vault_path}")
    print(f"🔌 Plugin: {plugin_target}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault-path",
        type=Path,
        default=None,
        help="Path to an existing avenoxbeyin vault",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Only run preflight checks",
    )
    args = parser.parse_args()

    report = check_preflight()
    if args.preflight_only:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0 if report["ok"] else 1)

    if not report["ok"]:
        print("Ön kontrol başarısız:", file=sys.stderr)
        for err in report["errors"]:
            print(f" - {err}", file=sys.stderr)
        sys.exit(1)

    vault_path = args.vault_path
    if not vault_path:
        raw_path = input("Vault dizini (örn: ~/Brain): ").strip()
        if not raw_path:
            print("HATA: Vault dizini belirtilmedi.", file=sys.stderr)
            sys.exit(1)
        vault_path = Path(raw_path).expanduser().resolve()

    success = install_plugin(vault_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
