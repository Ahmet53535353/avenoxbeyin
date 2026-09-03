#!/usr/bin/env python3
"""Platform-specific path utilities for security hardening."""

from __future__ import annotations

import os
from pathlib import Path
import stat


_WIN_REPARSE = 0x0400


def _is_link_or_reparse(path: Path) -> bool:
    """Check if a path is a symlink, junction, or reparse point (Windows)."""
    try:
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            return True
        # Windows reparse points (junctions, symlinks) have FILE_ATTRIBUTE_REPARSE_POINT
        if hasattr(st, "st_file_attributes"):
            if st.st_file_attributes & _WIN_REPARSE:
                return True
    except OSError:
        pass
    return False


def _has_unsafe_component(path: Path, vault_root: Path) -> bool:
    """Check if any component of the path is a link/reparse point."""
    try:
        relative = path.absolute().relative_to(vault_root.absolute())
    except ValueError:
        return False
    current = vault_root.absolute()
    if _is_link_or_reparse(current):
        return True
    for part in relative.parts:
        current /= part
        if _is_link_or_reparse(current):
            return True
    return False


def path_within_vault(path: Path, vault_root: Path) -> bool:
    """Return true only for a contained path reached without links/reparse points."""
    candidate = Path(path)
    root = Path(vault_root)
    if _has_unsafe_component(candidate, root):
        return False
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def check_source(path: Path, vault_root: Path, directory: bool) -> None:
    """Validate that a source path is a regular file/dir within vault, not a link or reparse point."""
    if _is_link_or_reparse(path):
        raise ValueError(f"source-reparse-point:{path.relative_to(vault_root)}")
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    st = path.lstat()
    if not expected(st.st_mode):
        raise ValueError(f"source-type:{path.relative_to(vault_root)}")
    resolved = path.resolve(strict=True)
    if not path_within_vault(path, vault_root):
        raise ValueError(f"source-escape:{path.name}")


def create_exclusive_claim(path: Path, mode: int = 0o600) -> bool:
    """Create a claim file once without overwriting an existing claimant."""
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    except FileExistsError:
        return False
    except PermissionError:
        if os.name == "nt" and path.exists():
            return False
        raise
    os.close(descriptor)
    return True