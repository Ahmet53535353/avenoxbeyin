#!/usr/bin/env python3
"""Cross-platform installer for avenoxbeyin on Google Antigravity.

Usage:
  python scripts/install_antigravity.py --vault-path "/path/to/MyOS" \
      --user-name "Mehmet" --user-bio "Yazılım Geliştirici" \
      --companion "Echo" --os-name "MehmetOS"

  python scripts/install_antigravity.py --preflight-only
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

sys.dont_write_bytecode = True

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "template"


def resolve_placeholders(root: Path, values: dict[str, str]) -> None:
    """Replace all {{KEY}} occurrences in .md, .json and .txt files."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".md", ".json", ".txt", ".sh", ".ps1", ".py"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
            if "{{" not in content:
                continue
            for k, v in values.items():
                content = content.replace("{{" + k + "}}", v)
            path.write_text(content, encoding="utf-8")
        except Exception:
            pass


def check_preflight() -> dict[str, Any]:
    """Verify environment readiness."""
    report: dict[str, Any] = {
        "ok": True,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "template_exists": TEMPLATE_DIR.is_dir(),
        "gemini_api_key": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "errors": []
    }

    if sys.version_info < (3, 8):
        report["ok"] = False
        report["errors"].append("Python 3.8 veya üzeri gereklidir.")

    if not TEMPLATE_DIR.is_dir():
        report["ok"] = False
        report["errors"].append(f"Template dizini bulunamadı: {TEMPLATE_DIR}")

    return report


def install_vault(
    vault_path: Path,
    user_name: str,
    user_bio: str,
    companion: str,
    os_name: str,
) -> bool:
    vault_path = vault_path.expanduser().resolve()

    if vault_path.exists() and any(vault_path.iterdir()):
        print(f"HATA: Hedef dizin zaten var ve boş değil: {vault_path}", file=sys.stderr)
        return False

    print(f"📦 Şablon kopyalanıyor: {vault_path}")
    shutil.copytree(TEMPLATE_DIR, vault_path, dirs_exist_ok=True)

    today_str = dt.date.today().strftime("%Y-%m-%d")
    values = {
        "OS_NAME": os_name,
        "USER_NAME": user_name,
        "USER_BIO": user_bio,
        "COMPANION": companion,
        "VAULT_PATH": str(vault_path),
        "TODAY": today_str,
    }

    print("🔧 Değişkenler ve şablonlar yerleştiriliyor...")
    resolve_placeholders(vault_path, values)

    # Ensure state dir
    (vault_path / ".agents" / "scripts" / ".state").mkdir(parents=True, exist_ok=True)

    print("\n✅ avenoxbeyin (Antigravity) başarıyla kuruldu!")
    print(f"📁 Vault Konumu: {vault_path}")
    print(f"🧠 AI Ortağı: {companion}")
    print(f"👤 Kullanıcı: {user_name}")
    print("\nNasıl Başlanır:")
    print(f"1. Antigravity ile açmak için bu dizine gidin:\n   cd \"{vault_path}\"")
    print("2. Google Antigravity oturumu başlatın.")
    print("3. İsteğe bağlı: Obsidian uygulamasında 'Open folder as vault' diyerek bu klasörü açın.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-path", type=Path, default=None, help="Target directory for the new vault")
    parser.add_argument("--user-name", type=str, default=None, help="Your name")
    parser.add_argument("--user-bio", type=str, default=None, help="Your role / bio")
    parser.add_argument("--companion", type=str, default=None, help="AI companion name (e.g. Echo, Nova, Atlas)")
    parser.add_argument("--os-name", type=str, default=None, help="Vault OS name (e.g. MehmetOS)")
    parser.add_argument("--preflight-only", action="store_true", help="Only run preflight checks")
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
    user_name = args.user_name
    user_bio = args.user_bio
    companion = args.companion
    os_name = args.os_name

    # Interactive prompt for missing parameters
    if not vault_path:
        raw_path = input("Vault hedef dizini (örn: C:/Users/Mehmet/Documents/MehmetOS): ").strip()
        if not raw_path:
            print("HATA: Vault dizini belirtilmedi.", file=sys.stderr)
            sys.exit(1)
        vault_path = Path(raw_path)

    if not user_name:
        user_name = input("Adınız: ").strip() or "Kullanıcı"

    if not companion:
        companion = input("AI Ortağınızın adı (örn: Echo, Nova, Atlas, Beyin): ").strip() or "Echo"

    if user_bio is None:
        user_bio = input("Mesleğiniz / İlgi alanlarınız (AI için bağlam): ").strip() or "Genel"

    if not os_name:
        os_default = f"{user_name}OS"
        os_input = input(f"Sisteminizin adı (varsayılan: {os_default}): ").strip()
        os_name = os_input or os_default

    success = install_vault(vault_path, user_name, user_bio, companion, os_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
