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
# Match French function words as written (case-sensitive). Case-insensitive
# matching turned OCR-caps fragments like "UN" and "L" into false dict hits,
# rescuing noise lines. Real French prose contains these words lowercase.
WORD_RE = re.compile(
    r"(?<![a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ])("
    + "|".join(re.escape(w) for w in FRENCH_WORDS)
    + r")(?![a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ])"
)

# A "word" for density measurement: 3+ letter run.
LETTER_RUN_RE = re.compile(r"[a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]{3,}")
LETTER_RE = re.compile(r"[a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]")


# A "real word" token: optional leading capital, then 3+ lowercase letters.
# Catches "les", "Antoinette", "aube" fragments; rejects OCR junk like
# "ir", "ln", "fi", "np", "Ch" that only have 1-2 lowercase letters.
REAL_WORD_RE = re.compile(
    r"(?<![a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ])"
    r"[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]?[a-zàâçéèêëîïôûùüÿñæœ]{3,}"
    r"(?![a-zA-ZàâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ])"
)


def is_noise(line: str) -> bool:
    """Return True if the line looks like OCR garbage from a scanned image."""
    stripped = line.strip()
    if not stripped:
        return False  # blank — preserve

    # Preserve markdown structure verbatim (only block markers that aren't
    # easily faked by OCR garbage). `#` and `>` are too easily produced by
    # OCR junk so we let them fall through to the prose check.
    if stripped.startswith(("---", "```")):
        return False
    # Don't treat `|` lines as tables — this corpus has no real markdown tables
    # in body content, and OCR margin noise produces lots of `|`. Strip leading
    # pipe(s) and fall through to the prose check.
    while stripped.startswith("|"):
        stripped = stripped[1:].strip()
    if not stripped:
        return True
    # Strip OCR splice markers — they belong in the raw OCR, not rendered output.
    if stripped.startswith(("[leaf", "[COLOPHON", "[BACK-MATTER", "[GUIEYSSE", "[p.")):
        return True
    # Pure digits 1-4 chars (e.g. "145", "7", "1110008" handled by length) =
    # margin page numbers. Drop. Longer digit-only strings could be years,
    # statistics — keep them.
    if re.fullmatch(r"\d{1,4}", stripped):
        return True
    if re.fullmatch(r"[\d\s.,\-–—]+", stripped):
        return False  # pure digit/price/dash line

    # Real-word tokens: lowercase-bearing tokens of 3+ chars.
    real_words = REAL_WORD_RE.findall(stripped)
    dict_hits = len(WORD_RE.findall(stripped))

    letters = LETTER_RE.findall(stripped)
    if len(letters) == 0:
        return True
    letter_ratio = len(letters) / len(stripped)

    # Reject lines dominated by junk fragments — many tokens but few are real
    # words. Catches OCR garbage like "on D RE FRE) NRC Ter SOA aus SR mnt"
    # where common 2-char function words (on, et, ne) score dict hits despite
    # the line being clearly noise.
    tokens = [t for t in stripped.split() if any(c.isalpha() for c in t)]
    if len(tokens) >= 5 and len(real_words) / len(tokens) < 0.4:
        return True

    # Clear prose: multiple real words AND a function-word hit AND decent
    # letter density.
    if len(real_words) >= 3 and dict_hits >= 1 and letter_ratio >= 0.55:
        return False
    # Proper-noun-heavy lines (datelines, lists of names): 3+ real words AND
    # at least one substantial word (5+ chars) AND decent density. Catches
    # "Tien-Tsin, 25 février 1901" type lines that lack function words.
    if len(real_words) >= 3 and any(len(w) >= 5 for w in real_words) and letter_ratio >= 0.55:
        return False
    # Shorter prose lines: e.g. dialogue or one-line paragraphs.
    if len(real_words) >= 2 and dict_hits >= 1 and letter_ratio >= 0.5:
        return False
    # Single real word with a function-word hit on a short line (>=0.6 density):
    # e.g. "Le lendemain." — short prose. Allow only if the real word is 4+
    # chars (to reject lines like "ANR SRE CUS À Me ne nie OU AC MS" where
    # "nie" + "ne" technically satisfy the looser rules).
    if (len(real_words) >= 1 and dict_hits >= 1 and letter_ratio >= 0.65
            and len(stripped) <= 40
            and any(len(w) >= 4 for w in real_words)):
        return False

    return True


# Strip trailing OCR margin artifacts from a line: standalone 1-3 char
# token after sentence-ending punctuation or whitespace. Catches page-sig
# marks like " 4", " k", " 1e", " * 1", " — 1.", " ; 2" embedded in prose.
# Repeats until the tail stabilizes — handles multi-token cruft like " . 4".
TRAILING_NOISE_RE = re.compile(
    r"\s+[*\-–—|:;,.]?\s*[A-Za-z0-9]{1,3}[.,;:!?]?\s*$"
)


