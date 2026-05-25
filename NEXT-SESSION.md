# Next-session brief — Finish the 13 remaining EMPTY_FR pieces

Last updated 2026-05-25 PM2 after a long ingest session (commits `e0c0989`,
`fb63ab6`, `c6d7821`, `de2c2f5`). Drop this file into a fresh `/clear`'d
session inside `~/charlespeguy.org/` to pick up the work.

---

## Where things stand

- Site is live: https://charlespeguy-org.vercel.app (custom domain DNS still pending).
- Repo: `github.com/wilsonpruitt/charlespeguy.org` (private).
- Build: ~1,680 pages, passes.
- Current audit (`python3 scripts/audit-pieces.py`): **13 EMPTY_FR, 0 NO_FR**.
  Down from 19 EMPTY_FR + 17 NO_FR at the start of the 2026-05-25 PM session.
- All `NO_FR` is gone. All remaining FR work is *EMPTY_FR* — files exist but
  bodies are pure OCR garbage from the migration.

## What this session no longer needs to do

Don't re-attempt any of these — they're done:

- **Round 1 (Jean-Christophe gaps):** consolidated `15ee939` (most of them) +
  s10-c09 *Dans la maison* pulled from Wikisource (`de2c2f5`).
- **Round 2 (canonical Péguy):** all 3 done. s11-c06 *Mystère de la charité de
  Jeanne d'Arc* and s13-c12 *Mystère des saints Innocents* from Wikisource
  (Tomes 5/6 of Œuvres complètes). s12-c10 postface ingested from existing
  `~/charlespeguy.com/raw/s12-c10-ocr.txt` (pp.149-174). Commits `e0c0989`,
  `fb63ab6`.
- **Round 3 (Vuillaume Cahiers rouges):** consolidated. Same umbrella/stub
  pattern as Jean-Christophe. s10-c11 `au-large`, s11-c09 `dernier-cahier`,
  s14-c11 `ix` + `lettres-et-temoignages` all dropped — they were subtitle
  labels for sections already inside the `mes-cahiers-rouges` umbrella.
  s14-c11 umbrella ingested from existing OCR. Commit `fb63ab6`.
- **Round 4 (Milliet):** s11-c13 / s11-c14 / s13-c07 all ingested from
  existing `.com` OCR. Cahier-JSON `titleFr` English fields fixed to French.
  Commit `c6d7821`.
- **Round 5 cheap wins (single-piece cahiers with existing OCR):** s09-c03,
  s12-c03, s13-c02, s14-c08, s15-c06, s15-c10 — 6 pieces ingested from
  `.com` OCR. Commit `c6d7821`.
- **s14-c04 L'Ordination II / La Chute:** overwrote 44k Tesseract-garbage
  body with clean 10k OCR; retitled `L'ordination. II — La chute`; dropped
  `la-chute` stub. Commit `c6d7821`.
- **s12-c10 sub-piece consolidation:** dropped `adrien-de-tuce` and
  `cinq-ans-au-mexique` from JSON — they were subtitle labels for chapter VII
  of *Les Milliet*, already in the les-milliet umbrella. Commit `c6d7821`.
- **s03-c04 Études socialistes (Jaurès):** pulled from Wikisource. Commit `de2c2f5`.
- **s08-c02 L'abdication (Rolland, Vie de Michel-Ange II):** pulled from
  Wikisource (3 subpages: Amour / Foi / Solitude). Commit `de2c2f5`.

**Don't re-attempt s12-c06 author miscredit either** — that was fixed in commit
`15ee939` (Les Milliet V → paul-milliet). The 4 remaining AUTHOR_MISMATCH
flags are false positives (Suarès *on* Tolstoy, Péguy *on* Milliets, etc.).

## What's actually left

**13 EMPTY_FR pieces.** All need fresh vision OCR — Wikisource has already
been checked for the obvious candidates and Tharaud / Hamp / etc. are
confirmed not transcribed there (only indexed in the Cahiers de la Quinzaine
listing).

