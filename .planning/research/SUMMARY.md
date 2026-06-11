# Research Summary — VaultScan

**Synthesized from:** STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md
**Date:** 2026-06-11
**Overall confidence:** HIGH

---

## Executive Summary

VaultScan is a local-only security scanner targeting three threat surfaces: hardcoded secrets in source files, misconfigured IaC (Dockerfiles, GitHub Actions, .env files), and secrets buried in git history. The correct architecture is a layered pipeline — SecretsScanner, IaCScanner, GitHistoryScanner — running as a FastAPI BackgroundTask, with results stored in-memory and served to a Vanilla JS dashboard.

The single highest-leverage early decision: enforce `matched_value` (internal, never sent over the wire) vs `masked_value` (API-safe, redacted) on the `Finding` Pydantic model from day one. Shannon entropy must be a secondary signal that elevates regex matches — never a standalone detector.

---

## Stack

| Technology | Version | Role |
|---|---|---|
| Python | 3.11 | Runtime |
| FastAPI | >=0.135.0 | API + SSE + static file serving (**0.135.0 is hard minimum** for native `EventSourceResponse`) |
| Uvicorn | ^0.30 | ASGI server (single process, no Gunicorn) |
| Pydantic | ^2.7 | All data models and config validation |
| GitPython | ^3.1 | Commit history traversal (pure-Python, cross-platform) |
| PyYAML | ^6.0 | GitHub Actions YAML parsing (always `yaml.safe_load()`) |
| python-dotenv | ^1.0 | .env file parsing |
| Typer | ^0.12 | CLI entry point |
| Jinja2 | ^3.1 | HTML report template rendering |
| Tailwind CSS v4 | standalone CLI | Utility-first styling; no Node.js required |
| pytest + httpx + pytest-asyncio | ^8.0 / ^0.27 / ^0.23 | Testing stack |

**Hard rejections:** TruffleHog/gitleaks (Go binaries), checkov/trivy/tfsec (enterprise CI tools), Celery+Redis (external services), WebSockets (overkill for unidirectional progress), Tailwind Play CDN (dev-only per official docs).

---

## Table Stakes (must-have for v1)

- Regex secret detection: AWS, GitHub, OpenAI, Stripe
- Shannon entropy as secondary signal (elevates regex matches — never standalone)
- Git history scan across ALL commits (not just HEAD)
- Finding deduplication (git history explodes raw count without it)
- Exact file path + line number + context snippet (3–5 surrounding lines) per finding
- Severity classification: Critical / High / Medium / Low — deterministic, documented matrix
- False positive suppression via `vaultscan.yml`
- IaC detection: Dockerfile, GitHub Actions YAML, .env files
- CLI with proper exit codes (`exit 1` on findings, `exit 0` on clean)
- JSON + HTML export (HTML with redacted secret values only)
- Scan progress feedback via SSE polling

---

## Key Differentiators

- **Web dashboard with severity cards + live filtering** — no CLI-native secrets tool has this
- **Commit timeline visualization** — shows WHEN a secret entered the repo and if it was later removed
- **Three-layer pipeline (secrets + IaC + git history) in one tool** — competitors cover at most two
- **`source` field on findings** (`working_tree` vs `git_history`) — history-only findings auto-demoted one severity level; prevents alert fatigue from rotated credentials

**Never build:** cloud sync, live credential API verification, multi-user features, auto-remediation, remote repo scanning.

---

## Architecture Overview

Layered pipeline + API gateway. CLI or browser submits a scan; FastAPI returns 202 immediately and runs the pipeline as a BackgroundTask; three scanner layers run in sequence; FilterChain removes false positives; ScanReport lands in a thread-safe in-memory ReportStore; frontend polls `/api/status` then fetches `/api/report`.