def strip_leading_marginalia(line: str) -> str:
    """Strip leading pure-digit margin artifacts like '7 On apporte...'.

    Only acts on pure-digit heads followed by space + capital letter. Leaves
    alpha heads alone (too easy to clobber "Je", "Il", "On", "À", "Y", etc.).
    """
    m = re.match(r"^(\d{1,3})\s+([A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ])", line)
    if m:
        return line[m.start(2):]
    return line


_SAFE_2CHAR = {
    "le", "la", "de", "du", "et", "ou", "ce", "se", "me", "te", "ne", "ni",
    "on", "en", "au", "si", "il", "je", "tu", "ma", "ta", "sa", "où",
    "oh", "ah", "eh", "ai", "as", "es", "an", "un", "à", "y", "ne",
}
_SAFE_1CHAR_ALPHA = {"a", "à", "y", "o", "ô", "é", "è", "ê", "ï", "ù"}


def strip_inline_junk(line: str) -> str:
    """Strip whitespace-bounded OCR-junk tokens from within a line. Targets
    short tokens that paragraph reading misses but rendered typography exposes —
    " 5e ", " '42 ", " x ", " RU ", " dl ", " I] " — while preserving real
    French prose, page numbers ("52 pages"), addresses ("8 rue"), dates
    ("10 mars 1903"), and proper-noun initials ("M. Dupont").
    """
    # Strip leading `#` and `>` (OCR margin marks misread as markdown blocks).
    line = re.sub(r"^[#>]+\s*", "", line)
    parts = re.split(r"(\s+)", line)
    out = []
    for part in parts:
        if part == "" or part.isspace():
            out.append(part)
            continue
        has_digit = any(c.isdigit() for c in part)
        has_alpha = any(c.isalpha() for c in part)
        # Mixed alphanumeric short token — almost always OCR debris.
        # (Pure digits like "52" or "1903" lack alpha and survive.)
        if has_digit and has_alpha and len(part) <= 5:
            continue
        # Apostrophe-prefixed short digit tokens like " '42 ", " '03 " —
        # OCR artifacts from page corner / running header digits with
        # adjacent quotation marks.
        if re.fullmatch(r"['‘’`]\d{1,4}[.,;:'‘’`]?", part):
            continue
        # Mixed letter-and-symbol 2-char tokens like "\J", "I]" — but NOT
        # "M." or other initials (handled by the period-keeps-it rule below).
        if (len(part) == 2 and has_alpha and not part.isalpha()
                and not part.isalnum() and "." not in part):
            continue
        # Tokens containing a period (likely abbreviation/initial) are kept.
        if "." in part:
            out.append(part)
            continue
        # Pure punctuation/symbol residue surrounded by spaces.
        if not has_alpha and not has_digit:
            # Keep common punctuation that legitimately appears mid-line.
            if part in {",", ";", ":", "!", "?", "—", "–", "-", "...", "…", "«", "»", "(", ")"}:
                out.append(part)
            # Drop bare `|`, `_`, `<`, `>`, `%`, `&`, `+`, `*` and similar.
            continue
        # Single alpha — drop unless it's a safe one-letter word.
        if len(part) == 1 and part.isalpha() and part.lower() not in _SAFE_1CHAR_ALPHA:
            continue
        # 2-char pure-alpha — drop unless safe French short word.
        if len(part) == 2 and part.isalpha() and part.lower() not in _SAFE_2CHAR:
            continue
        out.append(part)
    cleaned = "".join(out)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    return cleaned.strip()


def strip_trailing_marginalia(line: str) -> str:
    """Strip trailing OCR margin junk: digits, digit-containing fragments, or
    single letters preceded by whitespace/punctuation.

    Avoids stripping real French short words by requiring the tail to either
    contain a digit or be exactly one alpha character (excluding 'à', 'y').
    """
    stripped = line.rstrip()
    if not stripped:
        return line
    for _ in range(4):
        m = re.search(
            r"(\s+[*\-–—|:;,.]?\s*)([A-Za-z0-9àâçéèêëîïôûùüÿñæœÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]{1,3})([.,;:!?]?)\s*$",
            stripped,
        )
        if not m:
            break
        tail = m.group(2)
        is_noise_tail = (
            tail.isdigit()
            or any(c.isdigit() for c in tail)
            or (len(tail) == 1 and tail not in ("à", "y", "À", "Y", "a", "A"))
        )
        if is_noise_tail:
            stripped = stripped[: m.start()].rstrip()
            continue
        break
    return stripped


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
        # Trim leading + inline + trailing OCR margin artifacts.
        line = strip_leading_marginalia(line)
        line = strip_inline_junk(line)
        line = strip_trailing_marginalia(line)
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
