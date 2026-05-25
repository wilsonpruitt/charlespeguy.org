#!/usr/bin/env python3
"""
Audit ~/charlespeguy.org/src/content/pieces + src/data/cahiers for known data
quality issues. Emits a CSV (audit.csv) + a human-readable report (stdout) /
markdown summary (audit.md).

Flags:
  EMPTY_FR        — .fr.md exists but has 0 prose lines
  EMPTY_EN        — .en.md exists but has 0 prose lines
  NO_FR           — cahier piece has .en.md but no .fr.md
  NO_EN           — cahier piece has .fr.md but no .en.md
  LOW_PROSE_FR    — FR file present but prose ratio < 0.5
  LOW_PROSE_EN    — EN file present but prose ratio < 0.5
  SPLIT_SUSPECT   — cahier has 2 pieces where piece-2's title looks like a
                    Roman-numeral subtitle of piece-1 (probable mis-split)
  AUTHOR_MISMATCH — piece title contains a known-author surname that does
                    not match the listed author
  COM_PLACEHOLDER — original ~/charlespeguy.com source file is marked
                    status: "placeholder"
  COM_MISSING     — original ~/charlespeguy.com source file does not exist

Usage:
    python3 scripts/audit-pieces.py
"""

import csv
import json
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
PIECES = ROOT / "src/content/pieces"
CAHIERS_JSON = ROOT / "src/data/cahiers"
COM_TEXTS = pathlib.Path.home() / "charlespeguy.com/src/content/texts"

WORD_RE = re.compile(r"(?i)\b(le|la|les|de|et|qui|que|une?|dans|pour|avec|était|elle|il|sur|ses|aux?|comme|son|sa|nous|vous|ce|cette|mais|plus|tout|tous)\b")
REAL_WORD_RE = re.compile(r"(?<![A-Za-zàâçéèêëîïôûùüÿñæœ])[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]?[a-zàâçéèêëîïôûùüÿñæœ]{2,}(?![A-Za-zàâçéèêëîïôûùüÿñæœ])")
EN_WORD_RE = re.compile(r"(?i)\b(the|and|of|to|in|that|was|with|for|on|but|as|by|at|from|this|all|or|not|are|were)\b")

# Roman-numeral piece-2 detection: matches "I. ...", "III. ...", "IV. ...".
ROMAN_PREFIX_RE = re.compile(r"^(I{1,3}|IV|V|VI{1,3}|IX|X|XI{1,3}|XIV|XV)\.\s")

