#!/usr/bin/env python3
"""Platform-specific path utilities for security hardening."""

from __future__ import annotations

import os
from pathlib import Path
import stat


def path_within_vault(path: Path, vault_root: Path) -> bool:
    """Check if a path is within the vault root, resolving symlinks."""
    try:
        path.resolve(strict=True).relative_to(vault_root.resolve(strict=True))
    except (ValueError, OSError):
        return False
    return True


def _is_link_or_reparse(path: Path) -> bool:
    """Check if a path is a symlink, junction, or reparse point (Windows)."""
    try:
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            return True
        # Windows reparse points (junctions, symlinks) have FILE_ATTRIBUTE_REPARSE_POINT
        # On Windows, st.st_file_attributes has the attribute flags
        if hasattr(st, 'st_file_attributes'):
            # FILE_ATTRIBUTE_REPARSE_POINT = 0x400
            if st.st_file_attributes & 0x400:
                return True
    except OSError:
        pass
    return False


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