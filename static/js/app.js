let currentScanId = null;
let pollInterval = null;
let allFindings = [];
let filteredFindings = [];
let currentPage = 1;
const ITEMS_PER_PAGE = 50;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('scanBtnHero').addEventListener('click', () => startScan('hero'));
    document.getElementById('scanBtnHeader').addEventListener('click', () => startScan('header'));
    
    document.getElementById('applyFiltersBtn').addEventListener('click', applyFilters);
    document.getElementById('btnPrev').addEventListener('click', () => { if(currentPage > 1) { currentPage--; renderFindingsList(); } });
    document.getElementById('btnNext').addEventListener('click', () => { 
        if(currentPage * ITEMS_PER_PAGE < filteredFindings.length) { currentPage++; renderFindingsList(); } 
    });
    
    document.getElementById('btnExportJson').addEventListener('click', () => {
        if (currentScanId) window.open(`/api/export?scan_id=${currentScanId}&format=json`, '_blank');
    });
    document.getElementById('btnExportHtml').addEventListener('click', () => {
        if (currentScanId) window.open(`/api/export?scan_id=${currentScanId}&format=html`, '_blank');
    });
});

async function startScan(sourceBtn) {
    let repoPath = '';
    if (sourceBtn === 'hero') {
        repoPath = document.getElementById('repoInputHero').value.trim();
    } else {
        repoPath = document.getElementById('repoInputHeader').value.trim();
    }
    
    if (!repoPath) return alert('Please enter a repository path.');

    // Transition UI if coming from Hero
    if (sourceBtn === 'hero') {
        document.getElementById('heroSection').classList.add('hidden');
        document.getElementById('mainHeader').classList.remove('hidden');
        document.getElementById('mainLayout').classList.remove('hidden');
        document.getElementById('repoInputHeader').value = repoPath;
    }
    
    document.getElementById('scanBtnHeader').disabled = true;
    document.getElementById('scanBtnHeader').innerText = 'Scanning...';
    
    // Reset UI
    document.getElementById('dashboardContent').classList.add('hidden');
    document.getElementById('progressContainer').classList.remove('hidden');
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressText').innerText = '0%';
    document.getElementById('progressStatus').innerHTML = '<span class="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span> Initializing Deep Scan...';

    try {
        const res = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_path: repoPath })
        });
        
        if (res.status === 409) {
            alert('A scan is already in progress.');
            resetScanBtn();
            return;
        } else if (!res.ok) {
            const data = await res.json();
            alert(`Error: ${data.detail}`);
            resetScanBtn();
            return;
        }

        const data = await res.json();
        currentScanId = data.scan_id;
        
        // Start polling
        pollInterval = setInterval(pollStatus, 500);

    } catch (e) {
        alert('Network error trying to start scan.');
        resetScanBtn();
    }
}

function resetScanBtn() {
    document.getElementById('scanBtnHeader').disabled = false;
    document.getElementById('scanBtnHeader').innerText = 'Scan';
}

async function pollStatus() {
    if (!currentScanId) return;
    
    try {
        const res = await fetch(`/api/status?scan_id=${currentScanId}`);
        if (!res.ok) return;
        
        const data = await res.json();
        const pct = data.progress;
        
        document.getElementById('progressBar').style.width = `${pct}%`;
        document.getElementById('progressText').innerText = `${pct}%`;
        
        const statusEl = document.getElementById('progressStatus');
        if (pct < 50) {
            statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span> Analyzing Working Tree...';
        } else {
            statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-purple-500 animate-pulse"></span> Deep Scanning Git History...';
        }
        
        if (data.status === 'complete') {
            clearInterval(pollInterval);
            statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500"></span> Scan Complete!';
            setTimeout(fetchReport, 500);
        } else if (data.status === 'error') {
            clearInterval(pollInterval);
            statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500"></span> Scan Error.';
            statusEl.classList.add('text-red-400');
            resetScanBtn();
        }
    } catch (e) {
        console.error("Polling error", e);
    }
}

async function fetchReport() {
    try {
        const res = await fetch(`/api/report?scan_id=${currentScanId}`);
        if (!res.ok) {
            alert('Error fetching report');
            return;
        }
        
        const data = await res.json();
        allFindings = data.findings || [];
        
        // Populate UI
        document.getElementById('dashboardContent').classList.remove('hidden');
        document.getElementById('exportControls').classList.remove('hidden');
        resetScanBtn();
        
        updateCards();
        applyFilters(); // will call renderFindingsList()
        renderTimeline();
        
    } catch (e) {
        console.error("Report fetch error", e);
        resetScanBtn();
    }
}

function updateCards() {
    let counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    allFindings.forEach(f => {
        if (counts[f.severity] !== undefined) counts[f.severity]++;
    });
    
    document.getElementById('countCritical').innerText = counts.CRITICAL;
    document.getElementById('countHigh').innerText = counts.HIGH;
    document.getElementById('countMedium').innerText = counts.MEDIUM;
    document.getElementById('countLow').innerText = counts.LOW;
}

function applyFilters() {
    const sev = document.getElementById('filterSeverity').value;
    const src = document.getElementById('filterSource').value;
    const fileSearch = document.getElementById('filterFile').value.toLowerCase();
    
    filteredFindings = allFindings.filter(f => {
        if (sev !== 'ALL' && f.severity !== sev) return false;
        
        if (src !== 'ALL') {
            const hasSource = f.occurrences.some(o => o.source === src);
            if (!hasSource) return false;
        }
        
        if (fileSearch) {
            const matchesFile = f.occurrences.some(o => o.file_path.toLowerCase().includes(fileSearch));
            if (!matchesFile) return false;
        }
        
        return true;
    });
    
    currentPage = 1;
    document.getElementById('findingsCount').innerText = `${filteredFindings.length} results`;
    renderFindingsList();
}

