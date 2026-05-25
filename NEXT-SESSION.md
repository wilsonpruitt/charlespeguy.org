# Next-session brief — Finish the last 2 EMPTY_FR pieces (vision OCR) + Louis de Gonzague

Last updated 2026-05-25 PM4 after Rounds 6+7 (commits `66bf60b`, `857385d`).
Drop this file into a fresh `/clear`'d session inside `~/charlespeguy.org/`
to pick up the work.

---

## Where things stand

- Site: https://charlespeguy-org.vercel.app (custom DNS pending).
- Repo: `github.com/wilsonpruitt/charlespeguy.org` (private).
- Build: ~1,698 pages, passes.
- Current audit (`python3 scripts/audit-pieces.py`): **EMPTY_FR = 5**
  (was 13 at start of 2026-05-25 PM session — Rounds 6+7 cut 8 of them
  with zero new vision-OCR cycles).

## What changed in PM3/PM4 (don't redo)

### Round 6 (commit `66bf60b`) — 3 quick wins via existing sources

- **s06-c13** Tolstoï *Les Événements actuels en Russie* — Wikisource
  `ws-export` (4,003 w, traduction Bienstock).
- **s06-c03** Zangwill *Chad Gadya!* — Wikisource `ws-export` (6,900 w).
- **s02-c07** Péguy *Administration* — ingested ~85-word
  subscription/admin notice from tail of
  `~/charlespeguy.com/raw/s02-c07-administration-casse-cou.txt`.

### Round 7 (commit `857385d`) — the BIG finding + 8 splits

Discovered that the original migration parser had dumped each cahier's
full OCR into ONE piece file per cahier, leaving the other pieces as
empty stubs. **Almost every "EMPTY_FR" piece was actually sitting inside
the conflated text of its sibling**, identifiable by author
running-header transitions (`Author Name. — N.` at page tops).

Pieces filled via running-header splits (no new OCR):

| Cahier | Newly-filled piece | Source sibling that was conflated |
|---|---|---|
| s05-c07 | Tharaud *Moines de l'Athos* (15,075 w) | `notes-sur-la-hollande` |
| s06-c04 | Allier *L'enseignement primaire à Madagascar* (34,693 w) | `un-essai-de-monopole` |
| s07-c05 | Avenard *Le 22 janvier* (70,524 w) | `courrier-de-russie` |
| s07-c07 | Porché *Les suppliants* poem cycle (1,888 w) | `les-suppliants-paralleles` |
| s07-c08 | Spire *Et vous riez* (4,797 w) | `louis-de-gonzague` |
| s08-c07 | Garnier *Sonnets de Shakespeare I* (12,690 w) | swapped from `untitled` |
| s08-c15 | Garnier *Sonnets de Shakespeare* (15,444 w) | swapped from `untitled` |
| s10-c04 | Hamp *Vin de Champagne* (37,901 w) | swapped from `la-peine-des-hommes` |

All sibling files were trimmed + got `translationNotes` documenting the
reattribution.

## What's actually left

### Two pieces that need fresh vision OCR

| Cahier+piece | Title | Author | Why fresh OCR |
|---|---|---|---|
| s02-c14 courrier-de-chine | Courrier de Chine | lionel-landry | grep confirmed text is in no existing OCR file |
| s03-c02 les-universites-populaires | Les Universités Populaires | charles-guieysse | sibling too small to hide it |

### Three intentional placeholders (consider deleting)

These were created as side-effects of the Round 7 slug-swaps. They
hold no real content and the cahier JSON probably has the same slug —
deleting that row (and these .md files) would clean up the audit:

- `src/content/pieces/s08-c07--untitled.{fr,en}.md`
- `src/content/pieces/s08-c15--untitled.{fr,en}.md`
- `src/content/pieces/s10-c04--la-peine-des-hommes.{fr,en}.md`

Check `src/data/cahiers/sNN-cNN.json` (or wherever the piece roster
lives) before deleting — they may need a corresponding JSON entry
removed too.

### One quietly-missing essay

