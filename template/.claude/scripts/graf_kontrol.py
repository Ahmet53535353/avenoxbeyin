#!/usr/bin/env python3
"""Scan an Obsidian vault for broken wikilinks and orphan Markdown notes."""

from __future__ import annotations

import posixpath
import re
import sys
from pathlib import Path
import unicodedata
from urllib.parse import unquote


# --- AYAR ---------------------------------------------------------------------
ATLA_KLASOR = {
    ".git",
    ".claude",
    ".obsidian",
    "node_modules",
    "📦 900-Archive",
}
YETIM_MUAF_KLASOR = {"📋 Templates", "daily", "knowledge"}
YETIM_MUAF_YOL = {
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "MEMORY.md",
    "SETUP.md",
    "SETUP-WINDOWS.md",
    "SETUP-ANTIGRAVITY.md",
    "🎯 100-Command-Center/Dashboard.md",
    "🔮 850-Companion/Journal.md",
    "🔮 850-Companion/Kurallar.md",
    "🔮 850-Companion/Threads.md",
    "🔮 850-Companion/Last-Session.md",
    "🔮 850-Companion/Core.md",
}
# ------------------------------------------------------------------------------

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
INLINE_CODE = re.compile(r"`+[^`\n]*`+")
OBSIDIAN_COMMENT = re.compile(r"%%.*?%%", re.DOTALL)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
KIRP = 10


def _anahtar(value: str) -> str:
    value = unquote(value).replace("\\", "/").strip().lstrip("/")
    value = unicodedata.normalize("NFC", value)
    return value.casefold()


def _atlanir(path: Path, kok: Path) -> bool:
    try:
        parts = path.relative_to(kok).parts
    except ValueError:
        return True
    return any(part in ATLA_KLASOR for part in parts)


def _wikilink_metni(text: str) -> str:
    """Remove regions where Obsidian does not create graph edges."""
    text = OBSIDIAN_COMMENT.sub("", text)
    kept: list[str] = []
    fence_character: str | None = None
    for line in text.splitlines():
        match = FENCE.match(line)
        if match:
            character = match.group(1)[0]
            if fence_character is None:
                fence_character = character
            elif character == fence_character:
                fence_character = None
            continue
        if fence_character is None:
            kept.append(INLINE_CODE.sub("", line))
    return "\n".join(kept)


def _hedef(raw: str) -> str:
    # Markdown tables escape the alias separator as \|. In both forms the
    # portion after the first pipe is display text, not the target.
    target = raw.split("|", 1)[0].rstrip("\\").strip()
    target = re.split(r"[#^]", target, maxsplit=1)[0].strip()
    return unquote(target)


def _dosyalari_bul(kok: Path) -> tuple[list[Path], list[Path]]:
    all_files: list[Path] = []
    notes: list[Path] = []
    for path in kok.rglob("*"):
        if _atlanir(path, kok):
            continue
        try:
            is_file = path.is_file()
        except OSError:
            continue
        if not is_file:
            continue
        all_files.append(path)
        if path.suffix.casefold() == ".md":
            notes.append(path)
    return all_files, notes


def _hedef_haritasi(
    kok: Path,
    all_files: list[Path],
) -> tuple[dict[str, set[Path]], dict[str, set[Path]]]:
    by_path: dict[str, set[Path]] = {}
    by_name: dict[str, set[Path]] = {}

    def add(mapping: dict[str, set[Path]], key: str, path: Path) -> None:
        mapping.setdefault(_anahtar(key), set()).add(path)

    for path in all_files:
        relative = path.relative_to(kok)
        for start in range(len(relative.parts)):
            add(by_path, Path(*relative.parts[start:]).as_posix(), path)
        add(by_name, path.name, path)
        if path.suffix.casefold() == ".md":
            without_suffix = relative.with_suffix("")
            for start in range(len(without_suffix.parts)):
                add(
                    by_path,
                    Path(*without_suffix.parts[start:]).as_posix(),
                    path,
                )
            add(by_name, path.stem, path)
    return by_path, by_name


