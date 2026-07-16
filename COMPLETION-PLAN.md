# charlespeguy.org — Completion plan (to full-quality FR + EN, all 229 cahiers)

Drafted 2026-07-16 (Fable planning session). Execute phases in cheaper
sessions per the model assignments below. `audit-pieces.py` and
`audit-corpus-noise.py` are the source of truth; this file is the map,
not the tracker.

## Verified state as of 2026-07-16

- Site **live at charlespeguy.org** — bilingual chrome (EN + `/fr`),
  three axes built (cahiers / authors / works). Analytics live.
- **267 pieces** across 229 cahiers, 267 `.fr.md` / 261 `.en.md`.
- **FR corpus: 6.48M words.** Piece-level coverage nearly complete:
  3 EMPTY_FR, 1 LOW_PROSE_FR. Quality program in flight (re-OCR rounds
  17–22 done; ledger: 62 old-Gallica + 16 back-matter targets remain).
- **EN corpus: 3.05M words.** Of 263 substantive pieces (FR ≥ 100 w):
  - full EN (≥80% of FR length): **115**
  - partial (50–80%): 12 · excerpt (10–50%): 48 · stub (<10%): 82 · missing: 6
  - **EN gap = 148 pieces ≈ 3.9M FR words**
    (Péguy-authored: 42 pieces / 889k w · other authors: 106 pieces / 3.0M w)
- The mystères, Tapisserie, Notre jeunesse, Laudet all have **full EN
  already**. **Ève (s15-c04) is the one big verse holdout** (EN = 15 w).
- Old `.com` repo is essentially fully migrated. Only two salvage gaps:
  - `s03-c04` Études Socialistes (Jaurès): 72k EN words in `.com`, 7k in `.org`
  - `s14-c02` Jean-Christophe Nouvelle journée 1: 60k in `.com`, 35k in `.org`

## Decision gates (Wilson answers before the phase that needs them)

1. **Back-matter EN policy** — annonces / librairie catalogs / indexes /
   administration pieces (~16 targets, low-hundreds-of-k words). Full
   translation, or a documented "presented in French with EN headnote"
   standard? Recommendation: full EN for anything Péguy *wrote*
   (Administration, Pour moi, etc.); headnote standard for pure catalog
   matter (Librairie des cahiers, Petit index alphabétique, Inventaire).
2. **Ève** — memory says Wilson has his own EN translation of Ève ready.
   Ingest that (preferred), or run the verse pipeline on it?
3. **Model + go for the EN volume run** — hard stop #6. Estimated burn
   once-through, incl. chunking overhead: Péguy slice ≈ 1.6M in / 1.4M out
   (Opus per feedback_opus-for-authored-prose); other-author slice ≈
   5.5M in / 5M out (Sonnet, frozen prompt). State the numbers, ask
   "which model, and go?" before each wave block.

## Phase A — Close the last FR holes (Sonnet vision agents, small)

Order matters: FR is the source of truth; translating dirty FR bakes
noise into EN. A+B before C.

- [ ] `s10-c12` Le travail de Zarathoustra (Halévy) — EMPTY_FR **and**
      #1 dirtiest on the noise ledger; fresh vision OCR from scans.
- [ ] `s13-c03` La guerre de France — EMPTY_FR, vision OCR.
- [ ] `s13-c09` Un cas de conscience (Milliet) — EMPTY_FR, vision OCR.
- [ ] `s12-c02` "Les amis des cahiers" — LOW_PROSE_FR, repair.
- [ ] `s11-c09` Vuillaume — **Wilson supplies content-filter splices**
      (manual transcription of blocked pages); splice + finalize.
- [ ] Salvage the two `.com` migration gaps (s03-c04, s14-c02) — split
      existing EN into piece files; no retranslation.
- Standing rules: ≤5 parallel vision agents (8 GB RAM), never invent
  text, check conflated siblings before fresh OCR, `/clear` between
  cahiers, duplicate-scan and short-tail-leaf checks per memory.

## Phase B — FR quality to "quality French" (Sonnet, mechanical)

- [ ] Finish the re-OCR bucket program: **62 old-Gallica targets** on
      `audit-corpus-noise.py` ledger, worst-first (existing
      `reocr-*.workflow.js` harnesses; rounds 17–22 pattern).
