import { defineCollection, reference } from 'astro:content';
import { glob, file } from 'astro/loaders';
import { z } from 'astro/zod';

// charlespeguy.org content collections (Astro 6 — glob loaders required).
// See ~/.claude/projects/-Users-wilsonpruitt/memory/project_charlespeguy-site-direction.md

// ---------------------------------------------------------------------------
// Cahiers — the 229 issues of Cahiers de la Quinzaine (1900–1914).
// One JSON file per cahier at src/data/cahiers/<slug>.json.
// ---------------------------------------------------------------------------

const cahiers = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/data/cahiers' }),
  schema: z.object({
    slug: z.string(),                  // 's09-c14'
    series: z.number().int().min(1).max(15),
    issue: z.number().int().min(1),
    label: z.string(),                 // 'IX-14' (catalog label)
    titleFr: z.string(),               // 'Quatorzième cahier de la neuvième série'

    bonATirer: z.string().optional(),
    pageCount: z.number().int().optional(),
    printRun: z.number().int().optional(),
    whatmanCount: z.number().int().optional(),
    price: z.string().optional(),
    imprimeur: z.string().optional(),

    sourceUrl: z.string().url().optional(),
    sourceVolume: z.string().optional(),

    pieces: z.array(z.object({
      slug: z.string(),
      titleFr: z.string(),
      titleEn: z.string().optional(),
      author: reference('authors'),
      pages: z.string().optional(),
      isAvertissement: z.boolean().default(false),
    })),

    partOfWorks: z.array(reference('works')).default([]),
    notes: z.string().optional(),
  }),
});

// ---------------------------------------------------------------------------
// Pieces — every text inside a cahier, in FR and EN. Markdown bodies.
// File naming: src/content/pieces/<cahier-slug>--<piece-slug>.<lang>.md
// ---------------------------------------------------------------------------

const pieces = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/pieces' }),
  schema: z.object({
    cahier: reference('cahiers'),
    pieceSlug: z.string(),
    lang: z.enum(['fr', 'en']),
    title: z.string(),
    author: reference('authors'),
    isAvertissement: z.boolean().default(false),
    introducesPiece: z.string().optional(),
    ocrSource: z.string().optional(),
    translationDate: z.string().optional(),
    translationNotes: z.string().optional(),
    wordCount: z.number().int().optional(),
  }),
});

// ---------------------------------------------------------------------------
// Authors — every contributor to the Cahiers. Markdown bio body.
// ---------------------------------------------------------------------------

const authors = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/authors' }),
  schema: z.object({
    slug: z.string(),
    name: z.string(),
    nameSort: z.string(),
    born: z.string().optional(),
    died: z.string().optional(),
    nationality: z.string().optional(),
    isEditor: z.boolean().default(false),
  }),
});

// ---------------------------------------------------------------------------
// Works — five multi-cahier serials with literary identity beyond the Quinzaine.
// ---------------------------------------------------------------------------

const works = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/works' }),
  schema: z.object({
    slug: z.string(),
    title: z.string(),
    author: reference('authors'),
    parts: z.array(z.object({
      cahier: z.string(),
      piece: z.string(),
      label: z.string().optional(),
    })),
    yearSpan: z.string().optional(),
  }),
});

export const collections = { cahiers, pieces, authors, works };
