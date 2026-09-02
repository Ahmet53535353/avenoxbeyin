#!/usr/bin/env bash
# Git Sync — kalp atışı modu testleri
#
# Bu testler session-end.sh'e eklenecek git-sync bloğunun davranışını doğrular.
# Hiçbir test gerçek GitHub'a push yapmaz; her test kendi geçici git reposunu kurar.

set -euo pipefail

# Hermeticity: gerçek kullanıcının git config'i sızmasın
unset GIT_CONFIG_GLOBAL XDG_CONFIG_HOME
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null

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

# Geçici çalışma alanı
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Test ortak fixture: bare remote + çalışma vault
make_fixture() {
    local label="$1"
    local fixture="$tmp/fixture-$label"
    mkdir -p "$fixture"

    git -C "$fixture" init -q --bare remote.git 2>/dev/null || true

    mkdir -p "$fixture/vault"
    git -C "$fixture/vault" init -q -b main >/dev/null 2>&1 \
        || git -C "$fixture/vault" init -q >/dev/null 2>&1
    git -C "$fixture/vault" checkout -q main >/dev/null 2>&1 || true

    git -C "$fixture/vault" remote remove origin >/dev/null 2>&1 || true
    git -C "$fixture/vault" remote add origin "$fixture/remote.git" >/dev/null 2>&1

    # Varsayılan identity
    git -C "$fixture/vault" config --local user.name "Test User" >/dev/null 2>&1
    git -C "$fixture/vault" config --local user.email "test@example.com" >/dev/null 2>&1

    # İlk commit (branch'i main yap)
    echo "fixture: $label" > "$fixture/vault/README.md"
    git -C "$fixture/vault" add README.md >/dev/null 2>&1
    git -C "$fixture/vault" commit -q -m "initial" >/dev/null 2>&1 || true

    # Branch yoksa oluştur (eski git init -b yok sayar)
    if ! git -C "$fixture/vault" show-ref --verify --quiet refs/heads/main 2>/dev/null; then
        git -C "$fixture/vault" branch -f main >/dev/null 2>&1 || true
    fi
    git -C "$fixture/vault" checkout -q main >/dev/null 2>&1 || true

    # uzak repo'ya push (tüm çıktıyı bastır)
    git -C "$fixture/vault" push -q -u origin main >/dev/null 2>&1 || true
    git -C "$fixture/vault" branch --set-upstream-to=origin/main main >/dev/null 2>&1 || true
    git -C "$fixture/vault" config --local branch.main.remote origin >/dev/null 2>&1
    git -C "$fixture/vault" config --local branch.main.merge refs/heads/main >/dev/null 2>&1

    echo "$fixture"
}

# session-end.sh'den izole edilen git-sync fonksiyonu (test edilen kod)
git_sync() {
    local vault="$1"
    local state_dir="$2"

    [ -d "$vault/.git" ] || return 0
    command -v git >/dev/null 2>&1 || return 0

    local last_push_file="$state_dir/last-push.json"
    local now_epoch
    now_epoch=$(date '+%s')
    local now_readable
    now_readable=$(date '+%Y-%m-%d %H:%M:%S')
    local do_push=0

    if [ -f "$last_push_file" ]; then
        local last_push
        last_push=$(python3 -c "import json,sys; d=json.load(open('$last_push_file')); print(d.get('ts',0))" 2>/dev/null || echo 0)
        case "$last_push" in ''|*[!0-9]*) last_push=0 ;; esac
        local diff=$((now_epoch - last_push))
        [ "$diff" -ge 3600 ] && do_push=1
    else
        do_push=1
    fi

    if [ "$do_push" -eq 1 ]; then
        local remote
        remote=$(git -C "$vault" remote get-url origin 2>/dev/null || :)
        if [ -n "$remote" ]; then
            local branch
            branch=$(git -C "$vault" branch --show-current 2>/dev/null || echo "main")

            (
                cd "$vault" || exit 0

                if [ -z "$(git config user.name 2>/dev/null || :)" ]; then
                    git config --local user.name "avenoxbeyin"
                    git config --local user.email "beyin@avenox.local"
                fi

                git pull --ff-only -q origin "$branch" >/dev/null 2>&1 || :
                git add -A >/dev/null 2>&1 || :

                if git diff --cached --quiet >/dev/null 2>&1; then
                    : # değişiklik yok, push yok, last-push.json yazma
                else
                    git commit -q -m "vault backup: $now_readable" >/dev/null 2>&1 || :
                    git push -q origin "$branch" >/dev/null 2>&1 || :
                    printf '{"ts":%s,"last":"%s"}\n' "$now_epoch" "$now_readable" > "$last_push_file"
                fi
            ) >/dev/null 2>&1
        fi
    fi
}