- [ ] **16 back-matter targets** — apply gate-1 decision (re-OCR the
      "Péguy wrote it" set; headnote standard for catalog matter).
- [ ] Work the `audit-screens/verify-peguy-worklist.md` eyeball pass
      (62 ranked Péguy pieces): `denoise-fr-pieces.py` for mechanical
      noise, re-OCR for char-level garble, verify on RENDERED pages.
- [ ] Exit criteria: noise ledger top score < 5.0; worklist cleared or
      each residual flagged-with-reason in `translationNotes`.

## Phase C — EN completion, the big lift (~3.9M FR words)

Wave structure, mirroring the old prose waves. Freeze the translation
prompt before wave 1; carry `translationDate` + provenance frontmatter.

- [ ] **C0 — conventions:** freeze prose-translation prompt in-repo
      (register, names, "race"=lineage note, italics, page markers).
      If gate 2 = translate Ève here, run the verse-convention pilot
      first (calibrate against Wilson's Ève excerpts; freeze verse
      conventions file) — this pilot is Fable/Opus-shaped, do it while
      available.
- [ ] **C1 — Péguy prose gap (41 pieces / ~825k w) — Opus.** Waves of
      ~10 pieces, biggest first (Waldeck-Rousseau 83k, Congrès de
      Dresde 58k, Texte sans commentaires 42k, Petites garnisons 42k…).
      Complete the partial/excerpt pieces by *extending*, not
      retranslating what's good.
- [ ] **C2 — Ève** per gate 2 (ingest Wilson's translation or verse
      pipeline with frozen conventions; Wilson reviews either way).
- [ ] **C3 — other-author prose (106 pieces / ~3.0M w) — Sonnet,**
      frozen prompt, waves of ~10; long serials (Milliet, Vuillaume,
      Jean-Christophe remainders, Suarès) keep per-serial glossaries.
- [ ] **C4 — back-matter EN** per gate 1 (translate or headnote).
- Each wave: hard-stop #6 check-in ("est. burn X in / Y out, model Z —
  go?"), then run, then `audit-pieces.py` + build + commit.

## Phase D — EN quality assurance (Sonnet/Haiku)

- [ ] Extend `audit-pieces.py` with EN-side length-ratio + noise flags
      (mirror of the FR ledger) so "quality English" is measurable.
- [ ] Spot-QA sample per wave (1 piece per wave, rendered-page read).
- [ ] Fix the 4 AUTHOR_MISMATCH flags via an exemption list (known
      false positives — title mentions ≠ author).

## Phase E — Data integrity + definition of done (Haiku/Sonnet)

- [ ] Retire `COM_*` flags from `audit-pieces.py` (migration is done;
      50 flags are now noise) — keep as `--provenance` opt-in if useful.
- [ ] Delete the 3 intentional placeholder stubs + their cahier-JSON
      rows (s08-c07/s08-c15 `untitled`, s10-c04 `la-peine-des-hommes`).
- [ ] Split s10-c09/s10-c10 *Dans la maison* at the historical cahier
      break (flagged in s10-c09 `translationNotes`).
- [ ] Works/serials axis: confirm every long serial reads correctly
      both ways (all-installments and per-cahier).

**DONE means:** `audit-pieces.py` reports zero EMPTY/LOW/NO flags in
both languages · noise ledger top score < 5 · every substantive piece
has EN ≥ 80% of FR length (or a gate-1 headnote exemption recorded in
frontmatter) · build passes · site deployed · memory updated.

## Suggested session sequence

1. One Sonnet session: Phase A (a few days of vision-OCR rounds).
2. Sonnet sessions: Phase B rounds until ledger < 5.0 (resumable, any time).
3. One Fable/Opus session: C0 conventions (+ verse pilot if needed) — small, high-leverage.
4. Opus sessions: C1 waves (Wilson gates each wave's burn).
5. C2 Ève with Wilson in the loop.
6. Sonnet sessions: C3 waves (the long grind — ~3M words).
7. Haiku/Sonnet: C4, D, E cleanup, final audit, deploy.
