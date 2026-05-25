// Bidirectional URL translation for the EN/FR sibling routes.
// Same content, different chrome and URL slug per language.

const enToFrSegment: Record<string, string> = {
  about: 'a-propos',
  authors: 'auteurs',
  works: 'oeuvres',
  cahiers: 'cahiers', // same word both languages
};

const frToEnSegment: Record<string, string> = Object.fromEntries(
  Object.entries(enToFrSegment).map(([en, fr]) => [fr, en])
);

/** Return true if the given pathname is a French route. */
export function isFrPath(path: string): boolean {
  return path === '/fr' || path === '/fr/' || path.startsWith('/fr/');
}

/** Convert an EN path to its FR mirror, or return /fr/ for root. */
export function toFr(path: string): string {
  if (path === '/' || path === '') return '/fr/';
  if (isFrPath(path)) return path;
  // Translate first segment
  const segments = path.split('/').filter(Boolean);
  if (segments[0] && enToFrSegment[segments[0]]) {
    segments[0] = enToFrSegment[segments[0]];
  }
  return '/fr/' + segments.join('/');
}

/** Convert an FR path to its EN mirror. */
export function toEn(path: string): string {
  if (!isFrPath(path)) return path;
  const stripped = path.replace(/^\/fr/, '') || '/';
  if (stripped === '/') return '/';
  const segments = stripped.split('/').filter(Boolean);
  if (segments[0] && frToEnSegment[segments[0]]) {
    segments[0] = frToEnSegment[segments[0]];
  }
  return '/' + segments.join('/');
}

/** Build a chrome-language-appropriate URL for a section. */
export function navUrl(section: 'cahiers' | 'authors' | 'works' | 'about', isFr: boolean): string {
  if (!isFr) return `/${section}`;
  return `/fr/${enToFrSegment[section]}`;
}

/** Build a piece URL with the right chrome prefix. */
export function pieceUrl(cahierSlug: string, pieceSlug: string, pieceLang: 'fr' | 'en', chromeIsFr: boolean): string {
  const prefix = chromeIsFr ? '/fr' : '';
  return `${prefix}/cahiers/${cahierSlug}/${pieceSlug}/${pieceLang}`;
}

/** Build a cahier URL with the right chrome prefix. */
export function cahierUrl(cahierSlug: string, chromeIsFr: boolean): string {
  const prefix = chromeIsFr ? '/fr' : '';
  return `${prefix}/cahiers/${cahierSlug}`;
}

/** Build an author URL with the right chrome prefix. */
export function authorUrl(authorSlug: string, chromeIsFr: boolean): string {
  const prefix = chromeIsFr ? '/fr/auteurs' : '/authors';
  return `${prefix}/${authorSlug}`;
}

/** Build a work URL with the right chrome prefix. */
export function workUrl(workSlug: string, chromeIsFr: boolean): string {
  const prefix = chromeIsFr ? '/fr/oeuvres' : '/works';
  return `${prefix}/${workSlug}`;
}
