import { defineConfig } from 'astro/config';

// charlespeguy.org — a digital archive of Péguy's Cahiers de la Quinzaine.
// Front door: the periodical. Péguy as gérant, foregrounded.
// Three reading axes (cahier / author / work); cahier is primary.
// See ~/.claude/projects/-Users-wilsonpruitt/memory/project_charlespeguy-site-direction.md

export default defineConfig({
  site: 'https://charlespeguy.org',
  build: {
    format: 'directory',
  },
});
