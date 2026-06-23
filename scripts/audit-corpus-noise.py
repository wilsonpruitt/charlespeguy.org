"""
Corpus-wide FR noise audit (2026-06-23). Scores EVERY src/content/pieces/*.fr.md
for OCR noise, worst-first, so we know what still needs re-OCR after the
Rounds 17-20 archive.org campaign + the Wikisource imports.

Two signals, summed:
  1. line-flag density (reused from rank-verify-peguy.py: back-matter, caret/
     bracket, mixed alpha-digit, long merged tokens, leading page-num/md).
  2. char-garble token ratio (NEW): % of alphabetic tokens that are implausible
     French words -> catches "J'aflirme", "tvmiulte", "supei'be", "del'insulteur"
     that line-flags miss. THIS is the re-OCR signal.

Tags each piece with current source status from wikisource-audit.csv `action`
+ the file's own provenance frontmatter, so a clean WS/re-OCR import that happens
to score high (e.g. legit brackets) can be told apart from genuine old-OCR garble.

Writes audit-screens/corpus-noise-{tsv,md}. Worst-first.
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

VOWELS = set("aeiouyàâäéèêëîïôöûùüÿœæ")
WORD = re.compile(r"[A-Za-zÀ-ÿ'’]{2,}")
CONSON_RUN = re.compile(r"[bcdfghjklmnpqrstvwxzçñ]{5,}", re.I)


def is_garble(tok):
    """Heuristic: token is implausible French."""
    low = tok.lower().strip("'’")
    if len(low) < 4:
        return False
    # uppercase letter mid-word (OCR case confusion: J'aflirme, supEi'be)
    if re.search(r"[A-ZÀ-Ÿ]", tok[1:]) and not tok.isupper():
        return True
    core = "".join(c for c in low if c.isalpha())
    if len(core) < 4:
        return False
    # no vowel at all in a 4+ char alpha run
    if not (set(core) & VOWELS):
        return True
    # 5+ consonants in a row
    if CONSON_RUN.search(core):
        return True
    # apostrophe inside a long run (del'insulteur) - already split tokens, but
    # catch glued ones: an apostrophe not after a known elision letter
    m = re.search(r"[a-zà-ÿ]['’][a-zà-ÿ]{4,}", low)
    if m and low[m.start()] not in "cdjlmnst":
        return True
    return False


def analyse(stem):
    t = (PIECES / f"{stem}.fr.md").read_text(encoding="utf-8")
    has_prov = "sourceProvenance" in t or "vision re-OCR" in t
    body = re.sub(r'^---.*?---', '', t, 1, re.S)
    lines = [l for l in body.split("\n") if l.strip()]
    n = len(lines) or 1
    flags = {"LEAD-NUM": 0, "LEAD-MD": 0, "CARET/BRKT": 0, "MIX-AD": 0, "LONG-TOK": 0, "BACK-MATTER": 0}
    for l in lines:
        if LEADING_DIGIT_CAP.search(l): flags["LEAD-NUM"] += 1
        if LEADING_MD.search(l): flags["LEAD-MD"] += 1
        if CARET_BRACKET.search(l): flags["CARET/BRKT"] += 1
        if MIXED_AD.search(l): flags["MIX-AD"] += 1
        if LONG_TOKEN.search(l): flags["LONG-TOK"] += 1
        if BACKMATTER.search(l): flags["BACK-MATTER"] += 1
    line_density = sum(flags.values()) / n * 100
    # char-garble ratio
    toks = WORD.findall(body)
    nt = len(toks) or 1
    garble = sum(1 for tk in toks if is_garble(tk))
    garble_pct = garble / nt * 100
    penalty = 15 if flags["BACK-MATTER"] >= 2 else 0
    # garble weighted 3x: it's the true re-OCR signal
    score = round(line_density + garble_pct * 3 + penalty, 1)
    return n, nt, flags, round(line_density, 1), round(garble_pct, 2), score, has_prov


def main():
    OUT.mkdir(exist_ok=True)
    action = {}
    for r in csv.DictReader(open(ROOT / "wikisource-audit.csv")):
        action[(r["cahier"], r["pieceSlug"])] = r["action"]

    scored = []
    for f in sorted(PIECES.glob("*.fr.md")):
        stem = f.stem[:-3] if f.stem.endswith(".fr") else f.stem.replace(".fr", "")
        stem = f.name[:-6]  # strip ".fr.md"
        cahier = stem.split("--")[0]
        slug = stem.split("--", 1)[1] if "--" in stem else ""
        n, nt, flags, ld, gp, sc, prov = analyse(stem)
        act = action.get((cahier, slug), "?")
        # status: what source is this piece on now
        if prov or act == "done-reocr":
            status = "reocr"
        elif act in ("use-wikisource", "use-wikisource-jc"):
            status = "wikisource"
        elif act in ("filter-blocked",):
            status = "filter-blk"
        elif act in ("skip", "skip-editorial"):
            status = "skip"
        else:
            status = "old-ocr"
        topflags = ",".join(f"{k}:{v}" for k, v in sorted(flags.items(), key=lambda x: -x[1]) if v)
        scored.append((cahier, slug, n, nt, ld, gp, sc, status, topflags))

    scored.sort(key=lambda x: -x[6])

    with open(OUT / "corpus-noise.tsv", "w") as fh:
        fh.write("rank\tscore\tgarble%\tline%\tstatus\tcahier\tslug\twords\tflags\n")
        for i, (c, s, n, nt, ld, gp, sc, st, tf) in enumerate(scored, 1):
            fh.write(f"{i}\t{sc}\t{gp}\t{ld}\t{st}\t{c}\t{s}\t{nt}\t{tf}\n")

    # scanned-cahier set (proven archive.org pool can run now)
    src = (ROOT / "scripts" / "fetch-cahier-pages.py").read_text()
    mm = re.search(r"CAHIER_IDS\s*=\s*\{(.*?)\}", src, re.S)
    scanned = set(re.findall(r"['\"]([a-z0-9-]+)['\"]\s*:", mm.group(1))) if mm else set()
    BACK = ("administration", "librairie", "petit-index", "inventaire", "annonces",
            "proces-verbaux", "nouvelles-communications", "almanach",
            "memoires-et-dossiers", "oeuvres-choisies")

    # the actionable list = needs re-OCR (old-ocr/filter-blk), ranked
    todo = [x for x in scored if x[7] in ("old-ocr", "filter-blk")]
    back = [x for x in todo if any(b in x[1] for b in BACK)]
    real = [x for x in todo if x not in back]
    now = [x for x in real if x[0] in scanned]          # archive.org scan available
    gallica = [x for x in real if x[0] not in scanned]  # need Gallica fetcher

    def tbl(fh, rows):
        fh.write("| # | score | garble% | status | cahier | slug | words | top flags |\n|--|--|--|--|--|--|--|--|\n")
        for i, (c, s, n, nt, ld, gp, sc, st, tf) in enumerate(rows, 1):
            fh.write(f"| {i} | {sc} | {gp} | {st} | {c} | {s[:34]} | {nt} | {tf[:48]} |\n")
        fh.write("\n")

    with open(OUT / "corpus-noise.md", "w") as fh:
        fh.write("# Corpus FR noise audit (2026-06-23) — worst-first\n\n")
        fh.write(f"All {len(scored)} FR pieces scored. score = line-flag% + 3×garble% (+15 back-matter).\n")
        fh.write("garble% = implausible-French-token ratio = the true re-OCR signal.\n")
        fh.write("status: reocr=rebuilt from scans · wikisource=clean WS import · skip=back-matter/editorial · old-ocr=ORIGINAL noisy OCR · filter-blk=Wilson manual.\n\n")
        fh.write(f"**{len(todo)} re-OCR targets** = {len(real)} real-prose + {len(back)} back-matter (reclassify, don't OCR).\n\n")
        fh.write(f"## A. Real prose, archive.org scan available — run proven pool NOW ({len(now)})\n\n")
        tbl(fh, now)
        fh.write(f"## B. Real prose, NO archive scan — need Gallica fetcher ({len(gallica)})\n\n")
        tbl(fh, gallica)
        fh.write(f"## C. Back-matter — reclassify/skip, do NOT OCR ({len(back)})\n\n")
        tbl(fh, back)

    print(f"Scored {len(scored)} FR pieces. {len(todo)} re-OCR targets: "
          f"{len(now)} scanned-now, {len(gallica)} gallica, {len(back)} back-matter.")
    print("\nTop 20 dirtiest re-OCR targets:")
    print(f"  {'score':>6} {'garble%':>7}  {'status':<10} cahier   slug")
    for c, s, n, nt, ld, gp, sc, st, tf in todo[:20]:
        print(f"  {sc:>6} {gp:>7}  {st:<10} {c:8} {s[:40]}")


if __name__ == "__main__":
    main()