| Cahier+piece | Title | Author |
|---|---|---|
| s02-c07 administration | Administration | charles-peguy |
| s02-c14 courrier-de-chine | Courrier de Chine | lionel-landry |
| s03-c02 les-universites-populaires | Les Universités Populaires | charles-guieysse |
| s05-c07 moines-de-l-athos | Moines de l'Athos | les Tharaud |
| s06-c03 chad-gadya | Chad Gadya! | israel-zangwill |
| s06-c04 l-enseignement-primaire-a-madagascar | L'enseignement primaire à Madagascar | raoul-allier |
| s06-c13 les-evenements-actuels-en-russie | Les événements actuels en Russie | leon-tolstoi |
| s07-c05 le-22-janvier | Le 22 janvier | etienne-avenard |
| s07-c07 les-suppliants | Les suppliants | francois-porche |
| s07-c08 et-vous-riez | Et vous riez | andre-spire |
| s08-c07 les-sonnets-de-shakespeare-i | Les sonnets de Shakespeare. I | marie-garnier |
| s08-c15 les-sonnets-de-shakespeare | Les sonnets de Shakespeare | marie-garnier |
| s10-c04 vin-de-champagne | Vin de Champagne | pierre-hamp |

**Always run `python3 scripts/audit-pieces.py` first** to confirm — this list
may shift if Wilson did any cleanup between sessions.

## Before kicking off any OCR

1. Check `~/charlespeguy.com/raw/sNN-cNN-ocr.txt` — confirm it does NOT
   already exist for the target cahier. (Round 4/5 cheap wins worked because
   .com had usable OCR; none of the 13 listed above do.)
2. Check Wikisource one more time for the specific title, especially for
   famous authors (Tolstoy 1905, Spire) — Wikisource adds new transcriptions
   regularly.
3. Resource cap: 8 GB Mac, max 5 parallel vision-OCR agents.

## Workflow per cahier (unchanged from prior brief)

1. Probe `https://archive.org/metadata/<volume_id>` for leaves.
2. Download leaves via `~/charlespeguy.com/scripts/redownload-leaves.ts` or
   curl IIIF: `https://iiif.archive.org/image/iiif/3/<id>%2F<id>_jp2.zip%2F<id>_jp2%2F<id>_NNNN.jp2/full/1200,/0/default.jpg`.
3. Vision-OCR in chunks of ~28 leaves × 5 parallel subagents. Prompt MUST
   include: ignore right-margin spine bleed-through; skip blanks; preserve
   italics as `*…*`; `[?]` for illegibles; one `[leaf NNNN] [p. N]` marker
   per leaf.
4. Splice chunks → `raw/<slug>-ocr.txt`.
5. Write `~/charlespeguy.org/src/content/pieces/<cahier>--<piece>.fr.md`:
   ```yaml
   ---
   cahier: <cahier>
   pieceSlug: <piece>
   lang: fr
   title: <title>
   author: <author-slug>
   isAvertissement: false
   wordCount: <count>
   ocrSource: "Archive.org vision OCR 2026-MM-DD"
   ---
   ```
6. Rerun `scripts/audit-pieces.py` — EMPTY_FR should decrement.

## Done-criteria for the session

- `audit-pieces.py` shows EMPTY_FR lower than 13.
- `NODE_OPTIONS="--max-old-space-size=2048" npx astro build` passes.
- `git push` to `origin main`.
- Update `~/.claude/projects/-Users-wilsonpruitt/memory/project_charlespeguy-audit-2026-05-25.md`
  with the new totals.

## Other open items (not blocking FR repair)

- EMPTY_EN: 12. LOW_PROSE_EN: 17. NO_EN: 8. EN side is a separate
  workstream; defer until FR side is clean.
- 4 AUTHOR_MISMATCH flags are false positives — could add an exemption list
  to `scripts/audit-pieces.py` for cleaner output.
- s10-c09 holds the full ~59k-word Wikisource *Dans la maison* under the
  `dans-la-maison-1` slug, even though the original Cahier was just Part 1.
  s10-c10 still holds the prior umbrella (70k garbage-laden). A future
  polish pass could split the Wikisource text at the historical Cahiers
  part-break and apportion it between s10-c09 and s10-c10. The
  `translationNotes` field in s10-c09 flags this.
- Cloudflare DNS for charlespeguy.org still pending: A `76.76.21.21`
  (DNS-only) + CNAME `www → cname.vercel-dns.com`.

## Don't forget

- 8 GB RAM Mac — max 5 parallel vision-OCR agents.
- `denoise-fr-pieces.py` is idempotent and safe to rerun if any EMPTY_FR
  body looks like it might have lost real prose.
- `audit-pieces.py` is the source of truth; this file can drift.
- Commit messages end with the Claude co-author trailer.