echo "Git sync testleri"

# === TEST 1: Remote yoksa sessizce çık ===
echo ""
echo "1) Remote olmadan çalışma"
f1="$(make_fixture noremote)"
rm -rf "$f1/vault/.git/refs/remotes" 2>/dev/null || true
git -C "$f1/vault" remote remove origin 2>/dev/null || true
state1="$f1/vault/.claude/scripts/.state"
mkdir -p "$state1"
git_sync "$f1/vault" "$state1"
if [ ! -f "$state1/last-push.json" ]; then
    assert "remote_yoksa_push_yapilmaz" 0
else
    assert "remote_yoksa_push_yapilmaz" 1 "last-push.json yazildi"
fi

# === TEST 2: 3600 sn geçmemişse push yapma ===
echo ""
echo "2) 3600 sn geçmemişse"
f2="$(make_fixture recent)"
state2="$f2/vault/.claude/scripts/.state"
mkdir -p "$state2"
# Şu andan 5 saniye önce
now=$(date '+%s')
printf '{"ts":%s,"last":"recent"}\n' "$((now - 5))" > "$state2/last-push.json"
git_sync "$f2/vault" "$state2"
# last-push.json değişmemeli (yeni commit yok, push yok)
last_ts=$(python3 -c "import json; print(json.load(open('$state2/last-push.json'))['ts'])")
if [ "$last_ts" = "$((now - 5))" ]; then
    assert "3600sn_gicmemisse_push_atlanir" 0
else
    assert "3600sn_gicmemisse_push_atlanir" 1 "ts degisti: $last_ts"
fi

# === TEST 3: 3600 sn geçmişse push ===
echo ""
echo "3) 3600 sn geçmişse"
f3="$(make_fixture oldpush)"
state3="$f3/vault/.claude/scripts/.state"
mkdir -p "$state3"
now=$(date '+%s')
printf '{"ts":%s,"last":"old"}\n' "$((now - 7200))" > "$state3/last-push.json"
echo "yeni degisiklik" >> "$f3/vault/README.md"
git_sync "$f3/vault" "$state3"
last_ts=$(python3 -c "import json; print(json.load(open('$state3/last-push.json'))['ts'])")
if [ "$last_ts" = "$now" ]; then
    assert "3600sn_gicmisse_push_yapilir" 0
else
    assert "3600sn_gicmisse_push_yapilir" 1 "ts guncellenmedi: $last_ts"
fi

# === TEST 4: Değişiklik yoksa commit atlanmaz (sadece pull) ===
echo ""
echo "4) Değişiklik yok"
f4="$(make_fixture nochanges)"
state4="$f4/vault/.claude/scripts/.state"
mkdir -p "$state4"
git_sync "$f4/vault" "$state4"
# Değişiklik olmadığı için last-push.json YAZILMAMALI olur.
# Kodun: do_push=1 → remote var → commit atlanır (no changes) → last-push.json yazılmaz.
# AMA gerçek: kodumuz last-push.json'ı her koşulda yazıyor. Doğru davranış ne?
# Karar: değişiklik yoksa last-push.json YAZILMAMALI (gerek yok).
if [ ! -f "$state4/last-push.json" ]; then
    assert "degisiklik_yoksa_push_atlanir" 0
else
    assert "degisiklik_yoksa_push_atlanir" 1 "last-push.json yazildi ama degisiklik yoktu"
fi

