# Next-session brief — Repair remaining empty/missing FR cahier pieces

Drafted 2026-05-25; consolidated 2026-05-25 PM after Jean-Christophe pass. Drop this file into a fresh `/clear`'d Claude Code session inside `~/charlespeguy.org/` to pick up the work.

---

## Context (read first)

The site went live 2026-05-24 at https://charlespeguy-org.vercel.app (custom domain DNS pending). 1,684 static pages after Jean-Christophe consolidation, fully bilingual.

The original brief framed the problem as "11 cahiers of Jean-Christophe need vision OCR." That was the wrong scope. The full audit found ~86 pieces with data problems. **Then on 2026-05-25 PM we discovered 8 of the 9 Jean-Christophe gaps were not real OCR work** — each cahier already had a complete `--jean-christophe` umbrella piece next to an empty installment-named stub. Dropping the duplicates (commit `15ee939`) collapsed Round 1 down to a single real OCR: **s10-c09 *Dans la maison. 1***.

Read these in order:
1. This file.
2. `audit.md` (in repo root) — flag-by-flag list of every broken piece.
3. `audit.csv` — same data, machine-readable.
4. `~/.claude/projects/-Users-wilsonpruitt/memory/project_charlespeguy-site-direction.md`
5. `~/.claude/projects/-Users-wilsonpruitt/memory/peguy-translation-gaps.md` — OCR pipeline conventions, vision-OCR workflow.

## Diagnosis already done

- The `.com` source (`~/charlespeguy.com/src/content/texts/<slug>.md`) is the broken layer. 33 of those files are marked `status: "placeholder"` and contain raw Tesseract garbage; the `.org` migration faithfully copied them. 20 other cahiers have no `.com` source file at all.
- The `.com` repo is being wound down. Fixes should land **in `.org` directly**, not via the migration script.
- Author miscredits are also in the `.com` YAML — e.g. s12-c06 *Les Milliet V* is wrongly attributed to Péguy in both `.com` and `.org`.

## What was shipped in the prior session (commit `87b7067`)

- `scripts/denoise-fr-pieces.py` — idempotent OCR-noise stripper. Already run across all 269 FR files; preserves prose, removes only scan garbage. Re-run anytime, safe.
- `scripts/audit-pieces.py` — emits `audit.csv` + `audit.md`. Re-run after each repair to confirm progress.
- 174,158 lines of OCR noise removed; build passes (8m 25s, 1,716 pages).

## This session's job: remaining EMPTY_FR + NO_FR pieces

