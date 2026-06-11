# Technology Stack

**Project:** VaultScan — Local Secrets & IaC Misconfiguration Scanner
**Researched:** 2026-06-11
**Confidence:** MEDIUM-HIGH (FastAPI/Pydantic/Starlette from official docs; library versions from training data — verify on PyPI before pinning)

---

## Core Backend Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11 | Runtime | Already decided; 3.11 gives `tomllib` stdlib, solid `match` support, good type hint ergonomics |
| FastAPI | >=0.135.0 | HTTP API + SSE + static file serving | Native `EventSourceResponse` (SSE) added in 0.135.0 — exactly what the real-time scan progress feed needs. No extra library required. |
| Uvicorn | ^0.30 | ASGI server | FastAPI's canonical dev server. Single process is fine for a local tool. Use `--reload` during development. Do NOT use Gunicorn — single-user local tool. |
| Pydantic | ^2.7 | Data models, config validation | FastAPI 0.100+ requires Pydantic v2. Use `BaseModel` for `Finding`, `ScanResult`, and `ScanConfig` schemas. |
| Starlette | (auto-installed via FastAPI) | CORS, StaticFiles, StreamingResponse | Do not install separately — FastAPI pins the compatible version. |

---

## Real-Time Progress Streaming

**Decision: Server-Sent Events (SSE) over WebSockets.**

FastAPI 0.135.0 introduced native `EventSourceResponse` in `fastapi.sse`. SSE is correct for VaultScan because:
1. Communication is **unidirectional** — server pushes progress; browser does not send data back during a scan
2. SSE auto-reconnects on drop (browser `EventSource` API)
3. No extra library needed — it is in FastAPI core as of 0.135.0

For scan cancellation: use a separate `POST /api/scan/cancel` endpoint — keeps the transport simple.

---

## Secrets Detection

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Custom regex (stdlib `re`) | stdlib | Pattern matching for AWS, GitHub, OpenAI, Stripe | Four token families with stable patterns. Full control over false-positive tuning without dependency weight. |
| Shannon entropy (stdlib `math`) | stdlib | Secondary signal for high-entropy strings | `math.log2` is all you need. Catches unrecognized tokens that regex misses. |
| `detect-secrets` (Yelp) | ~1.5 | Optional: additional built-in detectors | Use as secondary layer, not primary. Has detectors for keyword patterns, basic auth, private keys, Slack. Pin a specific version — maintenance has been slow. |

**What NOT to use:**
- **TruffleHog / gitleaks**: Go binaries — break pure-Python install goal
- **Semgrep**: Heavy, requires separate install, overkill for four token families

**Recommendation:** Implement regex + entropy natively in `src/pipeline/secrets_scanner.py`. `detect-secrets` is an optional day-2 enhancement.

---

## IaC Misconfiguration Detection

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pyyaml` | ^6.0 | Parse GitHub Actions YAML | Safe YAML parser. Always use `yaml.safe_load()` — never bare `yaml.load()`. |
| `python-dotenv` | ^1.0 | Parse `.env` files | Battle-tested. Exposes key-value pairs for misconfiguration checks. |
| Custom regex (stdlib `re`) | stdlib | Dockerfile rule checks | Dockerfile syntax is line-oriented. Regex outperforms a full AST parser for this scope. |

**What NOT to use:**
- **checkov / tfsec / trivy**: Enterprise tools with large dep trees designed for CI pipelines, not Python embedding
- **`ruamel.yaml`**: Round-trip editing is unused here; PyYAML is sufficient for read-only parsing

---

## Git History Scanning

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `GitPython` | ^3.1 | Walk commit history, diff blobs, read file content at historical commits | Already decided. `repo.iter_commits()` + `commit.diff(parent)` gives efficient per-commit diffs. Pure-Python — safer for cross-platform installs than `pygit2` (requires compiled C extension). |

**Known caveats:**
- **Memory**: Scan diffs (`commit.diff(commit.parents[0])`) — NOT full trees. Iterating large repos with full blob reads spikes memory.
- **Security**: GitPython has had past CVEs related to unsafe `git` binary execution with attacker-controlled paths. Acceptable for local use — wrap `git.Repo(path)` in `try/except git.exc.InvalidGitRepositoryError`.

---

## CLI Entry Point

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `typer` | ^0.12 | `vaultscan scan /path/to/repo` CLI | Built on Click, uses Python type hints — zero boilerplate. `typer.launch()` opens a URL in the default browser. Maintained by the FastAPI author (Tiangolo). |
| `webbrowser` (stdlib) | stdlib | Browser open fallback | Always available, no extra dep. |

**What NOT to use:**
- **argparse**: Verbose; Typer produces better `--help` with 80% less code
- **Click directly**: Typer wraps Click cleanly; drop to raw Click only if you need advanced plugin architecture

---

## Configuration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pyyaml` | ^6.0 (shared with IaC scanner) | Parse `vaultscan.yml` | Shared dep — no extra install cost. Use with a Pydantic `BaseModel` to validate config and provide defaults. |
| `pydantic-settings` | ^2.3 | Environment variable overrides | Allows `VAULTSCAN_*` env vars to override `vaultscan.yml` values. Useful if the tool is later wired into pre-commit hooks or CI. |

