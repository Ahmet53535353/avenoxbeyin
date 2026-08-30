#!/bin/bash
[ -n "${BEYIN_INVOKED_BY:-}" ] && exit 0
# Count prompts and nudge at every multiple of fifteen.

BEYIN_HOOK_DIR=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd)
. "$BEYIN_HOOK_DIR/lib.sh" 2>/dev/null || exit 0

BEYIN_SESSION_KEY=$(beyin_session_key 2>/dev/null || :)
[ -n "$BEYIN_SESSION_KEY" ] || exit 0

BEYIN_PROMPT_COUNT_FILE="$BEYIN_STATE_DIR/prompt_count.$BEYIN_SESSION_KEY"
BEYIN_LOCK_FILE="$BEYIN_PROMPT_COUNT_FILE.lock"

mkdir -p "$BEYIN_STATE_DIR" 2>/dev/null || :

# flock(1) serialises all callers through the kernel file-lock queue.
# The wait timeout (5s) matches the hook timeout in settings.json so that
# lock contention does not cause hook timeouts. If flock times out we exit
# silently rather than counting. Losing one increment is preferable to a
# failed hook that stalls the session. 100 parallel forks serialise in ~1s
# (each holds the lock ~10ms), well within the 5s budget.
if ! command -v flock >/dev/null 2>&1; then
  # Fallback: busy-wait mkdir lock with long enough budget that it only
  # fails on genuine lock-holder-crash (not normal contention).
  BEYIN_LOCK_DIR="$BEYIN_PROMPT_COUNT_FILE.lock"
  BEYIN_LOCK_ATTEMPT=0
  BEYIN_LOCK_ACQUIRED=0
  while ! mkdir "$BEYIN_LOCK_DIR" 2>/dev/null; do
    BEYIN_LOCK_ATTEMPT=$((BEYIN_LOCK_ATTEMPT + 1))
    if [ "$BEYIN_LOCK_ATTEMPT" -gt 10000 ]; then
      exit 0
    fi
    sleep 0.01 2>/dev/null || sleep 1 2>/dev/null || exit 0
  done
  BEYIN_LOCK_ACQUIRED=1

  cleanup_lock() {
    if [ "$BEYIN_LOCK_ACQUIRED" -eq 1 ]; then
      rmdir "$BEYIN_LOCK_DIR" 2>/dev/null || :
    fi
  }
  trap cleanup_lock EXIT
  trap 'exit 0' HUP INT TERM
else
  exec 9>"$BEYIN_LOCK_FILE"
  flock -w 5 9 || { exec 9>&-; exit 0; }
  trap 'exec 9>&-' EXIT
fi

BEYIN_COUNT=0
[ -f "$BEYIN_PROMPT_COUNT_FILE" ] && BEYIN_COUNT=$(sed -n '1p' "$BEYIN_PROMPT_COUNT_FILE" 2>/dev/null || :)
case "$BEYIN_COUNT" in
  ''|*[!0-9]*) BEYIN_COUNT=0 ;;
esac

BEYIN_COUNT=$((BEYIN_COUNT + 1))
if ! command -v flock >/dev/null 2>&1; then
  BEYIN_COUNT_TMP="$BEYIN_PROMPT_COUNT_FILE.tmp.$$"
  if printf '%s\n' "$BEYIN_COUNT" > "$BEYIN_COUNT_TMP" 2>/dev/null; then
    mv -f "$BEYIN_COUNT_TMP" "$BEYIN_PROMPT_COUNT_FILE" 2>/dev/null || :
  fi
  rm -f "$BEYIN_COUNT_TMP" 2>/dev/null || :
else
  printf '%s\n' "$BEYIN_COUNT" > "$BEYIN_PROMPT_COUNT_FILE" 2>/dev/null || :
fi

if ! command -v flock >/dev/null 2>&1; then
  cleanup_lock
fi
trap - EXIT HUP INT TERM

if [ $((BEYIN_COUNT % 15)) -eq 0 ]; then
  beyin_emit UserPromptSubmit "[Hafıza] $BEYIN_COUNT. mesaj. Oturum sonunda 🔮 850-Companion/Last-Session.md ve Threads.md güncellemeyi unutma."
fi
exit 0
