"""
Fetch Cahiers de la Quinzaine page images from archive.org for vision re-OCR.

The stored FR pieces were OCR'd with a noisy Tesseract+mixed-vision pipeline.
Opus 4.8 vision transcribes the scans cleanly (single-column, normal type),
so the re-OCR process is: fetch the leaf images for a piece's page range, then
transcribe each per audit-screens/REOCR-PROTOCOL.md.

This script ONLY downloads images (it does no OCR — the model does that by
Read-ing the saved JPEGs). It resolves the archive.org item's data node +
path via the metadata API, then pulls each leaf through BookReaderImages.php
(server-side jp2->jpg, scale=2 ~ 840px wide, plenty for clean type).

Coverage: archive.org has 72 of ~300 cahier volumes (CAHIER_IDS below). For a
cahier not listed, pass --id with a Gallica/other source handled separately,
or find the BnF Gallica ark (fuller Cahiers coverage) — TODO: gallica fetcher.

Run:
  python3.11 scripts/fetch-cahier-pages.py --cahier s01-c01 --leaves 50-65
  python3.11 scripts/fetch-cahier-pages.py --id s1cahiersdelaquinz1pg --leaves 54
  python3.11 scripts/fetch-cahier-pages.py --cahier s01-c01 --probe   # just metadata
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANS = ROOT / "raw" / "scans"
UA = {"User-Agent": "charlespeguy-audit/1.0 (wilson.pruitt@gmail.com)"}

# cahier code -> archive.org identifier (derived 2026-06-20 from a
# identifier:*cahiersdelaqui* search; 72 volumes scanned, scattered).
CAHIER_IDS = {
    "s01-c01": "s1cahiersdelaquinz1pg", "s01-c05": "s1cahiersdelaqui05pg",
    "s01-c10": "s1cahiersdelaqui10pg", "s01-c12": "s1cahiersdelaqui12pg",
    "s02-c05": "s2cahiersdelaquinz05pg", "s02-c06": "s2cahiersdelaquinz06pg",
    "s02-c11": "s2cahiersdelaquinz11pg", "s02-c12": "s2cahiersdelaquinz12pg",
    "s03-c01": "s3cahiersdelaquinz01pg", "s03-c05": "s3cahiersdelaquinz05pg",
    "s03-c11": "s3cahiersdelaquinz11pg", "s03-c12": "s3cahiersdelaquinz12pg",
    "s03-c19": "s3cahiersdelaquinz19pg", "s04-c01": "s4cahiersdelaquinz01pg",
    "s04-c05": "s4cahiersdelaquinz05pg", "s04-c10": "s4cahiersdelaquinz10pg",
    "s04-c11": "s4cahiersdelaquinz11pg", "s04-c17": "s4cahiersdelaquinz17pg",
    "s04-c18": "s4cahiersdelaquinz18pg", "s05-c01": "s5cahiersdelaquinz01pg",
    "s05-c06": "s5cahiersdelaquinz06pg", "s05-c11": "s5cahiersdelaquinz11pg",
    "s05-c15": "s5cahiersdelaquinz15pg", "s05-c16": "s5cahiersdelaquinz16pg",
    "s06-c01": "s6cahiersdelaquinz01pg", "s06-c04": "s6cahiersdelaquinz04pg",
    "s06-c07": "s6cahiersdelaqui07pg", "s06-c09": "s6cahiersdelaquinz09pg",
    "s06-c13": "s6cahiersdelaquinz13pg", "s06-c16": "s6cahiersdelaquinz16pg",
    "s07-c01": "s7cahiersdelaquinz01pg", "s07-c05": "s7cahiersdelaquinz05pg",
    "s07-c08": "s7cahiersdelaquinz08pg", "s07-c12": "s7cahiersdelaquinz12pg",
    "s07-c16": "s7cahiersdelaquinz16pg", "s08-c01": "s8cahiersdelaquinz01pg",
    "s08-c04": "s8cahiersdelaquinz04pg", "s08-c05": "s8cahiersdelaquinz05pg",
    "s08-c11": "s8cahiersdelaquinz11pg", "s09-c01": "s9cahiersdelaquinz01pg",
    "s09-c04": "s9cahiersdelaquinz04pg", "s09-c05": "s9cahiersdelaquinz05pg",
    "s09-c09": "s9cahiersdelaquinz09pg", "s09-c13": "s9cahiersdelaqui13pg",
    "s09-c15": "s9cahiersdelaqui15pg", "s09-c16": "s9cahiersdelaqui16pg",
    "s10-c01": "s10cahiersdelaqui01pg", "s10-c02": "s10cahiersdelaqui02pg",
    "s10-c03": "s10cahiersdelaquinz03pg", "s10-c06": "s10cahiersdelaquinz06pg",
    "s10-c09": "s10cahiersdelaqui09pg", "s10-c11": "s10cahiersdelaqui11pg",
    "s11-c01": "s11cahiersdelaqui01pg", "s11-c04": "s11cahiersdelaqui04pg",
    "s11-c07": "s11cahiersdelaqui07pg", "s11-c09": "s11cahiersdelaqui09pg",
    "s11-c10": "s11cahiersdelaqui10pg", "s12-c01": "s12cahiersdelaqui01pg",
    "s12-c04": "s12cahiersdelaqui04pg", "s12-c07": "s12cahiersdelaqui07pg",
    "s13-c01": "s13cahiersdelaqui01pg", "s13-c04": "s13cahiersdelaqui04pg",
    "s13-c08": "s13cahiersdelaqui08pg", "s13-c09": "s13cahiersdelaqui09pg",
    "s14-c01": "s14cahiersdelaqui01pg", "s14-c05": "s14cahiersdelaqui05pg",
    "s14-c09": "s14cahiersdelaqui09pg", "s15-c01": "s15cahiersdelaquinz01pg",
    "s15-c04": "s15cahiersdelaquinz04pg", "s15-c07": "s15cahiersdelaquinz07pg",
    "s18-c10": "s18cahiersdelaqui10pg",
}


def meta(identifier: str) -> dict:
    url = f"https://archive.org/metadata/{identifier}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return json.load(r)


def parse_leaves(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(spec)]


def fetch_leaf(server: str, d: str, identifier: str, leaf: int, scale: int) -> bytes:
    fn = f"{identifier}_{leaf:04d}.jp2"
    q = {
        "zip": f"{d}/{identifier}_jp2.zip",
        "file": f"{identifier}_jp2/{fn}",
        "id": identifier, "scale": str(scale), "rotate": "0",
    }
    url = f"https://{server}/BookReader/BookReaderImages.php?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
        return r.read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cahier", help="cahier code, e.g. s01-c01")
    ap.add_argument("--id", help="archive.org identifier (overrides --cahier lookup)")
    ap.add_argument("--leaves", help="leaf or range, e.g. 54 or 50-65")
    ap.add_argument("--scale", type=int, default=2, help="2=~840px (default), 1=full")
    ap.add_argument("--probe", action="store_true", help="print metadata only")
    args = ap.parse_args()

    identifier = args.id or CAHIER_IDS.get(args.cahier or "")
    if not identifier:
        sys.exit(f"no archive.org id for {args.cahier!r} "
                 f"(not scanned on archive — try Gallica). Known: {len(CAHIER_IDS)} cahiers.")
    m = meta(identifier)
    server, d = m["server"], m["dir"]
    imgc = m["metadata"].get("imagecount")
    print(f"id={identifier}  server={server}  dir={d}  imagecount={imgc}")
    if args.probe:
        return
    if not args.leaves:
        sys.exit("--leaves required (or use --probe)")

    outdir = SCANS / identifier
    outdir.mkdir(parents=True, exist_ok=True)
    for leaf in parse_leaves(args.leaves):
        path = outdir / f"{identifier}_{leaf:04d}.jpg"
        if path.exists():
            print(f"  · leaf {leaf:4} exists"); continue
        try:
            data = fetch_leaf(server, d, identifier, leaf, args.scale)
        except Exception as e:
            print(f"  ✗ leaf {leaf:4} {e}"); continue
        if not data[:2] == b"\xff\xd8":  # not a JPEG (probably an error page)
            print(f"  ✗ leaf {leaf:4} not a JPEG ({len(data)}b)"); continue
        path.write_bytes(data)
        print(f"  ✓ leaf {leaf:4} -> {path.relative_to(ROOT)} ({len(data)//1024}kb)")
        time.sleep(0.4)


if __name__ == "__main__":
    main()
