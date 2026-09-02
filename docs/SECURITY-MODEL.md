# Security Model (v2.2)

> Threat model, defenses, and explicit non-goals for avenoxbeyin's v2.2 vault safety boundaries.

## Threat model

The vault stores untrusted agent output (LLM-emitted markdown) and trusted user content (manually
written notes, knowledge base). The model is treated as **untrusted**: a successful prompt-injection
or jailbreak may produce content that tries to:

1. **Escape the sandbox.** Write to files outside `knowledge/` (e.g. `.claude/settings.json`,
   `.bashrc`, SSH keys) to persist a foothold across sessions.
2. **Delete history.** Remove `knowledge/index.md`, `knowledge/log.md`, or daily logs to wipe memory
   of prior activity.
3. **Substitute a knowledge entry.** Replace an existing concept article with attacker-controlled
   text under the same slug.
4. **Trick the next session.** Inject directive-shaped sentences (e.g. "ignore previous
   instructions and …") into index/log/daily data so the next session reads them as commands.

Trust boundary diagram:

```
┌─────────────────────────────────────────────────────────┐
│ untrusted (LLM output)                                  │
│  - stage/<files> produced by `claude -p`                │
│  - daily/ entries (transcripts, may be injected)        │
│  - knowledge/index.md, knowledge/log.md,                │
│    knowledge/concepts/, knowledge/connections/          │
└─────────────────────────────────────────────────────────┘
                       │ only via _validate_manifest_diff
                       │ + _promote_changes + check_source
                       ▼
┌─────────────────────────────────────────────────────────┐
│ trusted (user-written, hooks read but do not write)     │
│  - vault root config (.beyin-version, .gitignore)       │
│  - 🔮 850-Companion/ memory folder                      │
│  - daily/<files> (hook writes here, never the model)    │
└─────────────────────────────────────────────────────────┘
```

## Defenses (v2.2)

### 1. Stage is always outside the vault

`compile.py:_prepare_stage` creates the working directory under `tempfile.gettempdir()` and
**refuses to run** if the tempdir accidentally resolves inside the vault root. Claude CLI's
`--safe-mode` auto-protects any path inside a project's `.claude/` and silently refuses
`Write/Edit` there; the stage is therefore rooted at `/tmp/beyin-compile-stage-XXXX` (or
`%TEMP%\beyin-compile-stage-XXXX` on Windows) with mode `0700`. Only after the agent exits and
manifest diff passes `_validate_manifest_diff` does the script promote individual allowed files
into the live vault via `_promote_changes`.

### 2. Manifest diff and policy

The model can only touch files in the allow-list:

- `knowledge/index.md`
- `knowledge/log.md`
- `knowledge/concepts/**/*.md`
- `knowledge/connections/**/*.md`

Anything else is `PolicyError("forbidden-write:<path>")` and the run is recorded as `fail:policy`
with no promotion. Deletions, type-changes (file ↔ directory), and reparse-points in the stage
all reject before any file touches the live vault.

### 3. Reparse-point detection (v2.2)

`_platform._is_link_or_reparse(path)` rejects:

- POSIX symlinks (`stat.S_ISLNK`)
- POSIX `.resolve() != lstat()` divergence (covers bind-mounts and hardlinked file systems where
  the path is reachable but the inode sits outside the vault)
- Windows reparse points: junction points, symlinks, and any `FILE_ATTRIBUTE_REPARSE_POINT` set
  on `FindFirstFileW`. `os.path.realpath` and `Path.resolve()` on Windows follow reparse points,
  so we use `os.lstat` and the `stat.S_ISLNK` test first, then re-check on the resolved parent.

This is checked on:

- the **transcript_path** passed into `flush.py` (the OpenCode plugin writes the JSONL outside
  the vault, so we never assume it's inside, only that it's a regular file)
- the existing `daily_dir` passed into `flush.py` (must be a real directory inside the vault)
- every source path `_check_source` validates in `compile.py` (knowledge root, copy sources,
  live destinations, etc.)

### 4. Path-within-vault guard

`_platform.path_within_vault(path, vault_root)` uses the same logic as the existing `check_source`
plus the reparse test:

```python
def path_within_vault(path: Path, vault_root: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
        vault = vault_root.resolve(strict=False)
    except (OSError, ValueError):
        return False
    if _is_link_or_reparse(path):
        return False
    return resolved == vault or vault in resolved.parents
```

The check is dual-purpose: reject symlinks that point out of the vault, and reject any path whose
real location is not under the vault (covers bind-mounts).

### 5. Staging isolation in `compile.py`

Before any model invocation, `_prepare_stage`:

1. `tempfile.mkdtemp(prefix="beyin-compile-stage-")`
2. `chmod(0o700)`
3. Verifies `os.path.commonpath([stage, vault]) != vault` — if the tempdir is under the vault,
   raise `PolicyError("stage-inside-vault")`
4. Copies in the live `knowledge/` tree (using `_check_source` on every source path)
5. Records a `live_baseline` (relative path → SHA-256) of every copied file
6. After the agent exits, builds an `after` manifest, calls `_validate_manifest_diff(before,
   after)`, then `_promote_changes` which:
   - Re-validates every destination with `_validate_live_destination` (re-resolves the parent,
     checks `stat.S_ISDIR` and `S_ISLNK`, verifies the path is still inside the vault)
   - Writes via `shutil.copy2` then `os.replace` on a tempfile
   - Verifies the final file's SHA-256 against the stage snapshot
   - Verifies the file is a regular file (not a symlink) after promotion
7. On any exception, `shutil.rmtree(stage)` runs in a `finally` block

If `_validate_live_destination` rejects a destination, the policy error is recorded and **no
files are promoted** — partial writes are impossible because promotion is per-file in a strict
allow-list order.

### 6. Transcript-path safety in `flush.py`

The OpenCode plugin stores a JSONL transcript at `${STATE_DIR}/transcript-<session>.jsonl`. The
plugin's location for `STATE_DIR` is `${HOME}/.opencode/.state/beyin/` (or
`${VAULT}/.claude/scripts/.state` if explicitly redirected). `flush.py` receives the absolute
path via the hook input. v2.2 validates it with:

