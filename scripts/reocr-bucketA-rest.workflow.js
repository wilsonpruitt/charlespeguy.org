export const meta = {
  name: 'reocr-bucketA-rest',
  description: 'Re-OCR the 8 remaining (medium/large) bucket-A Cahiers pieces from archive.org scans, multi-batch',
  phases: [
    { title: 'Scout', detail: 'pin leaf range + offset for each of the 8 pieces' },
    { title: 'Transcribe', detail: 'per piece: N parallel batch agents -> part files' },
  ],
}

const REPO = '/Users/wilsonpruitt/charlespeguy.org'
const BATCH_LEAVES = 26

const PROTOCOL = `
TRANSCRIPTION RULES (from audit-screens/REOCR-PROTOCOL.md — obey verbatim):
1. Transcribe EXACTLY what is printed. No modernizing/summarizing/paraphrasing or
   silent correction of the author's own spelling/punctuation.
2. Join hyphenated line-breaks into whole words ("pré-\\ncédent" -> "précédent");
   keep a hyphen only if genuinely hyphenated (peut-être).
3. Modern curly apostrophe ’ and accents as printed.
4. DROP running chrome: running head, page numbers, foot signature marks.
5. DROP publisher back-matter: subscription pages, price lists, Imprimerie… colophons,
   "Ce cahier est composé par des ouvriers syndiqués", catalogue pages.
6. PRESERVE structure: paragraph breaks, section dividers (* * *), speaker labels,
   block quotes. Use markdown ## for section/chapter headings, > for epigraphs/quotes.
7. Italics -> *italics*.
8. Footnotes: transcribe where the marker sits OR collect per page at page end —
   be consistent; keep (1) markers.
9. NEVER invent. Unreadable glyph -> [?]. Missing/ripped word -> […].
10. No commentary — only the transcribed text.
`

function scoutPrompt(p) {
  const stem = `${p.cahier}--${p.slug}`
  const boundary = p.totalPieces > 1
    ? `This cahier has ${p.totalPieces} pieces; target is piece ${p.pieceIndex + 1} ("${p.title}").${p.nextTitle ? ` It ENDS where the next piece "${p.nextTitle}" begins.` : ' It is the LAST piece — ends before the publisher colophon/back-matter.'}`
    : `Single-piece cahier ("${p.title}"): body runs from after the front-matter (cover, half-title, publisher's front listing) to before the final colophon/back-matter.`
  return `Locate the page-image leaf range for ONE Cahiers de la Quinzaine piece in archive.org item ${p.id}, so it can be transcribed. Work in ${REPO}.

PIECE: ${stem} — "${p.title}" by ${p.author}; stored (untrusted) wordCount ${p.words}.
Current body starts (noisy anchor): "${p.anchor}"
${boundary}

DO:
1. cd ${REPO} && python3 scripts/fetch-cahier-pages.py --id ${p.id} --probe   (note imagecount)
2. curl -s -A "peguy-audit/1.0" "https://archive.org/download/${p.id}/${p.id}_djvu.txt" -o /tmp/${p.id}.txt
   Grep it for the anchor words, the title, and (if not last) the next piece's title to
   find where this piece's prose starts and ends, using the embedded printed page numbers.
3. PIN THE OFFSET (leaf = printed page + offset): fetch 1-2 probe leaves
   (python3 scripts/fetch-cahier-pages.py --id ${p.id} --leaves N) and Read
   raw/scans/${p.id}/${p.id}_000N.jpg to see which printed page that leaf shows.
   BEWARE bound multi-cahier volumes (large imagecount) and duplicate/re-shot leaves.
4. Return the BODY leaf range (front-matter excluded, colophon excluded).

Return ONLY the structured result. Do NOT transcribe.`
}

const SCOUT_SCHEMA = {
  type: 'object',
  required: ['stem', 'firstLeaf', 'lastLeaf', 'offset', 'ok', 'notes'],
  properties: {
    stem: { type: 'string' },
    firstLeaf: { type: 'integer' },
    lastLeaf: { type: 'integer' },
    offset: { type: 'integer' },
    printedFirst: { type: 'integer' },
    printedLast: { type: 'integer' },
    ok: { type: 'boolean' },
    notes: { type: 'string' },
  },
}

function batchPrompt(p, a, b, k, nbatches) {
  const stem = `${p.cahier}--${p.slug}`
  return `Transcribe part ${k}/${nbatches} of the Cahiers piece "${p.title}" (${p.author}) from archive.org item ${p.id}. Work in ${REPO}.

YOUR LEAVES: ${a}-${b} (this is one slice of the piece's body; other agents handle the rest).

DO:
1. cd ${REPO} && python3 scripts/fetch-cahier-pages.py --id ${p.id} --leaves ${a}-${b}
2. Read each downloaded raw/scans/${p.id}/${p.id}_NNNN.jpg IN ORDER and transcribe it.
${PROTOCOL}
SEAM RULES (critical — you are a middle slice):
- Do NOT add the piece title or any heading that isn't printed on YOUR leaves.
- Start transcribing at the very top of your first leaf (even if mid-sentence) and stop
  at the very bottom of your last leaf (even if mid-sentence / mid-word with a hyphen).
  Keep a trailing hyphen if the last word breaks across the page — the assembler joins it.
- Part ${k} ${k === 1 ? 'IS the first slice: skip any front-matter before the body actually starts.' : 'is NOT the first slice: do not re-transcribe earlier pages.'}
${k === nbatches ? '- This is the LAST slice: stop before the publisher colophon/back-matter.' : ''}

3. Write the transcription to raw/reocr/${stem}.part${k}.md (create dirs if needed). Body text only.
   Then VERIFY the file is non-empty (wc -c). If it is empty/tiny, your transcription was lost —
   redo it; only report ok:true once the file actually contains the transcribed prose.
4. If the API blocks your output (content filter), STOP and report blocked:true — do not retry.

Return ONLY the structured result.`
}

