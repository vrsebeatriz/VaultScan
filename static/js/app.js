/* ─── State ───────────────────────────────────────────────── */
let currentScanId    = null;
let pollInterval     = null;
let allFindings      = [];
let filteredFindings = [];
let currentPage      = 1;
let lastProgress     = -1;
const ITEMS_PER_PAGE = 50;

/* ─── Init ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  // Wire buttons
  document.getElementById('scanBtnHero').addEventListener('click',   () => startScan('hero'));
  document.getElementById('scanBtnHeader').addEventListener('click', () => startScan('header'));
  document.getElementById('repoInputHero').addEventListener('keydown',   e => { if (e.key === 'Enter') startScan('hero');   });
  document.getElementById('repoInputHeader').addEventListener('keydown', e => { if (e.key === 'Enter') startScan('header'); });
  document.getElementById('applyFiltersBtn').addEventListener('click', applyFilters);
  document.getElementById('filterSeverity').addEventListener('change', applyFilters);
  document.getElementById('filterSource').addEventListener('change',   applyFilters);
  document.getElementById('filterFile').addEventListener('input',       applyFilters);
  document.getElementById('btnPrev').addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderFindings(); } });
  document.getElementById('btnNext').addEventListener('click', () => {
    if (currentPage * ITEMS_PER_PAGE < filteredFindings.length) { currentPage++; renderFindings(); }
  });
  document.getElementById('btnExportJson').addEventListener('click', () => {
    if (currentScanId) window.open(`/api/export?scan_id=${currentScanId}&format=json`, '_blank');
  });
  document.getElementById('btnExportHtml').addEventListener('click', () => {
    if (currentScanId) window.open(`/api/export?scan_id=${currentScanId}&format=html`, '_blank');
  });

  // Auto-detect CLI-triggered scan
  try {
    const res = await fetch('/api/scans/latest');
    if (res.ok) {
      const data = await res.json();
      currentScanId = data.scan_id;
      transitionToDashboard();
      pollInterval = setInterval(pollStatus, 600);
    }
  } catch (_) { /* no scans yet */ }
});

/* ─── UI Transitions ──────────────────────────────────────── */
function transitionToDashboard(repoPath = '') {
  document.getElementById('heroSection').classList.add('hidden');
  document.getElementById('mainHeader').classList.remove('hidden');
  document.getElementById('mainLayout').classList.remove('hidden');
  document.getElementById('dashboardContent').classList.add('hidden');
  document.getElementById('progressContainer').classList.remove('hidden');
  if (repoPath) {
    document.getElementById('repoInputHeader').value = repoPath;
    document.getElementById('summaryRepo').textContent = repoPath;
  }
}

function resetScanBtn() {
  const btn = document.getElementById('scanBtnHeader');
  btn.disabled = false;
  btn.innerHTML = `
    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
    </svg>
    Scan`;
}

/* ─── Scan ────────────────────────────────────────────────── */
async function startScan(source) {
  const inputId  = source === 'hero' ? 'repoInputHero' : 'repoInputHeader';
  const repoPath = document.getElementById(inputId).value.trim();
  if (!repoPath) {
    document.getElementById(inputId).classList.add('ring-1', 'ring-rose-500/60');
    setTimeout(() => document.getElementById(inputId).classList.remove('ring-1', 'ring-rose-500/60'), 1500);
    return;
  }

  if (source === 'hero') transitionToDashboard(repoPath);

  const btn = document.getElementById('scanBtnHeader');
  btn.disabled  = true;
  btn.innerHTML = `<span class="w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin"></span> Scanning…`;

  // Reset progress UI
  document.getElementById('dashboardContent').classList.add('hidden');
  document.getElementById('progressContainer').classList.remove('hidden');
  document.getElementById('progressBar').style.width = '0%';
  document.getElementById('progressText').textContent = '0%';
  document.getElementById('terminalLog').innerHTML = '';
  document.getElementById('summaryRepo').textContent = repoPath;
  lastProgress = -1;

  try {
    const res = await fetch('/api/scan', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ repo_path: repoPath }),
    });

    if (res.status === 409) { return showError('A scan is already running.'); }
    if (!res.ok) {
      const d = await res.json();
      return showError(d.detail || 'Scan failed to start.');
    }

    const d = await res.json();
    currentScanId = d.scan_id;
    pollInterval  = setInterval(pollStatus, 600);

  } catch (e) {
    showError('Network error — is the server running?');
  }
}

