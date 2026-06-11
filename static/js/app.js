let currentScanId = null;
let pollInterval = null;
let allFindings = [];
let filteredFindings = [];
let currentPage = 1;
const ITEMS_PER_PAGE = 50;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('scanBtn').addEventListener('click', startScan);
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

async function startScan() {
    const repoPath = document.getElementById('repoInput').value.trim();
    if (!repoPath) return alert('Please enter a repository path.');

    document.getElementById('scanBtn').disabled = true;
    document.getElementById('scanBtn').innerText = 'Scanning...';
    
    // Reset UI
    document.getElementById('dashboardContent').classList.add('hidden');
    document.getElementById('progressContainer').classList.remove('hidden');
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressText').innerText = '0%';
    document.getElementById('progressStatus').innerText = 'Initializing scan...';

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
    document.getElementById('scanBtn').disabled = false;
    document.getElementById('scanBtn').innerText = 'Start Scan';
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
        document.getElementById('progressStatus').innerText = pct < 50 ? 'Scanning working tree...' : 'Scanning git history...';
        
        if (data.status === 'complete') {
            clearInterval(pollInterval);
            document.getElementById('progressStatus').innerText = 'Scan Complete!';
            setTimeout(fetchReport, 500);
        } else if (data.status === 'error') {
            clearInterval(pollInterval);
            document.getElementById('progressStatus').innerText = 'Scan Error.';
            document.getElementById('progressStatus').classList.add('text-red-400');
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
        container.innerHTML = '<div class="text-slate-400 p-4 text-center">No findings match the filters.</div>';
        updatePagination();
        return;
    }
    
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageItems = filteredFindings.slice(start, end);
    
    pageItems.forEach(f => {
        const div = document.createElement('div');
        div.className = 'glass-panel p-5';
        
        // Get the first occurrence for preview
        const mainOcc = f.occurrences[0];
        const occCount = f.occurrences.length;
        
        div.innerHTML = `
            <div class="flex justify-between items-start mb-4">
                <div>
                    <h4 class="font-mono text-sm text-indigo-300 break-all">${f.masked_value}</h4>
                    <div class="text-xs text-slate-400 mt-1 flex items-center gap-2">
                        <span class="bg-slate-800 px-2 py-0.5 rounded text-slate-300">Rule: ${f.rule_id}</span>
                        ${occCount > 1 ? `<span class="bg-slate-800 px-2 py-0.5 rounded text-slate-300">+${occCount-1} more occurrences</span>` : ''}
                    </div>
                </div>
                <span class="${getBadgeClass(f.severity)}">${f.severity}</span>
            </div>
            
            <div class="bg-slate-900/80 rounded border border-slate-700/50 p-3 overflow-x-auto">
                <div class="text-xs text-slate-500 mb-2 border-b border-slate-700/50 pb-2 flex justify-between">
                    <span>File: ${mainOcc.file_path}:${mainOcc.line_number}</span>
                    <span>Source: ${mainOcc.source}</span>
                </div>
                <pre class="text-xs text-slate-300 font-mono"><code>${escapeHtml(mainOcc.snippet)}</code></pre>
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
    
    // Extract all occurrences with git_history
    const historyEvents = [];
    allFindings.forEach(f => {
        f.occurrences.forEach(o => {
            if (o.source === 'git_history' && o.commit_date) {
                historyEvents.push({ finding: f, occurrence: o });
            }
        });
    });
    
    if (historyEvents.length === 0) {
        container.innerHTML = '<div class="text-slate-400">No git history findings available.</div>';
        return;
    }
    
    // Sort chronological (oldest first or newest first) - Let's do newest first
    historyEvents.sort((a, b) => new Date(b.occurrence.commit_date) - new Date(a.occurrence.commit_date));
    
    historyEvents.forEach(evt => {
        const o = evt.occurrence;
        const f = evt.finding;
        const d = new Date(o.commit_date).toLocaleString();
        
        const div = document.createElement('div');
        div.className = 'relative pl-6';
        div.innerHTML = `
            <div class="absolute -left-[5px] top-1.5 w-2 h-2 rounded-full bg-indigo-500 ring-4 ring-[#0f172a]"></div>
            <div class="flex justify-between items-start mb-1">
                <div class="text-sm font-semibold text-white">${o.commit_sha.substring(0,7)} <span class="text-slate-400 font-normal ml-2">${d}</span></div>
                <span class="${getBadgeClass(f.severity)} text-[10px] px-1 py-0">${f.severity}</span>
            </div>
            <div class="text-sm text-slate-300 mb-2">Message: "${escapeHtml(o.commit_message)}"</div>
            <div class="bg-slate-900/50 rounded border border-slate-700/50 p-2 text-xs font-mono text-slate-400">
                Introduced ${f.masked_value} in ${o.file_path}:${o.line_number}
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
