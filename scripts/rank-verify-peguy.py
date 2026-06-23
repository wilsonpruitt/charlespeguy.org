"""
SET-UP for next session: rank the 62 `verify-peguy` FR pieces (Péguy texts with
no Wikisource source) by OCR-noise density, worst-first, so the manual eyeball
pass tackles the dirtiest first.

Reads wikisource-audit.csv (action == verify-peguy), scores each .fr.md, writes:
  audit-screens/verify-peguy-worklist.tsv   (machine-sortable)
  audit-screens/verify-peguy-worklist.md    (human checklist, ranked)

Score = flagged-line density + back-matter penalty. Flags reuse the
audit-fr-noise.py pattern families (leading page-num, md leak, caret/bracket
garble, mixed alpha-digit, long merged tokens, subscription back-matter).
"""
import csv, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "src" / "content" / "pieces"
OUT = ROOT / "audit-screens"

LEADING_DIGIT_CAP = re.compile(r"^\s{0,3}\d{1,3}\s+[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸÑÆŒ]")
LEADING_MD = re.compile(r"^\s*[#>|]")
CARET_BRACKET = re.compile(r"[\^\\\[\]]")
MIXED_AD = re.compile(r"\b[a-zàâçéèêëîïôûùüÿñæœ]+\d+[a-zàâçéèêëîïôûùüÿñæœ]*|\b\d+[a-zàâçéèêëîïôûùüÿñæœ]{2,}", re.I)
LONG_TOKEN = re.compile(r"\S{26,}")
BACKMATTER = re.compile(r"imprimerie|abonnement|souscription|rue de la sorbonne|paraissant|whatman|le gérant|ouvriers syndiqués|cahier de la .{0,20}série", re.I)


def body(stem):
    t = (PIECES / f"{stem}.fr.md").read_text(encoding="utf-8")
    return re.sub(r'^---.*?---', '', t, 1, re.S)


def score(stem):
    lines = [l for l in body(stem).split("\n") if l.strip()]
    n = len(lines) or 1
    flags = {"LEAD-NUM": 0, "LEAD-MD": 0, "CARET/BRKT": 0, "MIX-AD": 0, "LONG-TOK": 0, "BACK-MATTER": 0}
    for l in lines:
        if LEADING_DIGIT_CAP.search(l): flags["LEAD-NUM"] += 1
        if LEADING_MD.search(l): flags["LEAD-MD"] += 1
        if CARET_BRACKET.search(l): flags["CARET/BRKT"] += 1
        if MIXED_AD.search(l): flags["MIX-AD"] += 1
        if LONG_TOKEN.search(l): flags["LONG-TOK"] += 1
        if BACKMATTER.search(l): flags["BACK-MATTER"] += 1
    flagged = sum(min(v, 1) for v in flags.values())  # not used; keep per-flag
    total_flag_lines = sum(flags.values())
    density = total_flag_lines / n * 100
    # back-matter is a strong signal of misfiled content -> penalty
    penalty = 15 if flags["BACK-MATTER"] >= 2 else 0
    return n, flags, round(density + penalty, 1)


def main():
    OUT.mkdir(exist_ok=True)
    rows = [r for r in csv.DictReader(open(ROOT / "wikisource-audit.csv")) if r["action"].strip() == "verify-peguy"]
    scored = []
    for r in rows:
        stem = f"{r['cahier']}--{r['pieceSlug']}"
        f = PIECES / f"{stem}.fr.md"
        if not f.exists():
            scored.append((r, 0, {}, -1, "MISSING")); continue
        n, flags, s = score(stem)
        topflags = ",".join(f"{k}:{v}" for k, v in sorted(flags.items(), key=lambda x: -x[1]) if v)
        scored.append((r, n, flags, s, topflags))
    scored.sort(key=lambda x: -x[3])  # worst first

    with open(OUT / "verify-peguy-worklist.tsv", "w") as fh:
        fh.write("rank\tscore\tcahier\tslug\twords\tlines\tflags\n")
        for i, (r, n, flags, s, tf) in enumerate(scored, 1):
            fh.write(f"{i}\t{s}\t{r['cahier']}\t{r['pieceSlug']}\t{r['wordCount']}\t{n}\t{tf}\n")

    with open(OUT / "verify-peguy-worklist.md", "w") as fh:
        fh.write("# verify-peguy worklist (ranked worst-first)\n\n")
        fh.write("62 Péguy FR pieces with no Wikisource source — manual OCR eyeball pass.\n")
        fh.write("Score = flagged-line density % (+15 if back-matter leak). Tackle top-down.\n")
        fh.write("Tip: open the RENDERED page (typography exposes more noise than the .md):\n")
        fh.write("`charlespeguy.org/cahiers/<cahier>/<slug>/fr`. Fix mechanical noise via\n")
        fh.write("`denoise-fr-pieces.py`; char-level garble needs re-OCR (never invent).\n\n")
        fh.write("| # | score | cahier | slug | words | top flags |\n|--|--|--|--|--|--|\n")
        for i, (r, n, flags, s, tf) in enumerate(scored, 1):
            fh.write(f"| {i} | {s} | {r['cahier']} | {r['pieceSlug'][:38]} | {r['wordCount']} | {tf[:60]} |\n")
    print(f"Wrote worklist for {len(scored)} pieces. Top 5 dirtiest:")
    for r, n, flags, s, tf in scored[:5]:
        print(f"  {s:6}  {r['cahier']} {r['pieceSlug'][:38]:40} {tf[:50]}")


if __name__ == "__main__":
    main()
