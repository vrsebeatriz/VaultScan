# Roadmap: VaultScan

## Overview

VaultScan is built in seven phases that follow the natural dependency graph of a layered security scanner. Phase 1 locks in the data models, config system, and filter chain that every other component imports. Phases 2-4 implement the three scanner layers independently. Phase 5 wires the pipeline to HTTP via FastAPI. Phase 6 delivers the web dashboard against a stable API contract. Phase 7 completes the dual-entry-point experience with export and CLI.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Models, config, filter chain, and project skeleton that every scanner imports
- [ ] **Phase 2: Secrets Scanner** - Regex + entropy detection with deduplication and context snippets
- [ ] **Phase 3: Git History Scanner** - Full commit history traversal with source tracking and severity demotion
- [ ] **Phase 4: IaC Scanner** - Dockerfile, GitHub Actions, and .env misconfiguration detection
- [ ] **Phase 5: API + Orchestrator** - FastAPI routes, BackgroundTask pipeline, and in-memory ReportStore
- [ ] **Phase 6: Web Dashboard** - Severity cards, filtering, commit timeline, and real-time progress
- [ ] **Phase 7: Export + CLI** - HTML/JSON export, Typer CLI entry point, and browser auto-open

## Phase Details

### Phase 1: Foundation
**Goal**: The data backbone and infrastructure that every scanner layer depends on exists and is validated
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: CFG-01, CFG-02, FLT-01, FLT-02, FLT-03, FLT-04, SEV-01, SEV-02
**Success Criteria** (what must be TRUE):
  1. A `Finding` Pydantic model exists with `matched_value` (internal) and `masked_value` (API-safe) as distinct fields — the split is enforced at the model level and cannot be bypassed
  2. `vaultscan.yml` is loaded and validated by Pydantic at startup — unknown keys emit a warning, the config summary is printed, and entropy thresholds are configurable per character class
  3. The FilterChain correctly excludes `.lock`, `.min.js`, `.map`, `.svg`, `.png`, `.wasm`, `.bin` files and mandatorily blocks `node_modules/`, `.git/`, `__pycache__/`, `.venv/`, `dist/`, `build/` paths
  4. The fake-value denylist (`AKIAIOSFODNN7EXAMPLE` and equivalents) is present and test-covered — known fake values are never flagged
  5. Severity classification produces Critical / High / Medium / Low for any finding input, and findings in `test/`, `docs/`, `*.spec.*`, `*fixture*`, `*mock*`, `README*` are demoted to LOW (never suppressed)
**Plans**: TBD

### Phase 2: Secrets Scanner
**Goal**: Users can run a scan against a repository and receive deduplicated secret findings with context
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: DET-01, DET-02, DET-03, DET-04
**Success Criteria** (what must be TRUE):
  1. Running a scan against a repository containing hardcoded AWS, GitHub, OpenAI, and Stripe secrets produces findings with correct pattern identification
  2. Shannon entropy is computed per-character-class and only elevates existing regex matches — no finding is emitted from entropy alone
  3. Identical secrets appearing in multiple files are collapsed into one finding with an occurrence count, not reported as N separate findings
  4. Each finding includes a context snippet of 3-5 lines surrounding the match, with the matching line identified
**Plans**: TBD

### Phase 3: Git History Scanner
**Goal**: Users can scan the full commit history of a repository and see when secrets entered the codebase
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: GIT-01, GIT-02, GIT-03
**Success Criteria** (what must be TRUE):
  1. The scanner traverses all commits up to the configured cap (default 500) using a generator — it does not load all history into memory at once, and it emits a warning when the cap is reached
  2. Every finding carries a `source` field of `working_tree` or `git_history`; findings from `git_history` are automatically demoted one severity level compared to an identical finding in `working_tree`
  3. Each git history finding includes the commit SHA, commit date, and commit message where the secret was introduced
**Plans**: TBD

