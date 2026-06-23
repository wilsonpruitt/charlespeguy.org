"""
Build wikisource-audit.csv — one row per piece, tiered by Wikisource likelihood.

Tier 1: canonical authors (Péguy, Rolland, Tolstoï) — Wikisource holdings near-certain.
Tier 2: canonical contributors with smaller Cahiers footprint — check per piece.
Tier 3: hyper-specific Cahiers material — skip Wikisource, OCR pipeline only.

URLs for matched Péguy works come from the Auteur:Charles_Péguy index fetched
2026-05-27; Romain Rolland Jean-Christophe volumes from the index page same day.
Unmatched Péguy pieces are flagged VERIFY (some are short Cahiers prose like
prefaces or letters that may or may not have a Wikisource page). Tier-2 authors
get CHECK_WIKISOURCE so each piece is hand-confirmed before any run.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIECES_DIR = ROOT / "src" / "content" / "pieces"
OUT = ROOT / "wikisource-audit.csv"

WS = "https://fr.wikisource.org/wiki/"

# Tier-1: Wikisource holdings near-certain.
TIER1 = {"charles-peguy", "romain-rolland", "leon-tolstoi"}

# Tier-2: canonical contributors with substantial Wikisource footprint.
# Each piece still needs per-piece verification.
TIER2 = {
    "julien-benda", "daniel-halevy", "andre-suares", "georges-sorel",
    "jean-jaures", "anatole-france", "henri-bergson", "paul-lafargue",
    "georges-clemenceau", "bernard-lazare", "edmond-fleg",
    "joseph-reinach", "paul-desjardins", "henri-michel", "henry-michel",
    "ferdinand-lot", "joseph-bedier", "edouard-berth", "raoul-allier",
    "jean-schlumberger", "andre-spire", "felicien-challaye",
}

# Péguy pieceSlug → Wikisource page slug. Source: Auteur:Charles_Péguy index
# (fetched 2026-05-27). Status from the index (Proofread / Validated / Partial).
PEGUY_MAP: dict[str, tuple[str, str]] = {
    "notre-patrie": ("Notre_Patrie", "proofread"),
    "un-nouveau-theologien-m-fernand-laudet": (
        "Un_nouveau_théologien,_M._Fernand_Laudet", "proofread"),
    "de-jean-coste": ("De_Jean_Coste_(Péguy)", "proofread"),
    "zangwill": ("Zangwill", "proofread"),
    "les-suppliants-paralleles": ("Les_Suppliants_parallèles", "proofread"),
    "notre-jeunesse": ("Notre_Jeunesse", "proofread"),
    "victor-marie-comte-hugo": ("Victor-Marie,_comte_Hugo", "proofread"),
    "l-argent": ("L’Argent_(Péguy)", "validated"),
    "l-argent-suite": ("L’Argent_suite", "proofread"),
    "note-sur-m-bergson-et-la-philosophie-bergsonienne": (
        "Note_sur_M._Bergson", "proofread"),
    "note-sur-m-bergson": ("Note_sur_M._Bergson", "proofread"),
    "clio": ("Clio", "partial"),
    "le-mystere-de-la-charite-de-jeanne-d-arc": (
        "Le_Mystère_de_la_charité_de_Jeanne_d'Arc", "proofread"),
    "le-porche-du-mystere-de-la-deuxieme-vertu": (
        "Le_Porche_du_mystère_de_la_deuxième_vertu", "proofread"),
    "le-mystere-des-saints-innocents": (
        "Le_Mystère_des_saints_innocents", "partial"),
    "la-tapisserie-de-sainte-genevieve-et-de-jeanne-d-arc": (
        "La_Tapisserie_de_sainte_Geneviève_et_de_Jeanne_d'Arc", "validated"),
    "la-tapisserie-de-notre-dame": ("La_Tapisserie_de_Notre_Dame", "validated"),
    "eve": ("Ève_(Péguy)", "validated"),
    "sainte-genevieve-patronne-de-paris": (
        "Sainte_Geneviève_patronne_de_Paris", "validated"),
    "de-la-cite-socialiste": ("De_la_cité_socialiste", "proofread"),
    "de-la-raison": ("Études_socialistes/De_la_Raison", "validated"),
    "de-la-situation-faite-a-l-histoire-et-a-la-sociologie-dans-les-temps-modernes": (
        "De_la_situation_faite_à_l'histoire_et_à_la_sociologie_dans_les_temps_modernes",
        "proofread"),
    "de-la-situation-faite-au-parti-intellectuel-dans-le-monde-moderne": (
        "De_la_situation_faite_au_parti_intellectuel_dans_le_monde_moderne",
        "proofread"),
}

# Jean-Christophe: 10 published volumes. The Cahiers installments map cleanly:
JC_CAHIER_MAP: dict[str, tuple[str, str]] = {
    "s05-c09": ("L%E2%80%99Aube_(Jean-Christophe)", "L'Aube"),
    "s05-c10": ("Le_Matin_(Jean-Christophe)", "Le Matin"),
    "s06-c08": ("L%E2%80%99Adolescent_(Jean-Christophe)", "L'Adolescent"),
    "s08-c04": ("La_Révolte_(Jean-Christophe)", "La Révolte (pt 1)"),
    "s08-c06": ("La_Révolte_(Jean-Christophe)", "La Révolte (pt 2)"),
    "s08-c09": ("La_Révolte_(Jean-Christophe)", "La Révolte (pt 3)"),
    "s09-c13": ("La_Foire_sur_la_place", "La Foire sur la place (pt 1)"),
    "s09-c14": ("La_Foire_sur_la_place", "La Foire sur la place (pt 2)"),
    "s09-c15": ("Antoinette", "Antoinette"),
    "s10-c09": ("Dans_la_maison", "Dans la maison (pt 1)"),
    "s10-c10": ("Dans_la_maison", "Dans la maison (pt 2)"),
    "s11-c07": ("Les_Amies_(Jean-Christophe)", "Les Amies (pt 1)"),
    "s11-c08": ("Les_Amies_(Jean-Christophe)", "Les Amies (pt 2)"),
    "s13-c05": ("Le_Buisson_ardent", "Le Buisson ardent (pt 1)"),
    "s13-c06": ("Le_Buisson_ardent", "Le Buisson ardent (pt 2)"),
    "s14-c02": ("La_Nouvelle_Journée", "La Nouvelle Journée (pt 1)"),
    "s14-c03": ("La_Nouvelle_Journée", "La Nouvelle Journée (pt 2)"),
}

# Péguy editorial pieces unlikely to be on Wikisource as standalone pages
# (avertissements, congrès reports, "À nos abonnés"-style notices).
# Substrings — if a piece's title contains any of these, action = skip-editorial.
PEGUY_EDITORIAL_SUBSTRINGS = (
    "À nos", "A nos", "Avertissement", "Communication", "Catalogue",
    "Congrès", "Débats parlementaires", "Texte sans commentaires",
    "Lettre du provincial", "Réponse au provincial", "second Provincial",
    "Pour ou contre", "Préparation du congrès", "Cahiers d'Arnold",
)

ROLLAND_MAP: dict[str, tuple[str, str]] = {
    "vie-de-beethoven": ("Vie_de_Beethoven", "proofread"),
    "vie-de-michel-ange": ("Vie_de_Michel-Ange", "proofread"),
    "vie-de-tolstoi": ("Vie_de_Tolstoï", "in-progress"),
    "le-theatre-du-peuple": ("Le_Théâtre_du_peuple_(Romain_Rolland)", "validated"),
    "le-quatorze-juillet": ("Le_Quatorze_Juillet_(Romain_Rolland)", "validated"),
    "les-loups": ("Les_Loups_(Romain_Rolland)", "validated"),
    "danton": ("Danton_(Romain_Rolland)", "validated"),
}


def parse_frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def classify(author: str) -> str:
    if author in TIER1:
        return "T1"
    if author in TIER2:
        return "T2"
    return "T3"


def resolve_url(
    cahier: str, piece_slug: str, author: str, title: str
) -> tuple[str, str, str]:
    """Returns (url, status, action)."""
    if author == "charles-peguy":
        hit = PEGUY_MAP.get(piece_slug)
        if hit:
            return WS + hit[0], hit[1], "use-wikisource"
        if any(s in title for s in PEGUY_EDITORIAL_SUBSTRINGS):
            return "", "", "skip-editorial"
        return "", "", "verify-peguy"  # short prose, essays — case-by-case
    if author == "romain-rolland":
        for slug, (page, status) in ROLLAND_MAP.items():
            if slug in piece_slug:
                return WS + page, status, "use-wikisource"
        if cahier in JC_CAHIER_MAP:
            page, _label = JC_CAHIER_MAP[cahier]
            return WS + page, "validated", "use-wikisource-jc"
        return "", "", "verify-rolland"
    if author == "leon-tolstoi":
        return "", "", "verify-tolstoi"  # French trans on WS, slug varies
    if author in TIER2:
        return "", "", "check-wikisource"
    return "", "", "skip"


def main() -> None:
    rows: list[dict[str, str]] = []
    for path in sorted(PIECES_DIR.glob("*.fr.md")):
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        author = fm.get("author", "")
        slug = fm.get("pieceSlug", "")
        tier = classify(author)
        url, status, action = resolve_url(
            fm.get("cahier", ""), slug, author, fm.get("title", ""))
        rows.append({
            "cahier": fm.get("cahier", ""),
            "pieceSlug": slug,
            "author": author,
            "title": fm.get("title", ""),
            "wordCount": fm.get("wordCount", ""),
            "isAvertissement": fm.get("isAvertissement", ""),
            "tier": tier,
            "wikisource_url": url,
            "wikisource_status": status,
            "current_fr_source": fm.get("ocrSource", ""),
            "fr_file": str(path.relative_to(ROOT)),
            "action": action,
        })

    fields = [
        "cahier", "pieceSlug", "author", "title", "wordCount",
        "isAvertissement", "tier", "wikisource_url", "wikisource_status",
        "current_fr_source", "fr_file", "action",
    ]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # Console summary
    from collections import Counter
    tiers = Counter(r["tier"] for r in rows)
    actions = Counter(r["action"] for r in rows)
    print(f"Wrote {len(rows)} rows to {OUT.relative_to(ROOT)}")
    print(f"Tiers: {dict(tiers)}")
    print(f"Actions: {dict(actions)}")


if __name__ == "__main__":
    main()
