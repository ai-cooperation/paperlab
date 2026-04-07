/**
 * Normalization functions for metadata field comparison.
 * Rules derived from Paper 1 (Chen, 2026, Scientometrics).
 */

export function normalizeTitle(s) {
  if (!s) return '';
  return unifyHyphens(s)
    .replace(/<[^>]+>/g, '')   // strip HTML tags (CrossRef returns <scp>, <i>, etc.)
    .toLowerCase().trim()
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function normalizeYear(s) {
  if (!s) return null;
  const n = parseInt(String(s), 10);
  return isNaN(n) ? null : n;
}

/**
 * Normalize all hyphen-like Unicode characters to ASCII hyphen.
 */
function unifyHyphens(s) {
  // U+2010 hyphen, U+2011 non-breaking hyphen, U+2012 figure dash,
  // U+2013 en-dash, U+2014 em-dash, U+2015 horizontal bar, U+00AD soft hyphen
  return s.replace(/[\u2010\u2011\u2012\u2013\u2014\u2015\u00AD]/g, '-');
}

/**
 * Normalize a single author name to "family given" order (lowercase, no punctuation).
 * Handles: "LeCun, Yann" → "lecun yann", "Yann LeCun" → "lecun yann"
 */
export function normalizeAuthorName(name) {
  if (!name) return '';
  let s = unifyHyphens(name)
    .replace(/\./g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();

  // If contains comma → "family, given" → already correct order
  if (s.includes(',')) {
    const parts = s.split(',').map(p => p.trim()).filter(Boolean);
    const tokens = parts.flatMap(p => p.split(/\s+/));
    return tokens.sort().join(' ');
  }

  // No comma → "given family" or "given middle family"
  const tokens = s.split(/\s+/).filter(Boolean);
  return tokens.sort().join(' ');
}

export function normalizeAuthors(list) {
  if (!list || !Array.isArray(list)) return [];
  return list.map(normalizeAuthorName).filter(Boolean).sort();
}

export function normalizeJournal(s) {
  if (!s) return '';
  return unifyHyphens(s)
    .replace(/<[^>]+>/g, '')
    .toLowerCase()
    .replace(/\./g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function normalizePages(s) {
  if (!s) return '';
  return String(s)
    .replace(/\s*[-–—]\s*/g, '-')
    .trim();
}

export function normalizeVolume(s) {
  if (!s) return '';
  return String(s).trim();
}
