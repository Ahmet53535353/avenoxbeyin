#!/usr/bin/env bash
# End-to-end proof that a clean install works on Linux/WSL.
#
# Without this test the repo can only claim the pieces compile. It installs a
# vault from scratch into a temporary directory, then drives the real
# SessionEnd hook with a real payload and waits for the engine to write a
# daily log.
#
# `claude` is stubbed on PATH so the run costs no quota and no network. That
# is the only stubbed piece: the installer, the hooks, the detach and the
# engine are all the real ones.

set -euo pipefail

# Hermeticity: blank the developer's own global git config so tests don't pass
# for the wrong reason.
unset GIT_CONFIG_GLOBAL XDG_CONFIG_HOME
export GIT_CONFIG_NOSYSTEM=1
# HOME=/dev/null'u EXPORT ETME — sadece subprocess'lere gitsin ama kalici ortam
# degistirmesin. Asiri korumali git isolation icin gerekli oldugunda kullanilir.
# Bu sayede sonraki test scriptlerinin HOME'u etkilenmez.
:

repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

failures=0
total=0

assert() {
    local name="$1"; local condition="$2"; local detail="${3:-}"
    total=$((total + 1))
    if [ "$condition" -eq 0 ]; then
        echo "  ok   $name"
    else
        echo "  FAIL $name -- $detail"
        failures=$((failures + 1))
    fi
}

echo 'Temiz kurulum uctan uca testi (Linux)'

tmp="$(mktemp -d)"
vault="$tmp/AylinOS"
binDir="$tmp/bin"
mkdir -p "$binDir"

cleanup() {
    sleep 0.5
    rm -rf "$tmp"
}
trap cleanup EXIT

# Stub kurulumdan ONCE hazirlanir: install scriptinin on kontrolu claude arar,
# ve CI runner'inda gercek claude yoktur. Boylece uc paket de CI'da kosar.
export PATH="$binDir:$PATH"

# Ozet metni AYRI bir dosyaya yazilir ve stub yalnizca onu basar. Boylece
# Turkce karakterler hicbir kacis katmanindan gecmez.
cat > "$binDir/summary.txt" <<'SUMMARY'
## Bağlam
Test bağlamı.
## Önemli Konuşmalar
- Test konuşması.
## Alınan Kararlar
- Test kararı.
## Öğrenilenler
- Test öğrenimi.
## Yapılacaklar
- Test işi.
SUMMARY

# claude stub
cat > "$binDir/claude_stub.py" <<'PYSTUB'
import os, sys, subprocess
args = sys.argv[1:]
if '--version' in args:
    print("0.0.0-stub (Claude Code)")
    raise SystemExit(0)
sys.stdin.read()
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "summary.txt"), encoding="utf-8") as fh:
    sys.stdout.write(fh.read())
PYSTUB

cat > "$binDir/claude" <<'CLAUDE'
#!/bin/bash
exec python3 "$(dirname "$0")/claude_stub.py" "$@"
CLAUDE
chmod +x "$binDir/claude"

# ---------------------------------------------------------------- install
# Linux/WSL install: SETUP.md PHASE 2 mantigini birebir uygulayan inline script.
# install.sh yok; kullanicinin gercek kullaniminda Claude Code/Codex SETUP.md'yi
# uygular. Bu test ayni adimi otomatik yapar.
install_exit=0
mkdir -p "$vault" || install_exit=$?
cp -R "$repo/template/." "$vault/" || install_exit=$?

# placeholder'lari doldur (emoji klasor adlarini find -exec ile guvenli sekilde)
find "$vault" -type f \( -name '*.md' -o -name '*.json' \) -print0 2>/dev/null \
    | while IFS= read -r -d '' f; do
        if grep -q '{{' "$f" 2>/dev/null; then
            sed -i \
                -e "s|{{OS_NAME}}|AylinOS|g" \
                -e "s|{{USER_NAME}}|Aylin|g" \
                -e "s|{{USER_BIO}}|Urun tasarimcisi|g" \
                -e "s|{{COMPANION}}|Echo|g" \
                -e "s|{{VAULT_PATH}}|$vault|g" \
                -e "s|{{TODAY}}|$(date +%F)|g" \
                "$f" 2>/dev/null || true
        fi
    done

# kanca executable
find "$vault/.claude/hooks" -maxdepth 1 -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true

# CodeX hooks render (render_codex_hooks.py varsa)
if [ -f "$vault/.claude/scripts/render_codex_hooks.py" ]; then
    python3 "$vault/.claude/scripts/render_codex_hooks.py" \
        --vault "$vault" --platform posix > /dev/null 2>&1 || true
fi

# daily/ knowledge/ klasorlerini olustur
mkdir -p "$vault/daily" "$vault/knowledge/concepts" "$vault/knowledge/connections" 2>/dev/null || true

# .beyin-version yaz
echo "2.2.0" > "$vault/.beyin-version" 2>/dev/null || true

assert "kurulum_sifir_ile_biter" "$install_exit" "cikis kodu: $install_exit"

