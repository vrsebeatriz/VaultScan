# Domain Pitfalls: Secrets Scanner / IaC Security Tool

**Domain:** Local secrets scanner with regex + Shannon entropy + git history walking
**Project:** VaultScan
**Researched:** 2026-06-11
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: Entropy Threshold Set Wrong and Never Calibrated

**What goes wrong:** A single global Shannon entropy threshold (commonly 3.5 or 4.0) applied across all file types. Minified JS, base64-encoded images, long UUIDs, hashed filenames all exceed the threshold and flood results with noise.

**Warning signs:**
- First scan on any real project returns more than 20 findings
- Any `.lock` file or `node_modules/` directory appears in findings
- Entropy-only findings outnumber regex-matched findings

**Prevention:**
- Apply entropy per character class (base62 vs hex vs full-ASCII each need different thresholds)
- Never run entropy-only matching on `.lock`, `.min.js`, `.map`, `.svg`, `.png`, `.wasm` files
- Entropy must be a secondary signal that elevates regex matches, not a standalone detector
- Build test fixtures: known-true secrets + known-false strings (SHA256 hash, UUID, minified JS) and assert thresholds

**Phase to address:** Core scanner pipeline — before any UI work.

---

### Pitfall 2: Git History Walker Degrades Catastrophically on Large Repos

**What goes wrong:** GitPython's `repo.iter_commits()` with diff resolution loads entire diff objects into memory. Repos with accidentally-committed `.zip`, `.jar`, or `node_modules/` in history create enormous objects. Memory spikes, scan runs for 30+ minutes, FastAPI endpoint appears hung.

**Warning signs:**
- Scanning a repo with >1,000 commits takes more than 60 seconds
- Python process memory grows unboundedly during scan
- GET /api/report returns nothing because scan never completed

**Prevention:**
- Set a hard `max_commits` cap (default 500, configurable via `vaultscan.yml`)
- Filter diff entries by file extension BEFORE fetching blob content — skip binary extensions at diff entry level
- Per-blob size limit: skip any single diff hunk exceeding 512 KB
- Use generator-based commit iterator from day one
- Expose progress via polling endpoint so user knows scan is alive

**Phase to address:** Git history scanner — design commit iterator as a generator with limits before writing scan logic.

---

### Pitfall 3: Regex Patterns Match Test Files, Example Code, and Documentation

**What goes wrong:** `AKIA[0-9A-Z]{16}` correctly identifies AWS keys AND matches every AWS doc example, every unit test fixture, every README. These are never real secrets.

**Warning signs:**
- Findings clustering in `test/` or `docs/` directories
- Any finding whose matched value ends in `EXAMPLE`
- Unit tests in the target repo contain hardcoded fake tokens

**Prevention:**
- Maintain a denylist of known-fake values per token type. AWS: `AKIAIOSFODNN7EXAMPLE`, GitHub: `ghp_xxxxxxxxxxxxxxxx` patterns
- Apply path-context scoring: matches in `*.test.*`, `*.spec.*`, `*fixture*`, `*mock*`, `*example*`, `README*`, `docs/**` → auto-demote to LOW severity (never suppress)
- Never suppress findings — demote severity so users can audit the logic

**Phase to address:** Filter pipeline, in parallel with the regex engine.

---

### Pitfall 4: Git History Finds Rotated Secrets — No "Rotated" State Communicated

**What goes wrong:** Scanner finds an AWS key committed 18 months ago (already rotated). Reports it CRITICAL. Developer spends an hour verifying it's expired, then stops trusting history findings entirely.

**Warning signs:**
- History and working-tree findings displayed with identical visual weight
- No commit date visible on history findings
- No temporal context shown

**Prevention:**
- `Finding` model must distinguish `source: "working_tree"` vs `source: "git_history"` from day one
- Surface commit metadata: commit date, author, message
- Default severity for history-only findings: one level below working-tree findings of same pattern
- UI: "mark as rotated" affordance that persists to exported report

**Phase to address:** Data model design — `Finding` model needs `source`, `commit_hash`, `commit_date`, `commit_message` fields from Phase 1.

---

### Pitfall 5: IaC Scanner Rules Are Too Coarse — Triggers on Intentional Patterns

**What goes wrong:**
- Dockerfile scanner flags `ENV NODE_ENV=production`, `ENV PORT=3000`
- GitHub Actions scanner flags SHA-pinned actions (SHA pinning IS the most secure practice)
- `.env` scanner flags every line including gitignored files

**Warning signs:**
- IaC scanner returns findings on VaultScan's own `.github/workflows/` files during development
- Any finding on `ENV NODE_ENV` or `ENV PORT`
- `.env.example` files being flagged

**Prevention:**
- **Dockerfile**: Only flag `ENV VAR=literal_value` when the value looks like a credential. `ENV VAR` with no value = safe (runtime injection).
- **GitHub Actions**: `uses: org/action@SHA` = safe. `uses: org/action@branch` = CRITICAL (mutable). `uses: org/action@tag` = MEDIUM.
- **.env files**: Flag when file IS tracked in git index (use `git ls-files`), not just when it exists on disk. A gitignored `.env` = not a finding.
- Write at least 10 IaC rule tests (5 true positives + 5 true negatives per rule type) before phase is complete

**Phase to address:** IaC scanner implementation — rules must be reviewed against test set before marking phase done.

---

## Moderate Pitfalls

