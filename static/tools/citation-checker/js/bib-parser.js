/**
 * Lightweight BibTeX parser.
 * Extracts entries with DOI, title, and citekey from .bib content.
 * No external dependencies.
 */

/**
 * Parse a .bib string into an array of entry objects.
 * @param {string} bibContent - Raw .bib file content
 * @returns {Array<{citekey: string, type: string, doi: string|null, title: string|null, fields: Object}>}
 */
export function parseBib(bibContent) {
  const entries = [];
  // Match @type{citekey, ... } blocks (handles nested braces)
  const entryRegex = /@(\w+)\s*\{([^,]*),/g;
  let match;

  while ((match = entryRegex.exec(bibContent)) !== null) {
    const type = match[1].toLowerCase();
    if (type === 'string' || type === 'preamble' || type === 'comment') continue;

    const citekey = match[2].trim();
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(bibContent, startIdx);
    if (!body) continue;

    const fields = parseFields(body);
    const doi = fields.doi || null;
    const title = fields.title || null;

    entries.push({ citekey, type, doi, title, fields });
  }

  return entries;
}

/**
 * Extract content until matching closing brace, handling nesting.
 */
function extractBraceBlock(str, startIdx) {
  let depth = 1;
  let i = startIdx;
  while (i < str.length && depth > 0) {
    if (str[i] === '{') depth++;
    else if (str[i] === '}') depth--;
    i++;
  }
  if (depth !== 0) return null;
  return str.slice(startIdx, i - 1);
}

/**
 * Parse field = {value} or field = "value" pairs from entry body.
 */
function parseFields(body) {
  const fields = {};
  // Match: fieldname = {value} or fieldname = "value" or fieldname = number
  const fieldRegex = /(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|"([^"]*)"|(\d+))/g;
  let m;
  while ((m = fieldRegex.exec(body)) !== null) {
    const key = m[1].toLowerCase();
    const val = (m[2] !== undefined ? m[2] : m[3] !== undefined ? m[3] : m[4]) || '';
    fields[key] = val.trim();
  }
  return fields;
}

/**
 * Extract DOIs from a plain text list (one DOI per line, or mixed with URLs).
 * @param {string} text
 * @returns {Array<string>}
 */
export function extractDOIsFromText(text) {
  const doiRegex = /10\.\d{4,}\/[^\s,;]+/g;
  const matches = text.match(doiRegex) || [];
  // Deduplicate
  return [...new Set(matches.map(d => d.replace(/[.)}\]]+$/, '')))];
}