---

## Report Export

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `jinja2` | ^3.1 | HTML report template rendering | FastAPI's `Jinja2Templates` wraps this. A single `report.html.j2` template produces self-contained HTML. Often already a transitive dep. |
| `json` (stdlib) | stdlib | JSON report export | `json.dumps()` on Pydantic `.model_dump()` — no library needed. |

---

## Frontend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Vanilla JS | ES2022+ | Dashboard logic, fetch, SSE EventSource | Already decided. `fetch()` + `EventSource` (native browser APIs) handle all required interactions. |
| Tailwind CSS | v4 (standalone CLI) | Utility-first styling for glassmorphism cards | v4 is current major version (2025). Use the **standalone CLI executable** — no Node.js or npm required. Keeps the project a pure Python install. |

**Tailwind v4 specifics:**
- Config moves from `tailwind.config.js` to CSS `@theme {}` blocks
- Standalone CLI produces a single `output.css` served from `public/` via FastAPI `StaticFiles`
- v4 build times: 3-8x faster than v3
- **Do not use the Play CDN** — it is development-only per official docs

**What NOT to use:**
- **Alpine.js / HTMX / React/Vue/Svelte**: Violates Vanilla JS constraint; adds unnecessary complexity

---

## Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pytest` | ^8.0 | Test runner | Standard Python test runner |
| `httpx` | ^0.27 | FastAPI TestClient dependency | Required by FastAPI's `TestClient`. Use `httpx.AsyncClient` for async endpoint tests. |
| `pytest-asyncio` | ^0.23 | Async test support | Needed for `await` in async FastAPI path operation tests. Set `asyncio_mode = "auto"` in `pytest.ini`. |

---

## Full Dependency List

```
# requirements.txt
fastapi>=0.135.0          # SSE support requires 0.135.0+
uvicorn[standard]>=0.30   # [standard] includes watchfiles for --reload
pydantic>=2.7
pydantic-settings>=2.3
gitpython>=3.1
pyyaml>=6.0
python-dotenv>=1.0
jinja2>=3.1
typer>=0.12
httpx>=0.27               # FastAPI TestClient dependency

# requirements-dev.txt
pytest>=8.0
pytest-asyncio>=0.23
```

---

## What NOT to Use (Summary)

| Category | Rejected Option | Reason |
|----------|----------------|--------|
| Background tasks | Celery + Redis | External service dep; overkill for single-user local tool |
| Progress streaming | WebSockets | Unidirectional feed — SSE is simpler, auto-reconnects, native FastAPI 0.135+ |
| IaC scanner | checkov / trivy / tfsec | Heavy enterprise tools; CI pipeline targets, not embeddable |
| Secrets scanner | TruffleHog / gitleaks | Go binaries; break cross-platform pure-Python install |
| Tailwind | Play CDN | Development-only per official docs |
| Tailwind | v3 | v4 is current; start on v4 to avoid mid-project migration |
| YAML parser | `yaml.load()` bare | Executes arbitrary Python; always use `yaml.safe_load()` |
| Git history | Full tree scan per commit | Memory spike on large repos; scan diffs only |
| CLI | argparse | Typer produces equivalent output with far less boilerplate |

---

## Roadmap Implications

- Phase 1 can wire up the full FastAPI skeleton (routes, SSE endpoint, static file serving, CORS) before any scanner logic — the framework choices are stable
- Phase 2 (secrets scanner): implement regex + entropy natively first; add `detect-secrets` only if gap analysis shows missing detector coverage
- Phase 3 (IaC scanner): Dockerfile rules can be regex-based; GitHub Actions rules need PyYAML parsing
- The Tailwind standalone CLI binary must be documented in project setup — it is a build-time dep, not a runtime dep
- `FastAPI >= 0.135.0` is a hard minimum — verify this is the current release before locking the version

---

## Sources

- FastAPI release notes: https://fastapi.tiangolo.com/release-notes/
- FastAPI SSE tutorial: https://fastapi.tiangolo.com/tutorial/server-sent-events/
- FastAPI BackgroundTasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- FastAPI StaticFiles: https://fastapi.tiangolo.com/tutorial/static-files/
- FastAPI Testing: https://fastapi.tiangolo.com/tutorial/testing/
- Tailwind CSS v4 announcement: https://tailwindcss.com/blog/tailwindcss-v4
- Tailwind CSS standalone CLI: https://tailwindcss.com/docs/installation/tailwind-cli
