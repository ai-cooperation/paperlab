/**
 * Citation Metadata Checker — Main App
 * Supports single DOI and batch .bib verification.
 */

import { queryAll } from './api.js';
import { compareMetadata } from './compare.js';
import { toAPA, toBibTeX, toRIS } from './formatter.js';
import { parseBib, extractDOIsFromText } from './bib-parser.js';
import { verifyBatch, batchSummary } from './batch.js';
import { exportCorrectedBib, exportCSV, exportRIS, downloadFile } from './exporter.js';
import { trackSingleVerify, trackBatchVerify, trackCopyCitation, trackExport } from './analytics.js';

const DAILY_LIMIT = 100;
const BATCH_LIMIT = 100;
const STORAGE_KEY = 'cmc_usage';

// --- Usage tracking ---

function getDailyUsage() {
  const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  const today = new Date().toISOString().slice(0, 10);
  if (data.date !== today) return { date: today, count: 0 };
  return data;
}

function incrementUsage(n = 1) {
  const usage = getDailyUsage();
  usage.count += n;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(usage));
  updateUsageDisplay();
  return usage.count;
}

function updateUsageDisplay() {
  const usage = getDailyUsage();
  const el = document.getElementById('usage-counter');
  if (el) el.textContent = `${usage.count}/${DAILY_LIMIT} today`;
}

// --- DOI parser ---

function parseDOI(input) {
  const s = input.trim();
  const match = s.match(/10\.\d{4,}\/[^\s]+/);
  if (!match) return null;
  // Strip trailing punctuation/brackets that users accidentally copy
  return match[0].replace(/[.)}\],:;]+$/, '');
}

// --- Shared render helpers ---

function statusIcon(status) {
  switch (status) {
    case 'unanimous': return '<span class="status-icon ok" title="All databases agree">&#10003;</span>';
    case 'variant': return '<span class="status-icon warn" title="Legitimate variant (e.g. online-first vs print)">&#9888;</span>';
    case 'substantive': return '<span class="status-icon error" title="Substantive disagreement">&#10060;</span>';
    case 'missing': return '<span class="status-icon na" title="Not available">—</span>';
    case 'single': return '<span class="status-icon single" title="Only one source">1</span>';
    default: return '';
  }
}

function formatCellValue(val) {
  if (val === null || val === undefined || val === '') return '<span class="na">—</span>';
  if (Array.isArray(val)) return val.join('; ');
  return String(val);
}

