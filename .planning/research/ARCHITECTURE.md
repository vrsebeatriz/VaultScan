# Architecture Patterns

**Domain:** Local secrets scanner + IaC misconfiguration detector with web dashboard
**Project:** VaultScan
**Researched:** 2026-06-11
**Confidence:** HIGH (FastAPI structure verified via official docs; scanner pipeline patterns derived from project requirements and established OSS tool conventions)

---

## Recommended Architecture

VaultScan follows a **layered pipeline + API gateway** pattern. The CLI or browser triggers a scan job; the pipeline runs three scanner layers in sequence; filters strip false positives; results are written to an in-memory report store that the frontend polls via REST.

```
+-------------------------------------------------------------+
|                        Entry Points                          |
|   CLI (vaultscan scan /path)    Browser (dashboard field)    |
+--------------------+----------------------+-----------------+
                     |  HTTP POST /api/scan  |
                     v                       v
+-------------------------------------------------------------+
|                     FastAPI Backend                          |
|  +-------------+   +----------------------------------+     |
|  |  api/scan   |-->|  ScanOrchestrator (coordinator)  |     |
|  |  api/report |   +----------------+-----------------+     |
|  |  api/status |                    | spawns                 |
|  +-------------+                    v                        |
|                    +-----------------------------------+     |
|                    |       Pipeline (src/pipeline/)    |     |
|                    |  +-----------------------------+  |     |
|                    |  |  1. SecretsScanner          |  |     |
|                    |  |     regex + Shannon entropy  |  |     |
|                    |  +---------+-------------------+  |     |
|                    |  |  2. IaCScanner              |  |     |
|                    |  |     Dockerfile, GHA, .env   |  |     |
|                    |  +---------+-------------------+  |     |
|                    |  |  3. GitHistoryScanner        |  |     |
|                    |  |     GitPython commit walk   |  |     |
|                    |  +-----------------------------+  |     |
|                    +----------------+------------------+     |
|                                     | raw Finding[]          |
|                                     v                        |
|                    +-----------------------------------+     |
|                    |      Filters (src/filters/)       |     |
|                    |  extension, path, context rules   |     |
|                    +----------------+------------------+     |
|                                     | filtered Finding[]     |
|                                     v                        |
|                    +-----------------------------------+     |
|                    |   ReportStore (in-memory / file)  |     |
|                    |   ScanReport model (Pydantic)     |     |
|                    +----------------+------------------+     |
|                                     |                        |
|              +----------------------+------------------+     |
|              |                                          |     |
|              v                                          v     |
|   GET /api/report (JSON)              src/export/           |
|   (served to browser)             HTML + JSON export        |
+-------------------------------------------------------------+
                     |
                     v
+-------------------------------------------------------------+
|                  Frontend (public/)                          |
|   index.html + app.js + Tailwind CSS (glassmorphism)        |
|   - POST /api/scan on submit                                 |
|   - Poll GET /api/status for progress                        |
|   - Render GET /api/report findings                          |
+-------------------------------------------------------------+
```

---

## Component Boundaries

| Component | Location | Responsibility | Communicates With |
|-----------|----------|----------------|-------------------|
| CLI Entry Point | `cli.py` / `__main__.py` | Parse `vaultscan scan /path`, call POST /api/scan, open browser | FastAPI backend (HTTP) |
| FastAPI App | `src/api/main.py` | Route registration, static file mounting, app lifecycle | All backend components |
| API Router — scan | `src/api/routers/scan.py` | POST /api/scan: validate path, enqueue scan job | ScanOrchestrator |
| API Router — report | `src/api/routers/report.py` | GET /api/report, GET /api/status | ReportStore |
| ScanOrchestrator | `src/pipeline/orchestrator.py` | Sequence the three scanners, pass results to filters, write to ReportStore | Pipeline scanners, Filters, ReportStore |
| SecretsScanner | `src/pipeline/secrets_scanner.py` | Walk files, apply regex patterns + Shannon entropy | ConfigLoader |
| IaCScanner | `src/pipeline/iac_scanner.py` | Parse Dockerfile, GitHub Actions YAML, .env files for misconfigs | ConfigLoader |
| GitHistoryScanner | `src/pipeline/git_history_scanner.py` | Iterate commits via GitPython, apply secrets detection to historical blobs | GitPython, SecretsScanner (shared detection logic) |
| FilterChain | `src/filters/filter_chain.py` | Apply extension, path, and context filters in order | Finding models |
| ConfigLoader | `src/config.py` | Load and validate vaultscan.yml; expose typed config to all components | All scanners, FilterChain |
| Data Models | `src/models/` | Pydantic models: Finding, ScanReport, ScanRequest, ScanStatus | All components (shared) |
| ReportStore | `src/store.py` | Hold latest ScanReport in memory; thread-safe read/write | Orchestrator (write), API routers (read) |
| ExportEngine | `src/export/` | Render ScanReport to HTML (Jinja2 template) and JSON file | ScanReport model |
| Frontend | `public/` | Single-page dashboard: submit scan, poll status, render findings cards | API endpoints via fetch() |

---

## Data Flow

### 1. Scan Request Path

```
User input (CLI arg / browser form field)
  -> POST /api/scan  { repo_path: "/path/to/repo" }
  -> ScanRequest model validated (path exists, is git repo)
  -> ScanOrchestrator.run(scan_id, repo_path)  [BackgroundTask]
  -> Returns 202 { scan_id }  immediately
```

### 2. Pipeline Execution (background)