```python
if not _platform._is_link_or_reparse(transcript_path) \
   and transcript_path.is_file() \
   and not _platform.path_within_vault(transcript_path, vault_root):
    # OK: external regular file
```

A transcript that **is** inside the vault root is also accepted (matches the Claude/Codex
behavior where the transcript lives at `~/.claude/projects/.../transcript.jsonl`). A transcript
that is a symlink or reparse-point is rejected as `fail:unsafe-transcript-path` without
summarization, preventing a "make the summarizer read /etc/passwd via a symlink" attack.

## Explicit non-goals

These are **out of scope** for v2.2. They are noted so reviewers do not assume coverage:

- **Vault-resident secrets.** The vault must never contain `.env`, `settings.local.json` (now
  gitignored), SSH keys, or credentials. The installer untracks and gitignores these. This is
  enforced at install time, not at script runtime.
- **Sandbox escape via the model CLI itself.** We rely on the CLI's own `--safe-mode` /
  `--sandbox` flags plus the stage-outside-vault isolation. We do not implement our own syscall
  filter.
- **Denial-of-service.** A model could write a 10 GB file. `_validate_manifest_diff` allows it
  (it's a regular file under `knowledge/concepts/`). Disk-fill is mitigated by the user noticing
  at next `claude` open, not by the script.
- **Cross-session content injection via filename.** Daily file names are untrusted (the
  OpenCode plugin can craft any `<ISO ts>`). `flush.py` validates them with
  `DAILY_NAME_PATTERN` and rejects names that try to escape the daily directory
  (`..`, absolute paths, NUL bytes, etc.) before any file open.
- **A compromised harness binary.** If `claude` itself is malicious, the entire trust model
  collapses. We trust the harness.

## Failure modes the script does catch

| Symptom | Result |
| --- | --- |
| Stage inside vault | `PolicyError("stage-inside-vault")`, `fail:policy` |
| Source is symlink | `PolicyError("unsafe-source:<reason>")`, `fail:policy` |
| Live destination is symlink | `PolicyError("unsafe-live-parent:<path>")` |
| Stage file is symlink (escape attempt) | `PolicyError("symlink:<path>")` |
| Stage file deleted | `PolicyError("deletion:<path>")` |
| Stage file type-changed | `PolicyError("type-change:<path>")` |
| Stage file outside allow-list | `PolicyError("forbidden-write:<path>")` |
| Stage file in forbidden directory | `PolicyError("forbidden-directory:<path>")` |
| Live destination SHA-256 mismatch | `fail:stage-error`, no promotion |
| Transcript is a symlink | `fail:unsafe-transcript-path` |
| Provider CLI returns non-zero | `fail:<provider>-exit-<code>` |
| No changes in stage | `fail:no-changes` |
| Daily file hash changed mid-run | `fail:source-changed-after-call` |

## Test coverage

- `tests/scripts_test.py` (POSIX) — 31 tests including stage-outside-vault guard, manifest diff
  type-change, reparse-point rejection, path-within-vault helper.
- `tests/scripts_test_windows.py` — 26 tests, same coverage with `skipUnless` for reparse-point
  features that require Windows.

The Windows test for `test_model_subprocess_encoding_is_locale_independent` exercises
`model_runner.subprocess.run` with `encoding="utf-8", errors="replace"` directly to prove that
non-UTF-8 output from any provider (claude, codex, agy, custom, cursor) does not crash the
script on Windows code pages.

## History

- v1: no security model. Single bash hook, no stage, no manifest diff.
- v2.0 / v2.1: stage outside vault added; manifest diff; allow-list; deletion rejection.
- v2.2: reparse-point detection (POSIX + Windows), transcript-path reparse guard, provider
  abstraction (multi-harness), model_runner subprocess encoding fix.