### Pitfall 6: `vaultscan.yml` Config Schema Not Validated — Silent Misconfiguration

**What goes wrong:** User writes `exlcude_paths` instead of `exclude_paths`. Tool silently uses defaults. User believes exclusions are active; sensitive paths are scanned anyway.

**Prevention:**
- Use Pydantic to parse and validate `vaultscan.yml` on startup
- Emit a warning for any unrecognized key (do not silently ignore)
- Print a config summary at scan start: "Loaded config: exclude_paths=[.git, node_modules], max_commits=500"

**Phase to address:** Configuration loading, before any scanner logic uses config values.

---

### Pitfall 7: Concurrent Scan Requests Create Race Conditions

**What goes wrong:** User clicks "scan" twice. Two BackgroundTasks run concurrently. Results interleave or one overwrites the other's state mid-run.

**Prevention:**
- HTTP 409 if scan is already in progress: `{"error": "scan_in_progress"}`
- `asyncio.Lock` or `running: bool` flag in ReportStore
- UI disables scan button while `scan_state.running == True`

**Phase to address:** API layer and frontend — must ship together.

---

### Pitfall 8: HTML Export Contains Plaintext Secrets

**What goes wrong:** HTML export shows full matched string. Developer exports report, shares via Slack or commits to "security audit" directory. Secret is now in a new location.

**Prevention:**
- HTML export: redact to first-4 + last-4 (`AKIA****XXXX`)
- `Finding` model: `matched_value` (full, internal only) + `masked_value` (for export and API responses)
- Warning banner in HTML: "Do not commit this file to version control"

**Phase to address:** Export pipeline — redaction is a security property, not a polish item.

---

### Pitfall 9: Scanning `node_modules/`, `.git/`, and Virtual Environments

**What goes wrong:** File walker visits `node_modules/` (thousands of files, minified JS). Shannon entropy goes haywire. Scan time multiplies 10x.

**Prevention:**
- Use `git ls-files` via GitPython as the file list — not `os.walk()`. Automatically respects `.gitignore`.
- Mandatory hard-coded exclusion list (cannot be overridden): `.git/`, `node_modules/`, `__pycache__/`, `.venv/`, `venv/`, `dist/`, `build/`

**Phase to address:** File walker — use `git ls-files` from the beginning.

---

### Pitfall 10: Severity Inflation — Everything Is CRITICAL

**What goes wrong:** Every regex match labelled CRITICAL. Developer sees 47 CRITICAL findings, assumes tool is wrong, ignores all of them.

**Prevention:** Define severity matrix as a first-class data structure:
- `CRITICAL`: Active credential, working tree, high-confidence pattern, non-test path
- `HIGH`: Active credential, working tree, pattern match, non-test path
- `MEDIUM`: Credential in git history only, or IaC misconfig with direct exploit path
- `LOW`: Pattern match in test/docs path, entropy-only finding, IaC style issue

Surface severity rationale in UI: "CRITICAL because: working tree, AWS key pair, non-test path."

**Phase to address:** Data model and filter pipeline — severity matrix must exist before UI is built.

---

## Minor Pitfalls

### Pitfall 11: Regex Catastrophic Backtracking on Long Lines

**Prevention:** Skip any line exceeding 2,000 characters before applying regex. Use `re.compile()` at module import, not inside scanning loop.

**Phase to address:** Core scanner engine.

---

### Pitfall 12: `.env.example` Files Flagged as CRITICAL

**Prevention:**
- Add `.env.example`, `.env.template`, `.env.sample` to path-context demotion list → always LOW
- Placeholder value detection: strings containing `YOUR_`, `REPLACE_`, `_HERE`, `_EXAMPLE` → score zero confidence

**Phase to address:** Filter pipeline.

---

### Pitfall 13: Dashboard DOM Freeze on Large Finding Sets

**Prevention:**
- Paginate `GET /api/report?page=1&limit=50` — this is an API contract; changing post-launch breaks clients
- Render incrementally; group by severity first

**Phase to address:** Frontend and API design together.

---

## Phase Warning Summary

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Core scanner engine | Entropy threshold not calibrated per file type | Character-class thresholds + mandatory skip list |
| Regex pattern library | Matching test fixtures and AWS example keys | Known-fake-value denylist before phase is done |
| File walker | Scanning node_modules, .git, venv | Use `git ls-files` — never raw `os.walk()` |
| Git history scanner | Memory spike on large repos | Generator iterator + per-blob size limit + `max_commits` cap |
| Git history scanner | Rotated secrets shown as CRITICAL | `Finding` model needs `source` + `commit_date` from day one |
| IaC scanner | Dockerfile `ENV VAR` without value flagged | Rule must distinguish `ENV VAR=value` from `ENV VAR` |
| IaC scanner | `.env` flagged when gitignored | Check git index presence, not filesystem presence |
| IaC scanner | SHA-pinned Actions flagged as insecure | SHA=safe, branch=CRITICAL, tag=MEDIUM |
| Filter pipeline | Severity inflation | Severity matrix as data structure before UI |
| Config loading | Silent YAML misconfiguration | Pydantic validation + warn on unknown keys |
| Export pipeline | Plaintext secrets in HTML export | Redact to first-4+last-4 from day one |
| API layer | Concurrent scan race condition | asyncio.Lock + HTTP 409 + button disable |
| Dashboard frontend | DOM freeze on 500+ findings | Paginate API; render incrementally |
