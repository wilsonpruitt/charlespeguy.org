#!/usr/bin/env python3
"""
Re-import genuinely-clean FR sources from ~/charlespeguy.com/raw/cleaned/ into
charlespeguy.org's per-piece .fr.md files.

These cleaned cahier-level .txt files are the Gemini-OCR output (paragraph-
reflowed, soft-hyphens healed) that the .com → .org migration never picked
up. They exist for only 13 cahiers: s01-c01..s01-c12 plus s02-c11.

Algorithm per cahier:
  1. Read cahier JSON at src/data/cahiers/<slug>.json -> ordered pieces list.
  2. Read .com/src/content/texts/<slug>.md (which has the canonical 4-piece
     structure matching .org). For each piece, extract a stable opening-prose
     anchor (~80 chars from the piece body, normalized for matching).
  3. Read .com/raw/cleaned/<slug>.txt — same text, fully clean. Find each
     piece's anchor in cleaned.txt and use that offset as the boundary.
  4. Slice cleaned.txt by anchors -> per-piece body.
  5. Write each src/content/pieces/<slug>--<piece>.fr.md with original
     frontmatter + new body. Update wordCount.

Notes:
- Gemini's cleaned.txt has its own `##` sub-section structure that's MORE
  granular than the canonical pieces (e.g. cleaned s01-c01.txt has 11 `##`
  but the cahier has 4 pieces — the last 8 are subsections of L'Affaire
  Liebknecht). We ignore those headings entirely and use the .com texts
  file's boundaries.

Usage:
  python3 scripts/reimport-cleaned-fr.py --dry-run s01-c01
  python3 scripts/reimport-cleaned-fr.py s01-c01
  python3 scripts/reimport-cleaned-fr.py --all
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

ORG_ROOT = Path("/Users/wilsonpruitt/charlespeguy.org")
COM_ROOT = Path("/Users/wilsonpruitt/charlespeguy.com")
CLEANED_DIR = COM_ROOT / "raw" / "cleaned"
COM_TEXTS_DIR = COM_ROOT / "src" / "content" / "texts"
CAHIERS_DIR = ORG_ROOT / "src" / "data" / "cahiers"
PIECES_DIR = ORG_ROOT / "src" / "content" / "pieces"

HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
ANCHOR_LEN = 120  # chars of opening prose to use as a per-piece anchor


def normalize(s: str) -> str:
    """Lowercase, strip diacritics, drop punctuation, collapse spaces."""
    nfkd = unicodedata.normalize("NFKD", s)
    no_diacritics = "".join(c for c in nfkd if not unicodedata.combining(c))
    low = no_diacritics.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", low)
    return re.sub(r"\s+", " ", cleaned).strip()


def tokens(s: str) -> set[str]:
    """Significant tokens for matching — drop stopwords + 1-2 char words."""
    STOP = {"le", "la", "les", "de", "du", "des", "un", "une", "et", "ou",
            "a", "au", "aux", "en", "dans", "sur", "par", "pour", "à"}
    return {t for t in normalize(s).split() if len(t) >= 3 and t not in STOP}


def normalize_for_search(s: str) -> str:
    """Aggressive normalization for fuzzy substring search:
    strip diacritics, lowercase, drop punctuation, collapse whitespace.
    Used to match noisy .com-texts anchors against clean .com-cleaned text.
    """
    nfkd = unicodedata.normalize("NFKD", s)
    no_diacritics = "".join(c for c in nfkd if not unicodedata.combining(c))
    low = no_diacritics.lower()
    return re.sub(r"\W+", " ", low).strip()


def extract_piece_anchors(com_text: str, cahier: dict) -> list[Optional[str]]:
    """For each cahier piece (in order), extract an opening-prose anchor
    string from the .com texts/<slug>.md file. Returns parallel list with
    None for any piece whose body couldn't be located.

    The .com texts file uses `## <piece title>` headers (with French title
    case), optionally followed by `*Author Name*` and prose.
    """
    pieces = cahier.get("pieces", [])
    # Find the byte offset of each piece's body opening in the .com text.
    anchors: list[Optional[str]] = []
    # Find all headings + content.
    h_iter = list(HEADING_RE.finditer(com_text))
    for p in pieces:
        title_norm = normalize_for_search(p["titleFr"])
        # Find the heading whose normalized form best matches this piece title.
        best = None
        for m in h_iter:
            h_norm = normalize_for_search(m.group(1))
            if title_norm == h_norm or title_norm in h_norm or h_norm in title_norm:
                best = m
                break
        if best is None:
            # Fallback: substring on token overlap.
            tt = tokens(p["titleFr"])
            for m in h_iter:
                ht = tokens(m.group(1))
                if tt and (tt & ht) and len(tt & ht) >= max(1, len(tt) // 2):
                    best = m
                    break
        if best is None:
            anchors.append(None)
            continue
        # Walk forward past the heading and any *italic author* lines to find
        # the first substantive prose line.
        cur = best.end()
        body_start = None
        for line in com_text[cur:].splitlines(keepends=True):
            stripped = line.strip()
            if not stripped:
                cur += len(line)
                continue
            # Skip italicised author byline.
            if stripped.startswith("*") and stripped.endswith("*"):
                cur += len(line)
                continue
            body_start = cur
            break
        if body_start is None:
            anchors.append(None)
            continue
        # Build the anchor — first ANCHOR_LEN chars after body_start.
        raw_anchor = com_text[body_start : body_start + ANCHOR_LEN]
        anchors.append(raw_anchor)
    return anchors


def split_frontmatter(md: str) -> tuple[str, str]:
    """Return (frontmatter_with_delimiters, body)."""
    if not md.startswith("---\n"):
        return "", md
    end = md.find("\n---\n", 4)
    if end == -1:
        return "", md
    return md[: end + 5], md[end + 5 :]


def update_frontmatter_wordcount(fm: str, new_count: int) -> str:
    """Replace the wordCount line in frontmatter with the new count."""
    if "wordCount:" in fm:
        return re.sub(r"wordCount:\s*\d+", f"wordCount: {new_count}", fm)
    # Insert before closing --- if missing.
    return fm.rstrip().rstrip("---").rstrip() + f"\nwordCount: {new_count}\n---\n"


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def find_anchor_in_cleaned(anchor: str, cleaned_text: str,
                            cleaned_norm: str, char_index: list[int]) -> Optional[int]:
    """Find an anchor (raw .com text) in cleaned.txt. Uses normalized search
    to bridge OCR-noise differences, then maps back to a real char offset.

    Strategy: slide a 40-char probe window through the anchor (every 20 chars).
    The first window that matches in cleaned.txt wins. Returns the offset in
    cleaned_text that corresponds to the *start* of the matched window minus
    the window's offset inside the anchor — i.e. an estimate of where the
    piece's body opens in cleaned.txt.

    This handles cases where cleaned.txt omits some metadata (datelines,
    page sigs) that's present in the .com noisy anchor — at least one
    later window from the anchor should still match.
    """
    a_norm = normalize_for_search(anchor)
    if len(a_norm) < 40:
        i = cleaned_norm.find(a_norm)
        return char_index[i] if i >= 0 else None
    window = 40
    step = 20
    for start in range(0, len(a_norm) - window + 1, step):
        probe = a_norm[start : start + window]
        i = cleaned_norm.find(probe)
        if i >= 0:
            # Estimate body start: the match begins `start` chars into the
            # anchor's normalized form. Back off by an equivalent amount in
            # cleaned_text — but no more than 50 chars (safety).
            back_off = min(start, 50)
            cleaned_offset = char_index[i]
            return max(0, cleaned_offset - back_off)
    return None


def _build_normalized_index(text: str) -> tuple[str, list[int]]:
    """Return (normalized_text, char_index) where char_index[i] is the offset
    in `text` corresponding to position i in normalized_text."""
    out_chars: list[str] = []
    out_index: list[int] = []
    prev_space = True
    for i, ch in enumerate(text):
        nfkd = unicodedata.normalize("NFKD", ch)
        for c in nfkd:
            if unicodedata.combining(c):
                continue
            c = c.lower()
            if not re.match(r"\w", c):
                if prev_space:
                    continue
                out_chars.append(" ")
                out_index.append(i)
                prev_space = True
            else:
                out_chars.append(c)
                out_index.append(i)
                prev_space = False
    return "".join(out_chars).strip(), out_index


def process_cahier(slug: str, dry_run: bool = False) -> tuple[int, list[str]]:
    """Re-import one cahier. Returns (pieces_written, warnings)."""
    cleaned_path = CLEANED_DIR / f"{slug}.txt"
    cahier_path = CAHIERS_DIR / f"{slug}.json"
    com_text_path = COM_TEXTS_DIR / f"{slug}.md"
    warnings: list[str] = []

    if not cleaned_path.exists():
        return 0, [f"{slug}: no cleaned source at {cleaned_path}"]
    if not cahier_path.exists():
        return 0, [f"{slug}: no cahier JSON at {cahier_path}"]
    if not com_text_path.exists():
        return 0, [f"{slug}: no .com texts file at {com_text_path}"]

    cleaned_text = cleaned_path.read_text(encoding="utf-8")
    com_text = com_text_path.read_text(encoding="utf-8")
    cahier = json.loads(cahier_path.read_text(encoding="utf-8"))
    pieces = cahier.get("pieces", [])

    # Build per-piece anchors from .com/src/content/texts/<slug>.md.
    anchors = extract_piece_anchors(com_text, cahier)

    # Build normalized index of cleaned text for fuzzy substring search.
    cleaned_norm, char_index = _build_normalized_index(cleaned_text)

    # Find each anchor in cleaned.txt.
    offsets: list[Optional[int]] = []
    for p, anc in zip(pieces, anchors):
        if anc is None:
            offsets.append(None)
            warnings.append(f"{slug}/{p['slug']}: anchor missing in .com texts")
            continue
        off = find_anchor_in_cleaned(anc, cleaned_text, cleaned_norm, char_index)
        offsets.append(off)
        if off is None:
            warnings.append(f"{slug}/{p['slug']}: anchor not found in cleaned text")

    # Sanity: offsets should be in ascending order.
    nonnull = [o for o in offsets if o is not None]
    if nonnull != sorted(nonnull):
        warnings.append(f"{slug}: offsets out of order: {offsets} — abort")
        return 0, warnings

    pieces_written = 0
    for idx, p in enumerate(pieces):
        off = offsets[idx]
        if off is None:
            continue
        # End = next non-None offset, or EOF.
        end = len(cleaned_text)
        for j in range(idx + 1, len(offsets)):
            if offsets[j] is not None:
                end = offsets[j]
                break
        body = cleaned_text[off:end]

        # Strip any leading `## HEADING` lines that cleaned.txt inserted —
        # we don't want Gemini's sub-section structure rendered as H2s.
        # (We keep `###` and deeper just in case.)
        body = re.sub(r"^##\s+.+?\n+", "", body, count=0, flags=re.MULTILINE)
        # Cleaned bodies are paragraph-reflowed already; strip leading/trailing.
        body = body.strip() + "\n"

        # Read existing .fr.md to preserve frontmatter.
        fr_path = PIECES_DIR / f"{slug}--{p['slug']}.fr.md"
        if not fr_path.exists():
            warnings.append(f"{slug}/{p['slug']}: no existing .fr.md to update")
            continue
        existing = fr_path.read_text(encoding="utf-8")
        fm, _old_body = split_frontmatter(existing)
        if not fm:
            warnings.append(f"{slug}/{p['slug']}: no frontmatter in existing file")
            continue
        new_fm = update_frontmatter_wordcount(fm, count_words(body))
        new_content = new_fm + body

        if dry_run:
            old_lines = _old_body.count("\n")
            new_lines = body.count("\n")
            print(f"  {fr_path.name}: {old_lines} → {new_lines} lines "
                  f"(wordCount {count_words(_old_body)} → {count_words(body)})")
        else:
            fr_path.write_text(new_content, encoding="utf-8")
        pieces_written += 1

    return pieces_written, warnings


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*",
                    help="Cahier slugs to re-import (e.g. s01-c01)")
    ap.add_argument("--all", action="store_true",
                    help="Process every cahier that has a cleaned source")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing")
    args = ap.parse_args(argv)

    if args.all:
        slugs = sorted(p.stem for p in CLEANED_DIR.glob("*.txt"))
    elif args.slugs:
        slugs = args.slugs
    else:
        ap.error("provide one or more slugs, or --all")

    total_written, all_warnings = 0, []
    for slug in slugs:
        print(f"\n=== {slug} {'(dry-run)' if args.dry_run else ''} ===")
        written, warns = process_cahier(slug, dry_run=args.dry_run)
        total_written += written
        all_warnings.extend(warns)
        if not args.dry_run:
            print(f"  {written} piece(s) rewritten")

    if all_warnings:
        print("\n--- WARNINGS ---")
        for w in all_warnings:
            print(f"  {w}")
    print(f"\nTOTAL pieces rewritten: {total_written}")
    return 0 if not all_warnings else 0  # warnings don't fail


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
