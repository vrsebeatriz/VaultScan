<!-- GSD:project-start source:PROJECT.md -->

## Project

**VaultScan**

VaultScan é um scanner local de secrets expostos e misconfigurações de IaC em repositórios Git. Analisa o código-fonte atual e o histórico de commits via pipeline em 3 camadas, exibindo os resultados em um dashboard visual com triagem por severidade. 100% local — nenhum dado sai da máquina.

**Core Value:** Identificar secrets e misconfigurações antes que cheguem à produção, com evidência auditável exportável em HTML/JSON.

### Constraints

- **Tech Stack**: Python 3.11 + FastAPI + Vanilla JS + Tailwind CSS — já decidido pelo usuário
- **Privacy**: Dados de scan nunca saem da máquina local
- **Dependencies**: GitPython para acesso ao histórico de commits

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Core Backend Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11 | Runtime | Already decided; 3.11 gives `tomllib` stdlib, solid `match` support, good type hint ergonomics |
| FastAPI | >=0.135.0 | HTTP API + SSE + static file serving | Native `EventSourceResponse` (SSE) added in 0.135.0 — exactly what the real-time scan progress feed needs. No extra library required. |
| Uvicorn | ^0.30 | ASGI server | FastAPI's canonical dev server. Single process is fine for a local tool. Use `--reload` during development. Do NOT use Gunicorn — single-user local tool. |
| Pydantic | ^2.7 | Data models, config validation | FastAPI 0.100+ requires Pydantic v2. Use `BaseModel` for `Finding`, `ScanResult`, and `ScanConfig` schemas. |
| Starlette | (auto-installed via FastAPI) | CORS, StaticFiles, StreamingResponse | Do not install separately — FastAPI pins the compatible version. |

## Real-Time Progress Streaming

## Secrets Detection

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Custom regex (stdlib `re`) | stdlib | Pattern matching for AWS, GitHub, OpenAI, Stripe | Four token families with stable patterns. Full control over false-positive tuning without dependency weight. |
| Shannon entropy (stdlib `math`) | stdlib | Secondary signal for high-entropy strings | `math.log2` is all you need. Catches unrecognized tokens that regex misses. |
| `detect-secrets` (Yelp) | ~1.5 | Optional: additional built-in detectors | Use as secondary layer, not primary. Has detectors for keyword patterns, basic auth, private keys, Slack. Pin a specific version — maintenance has been slow. |

- **TruffleHog / gitleaks**: Go binaries — break pure-Python install goal
- **Semgrep**: Heavy, requires separate install, overkill for four token families

## IaC Misconfiguration Detection

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pyyaml` | ^6.0 | Parse GitHub Actions YAML | Safe YAML parser. Always use `yaml.safe_load()` — never bare `yaml.load()`. |
| `python-dotenv` | ^1.0 | Parse `.env` files | Battle-tested. Exposes key-value pairs for misconfiguration checks. |
| Custom regex (stdlib `re`) | stdlib | Dockerfile rule checks | Dockerfile syntax is line-oriented. Regex outperforms a full AST parser for this scope. |

- **checkov / tfsec / trivy**: Enterprise tools with large dep trees designed for CI pipelines, not Python embedding
- **`ruamel.yaml`**: Round-trip editing is unused here; PyYAML is sufficient for read-only parsing

## Git History Scanning

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `GitPython` | ^3.1 | Walk commit history, diff blobs, read file content at historical commits | Already decided. `repo.iter_commits()` + `commit.diff(parent)` gives efficient per-commit diffs. Pure-Python — safer for cross-platform installs than `pygit2` (requires compiled C extension). |

- **Memory**: Scan diffs (`commit.diff(commit.parents[0])`) — NOT full trees. Iterating large repos with full blob reads spikes memory.
- **Security**: GitPython has had past CVEs related to unsafe `git` binary execution with attacker-controlled paths. Acceptable for local use — wrap `git.Repo(path)` in `try/except git.exc.InvalidGitRepositoryError`.

## CLI Entry Point

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `typer` | ^0.12 | `vaultscan scan /path/to/repo` CLI | Built on Click, uses Python type hints — zero boilerplate. `typer.launch()` opens a URL in the default browser. Maintained by the FastAPI author (Tiangolo). |
| `webbrowser` (stdlib) | stdlib | Browser open fallback | Always available, no extra dep. |

- **argparse**: Verbose; Typer produces better `--help` with 80% less code
- **Click directly**: Typer wraps Click cleanly; drop to raw Click only if you need advanced plugin architecture

## Configuration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pyyaml` | ^6.0 (shared with IaC scanner) | Parse `vaultscan.yml` | Shared dep — no extra install cost. Use with a Pydantic `BaseModel` to validate config and provide defaults. |
| `pydantic-settings` | ^2.3 | Environment variable overrides | Allows `VAULTSCAN_*` env vars to override `vaultscan.yml` values. Useful if the tool is later wired into pre-commit hooks or CI. |

