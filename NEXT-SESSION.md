# Next-session brief — Jean-Christophe OCR repair + stub-translation cleanup

Drafted 2026-05-25 at the end of the launch session. Drop this whole file into a fresh `/clear`'d Claude Code session inside `~/charlespeguy.org/` to pick up the work.

---

## Context (read first)

Last session shipped charlespeguy.org to Vercel (live at `https://charlespeguy-org.vercel.app`; custom domain DNS pending). The site has **1,716 static pages**, fully bilingual (EN/FR with auto-detect + toggle), built from `~/charlespeguy.org/` (Astro 6 + content collections).

Read these memories in order:
1. `~/.claude/projects/-Users-wilsonpruitt/memory/project_charlespeguy-site-direction.md` — design decisions, page tree, known cleanup
2. `~/.claude/projects/-Users-wilsonpruitt/memory/peguy-translation-gaps.md` — OCR pipeline conventions, vision-OCR workflow, leaf-range corrections
3. `~/charlespeguy.com/PROGRESS.md` §"2026-05-24 OCR wave summary" — how today's parallel-agent OCR for s09-c14 worked

The PROGRESS.md section is the playbook: vision-OCR'd 140 leaves for s09-c14 via 5 parallel subagents in ~10 minutes, with zero `[?]` flags, by giving each agent a 28-leaf chunk and a clear prompt that included "ignore right-margin spine bleed-through fragments." Same pattern applies here.

---

## Problem 1 — Eleven Jean-Christophe cahiers have garbled French OCR

The migration pulled FR text from `~/charlespeguy.com/src/content/texts/<slug>.md`, where those files have Tesseract-image-bleed garbage instead of clean text. The original Foire-2 (s09-c14) had the same problem; we vision-OCR'd it through earlier today and it now reads clean.

The remaining 11 affected cahiers:

| Slug   | Installment                       | Catalog label | Archive volume |
|--------|------------------------------------|---------------|----------------|
| s05-c09 | I. L'aube                          | V-9           | s5cahiersdelaquinz06pg |
| s06-c08 | III. L'adolescent                  | VI-8          | nscahiersdelaqui08pg   |
| s08-c04 | IV. La révolte. 1. Sables mouvants | VIII-4        | s8cahiersdelaquinz04pg |
| s08-c06 | IV. La révolte. 2. L'enlisement    | VIII-6        | s8cahiersdelaquinz05pg |
| s08-c09 | IV. La révolte. 3. La délivrance   | VIII-9        | s8cahiersdelaquinz05pg |
| s09-c13 | À Paris. I. La foire sur la Place. 1 | IX-13       | s9cahiersdelaqui13pg   |
| s09-c15 | À Paris. Antoinette                | IX-15         | s9cahiersdelaqui15pg   |
| s10-c09 | À Paris. II. Dans la maison. 1     | X-9           | s10cahiersdelaqui09pg  |
| s10-c10 | À Paris. II. Dans la maison. 2     | X-10          | s10cahiersdelaqui09pg  |
| s14-c02 | La nouvelle journée. 1             | XIV-2         | s14cahiersdelaqui01pg  |
| s14-c03 | La nouvelle journée. 2             | XIV-3         | s14cahiersdelaqui01pg  |

(Already clean: s05-c10, s09-c14, s11-c07, s11-c08, s13-c05, s13-c06.)

**Each cahier is ~150–300 leaves.** Total roughly 2,200 leaves of vision OCR.

### Repair workflow per cahier (replicating today's s09-c14 success)

1. **Re-download leaves** from Archive.org. `~/charlespeguy.com/raw/ocr-images/` was deleted earlier today; need to bring images back. Use `npx tsx scripts/redownload-leaves.ts <slug>` from `~/charlespeguy.com/`. The script's leaf-ranges for these 11 cahiers should be correct (verified during today's discoveries) — but probe leaves at the start + end to confirm before kicking off the OCR.
2. **Classify leaves** (sparse/content/blank) via `scripts/classify-leaves.ts <slug>` if it exists; otherwise judge by file size (<100KB blank, 100–170KB sparse, >170KB content).
3. **Vision-OCR in chunks of ~28 leaves per subagent, dispatched in parallel**. 5 agents at a time worked well today on this 8 GB Mac. Each agent prompt should include the standard guards:
   - Page markers `[leaf NNNN] [p. N]` on their own line
   - Faithful transcription, NO paraphrase, `[?]` for illegibles
   - Ignore right-margin spine bleed-through (the key fix that worked for s09-c14)
   - Skip blank/binding leaves
   - Preserve italic markup as `*asterisks*`
4. **Splice chunks** into `~/charlespeguy.com/raw/<slug>-ocr.txt` with a clean header.
5. **Reconcile into the .org repo**: write/overwrite `~/charlespeguy.org/src/content/pieces/<slug>--<piece-slug>.fr.md` with the new body. Match the existing frontmatter format (see any existing piece for shape). Word count + `ocrSource: "Archive.org vision OCR 2026-05-25"`.

### Pace + budget

