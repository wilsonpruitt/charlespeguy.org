#!/usr/bin/env python3
"""
Flag suspect noise lines in FR piece files without modifying them.

Walks src/content/pieces/*.fr.md (or files given on argv) in slug order
and prints line-number + line for any line that matches a noise pattern.

Patterns flagged:
  - Leading digit + space + capital   (page-number-sig leak):  '^\\d+\\s+[A-Z]'
  - Lines starting with markdown #/>/|  surviving denoise
  - Single-letter or 2-char tokens between spaces (e.g. ' x ', ' 5e ', ' RU ')
  - Mixed alpha-digit word fragments (e.g. 'fé^Tier', 'compl mplaires')
  - Caret / backslash / square-bracket OCR garble
  - Very long no-space tokens (word-merge errors > 25 chars)
  - Subscription / back-matter cue words ("cahier de la ... série",
    "Imprimerie", "abonnement", "souscription")

Output: human-readable report to stdout; one section per file.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIECES = ROOT / "src" / "content" / "pieces"

# ---------------------------------------------------------------- patterns ---

LEADING_DIGIT_CAP = re.compile(r"^\s{0,3}\d{1,3}\s+[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]")
LEADING_MD = re.compile(r"^\s*[#>|]")
CARET_BACKSLASH = re.compile(r"[\^\\]")
SQUARE_BRACKET = re.compile(r"[\[\]]")
# Mixed alpha-digit inside one token: letter+digit or digit+letter with no space.
MIXED_ALPHA_DIGIT = re.compile(
    r"\b[a-zA-Zàâçéèêëîïôûùüÿñæœ]+\d+[a-zA-Zàâçéèêëîïôûùüÿñæœ]*"
    r"|\b\d+[a-zA-Zàâçéèêëîïôûùüÿñæœ]{2,}"
)
# Truly suspicious inline shorts: single non-vowel alpha letter (NOT 'a' or 'y'),
# or letter+digit combos ('5e', '1er' are real ordinals — exclude),
# or all-caps 2-letter that isn't a roman numeral.
SHORT_FR_OK_LOWER = {
    "a","à","y","ô","an","au","ce","ci","de","du","en","es","et","eu","il","je","la","le",
    "ma","me","mu","ne","ni","nu","on","ou","or","pu","sa","se","si","su",
    "ta","te","tu","un","va","vu","ya","ai","as","ah","oh","eh","si","or","ne",
    "ça","là","où","ès","dû","dé","ré",
}
ROMAN_NUMERALS = {
    "I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV",
    "XV","XVI","XVII","XVIII","XIX","XX","XL","L","LX","XC","C","CM","D","M",
}
# Suspicious: single letter (excluding a/à/y/ô/À/Y/Ô) or 2-letter all-caps not roman,
# or a token like '5e ' (page sig) when sentence-initial-ish.
INLINE_SHORT = re.compile(r"(?<=\s)([A-Za-zÀ-ÿ]{1,2})(?=\s)")
LONG_NOSPACE = re.compile(r"\b[A-Za-zÀ-ÿ]{26,}\b")
BACKMATTER_CUES = re.compile(
    r"\b(Imprimerie|abonnement|souscription|exemplaires?|"
    r"cahier de la (première|deuxième|troisième|quatrième|cinquième|sixième|"
    r"septième|huitième|neuvième|dixième|onzième|douzième|treizième|"
    r"quatorzième|quinzième) série"
    r"|frais d'envoi"
    r"|le numéro\s*:|le cahier\s*:)",
    re.IGNORECASE,
)


def flag_line(line: str) -> list[str]:
    flags = []
    if LEADING_DIGIT_CAP.match(line):
        flags.append("LEAD-NUM")
    if LEADING_MD.match(line):
        flags.append("LEAD-MD")
    if CARET_BACKSLASH.search(line):
        flags.append("CARET")
    if SQUARE_BRACKET.search(line) and "![" not in line and "](" not in line:
        flags.append("BRACKET")
    if MIXED_ALPHA_DIGIT.search(line):
        flags.append("MIX-AD")
    if LONG_NOSPACE.search(line):
        flags.append("LONG-TOK")
    if BACKMATTER_CUES.search(line):
        flags.append("BACK-MATTER")
    # Inline shorts: only flag truly suspicious ones.
    shorts = [m.group(0) for m in INLINE_SHORT.finditer(line)]
    sus = []
    for s in shorts:
        if s.lower() in SHORT_FR_OK_LOWER:
            continue
        if s in ROMAN_NUMERALS:
            continue
        # Single non-vowel letter or 2-letter all-caps non-roman.
        if len(s) == 1 and s.lower() not in {"a","y","ô","à"}:
            sus.append(s)
        elif len(s) == 2 and s.isupper() and s not in ROMAN_NUMERALS:
            sus.append(s)
    if sus:
        flags.append(f"SHORTS({','.join(sus[:6])})")
    return flags


def audit_file(path: Path) -> list[tuple[int, list[str], str]]:
    hits = []
    in_fm = False
    fm_done = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # Skip YAML frontmatter.
        if i == 1 and line.strip() == "---":
            in_fm = True
            continue
        if in_fm and line.strip() == "---":
            in_fm = False
            fm_done = True
            continue
        if in_fm:
            continue
        if not line.strip():
            continue
        flags = flag_line(line)
        if flags:
            hits.append((i, flags, line.rstrip()))
    return hits


def main(argv: list[str]) -> int:
    if argv:
        files = [Path(a) for a in argv]
    else:
        files = sorted(PIECES.glob("*.fr.md"))
    summary = []
    for f in files:
        hits = audit_file(f)
        summary.append((f.name, len(hits)))
        if hits:
            print(f"\n=== {f.name}  ({len(hits)} flagged) ===")
            for ln, flags, txt in hits:
                tag = ",".join(flags)
                show = txt if len(txt) <= 180 else txt[:177] + "..."
                print(f"  {ln:5}  [{tag}]  {show}")
    print("\n\n--- SUMMARY ---")
    for name, n in sorted(summary, key=lambda x: -x[1]):
        if n:
            print(f"  {n:5}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
