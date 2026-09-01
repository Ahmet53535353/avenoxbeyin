#!/bin/bash
[ -n "${BEYIN_INVOKED_BY:-}" ] && exit 0
# Mark relational-memory debt, then detach the automatic session flush.

BEYIN_HOOK_DIR=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd)
. "$BEYIN_HOOK_DIR/lib.sh" 2>/dev/null || exit 0

BEYIN_HOOK_INPUT="$BEYIN_STATE_DIR/hookin-$$.json"
umask 077
if ! cat > "$BEYIN_HOOK_INPUT" 2>/dev/null; then
  rm -f "$BEYIN_HOOK_INPUT" 2>/dev/null || :
  BEYIN_HOOK_INPUT=""
fi

BEYIN_SESSION_KEY=""
if [ -n "$BEYIN_HOOK_INPUT" ]; then
  BEYIN_SESSION_KEY=$(beyin_session_key < "$BEYIN_HOOK_INPUT" 2>/dev/null || :)
fi

BEYIN_MEMORY_DIR="$BEYIN_PROJECT_DIR/🔮 850-Companion"
BEYIN_START=0
BEYIN_PROMPTS=0
BEYIN_SESSION_START_FILE=""
BEYIN_PROMPT_COUNT_FILE=""
BEYIN_REFLECTION_FILE=""
if [ -n "$BEYIN_SESSION_KEY" ]; then
  BEYIN_SESSION_START_FILE="$BEYIN_STATE_DIR/session_start_time.$BEYIN_SESSION_KEY"
  BEYIN_PROMPT_COUNT_FILE="$BEYIN_STATE_DIR/prompt_count.$BEYIN_SESSION_KEY"
  BEYIN_REFLECTION_FILE="$BEYIN_STATE_DIR/needs_reflection.$BEYIN_SESSION_KEY"
  [ -f "$BEYIN_SESSION_START_FILE" ] && BEYIN_START=$(sed -n '1p' "$BEYIN_SESSION_START_FILE" 2>/dev/null || :)
  [ -f "$BEYIN_PROMPT_COUNT_FILE" ] && BEYIN_PROMPTS=$(sed -n '1p' "$BEYIN_PROMPT_COUNT_FILE" 2>/dev/null || :)
fi
case "$BEYIN_START" in ''|*[!0-9]*) BEYIN_START=0 ;; esac
case "$BEYIN_PROMPTS" in ''|*[!0-9]*) BEYIN_PROMPTS=0 ;; esac

BEYIN_MODIFIED=0
if [ -f "$BEYIN_MEMORY_DIR/Last-Session.md" ]; then
  BEYIN_FILE_MTIME=$(beyin_mtime "$BEYIN_MEMORY_DIR/Last-Session.md")
  case "$BEYIN_FILE_MTIME" in ''|*[!0-9]*) BEYIN_FILE_MTIME=0 ;; esac
  [ "$BEYIN_FILE_MTIME" -gt "$BEYIN_START" ] 2>/dev/null && BEYIN_MODIFIED=1
fi

if [ "$BEYIN_PROMPTS" -ge 5 ] && [ "$BEYIN_MODIFIED" -eq 0 ] && [ -n "$BEYIN_REFLECTION_FILE" ]; then
  printf 'Oturum hafıza güncellemeden bitti. Prompt: %s. %s\n' \
    "$BEYIN_PROMPTS" "$(date '+%Y-%m-%d %H:%M' 2>/dev/null)" \
    > "$BEYIN_REFLECTION_FILE" 2>/dev/null || :
fi

if [ -n "$BEYIN_HOOK_INPUT" ]; then
  if command -v python3 >/dev/null 2>&1; then
    nohup python3 "$BEYIN_PROJECT_DIR/.claude/scripts/flush.py" \
      --hook-input "$BEYIN_HOOK_INPUT" >/dev/null 2>&1 &
  else
    beyin_mark_python_missing
    rm -f "$BEYIN_HOOK_INPUT" 2>/dev/null || :
    beyin_emit SessionEnd 'Beyin arka plan özeti başlatılamadı: python3 bulunamadı. beyin-doktor çalıştır.'
  fi
fi

# Git sync - hourly backup to private repo (background, non-blocking)
if command -v git >/dev/null 2>&1; then
  nohup bash -c '
    VAULT="$1"
    STATE_DIR="$VAULT/.claude/scripts/.state"
    LAST_PUSH_FILE="$STATE_DIR/last-push.json"
    mkdir -p "$STATE_DIR"
    NOW_EPOCH=$(date +%s)
    DO_PUSH=0
    if [ -f "$LAST_PUSH_FILE" ]; then
      LAST_PUSH=$(python3 -c "import json,sys; d=json.load(open('\''$LAST_PUSH_FILE'\'')); print(d.get('\''ts'\'',0))" 2>/dev/null || echo 0)
      case "$LAST_PUSH" in ''|*[!0-9]*) LAST_PUSH=0 ;; esac
      [ $((NOW_EPOCH - LAST_PUSH)) -ge 3600 ] && DO_PUSH=1
    else
      DO_PUSH=1
    fi
    if [ "$DO_PUSH" -eq 1 ]; then
      REMOTE=$(git -C "$VAULT" remote get-url origin 2>/dev/null || :)
      if [ -n "$REMOTE" ]; then
        BRANCH=$(git -C "$VAULT" branch --show-current 2>/dev/null || echo "main")
        (
          cd "$VAULT" || exit 0
          if [ -z "$(git config user.name 2>/dev/null || :)" ]; then
            git config --local user.name "avenoxbeyin"
            git config --local user.email "beyin@avenox.local"
          fi
          git pull --ff-only -q origin "$BRANCH" >/dev/null 2>&1 || :
          git add -A >/dev/null 2>&1 || :
          if ! git diff --cached --quiet >/dev/null 2>&1; then
            NOW_READABLE=$(date '+%Y-%m-%d %H:%M:%S')
            git commit -q -m "vault backup: $NOW_READABLE" >/dev/null 2>&1 || :
            git push -q origin "$BRANCH" >/dev/null 2>&1 || :
            printf '\''{"ts":%s,"last":"%s"}\n'\'' "$NOW_EPOCH" "$NOW_READABLE" > "$LAST_PUSH_FILE"
          fi
        ) >/dev/null 2>&1
      fi
    fi
  ' _ "$BEYIN_PROJECT_DIR" >/dev/null 2>&1 &
fi

[ -n "$BEYIN_SESSION_START_FILE" ] && rm -f "$BEYIN_SESSION_START_FILE" 2>/dev/null || :
[ -n "$BEYIN_PROMPT_COUNT_FILE" ] && rm -f "$BEYIN_PROMPT_COUNT_FILE" 2>/dev/null || :
exit 0
