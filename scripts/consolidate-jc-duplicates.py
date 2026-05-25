#!/usr/bin/env python3
"""One-off: collapse Jean-Christophe umbrella + installment duplicate pieces.

For each (cahier, keep_slug, drop_slug, new_title) below:
  - cahier JSON: remove the drop_slug piece entry; update keep piece's titleFr.
  - piece files: delete <cahier>--<drop_slug>.{fr,en}.md;
                 update title: in <cahier>--<keep_slug>.{fr,en}.md frontmatter.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAHIERS = ROOT / "src" / "data" / "cahiers"
PIECES = ROOT / "src" / "content" / "pieces"

WORK = [
    ("s05-c10", "jean-christophe",          "le-matin",                          "Jean-Christophe. II. Le matin"),
    ("s06-c08", "jean-christophe",          "l-adolescent",                      "Jean-Christophe. III. L'adolescent"),
    ("s08-c04", "jean-christophe",          "la-revolte-1-sables-mouvants",      "Jean-Christophe. IV. La révolte. 1. Sables mouvants"),
    ("s08-c06", "jean-christophe",          "la-revolte-2-l-enlisement",         "Jean-Christophe. IV. La révolte. 2. L'enlisement"),
    ("s08-c09", "jean-christophe",          "la-revolte-3-la-delivrance",        "Jean-Christophe. IV. La révolte. 3. La délivrance"),
    ("s10-c10", "jean-christophe-a-paris",  "dans-la-maison-2",                  "Jean-Christophe à Paris. II. Dans la maison. 2"),
    ("s11-c07", "jean-christophe",          "la-fin-du-voyage-i-les-amies-1",    "Jean-Christophe. III. La fin du voyage. I. Les amies. 1"),
    ("s11-c08", "jean-christophe",          "la-fin-du-voyage-i-les-amies-2",    "Jean-Christophe. III. La fin du voyage. I. Les amies. 2"),
]

def update_frontmatter_title(path: Path, new_title: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    text2 = re.sub(r"(?m)^title:.*$", f"title: {new_title}", text, count=1)
    if text2 != text:
        path.write_text(text2, encoding="utf-8")
        print(f"  retitled: {path.name}")

for cahier, keep, drop, new_title in WORK:
    cj = CAHIERS / f"{cahier}.json"
    data = json.loads(cj.read_text(encoding="utf-8"))
    pieces = data.get("pieces", [])
    new_pieces = []
    for p in pieces:
        if p["slug"] == drop:
            continue
        if p["slug"] == keep:
            p = dict(p)
            p["titleFr"] = new_title
        new_pieces.append(p)
    data["pieces"] = new_pieces
    cj.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{cahier}: JSON updated (kept {keep}, dropped {drop})")

    for lang in ("fr", "en"):
        stub = PIECES / f"{cahier}--{drop}.{lang}.md"
        if stub.exists():
            stub.unlink()
            print(f"  deleted stub: {stub.name}")
        keep_file = PIECES / f"{cahier}--{keep}.{lang}.md"
        update_frontmatter_title(keep_file, new_title)

print("done")
