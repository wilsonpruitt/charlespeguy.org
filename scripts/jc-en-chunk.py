"""
Chunk the 17 clean Jean-Christophe FR installments into ~2500-word segments at
paragraph boundaries, for parallel translation. Writes:
  raw/jc-en-chunks/<cahier>/NNN.fr.txt          (source chunks)
  raw/jc-en-chunks/manifest.json                (list of all chunks)
Reassembly (after translation) is jc-en-reassemble.py.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "src" / "content" / "pieces"
OUT = ROOT / "raw" / "jc-en-chunks"
TARGET_WORDS = 2500

# the 17 JC installments (cahier-file stem, EN title)
INSTALLMENTS = [
    ("s05-c09--jean-christophe-i-l-aube", "Jean-Christophe. I. The Dawn"),
    ("s05-c10--jean-christophe", "Jean-Christophe. II. Morning"),
    ("s06-c08--jean-christophe", "Jean-Christophe. III. The Adolescent"),
    ("s08-c04--jean-christophe", "Jean-Christophe. IV. Revolt. 1. Shifting Sands"),
    ("s08-c06--jean-christophe", "Jean-Christophe. IV. Revolt. 2. The Quagmire"),
    ("s08-c09--jean-christophe", "Jean-Christophe. IV. Revolt. 3. Deliverance"),
    ("s09-c13--jean-christophe-a-paris-i-la-foire-sur-la-place-1", "Jean-Christophe in Paris. I. The Market-Place. 1"),
    ("s09-c14--jean-christophe-in-paris-i-the-fair-on-the-square-2", "Jean-Christophe in Paris. I. The Market-Place. 2"),
    ("s09-c15--jean-christophe-a-paris-antoinette", "Jean-Christophe in Paris. Antoinette"),
    ("s10-c09--dans-la-maison", "Jean-Christophe in Paris. II. The House. 1"),  # placeholder; resolved below
    ("s10-c10--jean-christophe-a-paris", "Jean-Christophe in Paris. II. The House. 2"),
    ("s11-c07--jean-christophe", "Jean-Christophe. The Journey's End. The Friends. 1"),
    ("s11-c08--jean-christophe", "Jean-Christophe. The Journey's End. The Friends. 2"),
    ("s13-c05--jean-christophe-le-buisson-ardent-1", "Jean-Christophe. The Burning Bush. 1"),
    ("s13-c06--jean-christophe-le-buisson-ardent-2", "Jean-Christophe. The Burning Bush. 2"),
    ("s14-c02--jean-christophe-la-nouvelle-journee-1", "Jean-Christophe. The New Dawn. 1"),
    ("s14-c03--jean-christophe-la-nouvelle-journee-2", "Jean-Christophe. The New Dawn. 2"),
]
# fix the DLM-1 stem (file is s10-c09--dans-la-maison-1)
INSTALLMENTS[9] = ("s10-c09--dans-la-maison-1", "Jean-Christophe in Paris. II. The House. 1")


def body(stem):
    t = (PIECES / f"{stem}.fr.md").read_text(encoding="utf-8")
    return re.sub(r'^---.*?---', '', t, 1, re.S).strip()


def chunk(paras, target):
    out, cur, n = [], [], 0
    for p in paras:
        w = len(p.split())
        if n + w > target and cur:
            out.append("\n\n".join(cur)); cur, n = [], 0
        cur.append(p); n += w
    if cur:
        out.append("\n\n".join(cur))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for stem, en_title in INSTALLMENTS:
        f = PIECES / f"{stem}.fr.md"
        if not f.exists():
            print(f"!! missing {stem}"); continue
        paras = re.split(r'\n\s*\n', body(stem))
        chunks = chunk(paras, TARGET_WORDS)
        d = OUT / stem
        d.mkdir(exist_ok=True)
        for i, c in enumerate(chunks):
            (d / f"{i:03d}.fr.txt").write_text(c, encoding="utf-8")
            manifest.append({"stem": stem, "enTitle": en_title, "idx": i,
                             "total": len(chunks), "words": len(c.split()),
                             "frPath": str((d / f'{i:03d}.fr.txt').relative_to(ROOT)),
                             "enPath": str((d / f'{i:03d}.en.txt').relative_to(ROOT))})
        print(f"{stem}: {len(chunks)} chunks, {sum(len(c.split()) for c in chunks)} words")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTOTAL: {len(manifest)} chunks across {len(INSTALLMENTS)} installments")


if __name__ == "__main__":
    main()
