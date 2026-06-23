"""
SET-UP for next session: probe fr.wikisource for the 46 `check-wikisource`
pieces (texts by NON-Péguy contributors — Jaurès, Sorel, Lazare, Anatole
France, etc.) to see whether a clean validated/proofread source exists.

For each piece: search fr.wikisource (title, then title+author), collect the
best candidate page(s) and their proofread quality level (via the
?action=query&prop=info + categories heuristic). Writes:
  audit-screens/check-wikisource-results.tsv

Result column verdict:
  FOUND-validated / FOUND-proofread / FOUND-maybe / NONE
so next session can promote FOUND rows to use-wikisource (pull + boundary as
needed) and demote NONE rows to verify (manual OCR).
"""
import csv, json, re, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://fr.wikisource.org/w/api.php"
UA = {"User-Agent": "charlespeguy-audit/1.0 (wilson.pruitt@gmail.com)"}

AUTHOR_NAMES = {
    "jean-jaures": "Jaurès", "georges-sorel": "Sorel", "bernard-lazare": "Lazare",
    "anatole-france": "Anatole France", "paul-lafargue": "Lafargue",
    "romain-rolland": "Rolland", "daniel-halevy": "Halévy", "julien-benda": "Benda",
    "leon-tolstoi": "Tolstoï", "andre-suares": "Suarès", "pierre-baudouin": "Péguy",
}


def api(params):
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    for a in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
        except Exception:
            if a == 2: raise
            time.sleep(2)


def search(q, limit=5):
    d = api({"action": "query", "list": "search", "srsearch": q, "srlimit": str(limit)})
    return [(h["title"], h.get("wordcount", 0)) for h in d.get("query", {}).get("search", [])]


def quality(title):
    """Heuristic proofread level via page categories."""
    d = api({"action": "query", "titles": title, "prop": "categories", "cllimit": "50"})
    pages = d.get("query", {}).get("pages", [])
    cats = " ".join(c["title"] for p in pages for c in p.get("categories", []))
    if "validés" in cats or "Textes validés" in cats: return "validated"
    if "corrigés" in cats or "Textes corrigés" in cats: return "proofread"
    return "maybe"


def title_words(s):
    return set(re.findall(r"\w{4,}", s.lower()))


def main():
    rows = [r for r in csv.DictReader(open(ROOT / "wikisource-audit.csv")) if r["action"].strip() == "check-wikisource"]
    out = ROOT / "audit-screens" / "check-wikisource-results.tsv"
    out.parent.mkdir(exist_ok=True)
    results = []
    for r in rows:
        title = r["title"].strip().strip('"')
        author_key = r["author"].strip()
        author = AUTHOR_NAMES.get(author_key, author_key.replace("-", " "))
        cands = search(f"{title}") or search(f"{title} {author}")
        time.sleep(0.5)
        want = title_words(title)
        best, verdict = "", "NONE"
        for cand_title, wc in cands:
            overlap = len(want & title_words(cand_title)) / (len(want) or 1)
            if overlap >= 0.5 and wc > 300:
                q = quality(cand_title); time.sleep(0.4)
                best, verdict = cand_title, f"FOUND-{q}"
                break
        results.append((verdict, r["cahier"], r["pieceSlug"], author, title, best))
        print(f"  {verdict:18} {r['cahier']} {r['pieceSlug'][:32]:34} -> {best[:45]}")

    order = {"FOUND-validated": 0, "FOUND-proofread": 1, "FOUND-maybe": 2, "NONE": 3}
    results.sort(key=lambda x: order.get(x[0], 9))
    with open(out, "w") as fh:
        fh.write("verdict\tcahier\tslug\tauthor\ttitle\twikisource_candidate\n")
        for v, c, s, a, t, b in results:
            fh.write(f"{v}\t{c}\t{s}\t{a}\t{t}\t{b}\n")
    found = sum(1 for r in results if r[0].startswith("FOUND"))
    print(f"\n{found}/{len(results)} have a Wikisource candidate. Wrote {out.name}")


if __name__ == "__main__":
    main()
