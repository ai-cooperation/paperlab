/**
 * Usage tracking — sends events to Google Apps Script webhook.
 * Fire-and-forget: never blocks UI, silently fails.
 */

const WEBHOOK_URL = 'https://script.google.com/macros/s/AKfycbyh7eY6RufL97OCJ1esbPwFlKcoN8axZf0_FxTNSfUnzNzTQzNhF6NMdhil2sF3tiGkqQ/exec';

const UA = navigator.userAgent.slice(0, 100);
let cachedIP = null;

// Get client IP once (free API, no key needed)
async function getClientIP() {
  if (cachedIP) return cachedIP;
  try {
    const res = await fetch('https://api.ipify.org?format=json');
    const data = await res.json();
    cachedIP = data.ip || '';
  } catch {
    cachedIP = '';
  }
  return cachedIP;
}

// Preload IP on page load
getClientIP();


export function trackEvent(data) {
  if (!WEBHOOK_URL) return;
  try {
    const payload = {
      ...data,
      ip: cachedIP || '',
      user_agent: UA,
      client_ts: new Date().toISOString(),
    };
    const params = new URLSearchParams({ json: JSON.stringify(payload) });
    const img = new Image();
    img.src = `${WEBHOOK_URL}?${params.toString()}`;
  } catch {
    // silent fail
  }
}

export function trackSingleVerify(doi, foundCount, discrepancies, comparison) {
  // Build field-level detail: "authors:variant,year:substantive"
  const fieldDetail = comparison?.fields
    ? Object.entries(comparison.fields)
        .filter(([, f]) => f.status !== 'unanimous' && f.status !== 'missing')
        .map(([name, f]) => `${name}:${f.status}`)
        .join(',')
    : '';
  // Which DBs responded
  const dbs = comparison ? [
    comparison.fields?.title?.values?.crossref !== undefined ? 'CR' : '',
    comparison.fields?.title?.values?.openalex !== undefined ? 'OA' : '',
    comparison.fields?.title?.values?.s2 !== undefined ? 'S2' : '',
  ].filter(Boolean).join('+') : '';

  trackEvent({
    event: 'single_verify',
    doi,
    found: foundCount,
    discrepancies,
    fields: fieldDetail,
    dbs,
  });
}

export function trackBatchVerify(summary) {
  trackEvent({
    event: 'batch_verify',
    batch_total: summary.total,
    batch_clean: summary.clean,
    batch_notfound: summary.notFound,
    discrepancies: summary.substantive + summary.variant,
  });
}

export function trackCopyCitation(doi, format) {
  trackEvent({ event: 'copy_citation', doi, format });
}

export function trackExport(format, count) {
  trackEvent({ event: 'export_file', format, doi: count });
}
