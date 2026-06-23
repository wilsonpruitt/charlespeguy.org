"""
Pull clean validated FR text for the Jean-Christophe (Romain Rolland) cahier
installments from fr.wikisource.org.

JC is published on Wikisource as 10 volumes, each either a single
"<Volume>/Texte entier" page or a set of ordered chapter subpages (roman or
arabic). This script fetches by an explicit MANIFEST that maps each cahier
piece -> the exact Wikisource page(s) to assemble, so there is no guessing.

Phase A (this run): the 7 installments that are 1:1 with a Wikisource unit.
Phase B installments (multi-cahier volume splits) are NOT in the manifest yet —
they need cahier-boundary anchoring against the existing OCR and are handled
separately.

For each manifest entry:
  1. Fetch each WS page via MediaWiki API (action=parse&prop=text).
  2. Save raw HTML to raw/wikisource/<cahier>--<slug>.jc.html (audit trail).
  3. Strip MediaWiki chrome, drop the page-image/header tables, keep prose.
  4. pandoc HTML -> markdown.
  5. Back up current .fr.md to raw/wikisource/_backup/.
  6. Write new .fr.md: preserved frontmatter + recomputed wordCount +
     sourceProvenance.

Run:  python3.11 scripts/pull-jc-wikisource.py            (all manifest)
      python3.11 scripts/pull-jc-wikisource.py --dry-run  (fetch+report, no write)
      python3.11 scripts/pull-jc-wikisource.py --only s05-c09
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "src" / "content" / "pieces"
RAW = ROOT / "raw" / "wikisource"
BACKUP = RAW / "_backup"
API = "https://fr.wikisource.org/w/api.php"
UA = {"User-Agent": "charlespeguy-audit/1.0 (wilson.pruitt@gmail.com)"}

# cahier -> (fr_slug, title, [ordered Wikisource page titles to concatenate])
# Phase A: 1:1 installments only.
MANIFEST = {
    "s05-c09": ("jean-christophe-i-l-aube", "Jean-Christophe. I. L'aube",
                ["L’Aube (Jean-Christophe)/I", "L’Aube (Jean-Christophe)/II", "L’Aube (Jean-Christophe)/III"]),
    "s05-c10": ("jean-christophe", "Jean-Christophe. II. Le matin",
                ["Le Matin (Jean-Christophe)/I La Mort de Jean-Michel",
                 "Le Matin (Jean-Christophe)/II Otto",
                 "Le Matin (Jean-Christophe)/III Minna"]),
    "s06-c08": ("jean-christophe", "Jean-Christophe. III. L'adolescent",
                ["L’Adolescent (Jean-Christophe)/I La Maison Euler",
                 "L’Adolescent (Jean-Christophe)/II Sabine",
                 "L’Adolescent (Jean-Christophe)/III Ada"]),
    "s08-c04": ("jean-christophe", "Jean-Christophe. IV. La révolte. 1. Sables mouvants",
                ["La Révolte (Jean-Christophe)/I Sables mouvants"]),
    "s08-c06": ("jean-christophe", "Jean-Christophe. IV. La révolte. 2. L'enlisement",
                ["La Révolte (Jean-Christophe)/II L’Enlisement"]),
    "s08-c09": ("jean-christophe", "Jean-Christophe. IV. La révolte. 3. La délivrance",
                ["La Révolte (Jean-Christophe)/III La Délivrance"]),
    "s09-c15": ("jean-christophe-a-paris-antoinette", "Jean-Christophe à Paris. Antoinette",
                ["Antoinette/Texte entier"]),
}


def fetch(page: str) -> str:
    q = {"action": "parse", "page": page, "prop": "text", "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(3):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
            if "parse" not in d:
                raise RuntimeError(f"no parse for {page}: {d.get('error')}")
            return d["parse"]["text"]
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def clean_html(html: str) -> str:
    # JC prose pages carry no data tables — the only <table>s are the WS
    # header/footer templates, so drop them all. Same for nav/scan chrome.
    html = re.sub(r'<table.*?</table>', '', html, flags=re.S)
    html = re.sub(r'<div[^>]*class="[^"]*(ws-noexport|ws-summary|navigation-not-searchable)[^"]*".*?</div>',
                  '', html, flags=re.S)
    html = re.sub(r'<style.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<sup[^>]*class="[^"]*reference[^"]*".*?</sup>', '', html, flags=re.S)
    html = re.sub(r'<span[^>]*class="[^"]*pagenum[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)
    html = re.sub(r'<span[^>]*class="[^"]*ws-pagenum[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)
    return html


def to_markdown(html: str) -> str:
    # disable span/div/link-attribute extensions so no {itemprop=...} braces survive
    fmt = ("markdown-raw_html-native_divs-native_spans-bracketed_spans"
           "-fenced_divs-link_attributes-header_attributes")
    p = subprocess.run(["pandoc", "-f", "html", "-t", fmt, "--wrap=none"],
                       input=html, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("pandoc failed: " + p.stderr[:400])
    md = p.stdout
    md = re.sub(r'\{[^}]*\}', '', md)                 # any leftover attribute braces
    md = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', md)  # [text](url) -> text
    md = re.sub(r'^:::.*$', '', md, flags=re.M)        # fenced-div residue
    md = re.sub(r'[​‌‍]', '', md)       # zero-width chars
    # drop lines that are only pandoc hard-break backslashes / empty brackets
    md = re.sub(r'^[\\\s\[\]]*$', '', md, flags=re.M)
    md = re.sub(r' *\\$', '', md, flags=re.M)          # trailing hard-break backslash
    # tidy chapter headings: "### III LA DÉLIVRANCE" keep; strip stray leading empties
    md = re.sub(r'^#+\s+', lambda m: m.group(0), md, flags=re.M)
    md = re.sub(r'\n{3,}', '\n\n', md)
    return strip_leading_header(md.strip())


def strip_leading_header(md: str) -> str:
    """Drop the per-page Wikisource header: breadcrumb line, the
    'Paul Ollendorff, YYYY (Tome N, p. X-Y).' source line, and a trailing
    bare part-name line, leaving the first chapter heading / prose intact."""
    lines = md.split("\n")
    # find the publisher source line
    pub = next((i for i, l in enumerate(lines) if re.match(r'^\s*Paul Ollendorff,\s*\d{4}', l)), None)
    if pub is not None:
        lines = lines[pub + 1:]
    # drop leading empties + short non-heading, non-sentence "part name" lines
    while lines:
        l = lines[0].strip()
        if not l:
            lines.pop(0); continue
        if l.startswith("#"):
            break
        if len(l) < 70 and not re.search(r'[.!?…»]$', l):
            lines.pop(0); continue
        break
    return "\n".join(lines).strip()


def read_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r'^---\n(.*?)\n---\n?(.*)$', text, re.S)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    BACKUP.mkdir(parents=True, exist_ok=True)

    for cahier, (slug, title, pages) in MANIFEST.items():
        if args.only and args.only != cahier:
            continue
        fr_path = PIECES / f"{cahier}--{slug}.fr.md"
        if not fr_path.exists():
            print(f"!! MISSING target {fr_path.name} — skip")
            continue
        print(f"\n== {cahier} {slug}  ({len(pages)} WS page(s)) ==")
        parts = []
        for pg in pages:
            print(f"   fetch: {pg}")
            html = clean_html(fetch(pg))
            (RAW / f"{cahier}--{slug}.{pg.split('/')[-1].replace(' ','_')}.html").write_text(html, encoding="utf-8")
            parts.append(to_markdown(html))
            time.sleep(1)
        body = "\n\n".join(parts).strip()
        wc = len(re.findall(r"\b\w+\b", body))
        fm, old_body = read_frontmatter(fr_path)
        old_wc = len(re.findall(r"\b\w+\b", old_body))
        # rebuild frontmatter: update wordCount, add sourceProvenance
        fm_lines = [l for l in fm.split("\n") if not l.startswith(("wordCount:", "sourceProvenance:"))]
        fm_lines.append(f"wordCount: {wc}")
        prov = "; ".join(pages)
        fm_lines.append(f'sourceProvenance: "Wikisource ({prov}, status=validated); pulled 2026-06-19"')
        new = "---\n" + "\n".join(fm_lines) + "\n---\n\n" + body + "\n"
        print(f"   wordCount: OCR {old_wc} -> WS {wc}")
        if args.dry_run:
            print("   [dry-run] not written")
            continue
        shutil.copy2(fr_path, BACKUP / f"{fr_path.name}.bak-2026-06-19")
        fr_path.write_text(new, encoding="utf-8")
        print(f"   wrote {fr_path.name}")


if __name__ == "__main__":
    main()
