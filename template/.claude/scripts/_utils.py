#!/usr/bin/env python3
"""Shared utilities for the beyin memory runtime."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def session_key(session_id: str) -> str:
    """Generate a deterministic session key from session_id."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def path_within_vault(path: Path, vault_root: Path) -> bool:
    """Check if a path is within the vault root, resolving symlinks."""
    try:
        path.resolve(strict=True).relative_to(vault_root.resolve(strict=True))
    except (ValueError, OSError):
        return False
    return True


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_write(path: Path, value: str, mode: int = 0o600) -> None:
    """Atomically write a string to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.chmod(temporary, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def read_integer(path: Path) -> int:
    """Read an integer from a file, returning 0 on failure."""
    try:
        value = path.read_text(encoding="utf-8").splitlines()[0]
        return int(value) if value.isdigit() else 0
    except (OSError, IndexError, UnicodeError):
        return 0


def read_lines(path: Path, limit: int | None = None) -> list[str]:
    """Read lines from a file, optionally limited."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []
    return lines if limit is None else lines[:limit]


def sha256(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()