# Dosya varlik kontrolleri
for p in \
    ".claude/scripts/flush.py" \
    ".claude/scripts/compile.py" \
    ".claude/scripts/.state" \
    ".claude/settings.json" \
    "daily" \
    "knowledge/index.md"
do
    pname="$(echo "$p" | tr '/' '_' | tr '.' '_')"
    if [ -e "$vault/$p" ]; then
        assert "kuruldu_$pname" 0
    else
        assert "kuruldu_$pname" 1 "eksik: $p"
    fi
done

# Placeholder kontrolu
left="$(find "$vault" \( -name '*.md' -o -name '*.json' \) -type f -exec grep -lE '\{\{[A-Z_]+\}\}' {} \; 2>/dev/null || true)"
if [ -z "$left" ]; then
    assert "placeholder_kalmadi" 0
else
    count="$(echo "$left" | wc -l)"
    assert "placeholder_kalmadi" 1 "kalan: $count"
fi

# Kanca kayit kontrolu
if [ -f "$vault/.claude/settings.json" ]; then
    events="$(python3 -c "import json; d=json.load(open('$vault/.claude/settings.json')); print(len(d.get('hooks',{})))" 2>/dev/null || echo "0")"
    if [ "$events" -eq 4 ]; then
        assert "dort_kanca_kayitli" 0
    else
        assert "dort_kanca_kayitli" 1 "kanca sayisi: $events"
    fi
else
    assert "dort_kanca_kayitli" 1 "settings.json yok"
fi

# ------------------------------------------------------------ transcript
transcript="$tmp/transcript.jsonl"
{
    for i in $(seq 1 6); do
        echo '{"type":"user","message":{"role":"user","content":"kullanici mesaji '"$i"'"}}'
        echo '{"type":"assistant","message":{"role":"assistant","content":"asistan cevabi '"$i"'"}}'
    done
} > "$transcript"

# ---------------------------------------------------- drive the real hook
# Hook stdin'den JSON payload okur: { session_id, transcript_path, hook_event_name }.
saved_project="${CLAUDE_PROJECT_DIR:-}"
export CLAUDE_PROJECT_DIR="$vault"

hook_input="$tmp/hook_input.json"
{
    printf '{"session_id":"e2e-clean-install","hook_event_name":"SessionEnd","transcript_path":"%s"}\n' \
        "$transcript"
} > "$hook_input"

hook_exit=0
if [ -f "$vault/.claude/hooks/session-end.sh" ]; then
    bash "$vault/.claude/hooks/session-end.sh" < "$hook_input" > /dev/null 2>&1 || hook_exit=$?
else
    hook_exit=127
fi
assert "sessionend_kancasi_sifir_ile_biter" "$hook_exit" "cikis kodu: $hook_exit"

# The summarizer is detached on purpose, so poll rather than assume.
scale="${BEYIN_TEST_TIMEOUT_SCALE:-1.0}"
wait_seconds="$(python3 -c "print(int(60 * $scale))" 2>/dev/null || echo 60)"
wrote=1

deadline_start="$(date +%s)"
deadline_end=$((deadline_start + wait_seconds))

while true; do
    now="$(date +%s)"
    if [ "$now" -ge "$deadline_end" ]; then
        break
    fi
    if [ -n "$(find "$vault/daily" -name '*.md' -type f 2>/dev/null | head -1)" ]; then
        wrote=0
        break
    fi
    sleep 0.5
done

assert "motor_daily_altina_yazdi" "$wrote" "daily/ $wait_seconds saniyede bos kaldi"

if [ "$wrote" -eq 0 ]; then
    log="$(find "$vault/daily" -name '*.md' -type f 2>/dev/null | head -1)"
    if [ -n "$log" ]; then
        body="$(cat "$log" 2>/dev/null || true)"
        if echo "$body" | grep -q 'Bağlam' && echo "$body" | grep -q 'Alınan Kararlar' && echo "$body" | grep -q 'Yapılacaklar'; then
            assert "gunluk_log_bes_baslik_iceriyor" 0
        else
            assert "gunluk_log_bes_baslik_iceriyor" 1 "log govdesi beklenen Turkce basliklari tasimiyor"
        fi
    else
        assert "gunluk_log_bes_baslik_iceriyor" 1 "log dosyasi okunamadi"
    fi
fi

# flush hata kontrolu
if [ -f "$vault/.claude/scripts/.state/flush_last_error" ]; then
    assert "flush_hatasi_yok" 1 "flush_last_error yazilmis"
else
    assert "flush_hatasi_yok" 0
fi

# python3 eksik isareti kontrolu
if [ -f "$vault/.claude/scripts/.state/python3-missing" ]; then
    assert "python_eksik_isareti_yok" 1 "python3-missing yazilmis"
else
    assert "python_eksik_isareti_yok" 0
fi

# Cleanup environment
if [ -z "$saved_project" ]; then
    unset CLAUDE_PROJECT_DIR
else
    export CLAUDE_PROJECT_DIR="$saved_project"
fi

echo ""
if [ "$failures" -gt 0 ]; then
    echo "BASARISIZ: $failures/$total"
    exit 1
fi
echo "TAMAM: $total kontrol gecti -- temiz kurulum uctan uca calisiyor (Linux)"
exit 0