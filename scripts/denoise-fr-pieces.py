#!/usr/bin/env python3
"""
Strip OCR-noise lines from FR piece files while preserving real Rolland prose.

A line is "noise" if it has high non-word-character density AND no real French
function words. Real-prose lines have common French words like le, la, et, qui.

Usage:
    python3 scripts/denoise-fr-pieces.py path/to/file.fr.md [more files...]
    python3 scripts/denoise-fr-pieces.py --dry-run path/to/file.fr.md
"""

import sys
import re
import argparse
from pathlib import Path

# Common French function/content words. A line containing any of these (as a
# whole word) is treated as real prose. Diacritics are matched explicitly so we
# don't have to lowercase or normalize.
FRENCH_WORDS = {
    "le", "la", "les", "l", "un", "une", "des", "du", "de",
    "et", "ou", "mais", "donc", "car", "ni", "que", "qui", "quoi",
    "dans", "sur", "sous", "avec", "sans", "pour", "par", "vers", "chez", "entre",
    "il", "elle", "ils", "elles", "on", "nous", "vous", "je", "tu", "moi", "toi", "lui", "leur",
    "son", "sa", "ses", "mon", "ma", "mes", "ton", "ta", "tes", "notre", "votre", "nos", "vos",
    "ce", "cette", "ces", "cet",
    "est", "était", "sont", "étaient", "fut", "furent", "sera", "seront",
    "avait", "avaient", "avait", "ont", "avez", "avons",
    "pas", "ne", "plus", "déjà", "encore", "toujours", "jamais",
    "comme", "quand", "où", "puis", "alors", "ainsi", "aussi", "même", "très", "bien", "tant", "tout", "tous", "toute", "toutes",
    "fait", "faire", "dit", "dire", "voir", "vu",
    "homme", "femme", "enfant", "jour", "nuit", "temps", "année", "vie", "monde", "pays",
    "père", "mère", "fils", "fille", "frère", "sœur",
    "christophe", "olivier", "antoinette", "rolland",
}
# Compile a regex that matches any of these as a whole word (case-insensitive).
WORD_RE = re.compile(
    r"(?i)(?<![a-zàâçéèêëîïôûùüÿñæœ])("
    + "|".join(re.escape(w) for w in FRENCH_WORDS)
    + r")(?![a-zàâçéèêëîïôûùüÿñæœ])"
)

# A "word" for density measurement: 3+ letter run.
LETTER_RUN_RE = re.compile(r"[a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]{3,}")
LETTER_RE = re.compile(r"[a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]")


# A "real word" token: capital-or-lowercase first letter, then 2+ lowercase
# letters. Catches "Le", "Antoinette", "l'aube" fragments; rejects ALL-CAPS
# short fragments like "LE", "AR", "PARIS", or solo capitals.
REAL_WORD_RE = re.compile(
    r"(?<![a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ])"
    r"[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]?[a-zàâçéèêëîïôûùüÿñæœ]{2,}"
    r"(?![a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ])"
)


def is_noise(line: str) -> bool:
    """Return True if the line looks like OCR garbage from a scanned image."""
    stripped = line.strip()
    if not stripped:
        return False  # blank — preserve

    # Preserve markdown structure and page markers verbatim.
    if stripped.startswith(("#", "---", "|", "```", ">")) or stripped.startswith("[leaf"):
        return False
    if re.fullmatch(r"[\d\s.,\-–—]+", stripped):
        return False  # pure digit/price/dash line

    # Real-word tokens: lowercase-bearing tokens of 3+ chars.
    real_words = REAL_WORD_RE.findall(stripped)
    dict_hits = len(WORD_RE.findall(stripped))

    letters = LETTER_RE.findall(stripped)
    if len(letters) == 0:
        return True
    letter_ratio = len(letters) / len(stripped)

    # Clear prose: multiple real words AND a function-word hit AND decent
    # letter density.
    if len(real_words) >= 3 and dict_hits >= 1 and letter_ratio >= 0.55:
        return False
    # Shorter prose lines: e.g. dialogue or one-line paragraphs.
    if len(real_words) >= 2 and dict_hits >= 1 and letter_ratio >= 0.5:
        return False
    # Single real word with a function-word hit on a short line (>=0.6 density):
    # e.g. "Le lendemain." — short prose. Allow.
    if len(real_words) >= 1 and dict_hits >= 1 and letter_ratio >= 0.65 and len(stripped) <= 40:
        return False

    return True


def denoise_text(text: str) -> tuple[str, int, int]:
    """Return (cleaned_text, lines_kept, lines_dropped)."""
    # Preserve frontmatter block verbatim.
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            frontmatter = text[: end + 5]
            body = text[end + 5 :]
        else:
            frontmatter = ""
            body = text
    else:
        frontmatter = ""
        body = text

    kept, dropped = [], 0
    blank_run = 0
    for line in body.splitlines():
        if is_noise(line):
            dropped += 1
            continue
        # collapse runs of blank lines to at most 1
        if not line.strip():
            if blank_run >= 1:
                continue
            blank_run += 1
        else:
            blank_run = 0
        kept.append(line)

    # trim leading/trailing blanks in body
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()

    return frontmatter + "\n".join(kept) + "\n", len(kept), dropped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for fp in args.files:
        path = Path(fp)
        original = path.read_text(encoding="utf-8")
        cleaned, kept, dropped = denoise_text(original)
        before = original.count("\n") + 1
        print(f"{path.name}: {before} → {kept} lines (dropped {dropped} noise)")
        if not args.dry_run:
            path.write_text(cleaned, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
