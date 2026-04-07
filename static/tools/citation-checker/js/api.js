/**
 * API adapters for CrossRef, OpenAlex, and Semantic Scholar.
 * All public APIs, no keys required.
 */

const MAILTO = 'aicooperation.tw@gmail.com';

/** Strip HTML tags from API response strings (CrossRef returns <scp>, <i>, <sub>, etc.) */
function stripHtml(s) {
  if (!s || typeof s !== 'string') return s;
  return s.replace(/<[^>]+>/g, '');
}

export async function queryCrossRef(doi) {
  const url = `https://api.crossref.org/works/${encodeURIComponent(doi)}?mailto=${MAILTO}`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    const item = data.message;
    return {
      source: 'CrossRef',
      title: stripHtml(item.title?.[0]) || null,
      year: item.published?.['date-parts']?.[0]?.[0]
        || item['published-print']?.['date-parts']?.[0]?.[0]
        || item['published-online']?.['date-parts']?.[0]?.[0]
        || null,
      authors: (item.author || []).map(a => {
        const given = a.given || '';
        const family = a.family || '';
        return family ? `${family}, ${given}` : given;
      }).filter(Boolean),
      journal: stripHtml(item['container-title']?.[0]) || null,
      volume: item.volume || null,
      pages: item.page || null,
      doi: item.DOI || doi,
      abstract: item.abstract || null,
    };
  } catch {
    return null;
  }
}

export async function queryOpenAlex(doi) {
  const url = `https://api.openalex.org/works/doi:${encodeURIComponent(doi)}?mailto=${MAILTO}`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const item = await res.json();
    return {
      source: 'OpenAlex',
      title: stripHtml(item.title) || null,
      year: item.publication_year || null,
      authors: (item.authorships || []).map(a => {
        return a.author?.display_name || '';
      }).filter(Boolean),
      journal: item.primary_location?.source?.display_name || null,
      volume: item.biblio?.volume || null,
      pages: item.biblio?.first_page && item.biblio?.last_page
        ? `${item.biblio.first_page}-${item.biblio.last_page}`
        : item.biblio?.first_page || null,
      doi: item.doi?.replace('https://doi.org/', '') || doi,
      abstract: item.abstract_inverted_index
        ? reconstructAbstract(item.abstract_inverted_index)
        : null,
    };
  } catch {
    return null;
  }
}

function reconstructAbstract(invertedIndex) {
  if (!invertedIndex) return null;
  const words = [];
  for (const [word, positions] of Object.entries(invertedIndex)) {
    for (const pos of positions) {
      words[pos] = word;
    }
  }
  return words.join(' ');
}

export async function querySemanticScholar(doi) {
  const fields = 'title,year,authors,venue,externalIds,journal,abstract';
  const url = `https://api.semanticscholar.org/graph/v1/paper/DOI:${encodeURIComponent(doi)}?fields=${fields}`;
  try {
    let res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    // Retry up to 2 times with increasing delay if rate-limited
    for (let retry = 0; retry < 2 && res.status === 429; retry++) {
      const wait = (retry + 1) * 4000; // 4s, 8s
      await new Promise(r => setTimeout(r, wait));
      res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    }
    if (!res.ok) {
      console.warn(`S2 API error: ${res.status} ${res.statusText}`);
      return { source: 'Semantic Scholar', _error: `HTTP ${res.status}` };
    }
    const item = await res.json();
    return {
      source: 'Semantic Scholar',
      title: item.title || null,
      year: item.year || null,
      authors: (item.authors || []).map(a => a.name || '').filter(Boolean),
      journal: item.journal?.name || item.venue || null,
      volume: item.journal?.volume || null,
      pages: item.journal?.pages || null,
      doi: item.externalIds?.DOI || doi,
      abstract: item.abstract || null,
    };
  } catch (e) {
    console.warn('S2 fetch error:', e);
    return { source: 'Semantic Scholar', _error: e.message || 'unavailable' };
  }
}

// Toggle S2 on/off (set false when rate-limited to avoid delays)
export let s2Enabled = true;
export function setS2Enabled(val) { s2Enabled = val; }

export async function queryAll(doi) {
  const promises = [
    queryCrossRef(doi),
    queryOpenAlex(doi),
    s2Enabled ? querySemanticScholar(doi) : Promise.resolve({ source: 'Semantic Scholar', _error: 'disabled' }),
  ];
  const [cr, oa, s2] = await Promise.all(promises);
  return { crossref: cr, openalex: oa, s2 };
}
