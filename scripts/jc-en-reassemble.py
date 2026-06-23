"""
Reassemble translated JC chunks (raw/jc-en-chunks/<stem>/NNN.en.txt) into the
.en.md files, preserving frontmatter, updating title/wordCount/provenance.
Run after the translation workflow completes. Reports any missing chunk.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "src" / "content" / "pieces"
OUT = ROOT / "raw" / "jc-en-chunks"


def read_fm(path):
    t = path.read_text(encoding="utf-8")
    m = re.match(r'^---\n(.*?)\n---\n?(.*)$', t, re.S)
    return (m.group(1), m.group(2)) if m else (None, t)


def main():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    by_stem = {}
    for m in manifest:
        by_stem.setdefault(m["stem"], []).append(m)
    missing = []
    for stem, chunks in by_stem.items():
        chunks.sort(key=lambda c: c["idx"])
        parts = []
        for c in chunks:
            p = ROOT / c["enPath"]
            if not p.exists() or not p.read_text(encoding="utf-8").strip():
                missing.append(c["enPath"]); parts.append(f"[[MISSING CHUNK {c['idx']}]]")
            else:
                parts.append(p.read_text(encoding="utf-8").strip())
        body = "\n\n".join(parts).strip()
        en_path = PIECES / f"{stem}.en.md"
        fm, _ = read_fm(en_path) if en_path.exists() else (None, "")
        if fm is None:
            print(f"!! {stem}: no .en.md frontmatter, skip"); continue
        wc = len(re.findall(r"\b\w+\b", body))
        title = chunks[0]["enTitle"]
        lines = [l for l in fm.split("\n")
                 if not l.startswith(("wordCount:", "sourceProvenance:", "translationDate:", "title:"))]
        lines.insert(0, f"title: {title}")
        lines.append(f"wordCount: {wc}")
        lines.append('translationDate: "2026-06-19"')
        lines.append('sourceProvenance: "Fresh translation from validated Wikisource FR (Jean-Christophe); 2026-06-19"')
        en_path.write_text("---\n" + "\n".join(lines) + "\n---\n\n" + body + "\n", encoding="utf-8")
        print(f"{stem}: {wc} words from {len(chunks)} chunks")
    if missing:
        print(f"\n!! {len(missing)} MISSING chunk translations:")
        for m in missing[:40]:
            print("   ", m)


if __name__ == "__main__":
    main()
