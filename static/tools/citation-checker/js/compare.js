/**
 * Cross-database metadata comparison logic.
 * Rules from Paper 1 (Chen, 2026, Scientometrics).
 */

import {
  normalizeTitle, normalizeYear, normalizeAuthors,
  normalizeJournal, normalizePages, normalizeVolume
} from './normalize.js';

const FIELDS = ['title', 'year', 'authors', 'journal', 'volume', 'pages', 'doi'];

const NORMALIZERS = {
  title: normalizeTitle,
  year: normalizeYear,
  authors: normalizeAuthors,
  journal: normalizeJournal,
  volume: normalizeVolume,
  pages: normalizePages,
  doi: v => v ? v.toLowerCase().trim() : '',
};

/**
 * Compare a single field across sources.
 * Returns { status, values, suggested, detail }
 */
function compareField(field, sources) {
  const raw = {};
  const normalized = {};

  for (const [name, data] of Object.entries(sources)) {
    if (!data || data._error) continue;
    const val = data[field];
    raw[name] = val;
    if (val !== null && val !== undefined && val !== '') {
      normalized[name] = NORMALIZERS[field](val);
    }
  }

  const entries = Object.entries(normalized).filter(([, v]) =>
    v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0)
  );

  if (entries.length === 0) {
    return { status: 'missing', values: raw, suggested: null, detail: 'No database returned this field' };
  }

  if (entries.length === 1) {
    const [src] = entries[0];
    return { status: 'single', values: raw, suggested: raw[src], detail: `Only ${src} returned this field` };
  }

  // Compare normalized values
  const allSame = entries.every(([, v]) => {
    const first = entries[0][1];
    if (Array.isArray(v) && Array.isArray(first)) {
      return JSON.stringify(v) === JSON.stringify(first);
    }
    return String(v) === String(first);
  });

  if (allSame) {
    return { status: 'unanimous', values: raw, suggested: raw[entries[0][0]], detail: 'All databases agree' };
  }

  // Disagreement — classify variant vs substantive
  const classification = classifyDisagreement(field, raw, normalized);
  const suggested = suggestBestValue(field, raw, sources);

  return {
    status: classification,
    values: raw,
    suggested,
    detail: getDisagreementDetail(field, raw, normalized),
  };
}

function classifyDisagreement(field, raw, normalized) {
  const vals = Object.values(normalized).filter(v =>
    v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0)
  );

  switch (field) {
    case 'year': {
      const years = vals.map(Number).filter(n => !isNaN(n));
      if (years.length < 2) return 'variant';
      const diff = Math.max(...years) - Math.min(...years);
      return diff <= 1 ? 'variant' : 'substantive';
    }
    case 'authors': {
      // If same number of authors and names are similar → variant
      const lists = vals.filter(Array.isArray);
      if (lists.length < 2) return 'variant';
      const lenSame = lists.every(l => l.length === lists[0].length);
      if (!lenSame) return 'substantive';
      return 'variant'; // initials vs full name
    }
    case 'pages': {
      const cleaned = vals.map(v => String(v).replace(/[-–—\s]/g, ''));
      const allSame = cleaned.every(v => v === cleaned[0]);
      return allSame ? 'variant' : 'substantive';
    }
    case 'journal': {
      // Check if one is abbreviation of the other
      const strs = vals.map(String);
      const shortest = strs.reduce((a, b) => a.length < b.length ? a : b);
      const longest = strs.reduce((a, b) => a.length > b.length ? a : b);
      if (longest.toLowerCase().includes(shortest.toLowerCase())) return 'variant';
      return 'substantive';
    }
    case 'title': {
      // Minor differences (articles, capitalization) → variant
      const strs = vals.map(String);
      if (strs.every(s => s === strs[0])) return 'variant';
      return 'substantive';
    }
    default:
      return 'substantive';
  }
}

/**
 * Suggest best value based on Paper 1 Table 5 heuristics.
 */
function suggestBestValue(field, raw, sources) {
  const priority = {
    title: ['crossref', 'openalex', 's2'],
    year: ['crossref', 'openalex', 's2'],
    volume: ['crossref', 'openalex', 's2'],
    journal: ['crossref', 'openalex', 's2'],
    pages: ['openalex', 'crossref', 's2'],
    doi: ['crossref', 'openalex', 's2'],
    authors: null, // special: pick longest/most complete
  };

  if (field === 'authors') {
    // Pick the source with the most complete author names (longest total string)
    let best = null;
    let bestLen = 0;
    for (const [name, data] of Object.entries(sources)) {
      if (!data || !data.authors) continue;
      const total = data.authors.join(', ').length;
      if (total > bestLen) {
        bestLen = total;
        best = data.authors;
      }
    }
    return best;
  }

  const order = priority[field] || ['crossref', 'openalex', 's2'];
  for (const src of order) {
    const val = sources[src]?.[field];
    if (val !== null && val !== undefined && val !== '') return val;
  }
  return null;
}

function getDisagreementDetail(field, raw, normalized) {
  const vals = Object.entries(raw)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([src, v]) => `${src}: "${Array.isArray(v) ? v.join('; ') : v}"`)
    .join(' vs ');
  return vals;
}

/**
 * Main comparison function.
 * @param {Object} sources - { crossref, openalex, s2 }
 * @returns {Object} Full comparison report
 */
export function compareMetadata(sources) {
  const foundCount = [sources.crossref, sources.openalex, sources.s2]
    .filter(s => s && !s._error).length;

  if (foundCount === 0) {
    return {
      found: false,
      foundCount: 0,
      fields: {},
      summary: { unanimous: 0, variant: 0, substantive: 0, missing: 0, single: 0 },
      discrepancyScore: 0,
    };
  }

  const fields = {};
  const summary = { unanimous: 0, variant: 0, substantive: 0, missing: 0, single: 0 };

  for (const field of FIELDS) {
    const result = compareField(field, sources);
    fields[field] = result;
    summary[result.status] = (summary[result.status] || 0) + 1;
  }

  const discrepancyScore = summary.variant + summary.substantive;

  return {
    found: true,
    foundCount,
    fields,
    summary,
    discrepancyScore,
  };
}