const BATCH_SCHEMA = {
  type: 'object',
  required: ['k', 'ok', 'blocked'],
  properties: {
    k: { type: 'integer' },
    ok: { type: 'boolean', description: 'true if part file written' },
    blocked: { type: 'boolean', description: 'true if content filter blocked transcription' },
    words: { type: 'integer' },
    notes: { type: 'string' },
  },
}

function assemblePrompt(p, sc, nbatches) {
  const stem = `${p.cahier}--${p.slug}`
  return `Assemble the transcribed parts of "${p.title}" into its final .fr.md. Work in ${REPO}.

PARTS: raw/reocr/${stem}.part1.md … raw/reocr/${stem}.part${nbatches}.md (read ALL in order).

DO:
1. Read the ${nbatches} part files in numeric order.
2. Join them into one body:
   - If a part ends mid-word with a hyphen and the next starts a word -> join into one word.
   - If a part ends mid-sentence (no terminal punctuation) and the next continues lowercase
     -> join with a single space.
   - Otherwise (paragraph/section boundary) -> separate with a blank line.
   - Do NOT duplicate text across the seam; remove any obvious overlap.
3. Rewrite ${REPO}/src/content/pieces/${stem}.fr.md:
   - KEEP existing frontmatter keys cahier, pieceSlug, lang, title, author, isAvertissement.
   - REMOVE any old ocrSource / sourceProvenance / "OCR:" / "Source:" lines; KEEP translationNotes if present.
   - SET wordCount to the new body's whitespace-token count.
   - ADD: ocrSource: "Archive.org ${p.id} leaves ${sc.firstLeaf}-${sc.lastLeaf} (printed p.${sc.printedFirst ?? '?'}-${sc.printedLast ?? '?'}), vision re-OCR (Opus 4.8) 2026-06-23 — replaces noisy prior OCR"
   - Body = the joined transcription, NO leftover title/H1 at the top (title is in frontmatter).
4. Spot-check the seams read continuously and the body is clean French.

Return ONLY the structured result.`
}

const ASSEMBLE_SCHEMA = {
  type: 'object',
  required: ['stem', 'ok', 'newWordCount'],
  properties: {
    stem: { type: 'string' },
    ok: { type: 'boolean' },
    newWordCount: { type: 'integer' },
    notes: { type: 'string' },
  },
}

const pieces = typeof args === 'string' ? JSON.parse(args) : args

// ---- Phase 1: scout all pieces in parallel (light) ----
phase('Scout')
const scouts = await parallel(
  pieces.map(p => () =>
    agent(scoutPrompt(p), { label: `scout:${p.cahier}`, phase: 'Scout', schema: SCOUT_SCHEMA })
  )
)

// ---- Phase 2: per piece, transcribe batches in parallel, then assemble. Pieces sequential (8GB). ----
phase('Transcribe')
const results = []
for (let i = 0; i < pieces.length; i++) {
  const p = pieces[i]
  const sc = scouts[i]
  if (!sc || !sc.ok || !(sc.lastLeaf > sc.firstLeaf)) {
    results.push({ stem: `${p.cahier}--${p.slug}`, status: 'scout-failed', notes: sc?.notes || 'no scout' })
    log(`✗ ${p.cahier}--${p.slug}: scout failed`)
    continue
  }
  // split [firstLeaf,lastLeaf] into ~BATCH_LEAVES chunks
  const ranges = []
  for (let a = sc.firstLeaf; a <= sc.lastLeaf; a += BATCH_LEAVES) {
    ranges.push([a, Math.min(a + BATCH_LEAVES - 1, sc.lastLeaf)])
  }
  const nb = ranges.length
  const batches = await parallel(
    ranges.map(([a, b], idx) => () =>
      agent(batchPrompt(p, a, b, idx + 1, nb),
        { label: `ocr:${p.cahier}-p${idx + 1}`, phase: 'Transcribe', schema: BATCH_SCHEMA })
    )
  )
  const blocked = batches.some(x => x && x.blocked)
  const allOk = batches.length === nb && batches.every(x => x && x.ok && !x.blocked)
  if (!allOk) {
    results.push({ stem: `${p.cahier}--${p.slug}`, status: blocked ? 'filter-blocked' : 'batch-failed',
      partsSaved: batches.filter(x => x && x.ok).length, nb, leafRange: `${sc.firstLeaf}-${sc.lastLeaf}` })
    log(`✗ ${p.cahier}--${p.slug}: ${blocked ? 'FILTER-BLOCKED' : 'batch failed'} (${batches.filter(x => x && x.ok).length}/${nb} parts saved)`)
    continue
  }
  const asm = await agent(assemblePrompt(p, sc, nb),
    { label: `assemble:${p.cahier}`, phase: 'Transcribe', schema: ASSEMBLE_SCHEMA })
  results.push({ stem: `${p.cahier}--${p.slug}`, status: asm && asm.ok ? 'done' : 'assemble-failed',
    newWordCount: asm?.newWordCount, leafRange: `${sc.firstLeaf}-${sc.lastLeaf}`, notes: asm?.notes })
  log(`✓ ${p.cahier}--${p.slug}: ${asm?.newWordCount}w (leaves ${sc.firstLeaf}-${sc.lastLeaf})`)
}

const done = results.filter(r => r.status === 'done').length
log(`Bucket-A rest: ${done}/${pieces.length} assembled`)
return results