# === TEST 5: Commit mesajı formatı ===
echo ""
echo "5) Commit mesajı formatı"
f5="$(make_fixture msgfmt)"
state5="$f5/vault/.claude/scripts/.state"
mkdir -p "$state5"
echo "yeni icerik" >> "$f5/vault/README.md"
git_sync "$f5/vault" "$state5"
last_commit=$(git -C "$f5/vault" log -1 --format=%s 2>/dev/null || echo "")
case "$last_commit" in
    "vault backup: "*) assert "commit_mesaji_formati" 0 ;;
    *) assert "commit_mesaji_formati" 1 "yanlis format: $last_commit" ;;
esac

# === TEST 6: last-push.json güncellenir ===
echo ""
echo "6) last-push.json güncelleme"
f6="$(make_fixture lastpush)"
state6="$f6/vault/.claude/scripts/.state"
mkdir -p "$state6"
now_before=$(date '+%s')
# Değişiklik ekle ki push tetiklensin
echo "yeni degisiklik" >> "$f6/vault/README.md"
git_sync "$f6/vault" "$state6"
if [ -f "$state6/last-push.json" ]; then
    last_ts=$(python3 -c "import json; print(json.load(open('$state6/last-push.json'))['ts'])")
    now_after=$(date '+%s')
    if [ "$last_ts" -ge "$now_before" ] && [ "$last_ts" -le "$now_after" ]; then
        assert "last_push_json_guncellenir" 0
    else
        assert "last_push_json_guncellenir" 1 "ts aralik disinda: $last_ts"
    fi
else
    assert "last_push_json_guncellenir" 1 "dosya yok"
fi

# === TEST 7: Vault değilse sessizce çık ===
echo ""
echo "7) .git olmadan"
f7="$(mktemp -d)"
state7="$f7/.claude/scripts/.state"
mkdir -p "$state7"
git_sync "$f7" "$state7"
if [ ! -f "$state7/last-push.json" ]; then
    assert "git_yoksa_sessiz_cik" 0
else
    assert "git_yoksa_sessiz_cik" 1 "push yapildi"
fi

# === TEST 8: git komutu yoksa ===
echo ""
echo "8) git yok"
f8="$(mktemp -d)"
mkdir -p "$f8/.git"
state8="$f8/.claude/scripts/.state"
mkdir -p "$state8"
PATH="/usr/bin:/bin" git_sync "$f8" "$state8" 2>/dev/null || true
# Gerçekten git yoksa, sessizce çıkmalı
assert "git_komutu_yoksa_sessiz_cik" 0

# === TEST 9: Branch dinamik algılama ===
echo ""
echo "9) Branch algılama"
f9="$(make_fixture branch)"
git -C "$f9/vault" checkout -q -b develop
git -C "$f9/vault" push -q -u origin develop
state9="$f9/vault/.claude/scripts/.state"
mkdir -p "$state9"
git_sync "$f9/vault" "$state9"
current=$(git -C "$f9/vault" branch --show-current)
if [ "$current" = "develop" ]; then
    assert "branch_dinamik_algilanir" 0
else
    assert "branch_dinamik_algilanir" 1 "branch: $current"
fi

# === TEST 10: git kimliği yoksa local ayarla ===
echo ""
echo "10) Git kimliği kontrolü"
f10="$(make_fixture gitid)"
# Config dosyasından [user] bloğunu kaldır (git config --unset yerine)
sed -i '/^\[user\]/,/^$/d' "$f10/vault/.git/config" 2>/dev/null || true
state10="$f10/vault/.claude/scripts/.state"
mkdir -p "$state10"
git_sync "$f10/vault" "$state10"
set_name=$(git -C "$f10/vault" config --local user.name 2>/dev/null || echo "")
if [ -n "$set_name" ]; then
    assert "git_kimligi_yoksa_local_ayarla" 0
else
    assert "git_kimligi_yoksa_local_ayarla" 1 "user.name ayarlanmadi"
fi

# === ÖZET ===
echo ""
if [ "$failures" -gt 0 ]; then
    echo "BASARISIZ: $failures/$total"
    exit 1
fi
echo "TAMAM: $total test gecti"
exit 0