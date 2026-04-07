/**
 * Citation format generators: APA 7, BibTeX, RIS.
 */

function formatAuthorAPA(authors) {
  if (!authors || authors.length === 0) return '';
  if (authors.length === 1) return authors[0];
  if (authors.length === 2) return `${authors[0]} & ${authors[1]}`;
  if (authors.length <= 20) {
    return authors.slice(0, -1).join(', ') + ', & ' + authors[authors.length - 1];
  }
  return authors.slice(0, 19).join(', ') + ', ... ' + authors[authors.length - 1];
}

function generateCitekey(authors, year, title) {
  const lastName = (authors?.[0] || 'Unknown').split(',')[0].split(' ')[0].replace(/[^\w]/g, '');
  const y = year || 'XXXX';
  const firstWord = (title || '').split(/\s+/).find(w => w.length > 3 && !['the', 'and', 'for', 'with'].includes(w.toLowerCase())) || 'untitled';
  return `${lastName}${y}${firstWord.toLowerCase().replace(/[^\w]/g, '')}`;
}

export function toAPA(data) {
  const authors = formatAuthorAPA(data.authors || []);
  const year = data.year ? `(${data.year})` : '(n.d.)';
  const title = data.title || 'Untitled';
  const journal = data.journal ? `*${data.journal}*` : '';
  const vol = data.volume ? `, *${data.volume}*` : '';
  const pages = data.pages ? `, ${data.pages}` : '';
  const doi = data.doi ? ` https://doi.org/${data.doi}` : '';

  return `${authors} ${year}. ${title}. ${journal}${vol}${pages}.${doi}`;
}

export function toBibTeX(data) {
  const key = generateCitekey(data.authors, data.year, data.title);
  const authors = (data.authors || []).join(' and ');
  const lines = [`@article{${key},`];
  if (authors) lines.push(`  author = {${authors}},`);
  if (data.title) lines.push(`  title = {${data.title}},`);
  if (data.journal) lines.push(`  journal = {${data.journal}},`);
  if (data.year) lines.push(`  year = {${data.year}},`);
  if (data.volume) lines.push(`  volume = {${data.volume}},`);
  if (data.pages) lines.push(`  pages = {${data.pages}},`);
  if (data.doi) lines.push(`  doi = {${data.doi}},`);
  lines.push('}');
  return lines.join('\n');
}

export function toRIS(data) {
  const lines = ['TY  - JOUR'];
  for (const author of (data.authors || [])) {
    lines.push(`AU  - ${author}`);
  }
  if (data.title) lines.push(`TI  - ${data.title}`);
  if (data.journal) lines.push(`JO  - ${data.journal}`);
  if (data.year) lines.push(`PY  - ${data.year}`);
  if (data.volume) lines.push(`VL  - ${data.volume}`);
  if (data.pages) {
    const parts = data.pages.split(/[-–—]/);
    if (parts[0]) lines.push(`SP  - ${parts[0].trim()}`);
    if (parts[1]) lines.push(`EP  - ${parts[1].trim()}`);
  }
  if (data.doi) lines.push(`DO  - ${data.doi}`);
  lines.push('ER  -');
  return lines.join('\n');
}