# Known authors by surname → expected slug. Used for miscredit detection.
SURNAME_TO_SLUG = {
    "Rolland": "romain-rolland",
    "Milliet": "paul-milliet",
    "Suarès": "andre-suares",
    "Suares": "andre-suares",
    "Vuillaume": "maxime-vuillaume",
    "Tolstoï": "leon-tolstoi",
    "Tolstoi": "leon-tolstoi",
    "Benda": "julien-benda",
    "Halévy": "daniel-halevy",
    "Halevy": "daniel-halevy",
    "Mangasarian": "mangasarian",
    "Salomé": "rene-salome",
    "Desjardins": "paul-desjardins",
    "Reinach": "joseph-reinach",
    "Clemenceau": "georges-clemenceau",
    "Lafargue": "paul-lafargue",
    "Picquart": "georges-picquart",
    "Dostoïevski": "andre-suares",  # Dostoïevski is Suarès's *subject*, careful
    "Porché": "francois-porche",
    "Porche": "francois-porche",
    "Delahache": "delahache",
}
# Surnames that appear as subject-of in titles (not the author of the piece);
# don't flag mismatches for these.
TITLES_AS_SUBJECT = {"Dostoïevski"}


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Cheap parse — return (fm_dict, body). fm_dict has just the keys we need."""
    fm = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm_block = text[4:end]
            body = text[end + 5:]
            for line in fm_block.splitlines():
                m = re.match(r"^(\w+):\s*(.*)$", line)
                if m:
                    fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm, body


def prose_stats(body: str, lang: str) -> tuple[int, int, float]:
    """Return (total_nonblank_lines, prose_lines, ratio)."""
    lines = [l for l in body.splitlines() if l.strip()]
    if not lines:
        return 0, 0, 0.0
    prose = 0
    for l in lines:
        rw = len(REAL_WORD_RE.findall(l))
        if lang == "fr":
            dh = len(WORD_RE.findall(l))
        else:
            dh = len(EN_WORD_RE.findall(l))
        if rw >= 2 and dh >= 1:
            prose += 1
    return len(lines), prose, prose / len(lines)


def is_com_placeholder(cahier_slug: str) -> str:
    """Return COM_PLACEHOLDER, COM_MISSING, or '' (ok)."""
    src = COM_TEXTS / f"{cahier_slug}.md"
    if not src.exists():
        return "COM_MISSING"
    try:
        text = src.read_text(encoding="utf-8")
    except Exception:
        return "COM_MISSING"
    if 'status: "placeholder"' in text:
        return "COM_PLACEHOLDER"
    return ""


def main() -> int:
    # ----- load cahier JSONs -----
    cahiers = {}
    for jp in sorted(CAHIERS_JSON.glob("*.json")):
        cahiers[jp.stem] = json.loads(jp.read_text(encoding="utf-8"))

    # ----- index piece files -----
    fr_files = {}  # (cahier_slug, piece_slug) -> Path
    en_files = {}
    for p in PIECES.glob("*.md"):
        m = re.match(r"^(s\d{2}-c\d{2})--(.+)\.(fr|en)\.md$", p.name)
        if not m:
            print(f"  skipping malformed filename: {p.name}", file=sys.stderr)
            continue
        cahier_slug, piece_slug, lang = m.group(1), m.group(2), m.group(3)
        (fr_files if lang == "fr" else en_files)[(cahier_slug, piece_slug)] = p

    # ----- walk every (cahier, piece) declared in JSON, plus orphan files -----
    rows = []
    declared = set()
    for cslug, data in cahiers.items():
        pieces = data.get("pieces", [])
        com_status = is_com_placeholder(cslug)
        # SPLIT_SUSPECT detection: 2 pieces where piece-2 starts with Roman numeral
        split_suspect = False
        if len(pieces) == 2:
            t2 = pieces[1].get("titleFr", "") or pieces[1].get("title", "")
            if ROMAN_PREFIX_RE.match(t2):
                split_suspect = True

        for p in pieces:
            pslug = p["slug"]
            declared.add((cslug, pslug))
            listed_author = p.get("author", "")
            title = p.get("titleFr") or p.get("title") or ""
            flags = []
            if com_status:
                flags.append(com_status)
            if split_suspect:
                flags.append("SPLIT_SUSPECT")

            fr_path = fr_files.get((cslug, pslug))
            en_path = en_files.get((cslug, pslug))
            fr_prose_ratio = en_prose_ratio = None
            fr_prose = en_prose = 0
            if fr_path:
                _fm, body = split_frontmatter(fr_path.read_text(encoding="utf-8"))
                _, fr_prose, fr_prose_ratio = prose_stats(body, "fr")
                if fr_prose == 0:
                    flags.append("EMPTY_FR")
                elif fr_prose_ratio < 0.5:
                    flags.append("LOW_PROSE_FR")
            else:
                flags.append("NO_FR")
            if en_path:
                _fm, body = split_frontmatter(en_path.read_text(encoding="utf-8"))
                _, en_prose, en_prose_ratio = prose_stats(body, "en")
                if en_prose == 0:
                    flags.append("EMPTY_EN")
                elif en_prose_ratio < 0.5:
                    flags.append("LOW_PROSE_EN")
            else:
                flags.append("NO_EN")

            # AUTHOR_MISMATCH: title contains a known surname; expected slug
            # differs from listed_author.
            for surname, expected_slug in SURNAME_TO_SLUG.items():
                if surname in title and surname not in TITLES_AS_SUBJECT:
                    if listed_author and listed_author != expected_slug:
                        flags.append(f"AUTHOR_MISMATCH({listed_author}→{expected_slug})")
                    break

            rows.append({
                "cahier": cslug,
                "piece": pslug,
                "title": title,
                "listed_author": listed_author,
                "fr_prose": fr_prose,
                "fr_ratio": f"{fr_prose_ratio:.2f}" if fr_prose_ratio is not None else "",
                "en_prose": en_prose,
                "en_ratio": f"{en_prose_ratio:.2f}" if en_prose_ratio is not None else "",
                "flags": "|".join(flags),
            })

    # Orphan piece files (file exists but not declared in cahier JSON)
    for (cslug, pslug), path in {**fr_files, **en_files}.items():
        if (cslug, pslug) not in declared:
            rows.append({
                "cahier": cslug, "piece": pslug, "title": "", "listed_author": "",
                "fr_prose": "", "fr_ratio": "", "en_prose": "", "en_ratio": "",
                "flags": "ORPHAN_FILE",
            })

    # ----- write CSV -----
    out_csv = ROOT / "audit.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out_csv} ({len(rows)} rows)")

    # ----- markdown summary -----
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        for flag in (r["flags"] or "").split("|"):
            if flag:
                # collapse AUTHOR_MISMATCH(...) → AUTHOR_MISMATCH
                base = flag.split("(")[0]
                counts[base] += 1

    md = [f"# Pieces audit — {len(rows)} (cahier, piece) entries\n"]
    md.append("## Flag counts\n")
    for flag, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        md.append(f"- **{flag}**: {n}")
    md.append("")

    # Per-flag detail
    for flag in sorted(counts.keys()):
        md.append(f"\n## {flag}\n")
        matching = [r for r in rows if r["flags"] and (flag in r["flags"])]
        for r in matching[:50]:
            extra = ""
            if "AUTHOR_MISMATCH" in r["flags"] and flag == "AUTHOR_MISMATCH":
                # surface the full flag with parens
                for f in r["flags"].split("|"):
                    if f.startswith("AUTHOR_MISMATCH"):
                        extra = f.replace("AUTHOR_MISMATCH", "").strip("()")
                        break
            md.append(f"- {r['cahier']}--{r['piece']}: {r['title']}  *{r['listed_author']}*  ({extra})" if extra else
                      f"- {r['cahier']}--{r['piece']}: {r['title']}  *{r['listed_author']}*")
        if len(matching) > 50:
            md.append(f"- ... and {len(matching) - 50} more")
    out_md = ROOT / "audit.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out_md}")

    print("\nFlag counts:")
    for flag, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {flag:30s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
