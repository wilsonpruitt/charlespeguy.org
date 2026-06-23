export const meta = {
  name: 'reocr-waveA1',
  description: 'Re-OCR 6 small bucket-A Cahiers pieces from archive.org scans (vision, frozen protocol)',
  phases: [
    { title: 'Wave 1', detail: '3 pieces: et-vous-riez, ecoute-israel, de-napoleon' },
    { title: 'Wave 2', detail: '3 pieces: l-eglise-et-l-etat, evenements-actuels, crainquebille' },
  ],
}

const REPO = '/Users/wilsonpruitt/charlespeguy.org'

const PROTOCOL = `
TRANSCRIPTION RULES (from audit-screens/REOCR-PROTOCOL.md — obey verbatim):
1. Transcribe EXACTLY what is printed. No modernizing, summarizing, paraphrasing,
   or silent correction of the author's own spelling/punctuation.
2. Join hyphenated line-breaks into whole words: "pré-\\ncédent" -> "précédent".
   Keep a hyphen only if genuinely hyphenated (peut-être).
3. Use the modern curly apostrophe ’ and accents as printed (restore obvious
   accents the press set; never change wording).
4. DROP running chrome: running head (e.g. "cahier du 5 janvier 1900"), page
   numbers, signature marks at the foot. NOT text.
5. DROP publisher back-matter: subscription pages, price lists, Imprimerie…
   colophons, "Ce cahier est composé par des ouvriers syndiqués", catalogue pages.
6. PRESERVE structure: paragraph breaks, section dividers (* * *), speaker labels,
   block quotes.
7. Italics -> markdown *italics*.
8. Footnotes: transcribe where the marker sits OR collect per page at page end —
   be consistent; keep the (1) markers.
9. NEVER invent. Unreadable glyph -> [?]. Missing/ripped word -> […]. Do not guess
   proper names.
10. No commentary in output — only the transcribed text.
`

function pieceAgent(p) {
  const stem = `${p.cahier}--${p.slug}`
  const boundary = p.totalPieces > 1
    ? `This cahier has ${p.totalPieces} pieces; you want piece ${p.pieceIndex + 1} ("${p.title}").${p.nextTitle ? ` It ENDS where the next piece "${p.nextTitle}" begins.` : ' It is the LAST piece (ends before the publisher colophon/back-matter).'}`
    : `This cahier is a SINGLE piece ("${p.title}"). Transcribe all its body prose, skipping front-matter (cover, half-title, the publisher's front listing of cahiers) and the final colophon/back-matter.`
  return `You are re-OCR'ing one piece of Péguy's Cahiers de la Quinzaine from archive.org page scans, replacing noisy stored OCR with a clean vision transcription. Work in the repo ${REPO}.

PIECE: ${stem}
  title:  ${p.title}
  author: ${p.author}
  archive.org item id: ${p.id}
  stored (untrusted) wordCount: ${p.words}
  current body starts (noisy anchor, first 15 words): "${p.anchor}"
${boundary}

STEP 1 — SCOUT the leaf range:
  a. Probe the volume:  cd ${REPO} && python3 scripts/fetch-cahier-pages.py --id ${p.id} --probe
     Note the imagecount (total leaves).
  b. Download the archive text layer to find page/leaf boundaries:
     curl -s -A "peguy-audit/1.0" "https://archive.org/download/${p.id}/${p.id}_djvu.txt" -o /tmp/${p.id}.txt
     Grep it for the noisy anchor words and the piece title to find where the piece's
     prose starts, and (if not the last piece) where the next piece's title appears.
     The text has printed page numbers embedded — use them.
  c. PIN THE OFFSET (leaf = printed page + offset). Fetch 1–2 probe leaves as images
     to confirm, e.g.:  python3 scripts/fetch-cahier-pages.py --id ${p.id} --leaves N
     then Read raw/scans/${p.id}/${p.id}_000N.jpg and check which printed page that leaf shows.
     Determine firstLeaf and lastLeaf for the piece body (front-matter excluded).

STEP 2 — FETCH the leaves:
  python3 scripts/fetch-cahier-pages.py --id ${p.id} --leaves <firstLeaf>-<lastLeaf>
  (Images land in raw/scans/${p.id}/${p.id}_NNNN.jpg)

STEP 3 — TRANSCRIBE each leaf in order using the Read tool on each .jpg.
${PROTOCOL}

STEP 4 — WRITE the result:
  a. Write the assembled body to raw/reocr/${stem}.body.md (create dirs if needed).
  b. Rewrite ${REPO}/src/content/pieces/${stem}.fr.md:
     - KEEP the existing frontmatter keys cahier, pieceSlug, lang, title, author,
       isAvertissement EXACTLY as they are.
     - REMOVE any old ocrSource / sourceProvenance / "OCR:" / "Source:" lines.
     - SET wordCount to the new body's word count (count whitespace-separated tokens).
     - ADD this line in frontmatter:
       ocrSource: "Archive.org ${p.id} leaves <firstLeaf>-<lastLeaf> (printed p.<a>-<b>), vision re-OCR (Opus 4.8) 2026-06-23 — replaces noisy prior OCR"
     - Body = the transcription (NO leftover H1/title line at the top; the title lives
       in frontmatter — house style drops it).
  c. Spot-check: the body should read as clean French with none of the old garble.

Return ONLY the structured result.`
}

const SCHEMA = {
  type: 'object',
  required: ['stem', 'firstLeaf', 'lastLeaf', 'newWordCount', 'ok', 'notes'],
  properties: {
    stem: { type: 'string' },
    firstLeaf: { type: 'integer' },
    lastLeaf: { type: 'integer' },
    offset: { type: 'integer', description: 'leaf - printed page' },
    oldWordCount: { type: 'integer' },
    newWordCount: { type: 'integer' },
    ok: { type: 'boolean', description: 'true if the .fr.md was rewritten cleanly' },
    notes: { type: 'string', description: 'boundary reasoning, any [?]/[…] spots, anomalies' },
  },
}

const pieces = typeof args === 'string' ? JSON.parse(args) : args

phase('Wave 1')
const w1 = await parallel(
  pieces.slice(0, 3).map(p => () =>
    agent(pieceAgent(p), { label: `reocr:${p.cahier}-${p.slug.slice(0, 14)}`, phase: 'Wave 1', schema: SCHEMA })
  )
)

phase('Wave 2')
const w2 = await parallel(
  pieces.slice(3).map(p => () =>
    agent(pieceAgent(p), { label: `reocr:${p.cahier}-${p.slug.slice(0, 14)}`, phase: 'Wave 2', schema: SCHEMA })
  )
)

const all = [...w1, ...w2].filter(Boolean)
log(`Wave A1 done: ${all.filter(r => r.ok).length}/${pieces.length} rewritten`)
return all