function getAbstract(sources) {
  const abs = sources.s2?.abstract || sources.openalex?.abstract || sources.crossref?.abstract;
  if (!abs) return '';
  const truncated = abs.length > 300 ? abs.slice(0, 300) + '...' : abs;
  return `
    <div class="abstract-box">
      <strong>Abstract:</strong>
      <p>${truncated}</p>
      ${abs.length > 300 ? '<button class="expand-btn" onclick="this.previousElementSibling.textContent=decodeURIComponent(this.dataset.full);this.remove()" data-full="' + encodeURIComponent(abs) + '">Show full abstract</button>' : ''}
    </div>`;
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// --- Single DOI report ---

function renderReport(doi, sources, comparison) {
  const el = document.getElementById('result');

  if (!comparison.found) {
    el.innerHTML = `
      <div class="report not-found">
        <div class="report-header">
          <span class="status-icon error">&#10060;</span>
          <strong>DOI not found in any database</strong>
        </div>
        <p>This DOI could not be located in CrossRef, OpenAlex, or Semantic Scholar.
        It may be a fabricated citation, not yet indexed, or incorrectly formatted.</p>
        <p class="doi-display">${escapeHtml(doi)}</p>
      </div>`;
    return;
  }

  const fieldLabels = {
    title: 'Title', year: 'Year', authors: 'Authors',
    journal: 'Journal', volume: 'Volume', pages: 'Pages', doi: 'DOI'
  };

  let rows = '';
  for (const [field, label] of Object.entries(fieldLabels)) {
    const f = comparison.fields[field];
    const crVal = formatCellValue(sources.crossref?.[field]);
    const oaVal = formatCellValue(sources.openalex?.[field]);
    const s2Val = sources.s2?._error
      ? `<span class="na" title="${escapeHtml(sources.s2._error)}">${escapeHtml(sources.s2._error)}</span>`
      : formatCellValue(sources.s2?.[field]);
    rows += `
      <tr class="row-${f.status}">
        <td class="field-name">${label}</td>
        <td>${crVal}</td>
        <td>${oaVal}</td>
        <td>${s2Val}</td>
        <td class="status-cell">${statusIcon(f.status)}</td>
      </tr>`;
  }

  const summaryClass = comparison.discrepancyScore === 0 ? 'clean' :
    comparison.summary.substantive > 0 ? 'has-error' : 'has-warn';

  const s2Error = sources.s2?._error;
  const dbNote = s2Error ? ` (Semantic Scholar: ${s2Error})` : '';

  const summaryText = comparison.discrepancyScore === 0
    ? `Found in ${comparison.foundCount}/3 databases — All fields agree${dbNote}`
    : `Found in ${comparison.foundCount}/3 databases — ${comparison.discrepancyScore} disagreement${comparison.discrepancyScore > 1 ? 's' : ''} detected${dbNote}`;

  const suggested = {};
  for (const [field, f] of Object.entries(comparison.fields)) {
    suggested[field] = f.suggested;
  }

  const apa = toAPA(suggested);
  const bibtex = toBibTeX(suggested);
  const ris = toRIS(suggested);

  el.innerHTML = `
    <div class="report ${summaryClass}">
      <div class="report-header">
        ${comparison.discrepancyScore === 0
          ? '<span class="status-icon ok">&#10003;</span>'
          : comparison.summary.substantive > 0
            ? '<span class="status-icon error">&#9888;</span>'
            : '<span class="status-icon warn">&#9888;</span>'}
        <strong>${summaryText}</strong>
      </div>

      <div class="doi-link">
        <strong>DOI:</strong> <a href="https://doi.org/${encodeURIComponent(doi)}" target="_blank" rel="noopener">${escapeHtml(doi)}</a>
        <span class="hint">(click to verify on publisher page)</span>
      </div>

      ${getAbstract(sources)}

      <table class="comparison-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>CrossRef</th>
            <th>OpenAlex</th>
            <th>Sem. Scholar${s2Error ? ' <span class="na">(' + escapeHtml(s2Error) + ')</span>' : ''}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>

      <div class="suggested-section">
        <h3>Suggested Citation <span class="hint">(based on cross-database consensus)</span></h3>

        <div class="format-tabs">
          <button class="tab active" data-format="apa">APA 7</button>
          <button class="tab" data-format="bibtex">BibTeX</button>
          <button class="tab" data-format="ris">RIS</button>
        </div>

        <div class="format-content" id="format-apa">
          <pre>${escapeHtml(apa)}</pre>
          <button class="copy-btn" data-text="${encodeURIComponent(apa)}">Copy APA</button>
        </div>
        <div class="format-content hidden" id="format-bibtex">
          <pre>${escapeHtml(bibtex)}</pre>
          <button class="copy-btn" data-text="${encodeURIComponent(bibtex)}">Copy BibTeX</button>
        </div>
        <div class="format-content hidden" id="format-ris">
          <pre>${escapeHtml(ris)}</pre>
          <button class="copy-btn" data-text="${encodeURIComponent(ris)}">Copy RIS</button>
        </div>
      </div>
    </div>`;

  bindTabs(el);
  bindCopyButtons(el);
}

function bindTabs(container) {
  container.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      container.querySelectorAll('.format-content').forEach(c => c.classList.add('hidden'));
      tab.classList.add('active');
      document.getElementById(`format-${tab.dataset.format}`).classList.remove('hidden');
    });
  });
}

function bindCopyButtons(container) {
  container.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const text = decodeURIComponent(btn.dataset.text);
      navigator.clipboard.writeText(text).then(() => {
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = orig; btn.classList.remove('copied'); }, 1500);
      });
    });
  });
}

// --- Single verify handler ---

