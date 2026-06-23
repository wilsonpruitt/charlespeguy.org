"""
Split multi-cahier Jean-Christophe volumes from validated Wikisource into the
as-published cahier installments, cutting at boundaries VERIFIED (unique anchor,
checked against existing OCR) — not guessed.

Each volume's clean "Texte entier" is fetched + cleaned with the same pipeline
as pull-jc-wikisource.py, split at the paragraph containing a boundary anchor,
and each slice written to its .fr.md with frontmatter + sourceProvenance.

Boundaries:
  La Foire sur la place  -> s09-c13 | s09-c14   cut BEFORE "Parmi les jeunes filles du monde"  (anchor x1, verified)
  Dans la maison         -> s10-c09 | s10-c10   cut BEFORE "Christophe la tira si vigoureusement" (anchor x1, verified)
  La Nouvelle Journée    -> s14-c02 | s14-c03   cut AFTER  "qui les enveloppait" (end of c02 OCR, anchor x1)
  Le Buisson ardent      -> s13-c05 | s13-c06   cut AT     "DEUXIÈME PARTIE"  (STRUCTURAL inference — c05 OCR
                                                 truncated, c06 OCR garbled; flagged for confirmation)
"""
from __future__ import annotations
import importlib.util, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "src" / "content" / "pieces"
BACKUP = ROOT / "raw" / "wikisource" / "_backup"

# reuse fetch/clean/markdown from the pull script
spec = importlib.util.spec_from_file_location("pulljc", ROOT / "scripts" / "pull-jc-wikisource.py")
pulljc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pulljc)


def norm(s): return s.replace("’", "'")

# (volume page, cut_anchor, "before"|"after", part1_file, part2_file, provenance_note)
SPLITS = [
    ("La Foire sur la place/Texte entier", "Parmi les jeunes filles du monde", "before",
     "s09-c13--jean-christophe-a-paris-i-la-foire-sur-la-place-1.fr.md",
     "s09-c14--jean-christophe-in-paris-i-the-fair-on-the-square-2.fr.md", "verified anchor"),
    ("La Nouvelle Journée/Texte entier", "qui les enveloppait", "after",
     "s14-c02--jean-christophe-la-nouvelle-journee-1.fr.md",
     "s14-c03--jean-christophe-la-nouvelle-journee-2.fr.md", "verified anchor (c02 OCR end)"),
    # Le Buisson ardent: structural split at book Part I/II ("DEUXIÈME PARTIE"),
    # approved by Wilson 2026-06-19 (2 cahiers = 2 book parts; word counts fit).
    ("Le Buisson ardent/Texte entier", "DEUXIÈME PARTIE", "before",
     "s13-c05--jean-christophe-le-buisson-ardent-1.fr.md",
     "s13-c06--jean-christophe-le-buisson-ardent-2.fr.md",
     "structural split at book Part I/II, approved 2026-06-19"),
    # Dans la maison: boundary recovered from archive.org bound cahier 9-10
    # (s10cahiersdelaqui09pg). Cahier 9's DLM part-1 ends at Olivier's line
    # "Nous sommes ses enfants" (followed by the next piece "LA VOCE"); anchor
    # unique in WS @ word 22189/57353. Cut AFTER it.
    ("Dans la maison/Texte entier", "Nous sommes ses enfants", "after",
     "s10-c09--dans-la-maison-1.fr.md",
     "s10-c10--jean-christophe-a-paris.fr.md",
     "archive.org-anchored boundary (cahier 9 end), 2026-06-19"),
    # Les Amies: boundary from archive.org bound cahier 7-8 (s11cahiersdelaqui07pg).
    # Cahier 7 ends at "Et ils se prirent" (then the colophon); anchor unique in WS
    # @ 53%. Cut AFTER it.
    ("Les Amies (Jean-Christophe)/Texte entier", "Et ils se prirent", "after",
     "s11-c07--jean-christophe.fr.md",
     "s11-c08--jean-christophe.fr.md",
     "archive.org-anchored boundary (cahier 7 end), 2026-06-19"),
]


def write_piece(fname, body, prov):
    path = PIECES / fname
    fm, _ = pulljc.read_frontmatter(path) if path.exists() else (None, "")
    if fm is None:
        print(f"   !! {fname} has no frontmatter / missing — skip"); return None
    wc = len(re.findall(r"\b\w+\b", body))
    lines = [l for l in fm.split("\n") if not l.startswith(("wordCount:", "sourceProvenance:"))]
    lines.append(f"wordCount: {wc}")
    lines.append(f'sourceProvenance: "{prov}"')
    if path.exists():
        BACKUP.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, BACKUP / f"{fname}.bak-2026-06-19")
    path.write_text("---\n" + "\n".join(lines) + "\n---\n\n" + body.strip() + "\n", encoding="utf-8")
    return wc


def main():
    dry = "--dry-run" in sys.argv
    for page, anchor, side, f1, f2, note in SPLITS:
        print(f"\n== {page}  cut {side} '{anchor[:40]}' ==")
        md = pulljc.to_markdown(pulljc.clean_html(pulljc.fetch(page)))
        paras = re.split(r'\n\s*\n', md)
        idx = next((i for i, p in enumerate(paras) if norm(anchor) in norm(p)), None)
        if idx is None:
            print("   !! anchor NOT FOUND — skip"); continue
        if side == "before":
            p1 = "\n\n".join(paras[:idx]); p2 = "\n\n".join(paras[idx:])
        else:  # after: anchor paragraph stays with part 1
            p1 = "\n\n".join(paras[:idx + 1]); p2 = "\n\n".join(paras[idx + 1:])
        w1 = len(re.findall(r"\b\w+\b", p1)); w2 = len(re.findall(r"\b\w+\b", p2))
        prov = f"Wikisource ({page}, status=validated; split {note}); pulled 2026-06-19"
        print(f"   part1 {f1.split('--')[0]}: {w1}w  ->  part2 {f2.split('--')[0]}: {w2}w")
        if dry:
            print("   [dry-run]"); continue
        write_piece(f1, p1, prov); write_piece(f2, p2, prov)
        print("   wrote both")


if __name__ == "__main__":
    main()
