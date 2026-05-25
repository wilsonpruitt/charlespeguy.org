# charlespeguy.org

A digital archive of **Charles Péguy's *Cahiers de la Quinzaine*** (1900–1914) — Péguy's literary journal, which he founded, edited, and personally signed as *gérant* for fourteen years until his death at the Marne on 5 September 1914.

Today Péguy is remembered for a handful of writings (*Notre jeunesse*, *Le Mystère de la charité de Jeanne d'Arc*, *Ève*). This site is built around the corrective: that his life-project was the journal itself. 229 cahiers across 15 series, gathering writers like Romain Rolland (whose *Jean-Christophe* won the Nobel Prize in 1915), Maxime Vuillaume, Julien Benda, Daniel Halévy, Paul Milliet, and many others.

## Reading axes

The site has three:

1. **Cahier** (primary, front door) — chronological river of all 229 cahiers, each readable in its original publication form.
2. **Author** (secondary) — every contributor has an index page listing their pieces in publication order. Péguy's page additionally lists his *Avertissements*, each cross-linked to the article it introduced.
3. **Work** (tertiary) — five multi-cahier serials with literary identity beyond the Quinzaine get standalone pages:
   - *Jean-Christophe* (Rolland)
   - *Mes cahiers rouges* (Vuillaume)
   - *Les Milliet* (Paul Milliet)
   - *L'Ordination* (Benda)
   - *Les Mystères* (Péguy's trilogy)

## Stack

Astro 5 (static site generation), TypeScript, content collections for cahiers / pieces / authors / works. FR and EN have separate URLs per piece (`/cahiers/sNN-cMM/<piece>/fr` and `/cahiers/sNN-cMM/<piece>/en`).

## Status

Initial scaffold 2026-05-24. Content migrated from `~/charlespeguy.com/` (older site, English-only, custom build script).