async function handleVerify() {
  const input = document.getElementById('doi-input').value;
  const doi = parseDOI(input);
  const btn = document.getElementById('verify-btn');
  const el = document.getElementById('result');

  if (!doi) {
    el.innerHTML = '<div class="report has-error"><p>Please enter a valid DOI, e.g.<br><code>10.1038/s41598-023-41032-5</code></p></div>';
    return;
  }

  const usage = getDailyUsage();
  if (usage.count >= DAILY_LIMIT) {
    el.innerHTML = `<div class="report has-warn"><p>Daily limit reached (${DAILY_LIMIT} queries). Resets tomorrow.</p></div>`;
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Querying 3 databases...';
  el.innerHTML = '<div class="loading"><div class="spinner"></div><p>Querying CrossRef, OpenAlex, and Semantic Scholar...</p></div>';

  try {
    const sources = await queryAll(doi);
    const comparison = compareMetadata(sources);
    renderReport(doi, sources, comparison);
    incrementUsage();
    trackSingleVerify(doi, comparison.foundCount, comparison.discrepancyScore, comparison);
  } catch (err) {
    el.innerHTML = `<div class="report has-error"><p>Error: ${escapeHtml(err.message)}</p></div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Verify';
  }
}

// =============================================
// Batch mode
// =============================================

let batchAbortController = null;
let batchResults = null;

function showBatchPanel() {
  document.getElementById('batch-panel').classList.remove('hidden');
  document.getElementById('single-panel').classList.add('hidden');
  document.getElementById('tab-single').classList.remove('mode-active');
  document.getElementById('tab-batch').classList.add('mode-active');
}

function showSinglePanel() {
  document.getElementById('batch-panel').classList.add('hidden');
  document.getElementById('single-panel').classList.remove('hidden');
  document.getElementById('tab-single').classList.add('mode-active');
  document.getElementById('tab-batch').classList.remove('mode-active');
}

function handleFileSelect(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const content = e.target.result;
    document.getElementById('batch-text').value = content;
    parseBatchInput();
  };
  reader.readAsText(file);
}

function parseBatchInput() {
  const text = document.getElementById('batch-text').value.trim();
  const info = document.getElementById('batch-info');
  const startBtn = document.getElementById('batch-start-btn');

  if (!text) {
    info.textContent = '';
    startBtn.disabled = true;
    return;
  }

  // Try .bib parse first
  const bibEntries = parseBib(text);
  const bibDois = bibEntries.filter(e => e.doi).map(e => ({
    doi: e.doi, citekey: e.citekey, title: e.title
  }));

  if (bibDois.length > 0) {
    const noDoi = bibEntries.length - bibDois.length;
    info.innerHTML = `Parsed <strong>${bibDois.length}</strong> entries with DOI from .bib` +
      (noDoi > 0 ? ` (${noDoi} entries without DOI skipped)` : '');
    startBtn.disabled = false;
    startBtn.dataset.mode = 'bib';
    return;
  }

  // Try DOI list
  const dois = extractDOIsFromText(text);
  if (dois.length > 0) {
    info.innerHTML = `Found <strong>${dois.length}</strong> DOI${dois.length > 1 ? 's' : ''}`;
    startBtn.disabled = false;
    startBtn.dataset.mode = 'doi-list';
    return;
  }

  info.textContent = 'No DOIs found. Paste a .bib file or DOI list (one per line).';
  startBtn.disabled = true;
}

async function handleBatchStart() {
  const text = document.getElementById('batch-text').value.trim();
  const mode = document.getElementById('batch-start-btn').dataset.mode;
  const resultEl = document.getElementById('batch-result');
  const startBtn = document.getElementById('batch-start-btn');
  const stopBtn = document.getElementById('batch-stop-btn');

  let items;
  if (mode === 'bib') {
    const entries = parseBib(text);
    items = entries.filter(e => e.doi).map(e => ({ doi: e.doi, citekey: e.citekey, title: e.title }));
  } else {
    const dois = extractDOIsFromText(text);
    items = dois.map(d => ({ doi: d }));
  }

  if (items.length > BATCH_LIMIT) {
    resultEl.innerHTML = `<div class="report has-warn"><p>Maximum ${BATCH_LIMIT} entries per batch. You have ${items.length}. Please split your file.</p></div>`;
    return;
  }

  if (items.length === 0) {
    resultEl.innerHTML = '<div class="report has-error"><p>No DOIs found to verify.</p></div>';
    return;
  }

  // Start verification
  batchAbortController = new AbortController();
  startBtn.disabled = true;
  stopBtn.classList.remove('hidden');
  batchResults = null;

  const estimatedMinutes = Math.ceil(items.length * 1.5 / 60);
  resultEl.innerHTML = `
    <div class="batch-progress">
      <div class="progress-bar-track">
        <div class="progress-bar-fill" id="batch-progress-fill" style="width: 0%"></div>
      </div>
      <div class="progress-text" id="batch-progress-text">
        0/${items.length} — Starting... (est. ~${estimatedMinutes} min)
      </div>
      <div class="batch-live-log" id="batch-live-log"></div>
    </div>`;

  const progressFill = document.getElementById('batch-progress-fill');
  const progressText = document.getElementById('batch-progress-text');
  const liveLog = document.getElementById('batch-live-log');
  const startTime = Date.now();

  const onProgress = (completed, total, current) => {
    const pct = Math.round(completed / total * 100);
    progressFill.style.width = `${pct}%`;

    const elapsed = (Date.now() - startTime) / 1000;
    const perItem = elapsed / completed;
    const remaining = Math.ceil(perItem * (total - completed));
    const remainStr = remaining > 60 ? `${Math.ceil(remaining / 60)} min` : `${remaining}s`;

    progressText.textContent = `${completed}/${total} (${pct}%) — ~${remainStr} remaining`;

    // Add live log entry
    const icon = !current.comparison?.found ? '&#10060;' :
      current.comparison.summary.substantive > 0 ? '&#9888;' :
      current.comparison.discrepancyScore > 0 ? '&#9888;' : '&#10003;';
    const statusClass = !current.comparison?.found ? 'error' :
      current.comparison.summary.substantive > 0 ? 'error' :
      current.comparison.discrepancyScore > 0 ? 'warn' : 'ok';
    const label = current.citekey || current.doi;
    const shortTitle = current.title ? ` — ${current.title.slice(0, 50)}${current.title.length > 50 ? '...' : ''}` : '';

    liveLog.innerHTML += `<div class="live-log-item"><span class="status-icon ${statusClass}">${icon}</span> <strong>${escapeHtml(label)}</strong>${escapeHtml(shortTitle)}</div>`;
    liveLog.scrollTop = liveLog.scrollHeight;
  };

  try {
    const results = await verifyBatch(items, onProgress, batchAbortController.signal);
    batchResults = results;
    incrementUsage(results.length);
    const summary = batchSummary(results);
    trackBatchVerify(summary);
    renderBatchReport(results);
  } catch (err) {
    if (err.name !== 'AbortError') {
      resultEl.innerHTML = `<div class="report has-error"><p>Batch error: ${escapeHtml(err.message)}</p></div>`;
    }
  } finally {
    startBtn.disabled = false;
    stopBtn.classList.add('hidden');
    batchAbortController = null;
  }
}

function handleBatchStop() {
  if (batchAbortController) {
    batchAbortController.abort();
  }
}

function renderBatchReport(results) {
  const el = document.getElementById('batch-result');
  const summary = batchSummary(results);

  const pctClean = Math.round(summary.clean / summary.total * 100);
  const pctVariant = Math.round(summary.variant / summary.total * 100);
  const pctSubst = Math.round(summary.substantive / summary.total * 100);
  const pctNotFound = Math.round(summary.notFound / summary.total * 100);

  // Build detail rows
  let detailRows = '';
  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    const label = r.citekey || r.doi;
    const title = r.title || '';
    let statusClass, statusLabel;

    if (!r.comparison?.found) {
      statusClass = 'not-found';
      statusLabel = 'Not Found — Possibly Fabricated';
    } else if (r.comparison.summary.substantive > 0) {
      statusClass = 'substantive';
      statusLabel = `${r.comparison.summary.substantive} substantive`;
    } else if (r.comparison.summary.variant > 0) {
      statusClass = 'variant';
      statusLabel = `${r.comparison.summary.variant} variant`;
    } else {
      statusClass = 'clean';
      statusLabel = 'Clean';
    }

    detailRows += `
      <tr class="batch-row batch-row-${statusClass}" data-idx="${i}">
        <td class="batch-label">${escapeHtml(label)}</td>
        <td class="batch-title">${escapeHtml(title.slice(0, 60))}${title.length > 60 ? '...' : ''}</td>
        <td class="batch-found">${r.comparison?.foundCount ?? 0}/3</td>
        <td class="batch-status batch-status-${statusClass}">${statusLabel}</td>
      </tr>`;
  }

  el.innerHTML = `
    <div class="batch-summary-card">
      <h3>Batch Report — ${summary.total} citations verified</h3>
      <div class="batch-stats">
        <div class="stat stat-clean"><span class="stat-num">${summary.clean}</span><span class="stat-label">Clean (${pctClean}%)</span></div>
        <div class="stat stat-variant"><span class="stat-num">${summary.variant}</span><span class="stat-label">Variant (${pctVariant}%)</span></div>
        <div class="stat stat-substantive"><span class="stat-num">${summary.substantive}</span><span class="stat-label">Substantive (${pctSubst}%)</span></div>
        <div class="stat stat-notfound"><span class="stat-num">${summary.notFound}</span><span class="stat-label">Not Found (${pctNotFound}%)</span>${summary.notFound > 0 ? '<span class="stat-warn">Potentially fabricated</span>' : ''}</div>
      </div>

      <div class="batch-exports">
        <button class="export-btn" id="export-bib">Download corrected .bib</button>
        <button class="export-btn" id="export-csv">Download report .csv</button>
        <button class="export-btn" id="export-ris">Download .ris</button>
      </div>
    </div>

    <div class="batch-detail">
      <table class="batch-table">
        <thead>
          <tr>
            <th>Citekey / DOI</th>
            <th>Title</th>
            <th>Found</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>${detailRows}</tbody>
      </table>
    </div>

    <div id="batch-detail-view"></div>`;

  // Bind export buttons
  document.getElementById('export-bib').addEventListener('click', () => {
    downloadFile(exportCorrectedBib(results), 'corrected_references.bib', 'text/plain');
    trackExport('bib', results.length);
  });
  document.getElementById('export-csv').addEventListener('click', () => {
    downloadFile(exportCSV(results), 'verification_report.csv', 'text/csv');
    trackExport('csv', results.length);
  });
  document.getElementById('export-ris').addEventListener('click', () => {
    downloadFile(exportRIS(results), 'references.ris', 'text/plain');
    trackExport('ris', results.length);
  });

  // Bind row click to show detail
  el.querySelectorAll('.batch-row').forEach(row => {
    row.addEventListener('click', () => {
      const idx = parseInt(row.dataset.idx);
      const r = results[idx];
      if (r.sources && r.comparison?.found) {
        renderBatchDetail(r);
      }
    });
  });
}

function renderBatchDetail(result) {
  const el = document.getElementById('batch-detail-view');
  const { doi, sources, comparison } = result;

  const fieldLabels = {
    title: 'Title', year: 'Year', authors: 'Authors',
    journal: 'Journal', volume: 'Volume', pages: 'Pages', doi: 'DOI'
  };

  let rows = '';
  for (const [field, label] of Object.entries(fieldLabels)) {
    const f = comparison.fields[field];
    if (!f) continue;
    const crVal = formatCellValue(sources?.crossref?.[field]);
    const oaVal = formatCellValue(sources?.openalex?.[field]);
    const s2Val = sources?.s2?._error
      ? `<span class="na">${escapeHtml(sources.s2._error)}</span>`
      : formatCellValue(sources?.s2?.[field]);
    rows += `
      <tr class="row-${f.status}">
        <td class="field-name">${label}</td>
        <td>${crVal}</td>
        <td>${oaVal}</td>
        <td>${s2Val}</td>
        <td class="status-cell">${statusIcon(f.status)}</td>
      </tr>`;
  }

  el.innerHTML = `
    <div class="report batch-detail-report" style="margin-top: 1rem;">
      <div class="report-header">
        <strong>${escapeHtml(result.citekey || doi)}</strong>
        <button class="close-detail" style="margin-left:auto;background:none;border:none;font-size:1.2rem;cursor:pointer;">&#10005;</button>
      </div>
      <div class="doi-link">
        <a href="https://doi.org/${encodeURIComponent(doi)}" target="_blank" rel="noopener">${escapeHtml(doi)}</a>
      </div>
      ${sources ? getAbstract(sources) : ''}
      <table class="comparison-table">
        <thead>
          <tr><th>Field</th><th>CrossRef</th><th>OpenAlex</th><th>Sem. Scholar</th><th></th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  el.querySelector('.close-detail').addEventListener('click', () => { el.innerHTML = ''; });
}

// =============================================
// Init
// =============================================

document.addEventListener('DOMContentLoaded', () => {
  // Single mode
  document.getElementById('verify-btn').addEventListener('click', handleVerify);
  document.getElementById('doi-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') handleVerify();
  });

  // Mode tabs
  document.getElementById('tab-single').addEventListener('click', showSinglePanel);
  document.getElementById('tab-batch').addEventListener('click', showBatchPanel);

  // Batch mode
  document.getElementById('batch-file-input').addEventListener('change', e => {
    handleFileSelect(e.target.files[0]);
  });
  document.getElementById('batch-text').addEventListener('input', parseBatchInput);
  document.getElementById('batch-start-btn').addEventListener('click', handleBatchStart);
  document.getElementById('batch-stop-btn').addEventListener('click', handleBatchStop);

  // Drag & drop
  const dropZone = document.getElementById('batch-drop-zone');
  if (dropZone) {
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('drag-over'); });
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    });
  }

  updateUsageDisplay();
});
