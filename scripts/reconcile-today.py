#!/usr/bin/env python3
"""
Reconcile today's (2026-05-24) OCR + translation work from ~/charlespeguy.com/
into ~/charlespeguy.org/. Idempotent. Surgical — only touches the cahiers
listed in scope.

Run: python3 scripts/reconcile-today.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

COM = Path.home() / "charlespeguy.com"
ORG = Path.home() / "charlespeguy.org"
RAW = COM / "raw"
TRANSLATIONS = COM / "src" / "content" / "translations"
PIECES = ORG / "src" / "content" / "pieces"
CAHIERS = ORG / "src" / "data" / "cahiers"
AUTHORS = ORG / "src" / "content" / "authors"

OCR_SOURCE = "Archive.org vision OCR 2026-05-24 (see PROGRESS.md)"
TRANSLATION_DATE = "2026-05-24"

# ---------------------------------------------------------------------------
# FR scope: raw OCR file -> cahier slug. Whole body goes to first piece if
# multi-piece (cf. s13-c11 -> mes-cahiers-rouges).
# ---------------------------------------------------------------------------
FR_SCOPE = [
    ("s05-c11", "s05-c11-ocr.txt"),
    ("s05-c12", "s05-c12-ocr.txt"),
    ("s09-c14", "s09-c14-ocr.txt"),
    ("s11-c03", "s11-c03-ocr.txt"),
    ("s12-c05", "s12-c05-ocr.txt"),
    ("s12-c09", "s12-c09-ocr.txt"),
    ("s12-c10", "s12-c10-ocr.txt"),
    ("s13-c11", "s13-c11-ocr.txt"),
    ("s15-c03", "s15-c03-la-loi-militaire.txt"),
    ("s15-c09", "s15-c09-ocr.txt"),
]

EN_SCOPE = [
    "s01-c05", "s02-c16", "s04-c17", "s09-c14", "s11-c04",
    "s13-c02", "s13-c07", "s13-c11", "s14-c02", "s14-c03", "s15-c06",
]

report = {"fr": {}, "en": {}, "metadata": [], "notes": []}


def strip_ocr_header(text: str) -> str:
    """Strip leading lines that start with '#' (OCR provenance comments)."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (lines[i].startswith("#") or lines[i].strip() == ""):
        # only skip header block until first non-# line that has content
        if not lines[i].startswith("#") and lines[i].strip() == "":
            i += 1
            continue
        if lines[i].startswith("#"):
            i += 1
            continue
        break
    # also strip leading blank lines
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    return "\n".join(lines[i:]).rstrip() + "\n"


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def yaml_escape(s: str) -> str:
    """Quote for YAML if contains special chars."""
    if any(c in s for c in [":", "#", "'", '"', "\n"]) or s != s.strip():
        return json.dumps(s, ensure_ascii=False)
    return s


def write_piece(cahier_slug: str, piece_slug: str, lang: str, *, title: str,
                author: str, is_avertissement: bool, body: str,
                translation_notes: str | None = None,
                ocr_source: str | None = None,
                translation_date: str | None = None) -> Path:
    fm_lines = [
        "---",
        f"cahier: {cahier_slug}",
        f"pieceSlug: {piece_slug}",
        f"lang: {lang}",
        f"title: {yaml_escape(title)}",
        f"author: {author}",
        f"isAvertissement: {'true' if is_avertissement else 'false'}",
    ]
    if ocr_source:
        fm_lines.append(f"ocrSource: {yaml_escape(ocr_source)}")
    if translation_date:
        fm_lines.append(f'translationDate: "{translation_date}"')
    if translation_notes:
        fm_lines.append(f"translationNotes: {yaml_escape(translation_notes)}")
    fm_lines.append(f"wordCount: {word_count(body)}")
    fm_lines.append("---")
    fm_lines.append("")
    fm_lines.append(body.rstrip() + "\n")
    path = PIECES / f"{cahier_slug}--{piece_slug}.{lang}.md"
    path.write_text("\n".join(fm_lines), encoding="utf-8")
    return path


def load_cahier(slug: str) -> dict:
    return json.loads((CAHIERS / f"{slug}.json").read_text(encoding="utf-8"))


