"""
Pull clean French source text from fr.wikisource.org for confirmed Tier-1 pieces.

Reads wikisource-audit.csv, filters to rows with action == "use-wikisource"
(skipping the JC installments for now since they need cahier-boundary splitting
against a single volume page), and for each:

  1. Fetches parsed HTML via MediaWiki API (action=parse&prop=text).
  2. Saves raw HTML to raw/wikisource/<cahier>--<slug>.html (audit trail).
  3. Strips MediaWiki chrome (edit links, references, printfooter), preserves
     ws-pagenum spans as `[p. N]` markers.
  4. Pipes the cleaned HTML through pandoc → markdown.
  5. Backs up the current src/content/pieces/<cahier>--<slug>.fr.md to
     raw/wikisource/_backup/ before overwriting.
  6. Writes a new .fr.md with preserved frontmatter, recomputed wordCount, and
     a `sourceProvenance` field documenting the pull.

Run:  python3.11 scripts/pull-wikisource.py
      python3.11 scripts/pull-wikisource.py --slug notre-patrie   (single piece)
      python3.11 scripts/pull-wikisource.py --dry-run             (no overwrite)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "wikisource-audit.csv"
RAW_DIR = ROOT / "raw" / "wikisource"
BACKUP_DIR = RAW_DIR / "_backup"
PIECES_DIR = ROOT / "src" / "content" / "pieces"

UA = "charlespeguy.org wikisource-puller (wilson.pruitt@gmail.com)"
TODAY = "2026-06-20"

# Works whose Wikisource landing page is a TOC; we must fetch each sub-page
# and concat in reading order. Investigated 2026-05-27 by walking the landing
# pages. Front-/back-matter (Avertissement, Bibliographie, Table) included
# where it was published as part of the cahier.
SUBPAGES: dict[str, list[str]] = {
    "danton-trois-actes": [
        "Danton_(Romain_Rolland)/Personnages",
        "Danton_(Romain_Rolland)/Acte_I",
        "Danton_(Romain_Rolland)/Acte_II",
        "Danton_(Romain_Rolland)/Acte_III",
    ],
    "le-theatre-du-peuple": [
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Avertissement",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Introduction",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_I/I._Molière",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_I/II._La_Tragédie_classique",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_I/III._Le_Drame_romantique",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_I/IV._Le_Théâtre_bourgeois",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_I/V._Le_répertoire_étranger",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_I/VI._Il_n’existe_dans_le_passé_qu’un_répertoire_de_lectures_populaires,_non_de_théâtre_populaire…",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_I/VII._L’Œuvre_des_Trente_ans_de_Théâtre_et_les_galas_populaires",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_II/I._Les_Précurseurs_du_théâtre_du_peuple",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_II/II._Le_Théâtre_nouveau._Conditions_matérielles_et_morales",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_II/III._Quelques_genres_de_théâtre_populaire._Le_mélodrame",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_II/IV._L’Épopée_historique",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_II/V._De_quelques_autres_genres",
        "Le_Théâtre_du_peuple_(Romain_Rolland)/Partie_III/Les_Fêtes_du_peuple._Conclusion",
    ],
    # s07-c18 — Vie de Michel-Ange I. La Lutte (Partie I)
    "la-vie-de-michel-ange-i-la-lutte": [
        "Vie_de_Michel-Ange/Avant-Propos",
        "Vie_de_Michel-Ange/Michel-Ange",
        "Vie_de_Michel-Ange/Partie_I,_I._La_Force",
        "Vie_de_Michel-Ange/Partie_I,_II._La_Force_qui_se_brise",
        "Vie_de_Michel-Ange/Partie_I,_III._Le_Désespoir",
    ],
    # s08-c02 — Vie de Michel-Ange II. L'Abdication (Partie II + épilogue)
    "la-vie-de-michel-ange": [
        "Vie_de_Michel-Ange/Partie_II,_I._Amour",
        "Vie_de_Michel-Ange/Partie_II,_II._Foi",
        "Vie_de_Michel-Ange/Partie_II,_III._Solitude",
        "Vie_de_Michel-Ange/Épilogue._La_Mort",
    ],
    "la-tapisserie-de-notre-dame": [
        "Présentation_de_Paris_à_Notre_Dame",
        "Paris_vaisseau_de_charge",
        "Paris_double_galère",
        "Paris_vaisseau_de_guerre",
        "Présentation_de_la_Beauce_à_Notre_Dame_de_Chartres",
        "Les_Quatre_Prières_dans_la_cathédrale_de_Chartres",
    ],
    # s13-c08 — Suarès, Dostoïevski (Cahiers de la Quinzaine, Série XIII, c.8,
    # 1911 — the WS source IS this exact cahier edition). 6 prose sections in
    # TOC reading order; the /image frontispiece subpage is omitted.
    # s10-c05 — Suarès, "Le portrait d'Ibsen" = his essay *Ibsen* first run
    # in RDDM 1903 (same year as the cahier; body confirmed identical to the
    # OCR by distinctive-phrase match). 2 parts on WS (/02 validated).
    "le-portrait-d-ibsen": [
        "Ibsen (RDDM)/01",
        "Ibsen (RDDM)/02",
    ],
    "dostoievski": [
        "Dostoïevski (Suarès)/né à Moscou",
        "Dostoïevski (Suarès)/jusqu’ici",
        "Dostoïevski (Suarès)/sur sa vie",
        "Dostoïevski (Suarès)/sur son art",
        "Dostoïevski (Suarès)/passions et moments",
        "Dostoïevski (Suarès)/la profondeur russe",
    ],
}


def fetch_parsed_html(page_title: str) -> str:
    """Fetch parsed HTML for a Wikisource page via the MediaWiki API."""
    api = "https://fr.wikisource.org/w/api.php"
    params = {
        "action": "parse",
        "page": page_title,
        "format": "json",
        "prop": "text",
        "disableeditsection": "1",
        "redirects": "1",
    }
    url = f"{api}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "error" in data:
        raise RuntimeError(f"MediaWiki API error: {data['error']}")
    return data["parse"]["text"]["*"]


# --- HTML cleaning ----------------------------------------------------------
# We want to keep the prose and drop chrome. Strategy: walk the HTML, skip
# subtrees whose root element matches a blocklist (by class or tag), and emit
# the rest. Page-number spans (.ws-pagenum) get replaced with `[p. N]` text.

BLOCK_CLASSES = {
    # Editorial / nav / metadata chrome on Wikisource pages
    "mw-editsection", "noprint", "printfooter", "reference",
    "ws-noexport", "ws-noinclude", "ws-summary",
    "navigation-not-searchable", "mw-cite-backlink",
    "headertemplate", "headertemplate-author", "headertemplate-title",
    "headertemplate-reference", "footertemplate",
    "mw-html-heading", "Z3988",
    "pagenum", "ws-pagenum",  # drop page markers — not useful on canonical WS text
}
BLOCK_TAGS = {"style", "script"}


class Cleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def _is_block(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> bool:
        if tag in BLOCK_TAGS:
            return True
        cls = ""
        for k, v in attrs:
            if k == "class" and v:
                cls = v
                break
        if not cls:
            return False
        classes = set(cls.split())
        return bool(classes & BLOCK_CLASSES)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if self.skip_depth:
            self.skip_depth += 1
            return
        if self._is_block(tag, attrs):
            self.skip_depth = 1
            return
        # Preserve a few structural tags so pandoc renders correctly.
        if tag in {"p", "h1", "h2", "h3", "h4", "blockquote", "em", "i",
                  "strong", "b", "br", "hr", "ul", "ol", "li"}:
            attr_str = "".join(
                f' {k}="{v}"' for k, v in attrs if k == "class" and v
            )
            self.parts.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag in {"p", "h1", "h2", "h3", "h4", "blockquote", "em", "i",
                  "strong", "b", "ul", "ol", "li"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.parts.append(data)

    def html(self) -> str:
        return "".join(self.parts)


def clean_html(raw: str) -> str:
    c = Cleaner()
    c.feed(raw)
    return c.html()


def html_to_markdown(html: str) -> str:
    wrapped = f"<!doctype html><html><body>{html}</body></html>"
    result = subprocess.run(
        ["pandoc", "-f", "html", "-t", "markdown_strict-raw_html", "--wrap=none"],
        input=wrapped,
        capture_output=True,
        text=True,
        check=True,
    )
    md = result.stdout
    # Normalize soft hyphens (U+00AD) and zero-width chars Wikisource inserts
    # for line-break control. Collapse 3+ blank lines.
    md = md.replace("­", "").replace("​", "").replace("﻿", "")
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


# --- Frontmatter handling ---------------------------------------------------
def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, m.group(2)


FRONTMATTER_ORDER = [
    "cahier", "pieceSlug", "lang", "title", "author", "isAvertissement",
    "wordCount", "sourceProvenance", "ocrSource",
]


def render_frontmatter(fm: dict[str, str]) -> str:
    lines = ["---"]
    seen = set()
    for k in FRONTMATTER_ORDER:
        if k in fm:
            lines.append(f"{k}: {fm[k]}")
            seen.add(k)
    for k, v in fm.items():
        if k not in seen:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# --- Per-piece pipeline -----------------------------------------------------
def pull_one(row: dict[str, str], dry_run: bool, force: bool = False) -> tuple[str, str]:
    """Returns (status, message). Status in {'ok', 'skip', 'error'}."""
    cahier = row["cahier"]
    slug = row["pieceSlug"]
    url = row["wikisource_url"]
    if not url:
        return "skip", "no URL"
    page_title = url.split("/wiki/", 1)[1]
    page_title = urllib.parse.unquote(page_title)

    raw_html_path = RAW_DIR / f"{cahier}--{slug}.html"
    md_stage_path = RAW_DIR / f"{cahier}--{slug}.fr.md"
    pieces_path = PIECES_DIR / f"{cahier}--{slug}.fr.md"

    if not pieces_path.exists():
        return "error", f"no existing .fr.md at {pieces_path.relative_to(ROOT)}"

    # Multi-sub-page works: fetch each part, clean, concat with separators.
    subpage_list = SUBPAGES.get(slug)
    if subpage_list:
        parts: list[str] = []
        for i, sub in enumerate(subpage_list):
            try:
                sub_html = fetch_parsed_html(sub)
            except Exception as e:
                return "error", f"sub-fetch failed at {sub}: {e}"
            (RAW_DIR / f"{cahier}--{slug}__part{i:02d}.html").write_text(
                sub_html, encoding="utf-8")
            cleaned = clean_html(sub_html)
            try:
                parts.append(html_to_markdown(cleaned))
            except subprocess.CalledProcessError as e:
                return "error", f"pandoc failed on {sub}: {e.stderr[:200]}"
            time.sleep(0.5)
        md_body = "\n\n* * *\n\n".join(parts)
        raw_html_path.write_text(
            f"<!-- concatenated from {len(subpage_list)} sub-pages -->\n",
            encoding="utf-8")
    else:
        try:
            raw_html = fetch_parsed_html(page_title)
        except Exception as e:
            return "error", f"fetch failed: {e}"
        raw_html_path.write_text(raw_html, encoding="utf-8")
        cleaned = clean_html(raw_html)
        try:
            md_body = html_to_markdown(cleaned)
        except subprocess.CalledProcessError as e:
            return "error", f"pandoc failed: {e.stderr[:200]}"

    word_count = len(re.findall(r"\b\w+\b", md_body))
    md_stage_path.write_text(md_body, encoding="utf-8")

    existing = pieces_path.read_text(encoding="utf-8")
    fm, _old_body = parse_frontmatter(existing)
    old_wc = int(fm.get("wordCount", "0") or 0)
    # Landing-page guard, only when we DIDN'T explicitly concat sub-pages
    # and the caller didn't override (e.g. after hand-verifying the content).
    if not force and not subpage_list and old_wc > 1000 and word_count < 0.3 * old_wc:
        return "skip", (
            f"LANDING-PAGE GUARD: new={word_count}w vs existing={old_wc}w "
            f"(<30%). Page likely has sub-pages; investigate manually."
        )
    fm["wordCount"] = str(word_count)
    fm["sourceProvenance"] = (
        f'"Wikisource ({page_title}, status={row["wikisource_status"]}); '
        f'pulled {TODAY}"'
    )

    new_text = render_frontmatter(fm) + "\n" + md_body
    if dry_run:
        return "ok", f"DRY-RUN — would write {pieces_path.relative_to(ROOT)} ({word_count}w)"

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pieces_path, BACKUP_DIR / pieces_path.name)
    pieces_path.write_text(new_text, encoding="utf-8")
    return "ok", f"wrote {pieces_path.relative_to(ROOT)} ({word_count}w)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="run on a single pieceSlug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="bypass the landing-page size guard")
    ap.add_argument("--include-jc", action="store_true",
                    help="also pull use-wikisource-jc rows (DANGEROUS: cahier-split issue)")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(CSV_PATH.open()))

    eligible_actions = {"use-wikisource"}
    if args.include_jc:
        eligible_actions.add("use-wikisource-jc")

    todo = [r for r in rows if r["action"] in eligible_actions]
    if args.slug:
        todo = [r for r in todo if r["pieceSlug"] == args.slug]

    if not todo:
        print("Nothing to do.")
        return

    print(f"Processing {len(todo)} pieces (dry_run={args.dry_run})")
    print("-" * 70)
    counts = {"ok": 0, "skip": 0, "error": 0}
    for i, row in enumerate(todo, 1):
        status, msg = pull_one(row, args.dry_run, args.force)
        counts[status] += 1
        tag = {"ok": "✓", "skip": "·", "error": "✗"}[status]
        print(f"  [{i:2}/{len(todo)}] {tag} {row['cahier']:8} {row['pieceSlug'][:45]:45} {msg}")
        if i < len(todo):
            time.sleep(1.0)  # courtesy delay between API hits
    print("-" * 70)
    print(f"Done. ok={counts['ok']}  skip={counts['skip']}  error={counts['error']}")


if __name__ == "__main__":
    main()
