#!/usr/bin/env python3
"""
For every cahier listed in ~/charlespeguy.org/src/data/cahiers/*.json,
enumerate every candidate clean-FR source available across .com + .org
and emit a CSV with quality metrics.

Quality columns:
  lines       — total non-empty lines
  hyph_end    — count of lines ending in `<lowercase>+-` (soft-hyphen breaks)
  pgnum_end   — count of lines ending in `<lowercase>+<digits>` (mid-word page sigs)
  weird       — char-level OCR substitutions (letter + quote/backslash + alphanum)
  qmark       — count of `[?]` flags (vision-OCR uncertainty marker)

Source-type tags:
  org-piece           current .org per-piece FR (.fr.md, after round 12)
  com-cahier          .com src/content/texts/<slug>.md (post-migration noisy)
  gemini-clean        .com public/exports/gemini-clean/<slug>.md (hand-edited)
  gemini-raw          .com raw/cleaned/<slug>.txt (early Gemini)
  vision-ocr          .com raw/<slug>-ocr.txt (Claude vision)
  slug-fallback       .com raw/<slug>-<title-slug>.txt (archive.org text-layer)
  vision-fragment     .com raw/<slug>-ocr-{a,b,c,...}.txt or vision-repair-*.txt

Run:
  python3 scripts/source-inventory.py > audit-screens/source-inventory.csv
"""

from __future__ import annotations
import csv
import json
import re
import sys
from pathlib import Path
from glob import glob

ORG = Path("/Users/wilsonpruitt/charlespeguy.org")
COM = Path("/Users/wilsonpruitt/charlespeguy.com")

HYPH_END = re.compile(r"[a-zàâçéèêëîïôûùüÿñæœ]+-\s*$", re.MULTILINE)
PGNUM_END = re.compile(r"[a-zàâçéèêëîïôûùüÿñæœ]+\d{1,4}\s*$", re.MULTILINE)
WEIRD = re.compile(r"\b[a-zàâçéèêëîïôûùüÿñæœ]+['\"\\][a-zA-Z0-9]")
QMARK = re.compile(r"\[\?\]")


def stat_file(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"lines": 0, "hyph_end": 0, "pgnum_end": 0, "weird": 0, "qmark": 0, "bytes": 0}
    lines = sum(1 for ln in text.splitlines() if ln.strip())
    return {
        "lines": lines,
        "hyph_end": len(HYPH_END.findall(text)),
        "pgnum_end": len(PGNUM_END.findall(text)),
        "weird": len(WEIRD.findall(text)),
        "qmark": len(QMARK.findall(text)),
        "bytes": path.stat().st_size,
    }


def collect_for_cahier(slug: str) -> list[dict]:
    """Return list of candidate-source dicts for the given cahier."""
    out = []

    # 1. Current .org piece files (one row per piece, FR only)
    for fr in sorted(ORG.glob(f"src/content/pieces/{slug}--*.fr.md")):
        s = stat_file(fr)
        out.append({"cahier": slug, "type": "org-piece",
                    "path": str(fr.relative_to(Path.home())), **s})

    # 2. .com cahier-level texts
    com_cahier = COM / "src/content/texts" / f"{slug}.md"
    if com_cahier.exists():
        out.append({"cahier": slug, "type": "com-cahier",
                    "path": str(com_cahier.relative_to(Path.home())), **stat_file(com_cahier)})

    # 3. Gemini hand-edited (exports/gemini-clean)
    for d in ("public/exports/gemini-clean", "site/exports/gemini-clean"):
        p = COM / d / f"{slug}.md"
        if p.exists():
            out.append({"cahier": slug, "type": "gemini-clean",
                        "path": str(p.relative_to(Path.home())), **stat_file(p)})

    # 4. Gemini raw (raw/cleaned)
    p = COM / "raw/cleaned" / f"{slug}.txt"
    if p.exists():
        out.append({"cahier": slug, "type": "gemini-raw",
                    "path": str(p.relative_to(Path.home())), **stat_file(p)})
    p = COM / "raw/gemini-clean" / f"{slug}.txt"
    if p.exists():
        out.append({"cahier": slug, "type": "gemini-raw",
                    "path": str(p.relative_to(Path.home())), **stat_file(p)})

    # 5. Vision OCR primary
    p = COM / "raw" / f"{slug}-ocr.txt"
    if p.exists():
        out.append({"cahier": slug, "type": "vision-ocr",
                    "path": str(p.relative_to(Path.home())), **stat_file(p)})

    # 6. Vision OCR fragments / repair
    for p in sorted(COM.glob(f"raw/{slug}-ocr-*.txt")):
        if p.name.endswith(".bak") or "leaf-manifest" in p.name:
            continue
        out.append({"cahier": slug, "type": "vision-fragment",
                    "path": str(p.relative_to(Path.home())), **stat_file(p)})
    for p in sorted(COM.glob(f"raw/{slug}-vision-repair-*.txt")):
        out.append({"cahier": slug, "type": "vision-fragment",
                    "path": str(p.relative_to(Path.home())), **stat_file(p)})

    # 7. Slug-named fallback (archive.org text-layer): raw/<slug>-<title-slug>.txt
    #    — exclude already-captured *-ocr*.txt, manifests, backups, halves, etc.
    skip_suffix_re = re.compile(
        r"-(ocr|leaf-manifest|vision-repair|half\d|translation|manual|completion|"
        r"partial|extension|tail|bak|fill|summary|hathi|extra)"
    )
    for p in sorted(COM.glob(f"raw/{slug}-*.txt")):
        name_no_ext = p.stem
        # If the suffix after slug matches skip patterns, exclude.
        if skip_suffix_re.search(name_no_ext):
            continue
        if name_no_ext == slug:
            # Just `<slug>.txt` would be unusual — keep as fallback.
            pass
        out.append({"cahier": slug, "type": "slug-fallback",
                    "path": str(p.relative_to(Path.home())), **stat_file(p)})

    return out


def main():
    cahier_jsons = sorted((ORG / "src/data/cahiers").glob("*.json"))
    rows = []
    for cj in cahier_jsons:
        slug = cj.stem
        rows.extend(collect_for_cahier(slug))
    fieldnames = ["cahier", "type", "lines", "hyph_end", "pgnum_end",
                  "weird", "qmark", "bytes", "path"]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)


if __name__ == "__main__":
    main()
