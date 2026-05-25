#!/usr/bin/env python3.11
"""
Migrate content from ~/charlespeguy.com/ to ~/charlespeguy.org/.

- Reads catalog.ts (229 cahiers) + contributors.ts (~30 authors) via regex.
- Reads FR (src/content/texts/) + EN (src/content/translations/) markdown files.
- Writes Astro 6 content collections:
    - src/data/cahiers/<slug>.json
    - src/content/authors/<slug>.md
    - src/content/pieces/<cahier-slug>--<piece-slug>.<lang>.md
    - src/content/works/<slug>.md

Idempotent: rewrites files cleanly each run.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

SRC_REPO = Path("/Users/wilsonpruitt/charlespeguy.com")
DST_REPO = Path("/Users/wilsonpruitt/charlespeguy.org")

CATALOG_TS = SRC_REPO / "scripts/catalog.ts"
CONTRIBUTORS_TS = SRC_REPO / "src/data/contributors.ts"
TEXTS_DIR = SRC_REPO / "src/content/texts"
TRANSLATIONS_DIR = SRC_REPO / "src/content/translations"

CAHIERS_OUT = DST_REPO / "src/data/cahiers"
AUTHORS_OUT = DST_REPO / "src/content/authors"
PIECES_OUT = DST_REPO / "src/content/pieces"
WORKS_OUT = DST_REPO / "src/content/works"

FRENCH_ORDINALS = {
    1: "Premier", 2: "Deuxième", 3: "Troisième", 4: "Quatrième",
    5: "Cinquième", 6: "Sixième", 7: "Septième", 8: "Huitième",
    9: "Neuvième", 10: "Dixième", 11: "Onzième", 12: "Douzième",
    13: "Treizième", 14: "Quatorzième", 15: "Quinzième", 16: "Seizième",
    17: "Dix-septième", 18: "Dix-huitième", 19: "Dix-neuvième", 20: "Vingtième",
    21: "Vingt-et-unième", 22: "Vingt-deuxième", 23: "Vingt-troisième",
}


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------

def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )


def slugify(s: str) -> str:
    s = strip_accents(s or "")
    s = s.lower()
    s = re.sub(r"['’‘]", " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def cahier_slug(series: int, issue: int) -> str:
    return f"s{series:02d}-c{issue:02d}"


# ---------------------------------------------------------------------------
# Parse catalog.ts
# ---------------------------------------------------------------------------

CATALOG_LINE_RE = re.compile(
    r"\{\s*series:\s*(\d+),\s*issue:\s*(\d+),\s*label:\s*'([^']+)',\s*"
    r"url:\s*'([^']+)',\s*description:\s*'((?:[^'\\]|\\.)*)'\s*\}"
)


def parse_catalog() -> list[dict]:
    src = CATALOG_TS.read_text(encoding="utf-8")
    entries = []
    for m in CATALOG_LINE_RE.finditer(src):
        series = int(m.group(1))
        issue = int(m.group(2))
        label = m.group(3)
        url = m.group(4)
        # unescape \' and \\
        description = m.group(5).replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")
        entries.append({
            "series": series,
            "issue": issue,
            "label": label,
            "url": url,
            "description": description,
        })
    return entries


# ---------------------------------------------------------------------------
# Parse contributors.ts
# ---------------------------------------------------------------------------

CONTRIB_RE = re.compile(
    r'\{\s*name:\s*"((?:[^"\\]|\\.)*)",\s*slug:\s*"((?:[^"\\]|\\.)*)",\s*'
    r'dates:\s*"((?:[^"\\]|\\.)*)",\s*'
    r'bioFr:\s*`((?:[^`\\]|\\.)*)`,\s*'
    r'bioEn:\s*`((?:[^`\\]|\\.)*)`\s*\}',
    re.DOTALL,
)


def parse_contributors() -> list[dict]:
    src = CONTRIBUTORS_TS.read_text(encoding="utf-8")
    out = []
    for m in CONTRIB_RE.finditer(src):
        out.append({
            "name": m.group(1),
            "slug": m.group(2),
            "dates": m.group(3),
            "bioFr": m.group(4).strip(),
            "bioEn": m.group(5).strip(),
        })
    return out


def parse_dates(dates: str) -> tuple[str | None, str | None]:
    """Return (born, died) as ISO-ish strings. Handles '1873–1914', '1874–1953 / 1877–1952', etc."""
    if not dates:
        return None, None
    # Split on slash for paired (e.g. Tharaud brothers) — take first
    first = dates.split("/")[0].strip()
    parts = re.split(r"[–—\-]", first)
    parts = [p.strip() for p in parts if p.strip()]
    born = parts[0] if parts else None
    died = parts[1] if len(parts) > 1 else None
    # Strip non-digits except hyphen
    def clean(s):
        if not s:
            return None
        m = re.match(r"(\d{3,4})", s)
        return m.group(1) if m else None
    return clean(born), clean(died)


# ---------------------------------------------------------------------------
# Parse FR/EN cahier markdown
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_md(path: Path) -> tuple[dict, str] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        print(f"  YAML error in {path.name}: {e}", file=sys.stderr)
        return None
    body = m.group(2)
    return fm, body


def split_body_into_pieces(body: str, piece_titles: list[str]) -> list[str]:
    """
    Split body at '## ' headings. Return list aligned with piece_titles.
    If split count doesn't match, do best-effort: single body -> single piece.
    """
    # Split at lines starting with '## ' (level-2 headings)
    sections = re.split(r"(?m)^##\s+", body)
    # sections[0] is preamble before first '## ' heading (might be empty or intro junk)
    # sections[1..] each starts with the heading text
    heads_and_bodies = []
    for i, sec in enumerate(sections):
        if i == 0:
            # preamble - ignore unless no '##' splits happened
            continue
        nl = sec.find("\n")
        if nl == -1:
            heads_and_bodies.append((sec.strip(), ""))
        else:
            heads_and_bodies.append((sec[:nl].strip(), sec[nl + 1:]))

    # If no '##' splits found, the whole body belongs to whatever pieces exist
    if not heads_and_bodies:
        if len(piece_titles) == 1:
            return [body.strip()]
        # Multiple pieces but no headings — assign all to first, stubs to rest
        out = [body.strip()]
        out.extend([""] * (len(piece_titles) - 1))
        return out

    # If only one piece, the entire body (including preamble) belongs to it
    if len(piece_titles) == 1:
        return [body.strip()]

    # Try to match sections to piece titles by slug fuzzy
    title_slugs = [slugify(t) for t in piece_titles]
    matched: list[str | None] = [None] * len(piece_titles)
    unmatched_sections: list[tuple[str, str]] = []
    for head, sec_body in heads_and_bodies:
        head_slug = slugify(head)
        placed = False
        # Exact match
        for i, ts in enumerate(title_slugs):
            if matched[i] is None and (head_slug == ts or head_slug.startswith(ts) or ts.startswith(head_slug)):
                matched[i] = sec_body.strip()
                placed = True
                break
        if not placed:
            unmatched_sections.append((head, sec_body))

    # Fill missing in order with unmatched
    j = 0
    for i in range(len(matched)):
        if matched[i] is None:
            if j < len(unmatched_sections):
                head, sec_body = unmatched_sections[j]
                matched[i] = f"## {head}\n{sec_body}".strip()
                j += 1
            else:
                matched[i] = ""

    # Append any leftover unmatched sections to the last piece
    if j < len(unmatched_sections):
        leftover = "\n\n".join(f"## {h}\n{b}" for h, b in unmatched_sections[j:])
        matched[-1] = (matched[-1] or "") + "\n\n" + leftover

    return [m or "" for m in matched]


# ---------------------------------------------------------------------------
# Author resolution
# ---------------------------------------------------------------------------

class AuthorRegistry:
    def __init__(self, contributors: list[dict]):
        self.by_slug: dict[str, dict] = {}
        self.name_to_slug: dict[str, str] = {}
        for c in contributors:
            self.by_slug[c["slug"]] = c
            self._index_name(c["name"], c["slug"])
        # Common alias seeds
        self._alias("charles peguy", "charles-peguy")
        self._alias("ch peguy", "charles-peguy")
        self._alias("charles péguy", "charles-peguy")
        self._alias("suares", "andre-suares")  # may be auto-created
        self._alias("andre suares", "andre-suares")
        self._alias("andré suarès", "andre-suares")
        self._alias("jerome et jean tharaud", "jerome-et-jean-tharaud")
        self._alias("jérôme et jean tharaud", "jerome-et-jean-tharaud")

    def _norm(self, name: str) -> str:
        return re.sub(r"\s+", " ", strip_accents(name).lower().strip())

    def _index_name(self, name: str, slug: str):
        self.name_to_slug[self._norm(name)] = slug

    def _alias(self, name: str, slug: str):
        self.name_to_slug.setdefault(self._norm(name), slug)

    def resolve(self, name: str) -> str:
        """Return slug. Create stub if missing."""
        if not name:
            return self.ensure_stub("Anonymous", "anonymous")
        norm = self._norm(name)
        if norm in self.name_to_slug:
            return self.name_to_slug[norm]
        # Try substring match against existing
        for n, s in list(self.name_to_slug.items()):
            if n in norm or norm in n:
                if abs(len(n) - len(norm)) <= 3:
                    self.name_to_slug[norm] = s
                    return s
        # Create new stub
        slug = slugify(name)
        return self.ensure_stub(name, slug)

    def ensure_stub(self, name: str, slug: str) -> dict:
        if slug not in self.by_slug:
            self.by_slug[slug] = {
                "name": name,
                "slug": slug,
                "dates": "",
                "bioFr": "Notice biographique à venir.",
                "bioEn": "Bio pending.",
                "_stub": True,
            }
            self._index_name(name, slug)
            return slug
        return slug

    def all(self) -> list[dict]:
        return list(self.by_slug.values())


# ---------------------------------------------------------------------------
# Description parser for fallback piece derivation
# ---------------------------------------------------------------------------

UPPERCASE_AUTHOR_RE = re.compile(r"\b([A-Z][A-ZÀ-Ü\s\.]{2,}?)\.\s+")


def derive_pieces_from_description(desc: str) -> list[dict]:
    """
    Best-effort: parse 'AUTHOR. Title. AUTHOR2. Title.' into list of {title, author}.
    Fallback when frontmatter pieces array missing.
    """
    pieces = []
    # Strip leading parenthetical like "(Gallica) "
    desc = re.sub(r"^\([^)]+\)\s*", "", desc)
    # Find author markers (UPPERCASE NAME followed by .)
    parts = re.split(r"\b([A-Z][A-ZÀ-Ü]{2,}(?:\s+(?:ET\s+)?[A-Z][A-ZÀ-Ü]{2,})*)\.\s+", desc)
    # parts: [pre, AUTHOR1, content1, AUTHOR2, content2, ...]
    if len(parts) <= 1:
        # No uppercase author markers — single piece, no author
        title = desc.strip().rstrip(".").strip()
        if title:
            pieces.append({"title": title, "author": ""})
        return pieces

    pre = parts[0].strip()
    if pre:
        # Editorial content before first author (e.g. "Les Milliet. VI. ...")
        pieces.append({"title": pre.rstrip("."), "author": ""})

    i = 1
    current_author = ""
    while i < len(parts):
        if i + 1 < len(parts):
            author = parts[i].strip().title()
            content = parts[i + 1].strip()
            # Split content on '. ' to get individual titles
            titles = [t.strip().rstrip(".") for t in re.split(r"\.\s+", content) if t.strip()]
            for t in titles:
                if t:
                    pieces.append({"title": t, "author": author})
            current_author = author
            i += 2
        else:
            i += 1

    return pieces


# ---------------------------------------------------------------------------
# YAML/JSON output helpers
# ---------------------------------------------------------------------------

def write_yaml_frontmatter(data: dict, body: str) -> str:
    fm = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{fm}---\n\n{body.strip()}\n"


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def main():
    print("Parsing catalog...")
    catalog = parse_catalog()
    print(f"  {len(catalog)} cahier entries")

    print("Parsing contributors...")
    contributors = parse_contributors()
    print(f"  {len(contributors)} contributors")

    registry = AuthorRegistry(contributors)

    # Ensure output directories
    for d in [CAHIERS_OUT, AUTHORS_OUT, PIECES_OUT, WORKS_OUT]:
        d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Pass 1: gather all cahier piece info (read both FR/EN frontmatters)
    # ------------------------------------------------------------------
    cahier_records = []  # parallel list

    for entry in catalog:
        series = entry["series"]
        issue = entry["issue"]
        slug = cahier_slug(series, issue)
        fr_path = TEXTS_DIR / f"{slug}.md"
        en_path = TRANSLATIONS_DIR / f"{slug}.md"

        fr = parse_md(fr_path)
        en = parse_md(en_path)

        # Pieces list — prefer FR frontmatter, then EN, then derive
        fm_pieces = None
        date_fm = None
        if fr:
            fm_pieces = fr[0].get("pieces")
            date_fm = fr[0].get("date")
        if not fm_pieces and en:
            fm_pieces = en[0].get("pieces")
            if not date_fm:
                date_fm = en[0].get("date")
        if not fm_pieces:
            fm_pieces = derive_pieces_from_description(entry["description"])

        # Normalize pieces and dedupe slugs within cahier
        normalized = []
        used_slugs = set()
        for p in fm_pieces or []:
            title = (p.get("title") or "").strip()
            author = (p.get("author") or "").strip()
            if not title:
                continue
            base_slug = slugify(title)
            pslug = base_slug
            n = 2
            while pslug in used_slugs:
                pslug = f"{base_slug}-{n}"
                n += 1
            used_slugs.add(pslug)
            normalized.append({
                "slug": pslug,
                "title": title,
                "author": author,
                "isAvertissement": title.lower().startswith("avertissement")
                                  or title.lower().startswith("avis"),
            })

        if not normalized:
            # Cahier with truly no parseable pieces — make one stub piece using description
            normalized.append({
                "slug": "contenu",
                "title": entry["description"][:80].rstrip(".") or "Contenu",
                "author": "",
                "isAvertissement": False,
            })

        cahier_records.append({
            "entry": entry,
            "slug": slug,
            "pieces": normalized,
            "fr": fr,
            "en": en,
            "date": date_fm,
        })

    # ------------------------------------------------------------------
    # Pass 2: register all authors (so stubs exist before write)
    # ------------------------------------------------------------------
    for rec in cahier_records:
        for p in rec["pieces"]:
            author_name = p["author"] or "Anonymous"
            p["author_slug"] = registry.resolve(author_name)

    # ------------------------------------------------------------------
    # Pass 3: write authors
    # ------------------------------------------------------------------
    n_authors = 0
    for a in registry.all():
        slug = a["slug"]
        name = a["name"]
        born, died = parse_dates(a.get("dates", ""))
        # nameSort: last-name-first
        parts = name.split()
        if len(parts) >= 2 and "et" not in [p.lower() for p in parts]:
            name_sort = f"{parts[-1]}, {' '.join(parts[:-1])}"
        else:
            name_sort = name
        fm = {
            "slug": slug,
            "name": name,
            "nameSort": name_sort,
        }
        if born:
            fm["born"] = born
        if died:
            fm["died"] = died
        if slug == "charles-peguy":
            fm["isEditor"] = True

        bio_fr = a.get("bioFr", "Notice biographique à venir.")
        bio_en = a.get("bioEn", "Bio pending.")
        body = f"## En français\n\n{bio_fr}\n\n## In English\n\n{bio_en}"

        (AUTHORS_OUT / f"{slug}.md").write_text(write_yaml_frontmatter(fm, body), encoding="utf-8")
        n_authors += 1
    print(f"Wrote {n_authors} authors")

    # ------------------------------------------------------------------
    # Pass 4: write cahier JSON
    # ------------------------------------------------------------------
    n_cahiers = 0
    for rec in cahier_records:
        entry = rec["entry"]
        series = entry["series"]
        issue = entry["issue"]
        slug = rec["slug"]
        title_fr = f"{FRENCH_ORDINALS.get(issue, str(issue))} cahier de la {FRENCH_ORDINALS.get(series, str(series)).lower()} série"

        pieces_json = []
        for p in rec["pieces"]:
            pj = {
                "slug": p["slug"],
                "titleFr": p["title"],
                "author": p["author_slug"],
                "isAvertissement": p["isAvertissement"],
            }
            pieces_json.append(pj)

        obj: dict[str, Any] = {
            "slug": slug,
            "series": series,
            "issue": issue,
            "label": entry["label"],
            "titleFr": title_fr,
            "sourceUrl": entry["url"],
            "pieces": pieces_json,
            "partOfWorks": [],
        }
        if rec.get("date"):
            obj["bonATirer"] = str(rec["date"])

        (CAHIERS_OUT / f"{slug}.json").write_text(
            json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        n_cahiers += 1
    print(f"Wrote {n_cahiers} cahier JSON files")

    # ------------------------------------------------------------------
    # Pass 5: write piece markdown (FR + EN)
    # ------------------------------------------------------------------
    n_pieces = 0
    for rec in cahier_records:
        slug = rec["slug"]
        pieces = rec["pieces"]
        piece_titles = [p["title"] for p in pieces]

        for lang_key, parsed in (("fr", rec["fr"]), ("en", rec["en"])):
            if not parsed:
                continue
            _fm, body = parsed
            split = split_body_into_pieces(body, piece_titles)

            for i, p in enumerate(pieces):
                prose = split[i] if i < len(split) else ""
                word_count = len(prose.split())
                fm = {
                    "cahier": slug,
                    "pieceSlug": p["slug"],
                    "lang": lang_key,
                    "title": p["title"],
                    "author": p["author_slug"],
                    "isAvertissement": p["isAvertissement"],
                    "wordCount": word_count,
                }
                fname = f"{slug}--{p['slug']}.{lang_key}.md"
                (PIECES_OUT / fname).write_text(
                    write_yaml_frontmatter(fm, prose),
                    encoding="utf-8",
                )
                n_pieces += 1
    print(f"Wrote {n_pieces} piece markdown files")

    # ------------------------------------------------------------------
    # Pass 6: write works
    # ------------------------------------------------------------------
    # Build an index of (cahier_slug -> [piece_slug, title]) for membership tests
    cahier_pieces = {rec["slug"]: rec["pieces"] for rec in cahier_records}

    def find_piece(cahier_slug_str: str, *keywords: str) -> tuple[str, str] | None:
        """Return (cahier_slug, piece_slug) for first piece whose title contains all keywords (case-insensitive, accent-stripped)."""
        pieces = cahier_pieces.get(cahier_slug_str, [])
        for p in pieces:
            t = strip_accents(p["title"]).lower()
            if all(strip_accents(k).lower() in t for k in keywords):
                return cahier_slug_str, p["slug"]
        # Fallback: first piece
        if pieces:
            return cahier_slug_str, pieces[0]["slug"]
        return None

    def parts_from(cahiers_and_keywords: list[tuple[str, list[str], str]]) -> list[dict]:
        out = []
        for c_slug, keywords, label in cahiers_and_keywords:
            found = find_piece(c_slug, *keywords)
            if found:
                out.append({"cahier": found[0], "piece": found[1], "label": label})
        return out

    # Jean-Christophe installments by cahier (from catalog descriptions)
    jc_cahiers = [
        ("s05-c12", ["jean-christophe"], "L'aube"),
        ("s06-c01", ["matin"], "Le matin"),
        ("s06-c10", ["adolescent"], "L'adolescent"),
        ("s07-c01", ["revolte"], "La Révolte 1"),
        ("s07-c02", ["revolte"], "La Révolte 2"),
        ("s07-c10", ["foire"], "La Foire sur la Place 1"),
        ("s08-c08", ["foire"], "La Foire sur la Place 2"),
        ("s09-c03", ["antoinette"], "Antoinette"),
        ("s09-c07", ["dans la maison"], "Dans la maison 1"),
        ("s09-c11", ["dans la maison"], "Dans la maison 2"),
        ("s10-c10", ["amies"], "Les Amies"),
        ("s13-c05", ["buisson"], "Le Buisson ardent 1"),
        ("s13-c06", ["buisson"], "Le Buisson ardent 2"),
        ("s14-c02", ["nouvelle journee"], "La Nouvelle Journée 1"),
        ("s14-c03", ["nouvelle journee"], "La Nouvelle Journée 2"),
    ]

    vuillaume_cahiers = [
        ("s11-c08", ["mes cahiers rouges"], "I"),
        ("s11-c11", ["mes cahiers rouges"], "II"),
        ("s12-c01", ["mes cahiers rouges"], "III"),
        ("s12-c04", ["mes cahiers rouges"], "IV"),
        ("s12-c06", ["mes cahiers rouges"], "V"),
        ("s13-c11", ["mes cahiers rouges"], "VIII"),
        ("s14-c11", ["mes cahiers rouges"], "IX"),
        ("s15-c09", ["mes cahiers rouges"], "X"),
    ]

    milliet_cahiers = [
        ("s11-c09", ["milliet"], "I"),
        ("s11-c12", ["milliet"], "II"),
        ("s12-c02", ["milliet"], "III"),
        ("s12-c05", ["milliet"], "IV"),
        ("s12-c08", ["milliet"], "VI"),
        ("s12-c10", ["milliet"], "VII"),
        ("s13-c01", ["milliet"], "VIII"),
        ("s13-c03", ["milliet"], "IX"),
        ("s13-c07", ["milliet"], "X"),
        ("s13-c09", ["milliet"], "XI"),
    ]

    ordination_cahiers = [
        ("s12-c09", ["ordination"], "L'Ordination"),
        ("s14-c04", ["ordination"], "L'Ordination II — La chute"),
    ]

    mysteres_cahiers = [
        ("s11-c06", ["jeanne"], "Mystère de la charité de Jeanne d'Arc"),
        ("s13-c04", ["porche"], "Le porche du mystère de la deuxième vertu"),
        ("s13-c12", ["innocents"], "Le mystère des saints Innocents"),
    ]

    works_to_write = [
        {
            "slug": "jean-christophe",
            "title": "Jean-Christophe",
            "author": registry.resolve("Romain Rolland"),
            "parts": parts_from(jc_cahiers),
            "yearSpan": "1904–1912",
            "body": (
                "Romain Rolland's roman-fleuve, ten volumes long, ran in the *Cahiers de la Quinzaine* "
                "from 1904 to 1912. Following the German-born composer Jean-Christophe Krafft from childhood "
                "in a Rhenish town to old age in Paris and Switzerland, the novel braids music, friendship, "
                "and European cultural politics into a single arc. It was the *Cahiers'* commercial flagship "
                "and won Rolland the Nobel Prize in 1915. The installments here are reprinted in their "
                "original Quinzaine sequence."
            ),
        },
        {
            "slug": "mes-cahiers-rouges",
            "title": "Mes cahiers rouges",
            "author": registry.resolve("Maxime Vuillaume"),
            "parts": parts_from(vuillaume_cahiers),
            "yearSpan": "1909–1914",
            "body": (
                "Maxime Vuillaume — once a young red-cahier editor during the Paris Commune — gave Péguy "
                "his memoirs to publish in installments from 1909 onward. *Mes cahiers rouges* recounts "
                "the seventy-two days of the Commune from the inside, with the texture of a participant's "
                "notebook rather than a historian's narrative. The series is one of the most important "
                "primary sources for the Commune that the Quinzaine ever printed."
            ),
        },
        {
            "slug": "les-milliet",
            "title": "Les Milliet",
            "author": registry.resolve("Paul Milliet"),
            "parts": parts_from(milliet_cahiers),
            "yearSpan": "1909–1912",
            "body": (
                "Edited by Paul Milliet from his family papers, *Les Milliet* is an eleven-volume family "
                "chronicle that traces several generations of a French bourgeois family through the long "
                "nineteenth century — Italian travels, the Franco-Prussian war, the Commune, and the "
                "moral and artistic life of provincial France. Péguy ran it across three series of the "
                "*Cahiers*, treating it as a documentary counterweight to Rolland's fiction."
            ),
        },
        {
            "slug": "lordination",
            "title": "L'Ordination",
            "author": registry.resolve("Julien Benda"),
            "parts": parts_from(ordination_cahiers),
            "yearSpan": "1911–1913",
            "body": (
                "Julien Benda's two-part novel *L'Ordination* — followed in series XIV by *La Chute* — "
                "is the story of a young intellectual ordained into the secular priesthood of letters. "
                "Benda, later famous for *La Trahison des clercs*, was at this point one of the *Cahiers'* "
                "most distinctive prose voices, and Péguy gave the work two full cahiers to itself."
            ),
        },
        {
            "slug": "les-mysteres",
            "title": "Les Mystères",
            "author": registry.resolve("Charles Péguy"),
            "parts": parts_from(mysteres_cahiers),
            "yearSpan": "1910–1912",
            "body": (
                "Péguy's three *Mystères* — *Le mystère de la charité de Jeanne d'Arc* (1910), *Le porche "
                "du mystère de la deuxième vertu* (1911), and *Le mystère des saints Innocents* (1912) — "
                "form the spine of his mature religious poetry. Written in long unrhymed verse paragraphs "
                "that the *Cahiers* set as prose, they re-cast hope, charity, and martyrdom as the patient "
                "speech of God and the saints. They are among the only works Péguy published in the "
                "*Cahiers* that were also reissued in his lifetime as books."
            ),
        },
    ]

    n_works = 0
    for w in works_to_write:
        slug = w["slug"]
        fm = {
            "slug": slug,
            "title": w["title"],
            "author": w["author"],
            "parts": w["parts"],
        }
        if w.get("yearSpan"):
            fm["yearSpan"] = w["yearSpan"]
        (WORKS_OUT / f"{slug}.md").write_text(write_yaml_frontmatter(fm, w["body"]), encoding="utf-8")
        n_works += 1
    print(f"Wrote {n_works} works")

    # Summary
    print()
    print("=== SUMMARY ===")
    print(f"cahiers: {n_cahiers}")
    print(f"authors: {n_authors}")
    print(f"pieces:  {n_pieces}")
    print(f"works:   {n_works}")


if __name__ == "__main__":
    main()