Today's 9 cahiers OCR'd took ~5 hours wall-clock with parallel agents. 11 more cahiers + downloading + reconciliation = full session, possibly two. Each cahier's OCR can run as 5 parallel agents (~28 leaves × 5 = 140 leaves per wave); larger cahiers need 2 waves.

Order suggestion: smallest first to build momentum (Antoinette s09-c15 is shortest), biggest last (Foire 1 s09-c13 and Adolescent s06-c08 are largest).

---

## Problem 2 — Stub English translations pointing at sibling cahiers

When the original translator hit a work that ran across two cahiers (like *La Nouvelle Journée* across s14-c02 + s14-c03), they put the whole translation at the first cahier's URL and left the second as a 2-sentence pointer.

**Confirmed instance**: s14-c03 EN body says only:

> The Wikisource source for *La Nouvelle Journée* presents Cahiers s14-c02 and s14-c03 as a single continuous text. The complete English translation of both cahiers is published at s14-c02.

**Probable other instances** — pairs where one cahier hosts the full translation and the next has a stub:

| Pair | Work | Stub at... |
|---|---|---|
| s09-c13 + s09-c14 | *La foire sur la Place* 1+2 | maybe s09-c14? (we did our own translation today; check) |
| s10-c09 + s10-c10 | *Dans la maison* 1+2 | unknown |
| s11-c07 + s11-c08 | *La fin du voyage* 1+2 | unknown |
| s13-c05 + s13-c06 | *Le buisson ardent* 1+2 | unknown |
| s14-c02 + s14-c03 | *La nouvelle journée* 1+2 | **confirmed: s14-c03 is the stub** |

### Cleanup approach

For each affected pair:
1. Find which cahier hosts the full translation.
2. Decide policy:
   - **Option A**: Split the long translation in half at the print boundary (page where the original cahier ended) and put each half at its corresponding URL.
   - **Option B**: Keep the full translation at the first cahier's URL, but make the second cahier's piece page a graceful "continuation" view — not just a sentence, but a proper UI that says "This text continues in the previous cahier; read it here" with a strong link back, and link forward to the cahier-table that shows the boundary.

Wilson's likely preference: **Option A** (per-cahier URLs that match the periodical-as-printed framing). Splitting requires finding the page boundary in the EN text that corresponds to the cahier boundary — which means cross-referencing the FR page-numbers in the OCR'd source (so this depends on **Problem 1** being resolved first, since the FR text is currently garbage for most of these).

For pairs where both halves were translated separately today (s09-c14 was translated in this session; check whether s09-c13 has a clean EN), no action needed.

---

## Problem 3 — Other low-priority cleanup (do if there's time)

- **~23 remaining stub author bios** for minor single-piece contributors. Honest-stub treatment is acceptable; only fill in if you have real biographical info.
- **Piece-slug inconsistency**: some pieces have EN-slugified slugs (e.g. `the-milliets-i-up-to-the-threshold-of-exile`) because migration picked from EN frontmatter. Cosmetic; routes correctly. If you want consistency, rename to French-slug everywhere — touch the cahier JSON pieces array AND the piece MD files AND any `works/*.md` parts arrays that reference them.
- **Multi-author pieces** show only primary author (schema is `author: reference('authors')` single ref). If you want to support multi-author rendering properly, refactor schema to `authors: array<reference>` + update templates.
- **DNS for charlespeguy.org**: still pending. Cloudflare A-record at `76.76.21.21` (DNS-only, not proxied) and CNAME `www → cname.vercel-dns.com`. Verify Vercel email confirmation once propagated.
- **Custom 404 page** — currently Vercel's default. Add `src/pages/404.astro` with the site's restraint.

---

## How to know you're done

- `~/charlespeguy.com/raw/<slug>-ocr.txt` exists and is clean (no Tesseract garbage) for all 11 cahiers above.
- `~/charlespeguy.org/src/content/pieces/<slug>--<piece-slug>.fr.md` for each of the 11 cahiers contains the new clean FR text.
- Build is green: `cd ~/charlespeguy.org && NODE_OPTIONS="--max-old-space-size=2048" npx astro build`.
- Spot-check: open `/cahiers/s14-c03/<piece>/fr` in the dev server (`npm run dev`) and confirm the text reads as Rolland prose, not garbled OCR.
- Stub-English pairs identified and resolved (split or graceful continuation, your choice).
- Deploy: `npx vercel deploy --prod --yes`.
- Update `~/.claude/projects/-Users-wilsonpruitt/memory/project_charlespeguy-site-direction.md` "Cleanup landed" section with the new OCR repair.

---

## Don't forget

- 8 GB RAM Mac — don't launch more than 5 parallel vision-OCR agents.
- Per-day vision-OCR cap was lifted today; cost-aware but no hard cap.
- Reconciliation pattern is in `~/charlespeguy.org/scripts/reconcile-today.py` (idempotent).
- The s09-c14 vision-OCR-repair full transcript is in today's session memory if you want the exact prompt template — search `peguy-translation-gaps.md` for the `s09-c14 vision-OCR repair` block.
- Commit messages should end with the Claude co-author line.