/* ─── Polling ─────────────────────────────────────────────── */
async function pollStatus() {
  if (!currentScanId) return;
  try {
    const res  = await fetch(`/api/status?scan_id=${currentScanId}`);
    if (!res.ok) return;
    const data = await res.json();
    const pct  = data.progress;

    document.getElementById('progressBar').style.width = `${pct}%`;
    document.getElementById('progressText').textContent = `${pct}%`;

    // Append terminal lines at key milestones
    if (pct > lastProgress) {
      if (lastProgress < 0)  appendLog('▶ Initializing scan engine…', 'text-slate-400');
      if (pct >= 1  && lastProgress < 1)  appendLog('  Resolving repository structure…', 'text-slate-500');
      if (pct >= 10 && lastProgress < 10) appendLog('  Scanning working tree files…', 'text-slate-500');
      if (pct >= 50 && lastProgress < 50) appendLog('  Switching to git history analysis…', 'text-indigo-400');
      if (pct >= 75 && lastProgress < 75) appendLog('  Processing commit diffs…', 'text-slate-500');
      if (pct >= 99 && lastProgress < 99) appendLog('  Finalizing severity scores…', 'text-slate-500');
      lastProgress = pct;
    }

    if (data.status === 'complete') {
      clearInterval(pollInterval);
      appendLog('✔ Scan complete.', 'text-emerald-400');
      setTimeout(fetchReport, 400);
    } else if (data.status === 'error') {
      clearInterval(pollInterval);
      appendLog('✖ Scan error.', 'text-rose-400');
      resetScanBtn();
    }
  } catch (e) { /* transient network error, keep polling */ }
}

