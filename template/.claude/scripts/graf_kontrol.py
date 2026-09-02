#!/usr/bin/env python3
"""Scan the vault graph for broken wikilinks and orphan notes."""

# Bir not ancak ona giden bir kenar varsa bulunur. Yetim not diskte durur ama
# ajan ona ulasmak icin butun vault'u taramak zorunda kalir: ya token yakar ya
# bulamayip uydurur. Kirik baglanti ise haritada olmayan bir adresi gosterir.
# Ikisi de sessiz arizadir, baska hicbir kontrol yakalamaz.
#
# Celiski taramasi (ayni olay iki notta farkli tarihte, bir notta "canli"
# digerinde "beklemede") bu script'te YOK: o model isidir, koda sigmaz.
#
# Bagimlilik yok, stdlib yeter. Vault kokunden calistir:
#   python3 .claude/scripts/graf_kontrol.py            # ozet
#   python3 .claude/scripts/graf_kontrol.py --tam      # tam liste
#   python3 .claude/scripts/graf_kontrol.py --selftest # kendi kontrolu

from __future__ import annotations

import re
import sys
from pathlib import Path

# --- AYAR ---------------------------------------------------------------------
# Taranmayan klasorler.
ATLA_KLASOR = {".git", ".claude", ".obsidian", "node_modules", "📦 900-Archive"}

# Yetim sayilmayan klasorler: sablonlar (baglanmasi beklenmez), gunluk loglar
# (kronolojik, birbirine link vermez), knowledge/ (derleyici uretir).
YETIM_MUAF_KLASOR = {"📋 Templates", "daily", "knowledge"}

# Yetim sayilmayan dosyalar. Ilk satir giris dosyalari.
# Ikinci satir onemli: bu dosyalara hicbir not link vermez ama session-start
# kancasi iceriklerini her oturumda enjekte eder. Yani ulasilabilirligin iki
# yolu var, link ve kanca; kanca ile ulasilani yetim saymak her turda yanlis
# alarm uretir.
YETIM_MUAF_DOSYA = {
    "README", "CLAUDE", "MEMORY", "SETUP", "Dashboard",
    "Journal", "Kurallar", "Threads", "Last-Session", "Core",
}
# ------------------------------------------------------------------------------

# Hedefi ilk ], |, # veya ^ karakterinde keser: [[yol#baslik|takma-ad]] calisir.
LINK = re.compile(r"\[\[([^\]|#^]+)")
KIRP = 10


def tara(kok: Path):
    """Return (scanned count, broken links, orphan notes) for the vault at kok."""
    dosyalar = [
        p for p in kok.rglob("*.md")
        if not any(a in p.parts for a in ATLA_KLASOR)
    ]
    # Hedef cozumleme: hem dosya adi hem koke gore tam yol (uzantisiz) kabul edilir.
    hedefler = set()
    yol_ile = {}
    ad_ile = {}
    for p in dosyalar:
        yol = str(p.relative_to(kok).with_suffix(""))
        hedefler.add(p.stem)
        hedefler.add(yol)
        yol_ile[yol] = p
        ad_ile.setdefault(p.stem, p)

    kirik = []
    gelen = {p: 0 for p in dosyalar}

    for p in dosyalar:
        try:
            metin = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for ham in LINK.findall(metin):
            # Tablo icindeki [[yol\|takma-ad]] kacisini ve klasor linklerini ayikla.
            hedef = ham.rstrip("\\").strip()
            if not hedef or hedef.endswith("/") or hedef.startswith(("http://", "https://")):
                continue
            if hedef not in hedefler:
                kirik.append((p.relative_to(kok), hedef))
                continue
            varis = yol_ile.get(hedef) or ad_ile.get(hedef)
            if varis is not None and varis != p:
                gelen[varis] += 1

    yetim = [
        p.relative_to(kok) for p, n in gelen.items()
        if n == 0
        and not any(m in p.parts for m in YETIM_MUAF_KLASOR)
        and p.stem not in YETIM_MUAF_DOSYA
    ]
    return len(dosyalar), kirik, sorted(yetim, key=str)


def main() -> None:
    tam = "--tam" in sys.argv
    toplam, kirik, yetim = tara(Path("."))
    print(f"taranan: {toplam} not | kirik baglanti: {len(kirik)} | yetim not: {len(yetim)}")

    if kirik:
        print("\nKIRIK BAGLANTILAR:")
        goster = kirik if tam else kirik[:KIRP]
        for kaynak, hedef in goster:
            print(f"  {kaynak} -> [[{hedef}]]")
        if len(kirik) > len(goster):
            print(f"  ... +{len(kirik) - len(goster)} tane daha (--tam ile hepsi)")

    if yetim:
        print("\nYETIM NOTLAR (hicbir not buraya baglanmiyor):")
        if tam:
            for y in yetim:
                print(f"  {y}")
        else:
            # Duz liste yuzlerce satir olabiliyor; klasor basina sayim okunabilir kalir.
            sayim = {}
            for y in yetim:
                klasor = y.parts[0] if len(y.parts) > 1 else "(kok)"
                sayim[klasor] = sayim.get(klasor, 0) + 1
            for klasor, n in sorted(sayim.items(), key=lambda kv: -kv[1]):
                print(f"  {n:3d}  {klasor}")
            print("  (--tam ile dosya listesi)")


def _selftest() -> None:
    """Minimal check for vaults installed without the repo test suite."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        kok = Path(d)
        (kok / "a.md").write_text("[[b]] ve [[yok-boyle]]", encoding="utf-8")
        (kok / "b.md").write_text("govde", encoding="utf-8")
        (kok / "c.md").write_text("kimse bana baglanmiyor", encoding="utf-8")
        toplam, kirik, yetim = tara(kok)
        assert toplam == 3, toplam
        assert [h for _, h in kirik] == ["yok-boyle"], kirik
        assert [str(y) for y in yetim] == ["a.md", "c.md"], yetim
    print("selftest: gecti")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