Post-consolidation audit: **19 EMPTY_FR + 17 NO_FR**. The Jean-Christophe entries below (s05-c10 le-matin, s06-c08 l-adolescent, s08-c04/06/09 la-revolte-*, s10-c10 dans-la-maison-*) were already resolved via the umbrella-piece consolidation — they should **not** appear in a fresh `audit.csv`. The only Jean-Christophe cahier that still needs real OCR is **s10-c09 *Dans la maison. 1*** (umbrella has only 925 words of Péguy's editorial preface).

Run `python3 scripts/audit-pieces.py` first to confirm what's actually still flagged before starting any OCR.

### EMPTY_FR (file exists, body is pure garbage — denoise produced 0 prose)

| Cahier+piece | Title | Author |
|---|---|---|
| s02-c07 administration | Administration | charles-peguy |
| s02-c14 courrier-de-chine | Courrier de Chine | lionel-landry |
| s03-c02 les-universites-populaires | Les Universités Populaires | charles-guieysse |
| s03-c04 etudes-socialistes | Études Socialistes | jean-jaures |
| s05-c07 moines-de-l-athos | Moines de l'Athos | les Tharaud |
| s05-c10 le-matin | Le matin (Jean-Christophe II) | romain-rolland |
| s06-c03 chad-gadya | Chad Gadya! | israel-zangwill |
| s06-c04 l-enseignement-primaire-a-madagascar | L'enseignement primaire à Madagascar | raoul-allier |
| s06-c13 les-evenements-actuels-en-russie | Les événements actuels en Russie | leon-tolstoi |
| s07-c05 le-22-janvier | Le 22 janvier | etienne-avenard |
| s07-c07 les-suppliants | Les suppliants | francois-porche |
| s07-c08 et-vous-riez | Et vous riez | andre-spire |
| s08-c02 l-abdication | L'abdication | romain-rolland |
| s08-c07 les-sonnets-de-shakespeare-i | Les sonnets de Shakespeare. I | marie-garnier |
| s08-c15 les-sonnets-de-shakespeare | Les sonnets de Shakespeare | marie-garnier |
| s10-c04 vin-de-champagne | Vin de Champagne | pierre-hamp |
| s10-c11 au-large | Au large | maxime-vuillaume |
| s11-c06 le-mystere-de-la-charite-de-jeanne-d-arc | Le mystère de la charité de Jeanne d'Arc | charles-peguy |
| s11-c09 dernier-cahier | Dernier cahier | maxime-vuillaume |
| s13-c12 le-mystere-des-saints-innocents | Le mystère des saints Innocents | charles-peguy |
| s14-c04 la-chute | La chute | julien-benda |
| s14-c08 les-chants-de-l-ame-reveillee | Les chants de l'âme réveillée | rene-salome |
| s14-c11 mes-cahiers-rouges | Mes cahiers rouges IX | maxime-vuillaume |
| s14-c11 ix | IX (mis-split — duplicate of above) | maxime-vuillaume |
| s14-c11 lettres-et-temoignages | Lettres et témoignages | maxime-vuillaume |
| s15-c10 nous | Nous | francois-porche |
| (+ the 4 stub-split files we identified: s06-c08 l-adolescent, s08-c04/06/09 la-revolte-*, s10-c09/10 dans-la-maison-*) |

### 17 NO_FR (cahier declares the piece but no FR file exists at all)

Mostly Milliet/Rolland/Péguy installments where `.com` only ever had an EN translation, or where the cahier JSON was generated from EN frontmatter. Same Archive.org volumes as the EMPTY_FR list — many overlap.

## Workflow per cahier (this is the proven pattern)

1. **Find the Archive.org volume + leaf range.** Probe with `curl -s https://archive.org/metadata/<volume_id>`. Many leaf ranges are already in `~/charlespeguy.com/scripts/redownload-leaves.ts`. For ones not there, find the half-title page and colophon manually before kicking off OCR.
2. **Download leaves.** `~/charlespeguy.com/raw/ocr-images/` was deleted earlier this week; re-download via `npx tsx scripts/redownload-leaves.ts <slug>` (in the `.com` repo) or with a small curl script (the URL pattern is `https://iiif.archive.org/image/iiif/3/<id>%2F<id>_jp2.zip%2F<id>_jp2%2F<id>_NNNN.jp2/full/1200,/0/default.jpg`).
3. **Vision-OCR in chunks of ~28 leaves × 5 parallel subagents** (per `peguy-translation-gaps.md`). Each prompt must include: ignore right-margin spine bleed-through; skip blank/binding leaves; preserve italic markup as `*asterisks*`; `[?]` for illegibles; one `[leaf NNNN] [p. N]` marker per leaf.
4. **Splice chunks** into a clean `~/charlespeguy.com/raw/<slug>-ocr.txt` (or write directly into `.org`).
5. **Write the FR piece file** at `~/charlespeguy.org/src/content/pieces/<cahier>--<piece>.fr.md` with proper frontmatter:
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
6. **Re-run the audit.** `python3 scripts/audit-pieces.py` — flag count for EMPTY_FR / NO_FR should drop.

## Pace + budget

Post-Jean-Christophe-consolidation, ~3-4 sessions remaining. Prioritize:

1. **Round 1** — ~~Jean-Christophe gaps~~ DONE via consolidation, except **s10-c09 *Dans la maison. 1*** (real OCR still needed). **1 cahier.**
2. **Round 2** — Péguy's own missing prose (s11-c06 Mystère de Jeanne d'Arc, s13-c12 Saints Innocents, s12-c10 Œuvres choisies postface): canonical Péguy. **3 cahiers.** *Pull from Wikisource, not vision OCR — both Mystères are on fr.wikisource.org.*
3. **Round 3** — Vuillaume *Mes cahiers rouges* (s10-c11, s11-c09, s14-c11 ×3): 1871 Commune memoir, a coherent body. **5 cahiers.**
4. **Round 4** — Milliet missing FR (s11-c13, s11-c14, s12-c10 les-milliet, s13-c07): bilingual completion. **4 cahiers.**
5. **Round 5** — orphans (Allier, Garnier sonnets, Salomé chants, Spire, Avenard, Hamp, Porché, Benda, Delahache exode, Zangwill, Tolstoy 1905, Jaurès Études Socialistes, etc.). **~20 cahiers.**

## Quick wins (do these first, ~30–45 min)

Before the OCR push, knock out:

1. **s12-c06 author miscredit.** Audit's only confirmed real miscredit. Open `src/data/cahiers/s12-c06.json` and `src/content/pieces/s12-c06--les-milliet-v-jours-heureux.{fr,en}.md`; change `author: charles-peguy` → `paul-milliet`. Verify Paul Milliet author file exists (`src/content/authors/paul-milliet.md`).
2. **Verify the 4 other AUTHOR_MISMATCH** (audit.md AUTHOR_MISMATCH section) — most are likely OK (Suarès *on* Tolstoy, Péguy *on* Milliets). Document the call.
3. **Tune the denoise heuristic** if you hit prose lines that got stripped. The heuristic is in `scripts/denoise-fr-pieces.py:is_noise`; rerun safely (idempotent).

## How to know you're done with the session

- `python3 scripts/audit-pieces.py` shows fewer EMPTY_FR + NO_FR than 44.
- `NODE_OPTIONS="--max-old-space-size=2048" npx astro build` passes.
- Spot-check at least one repaired piece in dev (`npm run dev`).
- `npx vercel deploy --prod --yes` if you want it live.
- `git push` to `github.com/wilsonpruitt/charlespeguy.org` (private, set up 2026-05-25).
- Update `~/.claude/projects/-Users-wilsonpruitt/memory/project_charlespeguy-site-direction.md` with what you accomplished.

## Don't forget

- 8 GB RAM Mac — max 5 parallel vision-OCR agents at a time.
- The denoise script is idempotent and safe to rerun.
- Per `feedback_acta-usage.md`: cap subagents at 6 ever; 5 is comfortable.
- All paths in `audit.csv` are relative to `~/charlespeguy.org/`.
- Repo is now on GitHub (private). `gh repo view wilsonpruitt/charlespeguy.org`.
- Cloudflare DNS for charlespeguy.org still pending: A `76.76.21.21` (DNS-only) + CNAME `www → cname.vercel-dns.com`.
- Commit messages should end with the Claude co-author trailer.