### Phase 4: IaC Scanner
**Goal**: Users can detect Dockerfile, GitHub Actions, and .env misconfigurations with precise, low-noise rules
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: IAC-01, IAC-02, IAC-03
**Success Criteria** (what must be TRUE):
  1. The Dockerfile scanner flags `ENV VAR=literal_credential_value`, `FROM image:latest`, `ADD http://...`, and `RUN curl | sh` — and does NOT flag `ENV VAR` (no value assignment)
  2. The GitHub Actions scanner classifies `uses: org/action@branch` as CRITICAL, `uses: org/action@tag` as MEDIUM, and `uses: org/action@SHA` as safe (no finding emitted)
  3. The .env scanner flags `.env` files ONLY when they are tracked in the git index (`git ls-files`); files listed in `.gitignore` and not tracked produce no finding
  4. Each IaC rule has at least 5 true-positive and 5 true-negative test cases passing before the phase is marked done
**Plans**: TBD

### Phase 5: API + Orchestrator
**Goal**: The full scan pipeline is accessible over HTTP and results are safely served without leaking raw secret values
**Mode:** mvp
**Depends on**: Phase 2, Phase 3, Phase 4
**Requirements**: API-01, API-02, API-03
**Success Criteria** (what must be TRUE):
  1. `POST /api/scan` validates the repo path is a git repository, returns 202 with a `scan_id` immediately, and returns 409 if a scan is already running — the scan executes as a FastAPI BackgroundTask
  2. `GET /api/status?scan_id=xxx` returns the scan state (`running | complete | error`) and a progress percentage that advances during the scan
  3. `GET /api/report?scan_id=xxx` returns the full `ScanReport` JSON using only `masked_value` — `matched_value` is never present in any API response
**Plans**: TBD

### Phase 6: Web Dashboard
**Goal**: Users can explore scan results visually with severity filtering, commit timeline, and real-time progress
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05
**Success Criteria** (what must be TRUE):
  1. The dashboard displays severity cards (Critical / High / Medium / Low) with finding counts immediately after scan completion
  2. Users can filter the findings list by severity level, scanner type (secrets / iac / git_history), and file path — filters apply without a page reload
  3. The commit timeline shows when each secret first appeared in git history
  4. A real-time progress indicator updates during an active scan via polling of `GET /api/status`, without blocking the UI
  5. The findings list is paginated with a maximum of 50 findings per page — the browser does not freeze on large result sets
**Plans**: TBD
**UI hint**: yes

### Phase 7: Export + CLI
**Goal**: Users can export audit-ready reports and launch full scans from the terminal with a single command
**Mode:** mvp
**Depends on**: Phase 5, Phase 6
**Requirements**: EXP-01, EXP-02, CLI-01, CLI-02, CLI-03
**Success Criteria** (what must be TRUE):
  1. `GET /api/export?scan_id=xxx&format=html` produces a standalone HTML file where all secret values are redacted to first-4 + `****` + last-4, and the file includes a visible "do not commit this file" warning banner
  2. `GET /api/export?scan_id=xxx&format=json` produces a complete `ScanReport` JSON file usable for scripting
  3. Running `vaultscan scan /path/to/repo` starts the FastAPI server, triggers the scan, and opens the dashboard in the default browser automatically
  4. The CLI exits with code 1 when findings are present and code 0 when the repository is clean
  5. Users can submit a repository path via the dashboard's input field as an alternative to the CLI — the scan starts and results are displayed in the same session
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

Note: Phase 3 (Git History Scanner) and Phase 4 (IaC Scanner) both depend only on Phase 1 and can be planned in sequence after Phase 2 ships.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/TBD | Not started | - |
| 2. Secrets Scanner | 0/TBD | Not started | - |
| 3. Git History Scanner | 0/TBD | Not started | - |
| 4. IaC Scanner | 0/TBD | Not started | - |
| 5. API + Orchestrator | 0/TBD | Not started | - |
| 6. Web Dashboard | 0/TBD | Not started | - |
| 7. Export + CLI | 0/TBD | Not started | - |