def _cozumle(
    kok: Path,
    kaynak: Path,
    target: str,
    by_path: dict[str, set[Path]],
    by_name: dict[str, set[Path]],
) -> set[Path]:
    key = _anahtar(target)
    candidates = set(by_path.get(key, set()))
    if not candidates and ("/" in target or target.startswith(".")):
        source_parent = kaynak.relative_to(kok).parent.as_posix()
        relative_key = _anahtar(posixpath.normpath(f"{source_parent}/{target}"))
        candidates.update(by_path.get(relative_key, set()))
    if not candidates and "/" not in target:
        candidates.update(by_name.get(key, set()))
    return candidates


def tara(kok: Path):
    """Return (scanned Markdown count, broken links, orphan notes)."""
    kok = kok.resolve()
    all_files, notes = _dosyalari_bul(kok)
    by_path, by_name = _hedef_haritasi(kok, all_files)
    note_set = set(notes)
    gelen = {path: 0 for path in notes}
    kirik: list[tuple[Path, str]] = []

    for path in notes:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for raw in WIKILINK.findall(_wikilink_metni(text)):
            target = _hedef(raw)
            if (
                not target
                or target.endswith("/")
                or target.startswith(("http://", "https://"))
            ):
                continue
            candidates = _cozumle(kok, path, target, by_path, by_name)
            if not candidates:
                kirik.append((path.relative_to(kok), target))
                continue
            # A basename may map to more than one note. Obsidian resolves that
            # by source proximity. Counting every candidate is conservative:
            # the advisory orphan report must not invent a false broken chain.
            for destination in candidates & note_set:
                if destination != path:
                    gelen[destination] += 1

    yetim = [
        path.relative_to(kok)
        for path, incoming in gelen.items()
        if incoming == 0
        and not any(
            part in YETIM_MUAF_KLASOR
            for part in path.relative_to(kok).parts
        )
        and path.relative_to(kok).as_posix() not in YETIM_MUAF_YOL
    ]
    return len(notes), kirik, sorted(
        yetim, key=lambda item: str(item).casefold()
    )


def main() -> None:
    full = "--tam" in sys.argv
    total, broken, orphans = tara(Path("."))
    print(
        f"taranan: {total} not | kirik baglanti: {len(broken)} | "
        f"yetim not: {len(orphans)}"
    )

    if broken:
        print("\nKIRIK BAGLANTILAR:")
        shown = broken if full else broken[:KIRP]
        for source, target in shown:
            print(f"  {source} -> [[{target}]]")
        if len(broken) > len(shown):
            print(
                f"  ... +{len(broken) - len(shown)} tane daha "
                "(--tam ile hepsi)"
            )

    if orphans:
        print("\nYETIM NOTLAR (hicbir not buraya baglanmiyor):")
        if full:
            for orphan in orphans:
                print(f"  {orphan}")
        else:
            counts: dict[str, int] = {}
            for orphan in orphans:
                directory = (
                    orphan.parts[0] if len(orphan.parts) > 1 else "(kok)"
                )
                counts[directory] = counts.get(directory, 0) + 1
            for directory, count in sorted(
                counts.items(), key=lambda item: (-item[1], item[0].casefold())
            ):
                print(f"  {count:3d}  {directory}")
            print("  (--tam ile dosya listesi)")


def _selftest() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "a.md").write_text(
            "[[b]] ve [[yok-boyle]] ve `[[kod-ornegi]]`",
            encoding="utf-8",
        )
        (root / "b.md").write_text("govde", encoding="utf-8")
        (root / "c.md").write_text(
            "kimse bana baglanmiyor", encoding="utf-8"
        )
        total, broken, orphans = tara(root)
        assert total == 3, total
        assert [target for _, target in broken] == ["yok-boyle"], broken
        assert [str(orphan) for orphan in orphans] == [
            "a.md",
            "c.md",
        ], orphans
    print("selftest: gecti")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
