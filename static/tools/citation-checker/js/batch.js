/**
 * Batch verification engine.
 * Processes multiple DOIs with rate-limiting and progress callbacks.
 */

import { queryAll } from './api.js';
import { compareMetadata } from './compare.js';

const CONCURRENCY = 2; // max parallel requests (S2 allows ~1 req/sec unauthenticated)
const DELAY_MS = 2000; // delay between batches to avoid S2 429

/**
 * Verify a list of DOI items in batches.
 * @param {Array<{doi: string, citekey?: string, title?: string}>} items
 * @param {Function} onProgress - (completed, total, currentResult) => void
 * @param {AbortSignal} signal - optional abort signal
 * @returns {Promise<Array<{doi, citekey, title, sources, comparison}>>}
 */
export async function verifyBatch(items, onProgress, signal) {
  const results = [];
  let completed = 0;
  const total = items.length;

  for (let i = 0; i < total; i += CONCURRENCY) {
    if (signal?.aborted) break;

    const batch = items.slice(i, i + CONCURRENCY);
    const batchResults = await Promise.all(
      batch.map(async (item) => {
        try {
          const sources = await queryAll(item.doi);
          const comparison = compareMetadata(sources);
          return {
            doi: item.doi,
            citekey: item.citekey || null,
            title: item.title || sources.crossref?.title || sources.openalex?.title || sources.s2?.title || null,
            sources,
            comparison,
          };
        } catch (err) {
          return {
            doi: item.doi,
            citekey: item.citekey || null,
            title: item.title || null,
            sources: null,
            comparison: { found: false, foundCount: 0, fields: {}, summary: {}, discrepancyScore: 0, _error: err.message },
          };
        }
      })
    );

    for (const r of batchResults) {
      results.push(r);
      completed++;
      if (onProgress) onProgress(completed, total, r);
    }

    // Delay before next batch (skip after last batch)
    if (i + CONCURRENCY < total && !signal?.aborted) {
      await new Promise(r => setTimeout(r, DELAY_MS));
    }
  }

  return results;
}

/**
 * Compute batch summary statistics.
 * @param {Array} results - from verifyBatch
 * @returns {Object} summary counts
 */
export function batchSummary(results) {
  const summary = {
    total: results.length,
    clean: 0,      // all fields unanimous or single
    variant: 0,    // has variant but no substantive
    substantive: 0, // has substantive disagreement
    notFound: 0,   // DOI not found in any DB
    errors: 0,     // fetch errors
  };

  for (const r of results) {
    if (!r.comparison || r.comparison._error) {
      summary.errors++;
    } else if (!r.comparison.found) {
      summary.notFound++;
    } else if (r.comparison.summary.substantive > 0) {
      summary.substantive++;
    } else if (r.comparison.summary.variant > 0) {
      summary.variant++;
    } else {
      summary.clean++;
    }
  }

  return summary;
}
