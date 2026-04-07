/**
 * Export batch results to .bib, .csv, .ris files.
 * Uses suggested (corrected) values from cross-database comparison.
 */

import { toBibTeX, toRIS } from './formatter.js';

/**
 * Generate corrected .bib content from batch results.
 * Uses the "suggested" value (cross-DB consensus) for each field.
 */
export function exportCorrectedBib(results) {
  const entries = [];
  for (const r of results) {
    if (!r.comparison?.found) continue;
    const suggested = buildSuggested(r);
    const citekey = r.citekey || generateKey(suggested);
    const lines = [`@article{${citekey},`];
    if (suggested.authors?.length) lines.push(`  author = {${suggested.authors.join(' and ')}},`);
    if (suggested.title) lines.push(`  title = {${suggested.title}},`);
    if (suggested.journal) lines.push(`  journal = {${suggested.journal}},`);
    if (suggested.year) lines.push(`  year = {${suggested.year}},`);
    if (suggested.volume) lines.push(`  volume = {${suggested.volume}},`);
    if (suggested.pages) lines.push(`  pages = {${suggested.pages}},`);
    if (suggested.doi) lines.push(`  doi = {${suggested.doi}},`);
    lines.push('}');
    entries.push(lines.join('\n'));
  }
  return entries.join('\n\n');
}

/**
 * Generate CSV report from batch results.
 */
export function exportCSV(results) {
  const fields = ['title', 'year', 'authors', 'journal', 'volume', 'pages', 'doi'];
  const headers = ['citekey', 'doi', 'found_in', 'discrepancies'];
  for (const f of fields) {
    headers.push(`${f}_crossref`, `${f}_openalex`, `${f}_s2`, `${f}_status`, `${f}_suggested`);
  }

  const rows = [headers.join(',')];

  for (const r of results) {
    const cols = [
      csvEscape(r.citekey || ''),
      csvEscape(r.doi),
      r.comparison?.foundCount ?? 0,
      r.comparison?.discrepancyScore ?? 0,
    ];

    for (const f of fields) {
      const cr = r.sources?.crossref?.[f];
      const oa = r.sources?.openalex?.[f];
      const s2 = r.sources?.s2?._error ? r.sources.s2._error : r.sources?.s2?.[f];
      const status = r.comparison?.fields?.[f]?.status || 'missing';
      const suggested = r.comparison?.fields?.[f]?.suggested;

      cols.push(
        csvEscape(formatVal(cr)),
        csvEscape(formatVal(oa)),
        csvEscape(formatVal(s2)),
        status,
        csvEscape(formatVal(suggested)),
      );
    }
    rows.push(cols.join(','));
  }

  return rows.join('\n');
}

/**
 * Generate RIS export from batch results.
 */
export function exportRIS(results) {
  const entries = [];
  for (const r of results) {
    if (!r.comparison?.found) continue;
    const suggested = buildSuggested(r);
    entries.push(toRIS(suggested));
  }
  return entries.join('\n\n');
}

/**
 * Trigger file download in browser.
 */
export function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// --- Helpers ---

function buildSuggested(result) {
  const suggested = {};
  if (result.comparison?.fields) {
    for (const [field, data] of Object.entries(result.comparison.fields)) {
      suggested[field] = data.suggested;
    }
  }
  return suggested;
}

function generateKey(data) {
  const last = (data.authors?.[0] || 'Unknown').split(',')[0].split(' ')[0].replace(/[^\w]/g, '');
  const y = data.year || 'XXXX';
  return `${last}${y}`;
}

function formatVal(v) {
  if (v === null || v === undefined) return '';
  if (Array.isArray(v)) return v.join('; ');
  return String(v);
}

function csvEscape(s) {
  if (!s) return '""';
  const str = String(s);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}