function getBadgeClass(sev) {
    if (sev === 'CRITICAL') return 'badge-critical';
    if (sev === 'HIGH') return 'badge-high';
    if (sev === 'MEDIUM') return 'badge-medium';
    return 'badge-low';
}

function renderFindingsList() {
    const container = document.getElementById('findingsContainer');
    container.innerHTML = '';
    
    if (filteredFindings.length === 0) {
        container.innerHTML = '<div class="text-slate-400 p-8 text-center border border-dashed border-slate-700 rounded-xl">No findings match the current filters.</div>';
        updatePagination();
        return;
    }
    
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageItems = filteredFindings.slice(start, end);
    
    pageItems.forEach((f, index) => {
        const div = document.createElement('div');
        // Add staggering animation delay
        div.className = `glass-panel p-6 animate-fade-in-up hover:-translate-y-1 hover:shadow-lg transition-all duration-300`;
        div.style.animationDelay = `${index * 50}ms`;
        
        const mainOcc = f.occurrences[0];
        const occCount = f.occurrences.length;
        
        div.innerHTML = `
            <div class="flex justify-between items-start mb-4">
                <div>
                    <h4 class="font-mono text-base font-medium text-indigo-300 break-all mb-2">${f.masked_value}</h4>
                    <div class="text-xs text-slate-400 flex items-center gap-3">
                        <span class="bg-slate-800/80 px-2 py-1 rounded text-slate-300 border border-slate-700/50 shadow-inner">Rule: ${f.rule_id}</span>
                        ${occCount > 1 ? `<span class="bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded border border-indigo-500/20 shadow-inner">+${occCount-1} more occurrences</span>` : ''}
                    </div>
                </div>
                <span class="${getBadgeClass(f.severity)} shadow-sm">${f.severity}</span>
            </div>
            
            <div class="bg-[#0a0f1c] rounded-lg border border-slate-700/80 p-4 overflow-x-auto shadow-inner">
                <div class="text-xs font-semibold text-slate-500 mb-3 border-b border-slate-800 pb-2 flex justify-between items-center">
                    <span class="flex items-center gap-2">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        ${mainOcc.file_path}:${mainOcc.line_number}
                    </span>
                    <span class="bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/50">${mainOcc.source}</span>
                </div>
                <pre class="text-sm text-slate-300 font-mono leading-relaxed"><code>${escapeHtml(mainOcc.snippet)}</code></pre>
            </div>
        `;
        container.appendChild(div);
    });
    
    updatePagination();
}

function updatePagination() {
    const totalPages = Math.ceil(filteredFindings.length / ITEMS_PER_PAGE) || 1;
    document.getElementById('pageIndicator').innerText = `Page ${currentPage} of ${totalPages}`;
    
    document.getElementById('btnPrev').disabled = currentPage === 1;
    document.getElementById('btnNext').disabled = currentPage === totalPages;
}

function renderTimeline() {
    const container = document.getElementById('timelineContainer');
    container.innerHTML = '';
    
    const historyEvents = [];
    allFindings.forEach(f => {
        f.occurrences.forEach(o => {
            if (o.source === 'git_history' && o.commit_date) {
                historyEvents.push({ finding: f, occurrence: o });
            }
        });
    });
    
    if (historyEvents.length === 0) {
        container.innerHTML = '<div class="text-slate-400 p-8 text-center border border-dashed border-slate-700 rounded-xl">No git history findings available.</div>';
        return;
    }
    
    historyEvents.sort((a, b) => new Date(b.occurrence.commit_date) - new Date(a.occurrence.commit_date));
    
    historyEvents.forEach((evt, index) => {
        const o = evt.occurrence;
        const f = evt.finding;
        const d = new Date(o.commit_date).toLocaleString();
        
        const div = document.createElement('div');
        div.className = `relative pl-8 animate-fade-in-up`;
        div.style.animationDelay = `${index * 50}ms`;
        
        div.innerHTML = `
            <div class="absolute -left-[5px] top-1.5 w-3 h-3 rounded-full bg-indigo-500 ring-4 ring-[#0f172a] shadow-[0_0_10px_rgba(99,102,241,0.8)]"></div>
            <div class="flex justify-between items-start mb-2">
                <div class="text-sm font-bold text-white flex items-center gap-3">
                    <span class="bg-slate-800 px-2 py-1 rounded text-indigo-300 font-mono text-xs border border-slate-700">${o.commit_sha.substring(0,7)}</span>
                    <span class="text-slate-400 font-medium">${d}</span>
                </div>
                <span class="${getBadgeClass(f.severity)} text-[10px] px-2 py-0.5 shadow-sm">${f.severity}</span>
            </div>
            <div class="text-sm text-slate-300 mb-3 font-medium bg-slate-800/30 p-3 rounded-lg border-l-2 border-indigo-500">
                "${escapeHtml(o.commit_message)}"
            </div>
            <div class="bg-[#0a0f1c] rounded-lg border border-slate-700/50 p-3 text-xs font-mono text-slate-400 shadow-inner flex flex-col gap-2">
                <div>Introduced <span class="text-indigo-300 font-semibold">${f.masked_value}</span></div>
                <div class="text-slate-500">File: ${o.file_path}:${o.line_number}</div>
            </div>
        `;
        container.appendChild(div);
    });
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag] || tag));
}