```
ScanOrchestrator:
  ConfigLoader.load("vaultscan.yml")
    -> ScanConfig { rules, filters, excluded_paths, ... }

  SecretsScanner.scan(repo_path, config)
    -> walks all tracked files
    -> per file: apply regex rules -> match -> compute Shannon entropy
    -> yields Finding[]

  IaCScanner.scan(repo_path, config)
    -> detects Dockerfile / .github/workflows/*.yml / .env
    -> per file type: applies rule set
    -> yields Finding[]

  GitHistoryScanner.scan(repo, config)
    -> GitPython: repo.iter_commits("HEAD")
    -> per commit: diff blobs -> re-run secrets detection on deleted/added content
    -> yields Finding[] with commit metadata

  raw_findings = SecretsFindings + IaCFindings + GitFindings
```

### 3. Filter Path

```
FilterChain.apply(raw_findings, config.filters)
  -> ExtensionFilter: drop .png, .lock, .sum, etc.
  -> PathFilter: drop node_modules/, vendor/, .git/
  -> ContextFilter: drop findings where surrounding lines are test/mock patterns
  -> returns filtered_findings: Finding[]
```

### 4. Report Assembly

```
ScanReport(
  scan_id, repo_path, timestamp,
  findings = filtered_findings,
  summary = { critical: N, high: N, medium: N, low: N },
  git_timeline = [ { commit_sha, message, findings: [] } ]
)

ReportStore.save(scan_id, report)
ScanStatus -> COMPLETE
```

### 5. Frontend Consumption

```
browser polls: GET /api/status?scan_id=xxx
  -> { status: "running" | "complete" | "error", progress_pct }

on status=complete:
  GET /api/report?scan_id=xxx
  -> ScanReport JSON (masked_value only — never raw matched_value)

render:
  - Severity cards (critical / high / medium / low counts)
  - Finding cards with file, line, rule, masked value
  - Git timeline view
  - Filter controls (by severity, scanner type, file)
```

### 6. Export Path (on-demand)

```
GET /api/export?scan_id=xxx&format=html|json
  ExportEngine.render(report, format)
    html: Jinja2 template -> standalone HTML file
    json: report.model_dump_json()
  -> file download response
```

---

## Key Patterns

### Pattern 1: BackgroundTask for scan jobs

FastAPI's `BackgroundTasks` runs the scan pipeline after returning the 202 response. The scan_id is generated before enqueue; the frontend polls `/api/status`. No Celery/Redis needed at local scale.

```python
@router.post("/api/scan", status_code=202)
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    scan_id = generate_scan_id()
    background_tasks.add_task(orchestrator.run, scan_id, request.repo_path)
    return {"scan_id": scan_id}
```

### Pattern 2: Shared Finding model as pipeline contract

All three scanners emit the same `Finding` Pydantic model. FilterChain and exporters work on `list[Finding]` regardless of source.

```python
class Finding(BaseModel):
    rule_id: str
    severity: Literal["critical", "high", "medium", "low"]
    scanner: Literal["secrets", "iac", "git_history"]
    file_path: str
    line_number: int | None
    matched_value: str       # raw match — internal only, never sent to browser
    masked_value: str        # safe to return to API consumers
    context_snippet: str     # surrounding lines
    commit_sha: str | None   # populated by GitHistoryScanner only
    commit_message: str | None
```

### Pattern 3: FilterChain as composable pipeline

```python
FILTERS = [ExtensionFilter, PathFilter, ContextFilter]

def apply(findings, config):
    for f in FILTERS:
        findings = f.apply(findings, config)
    return findings
```

### Pattern 4: Static file mounting for SPA

API routers must be registered BEFORE mounting StaticFiles — otherwise StaticFiles captures all paths including `/api/*`.

```python
app.include_router(scan_router)
app.include_router(report_router)
app.mount("/", StaticFiles(directory="public", html=True), name="frontend")
```

### Pattern 5: ConfigLoader singleton

```python
@lru_cache
def get_config(config_path: str = "vaultscan.yml") -> ScanConfig:
    return ScanConfig.from_yaml(config_path)
```

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Correct Approach |
|---|---|---|
| Blocking scan in route handler | Blocks FastAPI event loop for entire scan duration | BackgroundTasks + 202 + polling |
| Scanner-specific Finding types | FilterChain and ExportEngine need type-switching | Single Finding model with `scanner` discriminator |
| Exposing raw matched_value in API | Raw secrets appear in browser DevTools | Only expose `masked_value` in GET /api/report |
| Mounting StaticFiles before API routers | Captures `/api/*` paths, returns 404 | Register all routers first, mount last |
| Each scanner loading config independently | Repeated disk I/O, inconsistent config | ConfigLoader singleton passed by orchestrator |

---

## Component Build Order

```
1. src/models/                         <- no dependencies; all others depend on this
2. src/config.py                       <- depends on models (ScanConfig)
3. src/filters/                        <- depends on models (Finding)
4. src/pipeline/secrets_scanner.py     <- depends on models, config
5. src/pipeline/iac_scanner.py         <- depends on models, config
6. src/pipeline/git_history_scanner.py <- depends on models, config, secrets_scanner
7. src/pipeline/orchestrator.py        <- depends on all three scanners + filters
8. src/store.py                        <- depends on models (ScanReport)
9. src/export/                         <- depends on models (ScanReport)
10. src/api/                           <- depends on orchestrator, store, export, models
11. cli.py                             <- depends on api (HTTP) or orchestrator (direct)
12. public/                            <- depends on api contract (HTTP)
```

**Roadmap implications:**
- Phase 1 must establish `src/models/` before any scanner work — load-bearing foundation
- Build SecretsScanner end-to-end (models → scanner → filter → API stub) before adding other scanners
- GitHistoryScanner comes after SecretsScanner (shares detection logic)
- Frontend can develop in parallel once HTTP contract is agreed
- ExportEngine and CLI are additive — no other component depends on them; build last
- `matched_value` masking must be enforced in Phase 1 model design, not retrofitted