function appendLog(text, cls = 'text-slate-400') {
  const log  = document.getElementById('terminalLog');
  const line = document.createElement('div');
  line.className = `terminal-line ${cls}`;
  line.innerHTML = `<span class="text-slate-700 select-none font-mono shrink-0">›</span><span>${text}</span>`;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

/* ─── Report ──────────────────────────────────────────────── */
async function fetchReport() {
  try {
    const res = await fetch(`/api/report?scan_id=${currentScanId}`);
    if (!res.ok) { showError('Failed to load report.'); return; }
    const data = await res.json();
    allFindings = data.findings || [];

    document.getElementById('progressContainer').classList.add('hidden');
    document.getElementById('dashboardContent').classList.remove('hidden');
    document.getElementById('exportControls').classList.remove('hidden');
    document.getElementById('exportControls').classList.add('flex');

    updateSeverityCards();
    applyFilters();
    renderTimeline();
    resetScanBtn();

    // Total summary
    document.getElementById('summaryTotal').innerHTML =
      `<span class="text-white font-semibold">${allFindings.length}</span> findings`;

  } catch (e) { showError('Failed to load report.'); }
}

/* ─── Severity cards ──────────────────────────────────────── */
function updateSeverityCards() {
  const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  allFindings.forEach(f => { if (counts[f.severity] !== undefined) counts[f.severity]++; });
  const total = allFindings.length || 1;

  document.getElementById('countCritical').textContent = counts.CRITICAL;
  document.getElementById('countHigh').textContent     = counts.HIGH;
  document.getElementById('countMedium').textContent   = counts.MEDIUM;
  document.getElementById('countLow').textContent      = counts.LOW;

  // Animate bars
  setTimeout(() => {
    document.querySelector('#barCritical div').style.width = `${(counts.CRITICAL / total) * 100}%`;
    document.querySelector('#barHigh div').style.width     = `${(counts.HIGH     / total) * 100}%`;
    document.querySelector('#barMedium div').style.width   = `${(counts.MEDIUM   / total) * 100}%`;
    document.querySelector('#barLow div').style.width      = `${(counts.LOW      / total) * 100}%`;
  }, 80);
}

/* ─── Filters ─────────────────────────────────────────────── */
function applyFilters() {
  const sev  = document.getElementById('filterSeverity').value;
  const src  = document.getElementById('filterSource').value;
  const file = document.getElementById('filterFile').value.toLowerCase().trim();

  filteredFindings = allFindings.filter(f => {
    if (sev !== 'ALL' && f.severity !== sev) return false;
    if (src !== 'ALL' && !f.occurrences.some(o => o.source === src)) return false;
    if (file && !f.occurrences.some(o => o.file_path.toLowerCase().includes(file))) return false;
    return true;
  });

  currentPage = 1;
  document.getElementById('findingsCount').textContent = `${filteredFindings.length} results`;
  renderFindings();
}

/* ─── Findings rendering ──────────────────────────────────── */
function sevAccentClass(sev) {
  return { CRITICAL:'finding-accent-critical', HIGH:'finding-accent-high', MEDIUM:'finding-accent-medium', LOW:'finding-accent-low' }[sev] || 'finding-accent-low';
}
function sevHoverClass(sev) {
  return { CRITICAL:'finding-critical', HIGH:'finding-high', MEDIUM:'finding-medium', LOW:'finding-low' }[sev] || 'finding-low';
}
function badgeClass(sev) {
  return { CRITICAL:'badge-critical', HIGH:'badge-high', MEDIUM:'badge-medium', LOW:'badge-low' }[sev] || 'badge-low';
}
function sourceLabel(src) {
  return src === 'git_history' ? 'Git History' : 'Working Tree';
}
function sourceIcon(src) {
  return src === 'git_history'
    ? `<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>`
    : `<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>`;
}

function renderFindings() {
  const container = document.getElementById('findingsContainer');
  container.innerHTML = '';

  if (filteredFindings.length === 0) {
    container.innerHTML = `
      <div class="flex flex-col items-center justify-center py-16 px-8 glass rounded-xl border-dashed opacity-60">
        <svg class="w-10 h-10 text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
        <p class="text-slate-500 text-sm font-medium">No findings match the current filters.</p>
      </div>`;
    updatePagination();
    return;
  }

  const start = (currentPage - 1) * ITEMS_PER_PAGE;
  const items = filteredFindings.slice(start, start + ITEMS_PER_PAGE);

  items.forEach((f, i) => {
    const mainOcc  = f.occurrences[0];
    const extraCnt = f.occurrences.length - 1;

    const card = document.createElement('div');
    card.className = `finding-card ${sevAccentClass(f.severity)} ${sevHoverClass(f.severity)}`;
    card.style.cssText = `animation: var(--animate-fade-up); animation-delay: ${i * 40}ms;`;

    card.innerHTML = `
      <!-- Card header -->
      <div class="flex items-start justify-between gap-4 px-5 pt-4 pb-3">
        <div class="flex-1 min-w-0">
          <code class="block text-sm font-mono font-medium text-indigo-300 truncate mb-2">${escHtml(f.masked_value)}</code>
          <div class="flex items-center flex-wrap gap-2">
            <span class="inline-flex items-center gap-1 text-[11px] font-mono text-slate-500 bg-white/4 border border-white/6 px-2 py-0.5 rounded">
              ${escHtml(f.rule_id)}
            </span>
            ${extraCnt > 0 ? `
              <span class="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-400 bg-indigo-500/8 border border-indigo-500/15 px-2 py-0.5 rounded">
                +${extraCnt} more occurrence${extraCnt > 1 ? 's' : ''}
              </span>` : ''}
          </div>
        </div>
        <span class="${badgeClass(f.severity)} shrink-0">${f.severity}</span>
      </div>

      <!-- Code block -->
      <div class="code-block mx-5 mb-4">
        <div class="code-block-header">
          <span class="flex items-center gap-2 text-[11px] font-mono text-slate-500">
            ${sourceIcon(mainOcc.source)}
            <span class="text-slate-400">${escHtml(mainOcc.file_path)}</span>
            <span class="text-slate-600">:${mainOcc.line_number}</span>
          </span>
          <span class="text-[11px] font-mono font-semibold px-2 py-0.5 rounded
            ${mainOcc.source === 'git_history'
              ? 'text-violet-400 bg-violet-500/10 border border-violet-500/20'
              : 'text-slate-500 bg-white/4 border border-white/6'}">
            ${sourceLabel(mainOcc.source)}
          </span>
        </div>
        <div class="px-4 py-3 overflow-x-auto">
          <pre class="text-xs text-slate-300 font-mono leading-relaxed whitespace-pre"><code>${escHtml(mainOcc.snippet)}</code></pre>
        </div>
      </div>
    `;

    container.appendChild(card);
  });

  updatePagination();
}

function updatePagination() {
  const total = Math.ceil(filteredFindings.length / ITEMS_PER_PAGE) || 1;
  document.getElementById('pageIndicator').textContent = `Page ${currentPage} of ${total}`;
  document.getElementById('btnPrev').disabled = currentPage === 1;
  document.getElementById('btnNext').disabled = currentPage === total;
}

/* ─── Timeline ────────────────────────────────────────────── */
function renderTimeline() {
  const section   = document.getElementById('timelineSection');
  const container = document.getElementById('timelineContainer');
  container.innerHTML = '';

  const events = [];
  allFindings.forEach(f => {
    f.occurrences.forEach(o => {
      if (o.source === 'git_history' && o.commit_date) events.push({ f, o });
    });
  });

  document.getElementById('timelineCount').textContent = `${events.length} events`;

  if (events.length === 0) {
    section.classList.add('hidden');
    return;
  }
  section.classList.remove('hidden');
  events.sort((a, b) => new Date(b.o.commit_date) - new Date(a.o.commit_date));

  events.forEach(({ f, o }, i) => {
    const d    = new Date(o.commit_date);
    const date = d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

    const el = document.createElement('div');
    el.className = 'relative pl-7';
    el.style.cssText = `animation: var(--animate-fade-up); animation-delay: ${i * 40}ms;`;
    el.innerHTML = `
      <div class="timeline-dot"></div>
      <div class="flex items-start justify-between gap-4 mb-2">
        <div class="flex items-center gap-3 flex-wrap">
          <code class="text-[11px] font-mono font-bold text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded">${o.commit_sha.slice(0,7)}</code>
          <span class="text-xs text-slate-500">${date} · ${time}</span>
        </div>
        <span class="${badgeClass(f.severity)} shrink-0">${f.severity}</span>
      </div>
      <div class="glass-sm rounded-lg px-4 py-2.5 mb-3 border-l-2 border-indigo-500/40">
        <p class="text-xs text-slate-300 font-medium italic">"${escHtml(o.commit_message)}"</p>
      </div>
      <div class="code-block">
        <div class="px-4 py-2.5 font-mono text-[11px] text-slate-500 flex flex-col gap-1">
          <span>Introduced <span class="text-indigo-300 font-semibold">${escHtml(f.masked_value)}</span></span>
          <span class="text-slate-600">${escHtml(o.file_path)}:${o.line_number}</span>
        </div>
      </div>
    `;
    container.appendChild(el);
  });
}

/* ─── Utilities ───────────────────────────────────────────── */
function showError(msg) {
  appendLog(`✖ ${msg}`, 'text-rose-400');
  resetScanBtn();
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