## Report Export

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `jinja2` | ^3.1 | HTML report template rendering | FastAPI's `Jinja2Templates` wraps this. A single `report.html.j2` template produces self-contained HTML. Often already a transitive dep. |
| `json` (stdlib) | stdlib | JSON report export | `json.dumps()` on Pydantic `.model_dump()` — no library needed. |

## Frontend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Vanilla JS | ES2022+ | Dashboard logic, fetch, SSE EventSource | Already decided. `fetch()` + `EventSource` (native browser APIs) handle all required interactions. |
| Tailwind CSS | v4 (standalone CLI) | Utility-first styling for glassmorphism cards | v4 is current major version (2025). Use the **standalone CLI executable** — no Node.js or npm required. Keeps the project a pure Python install. |

- Config moves from `tailwind.config.js` to CSS `@theme {}` blocks
- Standalone CLI produces a single `output.css` served from `public/` via FastAPI `StaticFiles`
- v4 build times: 3-8x faster than v3
- **Do not use the Play CDN** — it is development-only per official docs
- **Alpine.js / HTMX / React/Vue/Svelte**: Violates Vanilla JS constraint; adds unnecessary complexity

## Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pytest` | ^8.0 | Test runner | Standard Python test runner |
| `httpx` | ^0.27 | FastAPI TestClient dependency | Required by FastAPI's `TestClient`. Use `httpx.AsyncClient` for async endpoint tests. |
| `pytest-asyncio` | ^0.23 | Async test support | Needed for `await` in async FastAPI path operation tests. Set `asyncio_mode = "auto"` in `pytest.ini`. |

## Full Dependency List

# requirements.txt

# requirements-dev.txt

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

## Roadmap Implications

- Phase 1 can wire up the full FastAPI skeleton (routes, SSE endpoint, static file serving, CORS) before any scanner logic — the framework choices are stable
- Phase 2 (secrets scanner): implement regex + entropy natively first; add `detect-secrets` only if gap analysis shows missing detector coverage
- Phase 3 (IaC scanner): Dockerfile rules can be regex-based; GitHub Actions rules need PyYAML parsing
- The Tailwind standalone CLI binary must be documented in project setup — it is a build-time dep, not a runtime dep
- `FastAPI >= 0.135.0` is a hard minimum — verify this is the current release before locking the version

## Sources

- FastAPI release notes: https://fastapi.tiangolo.com/release-notes/
- FastAPI SSE tutorial: https://fastapi.tiangolo.com/tutorial/server-sent-events/
- FastAPI BackgroundTasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- FastAPI StaticFiles: https://fastapi.tiangolo.com/tutorial/static-files/
- FastAPI Testing: https://fastapi.tiangolo.com/tutorial/testing/
- Tailwind CSS v4 announcement: https://tailwindcss.com/blog/tailwindcss-v4
- Tailwind CSS standalone CLI: https://tailwindcss.com/docs/installation/tailwind-cli

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