**Component build order:**
```
1. src/models/          ← load-bearing foundation; every other component imports this
2. src/config.py        ← ConfigLoader singleton (@lru_cache); Pydantic-validated vaultscan.yml
3. src/filters/         ← FilterChain: ExtensionFilter, PathFilter, ContextFilter
4. src/pipeline/secrets_scanner.py  ← regex + entropy; uses git ls-files, never os.walk()
5. src/pipeline/iac_scanner.py      ← Dockerfile, GHA YAML, .env rules
6. src/pipeline/git_history_scanner.py ← shares detection logic with SecretsScanner
7. src/pipeline/orchestrator.py     ← sequences scanners + filters + ReportStore write
8. src/store.py                     ← asyncio.Lock-protected in-memory ReportStore
9. src/export/          ← Jinja2 HTML + JSON
10. src/api/            ← FastAPI routes (register BEFORE StaticFiles mount)
11. cli.py              ← Typer; calls POST /api/scan, opens browser
12. public/             ← Vanilla JS + Tailwind dashboard
```

**Critical rule:** `matched_value` (raw secret) never leaves the backend. Only `masked_value` (first-4 + `****` + last-4) is sent to the browser or written to HTML exports.

---

## Critical Pitfalls (top 5)

1. **Entropy threshold not calibrated per character class** — A single global threshold floods results with false positives from minified JS, UUIDs, base64 images. Fix: per-character-class thresholds, mandatory skip list for `.lock`, `.min.js`, `.map`, `.svg`, `.png`, `.wasm`. Entropy only elevates regex matches — never standalone.

2. **Git history walker loads full blobs without limits** — OOMs on repos with accidentally-committed binaries. Fix: generator-based commit iterator, `max_commits` cap (default 500, configurable), per-blob size limit (skip hunks >512 KB), skip binary extensions before fetching blob content.

3. **Regex patterns match test fixtures, docs, and example keys** — Fix: known-fake-value denylist per token type (AWS `AKIAIOSFODNN7EXAMPLE`, etc.), path-context scoring that demotes findings in `test/`, `docs/`, `*.spec.*`, `*fixture*`, `README*` to LOW (never suppress — demote only).

4. **IaC rules too coarse — flags safe patterns** — Fix: Dockerfile targets `ENV VAR=literal_credential_value` only; GHA treats SHA-pinned as safe, branch-pinned as CRITICAL, tag-pinned as MEDIUM; .env scanner checks git index presence via `git ls-files`, not filesystem.

5. **`matched_value` leaks into API responses or HTML export** — Fix: enforce `matched_value` vs `masked_value` split in `Finding` model in Phase 1 — cannot be retrofitted without security regressions.

---

## Build Order Recommendation

| Phase | Name | Rationale |
|---|---|---|
| 1 | Foundation — Models, Config, Project Skeleton | Lock in `matched_value`/`masked_value` split and `source` field now; every other component depends on this |
| 2 | Core Secrets Scanner + File Walker | Highest-risk implementation (entropy calibration, file walker scope); must be stable before others share its logic |
| 3 | Git History Scanner | Depends on SecretsScanner detection logic; generator-based iterator required before writing any scan logic |
| 4 | IaC Scanner | Independent; emits same `Finding` type; requires true/false test set per rule before marking done |
| 5 | API Layer + ReportStore + Orchestrator | Wire pipeline to HTTP; BackgroundTask + asyncio.Lock + StaticFiles mount order are sequencing-sensitive |
| 6 | Web Dashboard | Paginate `/api/report` from day one to avoid DOM freeze; stable HTTP contract required |
| 7 | CLI Entry Point + Polish | Additive; no other component depends on it |

---

## Research Flags for Roadmap

- Phase 2: Shannon entropy threshold calibration requires empirical testing — plan for 1–2 calibration iterations
- Phase 3: Memory behavior on large repos (>1,000 commits) must be benchmarked early with a real large repo
- Phase 4: Requires 5 true positives + 5 true negatives per rule type before marking phase done
- Before coding: verify `fastapi>=0.135.0` is available on PyPI (hard minimum for native SSE)
- Setup step: Tailwind CSS v4 standalone CLI must be documented — it is a build-time dep, not runtime