**s07-c08 Péguy *Louis de Gonzague*** (about the saint, not the
editorial back-matter). The current `s07-c08--louis-de-gonzague.fr.md`
holds only Péguy's editorial back-matter (errata, *Les suppliants
parallèles*, Gapone note). The actual *Louis de Gonzague* essay starts
at leaf 19 of `s7cahiersdelaquinz08pg` per the cahier's printed TOC
("CHARLES PÉGUY — Louis de Gonzague, p. XIII"). It is NOT flagged by
the audit (since the file has 3,286 w of *something*) but flagged in
the file's own `translationNotes`.

**The 156 JPGs for this cahier are already downloaded** at
`~/charlespeguy.com/raw/ocr-images/s07-c08/0005.jpg … 0160.jpg`. Cheap
to OCR — just need to find where the essay ends and Spire's poetry
begins.

### Extracted-OCR cleanup pass (optional)

All Round-7 extractions preserved the original OCR garble (margin
chars, lone letters, spine bleed). Per the project rule never invent
text — this is intentional but ugly. A future pass could run
`denoise-fr-pieces.py` or hand-clean the worst spots.

## Workflow per remaining cahier (s02-c14, s03-c02)

Same as prior brief — confirmed in Round 7's stopped first attempt:

1. **Sanity-check the conflated sibling first.** Round 7 proved that
   ~7/8 "EMPTY_FR" pieces were hiding in their siblings. Open the
   sibling .fr.md and grep for the target piece's author/keywords
   before launching any vision OCR.
2. If genuinely missing: probe
   `https://archive.org/metadata/<volume_id>` for leaves.
3. Download leaves via IIIF (`/raw/ocr-images/sNN-cNN/`).
4. Vision-OCR in chunks of ~28 leaves × 5 parallel subagents. Prompt MUST
   include: ignore right-margin spine bleed-through; skip blanks;
   preserve italics as `*…*`; `[?]` for illegibles; one
   `[leaf NNNN] [p. N]` marker per leaf.
5. Splice → `raw/<slug>-ocr.txt`.
6. Write `src/content/pieces/<cahier>--<piece>.fr.md` with proper
   frontmatter (`ocrSource` set to `Archive.org vision OCR <date>`).

Source URL lookups (from `~/charlespeguy.com/src/content/texts/sNN-cNN.md`):

- **s02-c14** Volume `s2cahiersdelaquinz12pg`, cahier range leaves 301–376
  (n300 → n376 in the source URL). 76 leaves total — small.
- **s03-c02** Volume `s3cahiersdelaquinz01pg`, cahier range leaves 81–150.
  70 leaves total — also small.

Both are small enough for 3 parallel subagents each.

## Done-criteria for the session

- `audit-pieces.py` shows EMPTY_FR ≤ 3 (the 3 placeholders may remain
  pending JSON cleanup, that's fine).
- `NODE_OPTIONS="--max-old-space-size=2048" npx astro build` passes.
- `git push` to `origin main`.
- Update `~/.claude/projects/-Users-wilsonpruitt/memory/project_charlespeguy-audit-2026-05-25.md`
  with the new totals.

## Other open items (not blocking)

- EMPTY_EN: 12. LOW_PROSE_EN: 17. NO_EN: 8. EN side is a separate
  workstream; defer until FR side is clean.
- 4 AUTHOR_MISMATCH flags are false positives — could add an exemption
  list to `scripts/audit-pieces.py` for cleaner output.
- s10-c09 still holds the full ~59k-word Wikisource *Dans la maison*
  under the `dans-la-maison-1` slug. A future polish pass could split
  the Wikisource text at the historical Cahier part-break and apportion
  between s10-c09 and s10-c10. Flagged in s10-c09's `translationNotes`.
- Cloudflare DNS for charlespeguy.org still pending: A `76.76.21.21`
  (DNS-only) + CNAME `www → cname.vercel-dns.com`.

## Don't forget

- 8 GB RAM Mac — max 5 parallel vision-OCR agents.
- `denoise-fr-pieces.py` is idempotent and safe to rerun.
- `audit-pieces.py` is the source of truth; this file can drift.
- Commit messages end with the Claude co-author trailer.
- **Always check the conflated sibling first** before assuming a piece
  needs fresh OCR — Round 7 burned a 60K-token wasted vision-OCR
  attempt that should have been a 5-second grep.