def save_cahier(slug: str, data: dict) -> None:
    (CAHIERS / f"{slug}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Process FR cahiers
# ---------------------------------------------------------------------------
def process_fr() -> None:
    for cahier_slug, raw_name in FR_SCOPE:
        raw_path = RAW / raw_name
        if not raw_path.exists():
            report["notes"].append(f"FR {cahier_slug}: raw file missing: {raw_path}")
            continue
        text = raw_path.read_text(encoding="utf-8", errors="replace")
        body = strip_ocr_header(text)

        cahier = load_cahier(cahier_slug)
        pieces = cahier.get("pieces", [])
        if not pieces:
            report["notes"].append(f"FR {cahier_slug}: cahier has no pieces")
            continue

        first = pieces[0]
        notes = None
        if len(pieces) > 1:
            notes = "FR text is the whole-cahier OCR; per-piece split pending."

        write_piece(
            cahier_slug=cahier_slug,
            piece_slug=first["slug"],
            lang="fr",
            title=first["titleFr"],
            author=first["author"],
            is_avertissement=first.get("isAvertissement", False),
            body=body,
            ocr_source=OCR_SOURCE,
            translation_notes=notes,
        )
        report["fr"][cahier_slug] = {
            "pieces_written": 1,
            "target_piece": first["slug"],
            "multi_piece_fallback": len(pieces) > 1,
            "word_count": word_count(body),
        }


# ---------------------------------------------------------------------------
# Process EN translations
# ---------------------------------------------------------------------------
TRANS_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_translation_file(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    m = TRANS_FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    fm_text, body = m.group(1), m.group(2)
    # We only need pieces list — naive parse: look for `pieces:` block
    fm = {}
    # Just return raw body — we'll split on ## headings
    return fm, body


def split_en_pieces(body: str) -> list[tuple[str, str]]:
    """Split body on top-level '## ' headings. Returns [(title, content), ...]."""
    # Match lines that start with exactly '## ' (not ### or more)
    parts = re.split(r"(?m)^## (?!#)", body)
    # First part is whatever comes before first ##
    sections = []
    if parts and parts[0].strip():
        # preamble — usually empty; ignore
        pass
    for chunk in parts[1:]:
        # First line is the title
        lines = chunk.split("\n", 1)
        title = lines[0].strip()
        content = lines[1] if len(lines) > 1 else ""
        sections.append((title, content.strip()))
    return sections


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[‘’“”]", "", s)
    s = re.sub(r"[^\w\s-]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s


def process_en() -> None:
    for cahier_slug in EN_SCOPE:
        trans_path = TRANSLATIONS / f"{cahier_slug}.md"
        if not trans_path.exists():
            report["notes"].append(f"EN {cahier_slug}: translation file missing")
            continue
        _, body = parse_translation_file(trans_path)
        sections = split_en_pieces(body)

        cahier = load_cahier(cahier_slug)
        pieces = cahier.get("pieces", [])
        if not pieces:
            report["notes"].append(f"EN {cahier_slug}: cahier has no pieces")
            continue

        # Single-piece fast path
        if len(pieces) == 1:
            first = pieces[0]
            if not sections:
                # No ## split — use whole body
                content = body.strip()
            elif len(sections) == 1:
                # Re-attach heading as it provides the title context
                title, content = sections[0]
                content = f"## {title}\n\n{content}"
            else:
                # Multi-section in a single-piece cahier; concatenate all
                content = "\n\n".join(f"## {t}\n\n{c}" for t, c in sections)
            write_piece(
                cahier_slug=cahier_slug,
                piece_slug=first["slug"],
                lang="en",
                title=first.get("titleEn") or first["titleFr"],
                author=first["author"],
                is_avertissement=first.get("isAvertissement", False),
                body=content,
                translation_date=TRANSLATION_DATE,
            )
            report["en"][cahier_slug] = {
                "pieces_written": 1,
                "target_piece": first["slug"],
                "word_count": word_count(content),
            }
            continue

        # Multi-piece: fuzzy slug match
        piece_slugs = [p["slug"] for p in pieces]
        assigned = {p["slug"]: [] for p in pieces}
        unmatched = []
        for title, content in sections:
            tslug = slugify(title)
            # match: piece slug appears in title slug, or vice versa
            best = None
            for pslug in piece_slugs:
                if pslug in tslug or tslug in pslug:
                    best = pslug
                    break
            if best:
                assigned[best].append(f"## {title}\n\n{content}")
            else:
                unmatched.append(f"## {title}\n\n{content}")

        if unmatched:
            # Dump into last piece
            assigned[piece_slugs[-1]].extend(unmatched)
            report["notes"].append(
                f"EN {cahier_slug}: {len(unmatched)} unmatched section(s) appended to last piece"
            )

        written = 0
        for p in pieces:
            chunks = assigned[p["slug"]]
            if not chunks:
                continue
            content = "\n\n".join(chunks)
            write_piece(
                cahier_slug=cahier_slug,
                piece_slug=p["slug"],
                lang="en",
                title=p.get("titleEn") or p["titleFr"],
                author=p["author"],
                is_avertissement=p.get("isAvertissement", False),
                body=content,
                translation_date=TRANSLATION_DATE,
            )
            written += 1
        report["en"][cahier_slug] = {
            "pieces_written": written,
            "sections_total": len(sections),
        }


# ---------------------------------------------------------------------------
# Metadata corrections
# ---------------------------------------------------------------------------
def ensure_author_adrien_de_tuce() -> None:
    path = AUTHORS / "adrien-de-tuce.md"
    if path.exists():
        return
    path.write_text(
        """---
slug: adrien-de-tuce
name: "Adrien de Tucé"
nameSort: "Tucé, Adrien de"
nationality: "French"
---

Adrien de Tucé, frère de Madame Milliet, dont les lettres du Mexique
(1862–1867) ont été éditées par Paul Milliet et publiées dans le septième
volume des *Milliet* (Cahiers de la Quinzaine, douzième série, cahier 10,
bon à tirer 20 juin 1911). Notice biographique à venir.

Bio pending.
""",
        encoding="utf-8",
    )
    report["metadata"].append("Created author file adrien-de-tuce.md")


def fix_metadata() -> None:
    # 1. s12-c09 — verify author is julien-benda (no change needed if already)
    s12c09 = load_cahier("s12-c09")
    changed = False
    for p in s12c09["pieces"]:
        if p["author"] != "julien-benda":
            p["author"] = "julien-benda"
            changed = True
    if changed:
        save_cahier("s12-c09", s12c09)
        report["metadata"].append("s12-c09.json: author -> julien-benda")
    else:
        report["metadata"].append("s12-c09.json: author already julien-benda (no change)")

    # 2. s12-c10 — change 'ii' / 'paul-milliet' authors to 'adrien-de-tuce' on
    # the Cinq ans / Adrien-de-Tuce pieces; ensure Péguy postface present.
    ensure_author_adrien_de_tuce()
    s12c10 = load_cahier("s12-c10")
    for p in s12c10["pieces"]:
        if p["slug"] in {"cinq-ans-au-mexique", "adrien-de-tuce"}:
            if p["author"] != "adrien-de-tuce":
                p["author"] = "adrien-de-tuce"
        if p["slug"] == "les-milliet" and p["author"] == "paul-milliet":
            # leave as-is; the user only said change the Tucé attribution
            pass
    # Add Péguy postface piece if not present
    slugs = {p["slug"] for p in s12c10["pieces"]}
    if "oeuvres-choisies-postface" not in slugs:
        s12c10["pieces"].append({
            "slug": "oeuvres-choisies-postface",
            "titleFr": "Œuvres choisies (postface)",
            "author": "charles-peguy",
            "isAvertissement": False,
            "pages": "153-172",
        })
        report["metadata"].append("s12-c10.json: appended oeuvres-choisies-postface piece (charles-peguy)")
    save_cahier("s12-c10", s12c10)
    report["metadata"].append("s12-c10.json: ii -> adrien-de-tuce on tuce/cinq-ans pieces")

    # 3. s15-c09 — title should be 'Proscrits' not 'Exilés'
    s15c09 = load_cahier("s15-c09")
    changed = False
    for p in s15c09["pieces"]:
        if "Exilés" in p.get("titleFr", ""):
            p["titleFr"] = p["titleFr"].replace("Exilés", "Proscrits")
            changed = True
    if changed:
        save_cahier("s15-c09", s15c09)
        report["metadata"].append("s15-c09.json: Exilés -> Proscrits")
    else:
        report["metadata"].append("s15-c09.json: already Proscrits (no change)")


# ---------------------------------------------------------------------------
def main() -> int:
    process_fr()
    process_en()
    fix_metadata()

    print("\n=== RECONCILE REPORT ===")
    print("\nFR cahiers:")
    for k, v in sorted(report["fr"].items()):
        print(f"  {k}: {v}")
    print("\nEN cahiers:")
    for k, v in sorted(report["en"].items()):
        print(f"  {k}: {v}")
    print("\nMetadata:")
    for m in report["metadata"]:
        print(f"  - {m}")
    if report["notes"]:
        print("\nNotes:")
        for n in report["notes"]:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
