# Feature Landscape: Secrets / IaC Security Scanner

**Domain:** Local CLI + Web Dashboard security scanner (secrets, IaC misconfigs, git history)
**Researched:** 2026-06-11
**Confidence note:** All findings from training data (TruffleHog, Gitleaks, detect-secrets, Checkov, Trivy, tfsec, Semgrep, GitGuardian). External tools were unavailable.

---

## Table Stakes

Features users expect from any secrets/IaC scanner. Missing = product feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Regex-based secret detection (API keys, tokens) | Every scanner does this; it is the baseline capability | Low | Must cover at minimum: AWS, GitHub, OpenAI, Stripe — already planned |
| Git history scan (not just working tree) | Leaks almost always come from old commits; scan-HEAD-only is a known false sense of security | Medium | GitPython traversal already planned; must scan ALL commits not just HEAD |
| Severity classification (Critical/High/Medium/Low/Info) | Users cannot triage 200 raw findings; severity is mandatory for prioritization | Low | Must be deterministic and documented, not arbitrary |
| Finding deduplication | Same secret committed 50 times = 1 finding with N occurrences, not 50 rows | Medium | Without this, large repos produce unusable output |
| False positive suppression (allowlist/ignore rules) | Every real codebase has test fixtures, example keys, placeholder tokens | Medium | Via `vaultscan.yml` + path/extension/content rules |
| JSON output | CI integration, scripting, post-processing | Low | Already planned |
| HTML report export | Non-engineers need to read findings; audit trail | Low | Already planned |
| Exact file + line number in each finding | Without location, a finding is useless | Low | Must include: file path, line number, matched value (redacted), commit SHA |
| Entropy-based detection for unrecognized tokens | Regex alone misses custom/internal tokens; entropy catches high-randomness strings | Medium | Shannon entropy on base64/hex strings; already planned |
| CLI with proper exit codes | CI pipelines need `exit 1` on findings, `exit 0` on clean | Low | Table stakes for developer adoption |
| Configuration file (`.yml`) | Developers must tune rules without modifying source code | Low | `vaultscan.yml` already planned |
| IaC misconfiguration detection (Dockerfile, .env, CI workflows) | .env files with real secrets, hardcoded ENV in Dockerfiles are extremely common leak vectors | Medium | Must cover: exposed ports, privileged containers, hardcoded secrets in ENV, .env committed |
| Scan progress feedback | Large repos with full git history can take minutes; silent tools feel broken | Low | Progress bar or streaming status in CLI; spinner/status in web UI |

---

## Differentiators

Features that set VaultScan apart. Not universally expected, but valued once discovered.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Commit timeline visualization | Shows WHEN a secret entered the repo and whether it was later removed — critical for breach investigation | High | Already planned; genuinely rare in CLI-only tools |
| Web dashboard with live filtering | Most secrets tools are pure CLI with JSON blobs; a browsable, filterable UI dramatically lowers time-to-triage | High | Core VaultScan differentiator; already planned |
| Shannon entropy as secondary signal with tunable threshold | Catches tokens that don't match known patterns (internal APIs, custom auth); most tools regex-only | Medium | Already planned; expose threshold in `vaultscan.yml` |
| Per-finding context snippet with redacted secret | Show 3–5 surrounding code lines; secret value partially masked | Low | Makes findings actionable without opening the file |
| Secret still-active indicator (history vs. HEAD) | Distinguish "secret only in history" vs. "secret in HEAD right now" — very different risk levels | Medium | Git blame + HEAD tree comparison; high triage value |
| Severity card summary on dashboard load | Visual at-a-glance: "3 Critical, 12 High, 40 Medium" before scrolling | Low | Already partially planned |
| Scan-scoped inline ignores (`# vaultscan:ignore`) | Inline suppression like ESLint disable comments; reduces false-positive friction | Low | Developers love this pattern |
| Export filtered view (not just full report) | Apply UI filters, export only what is visible | Medium | Requires filter state to propagate to export pipeline |
| Detailed IaC rule descriptions (why it's bad + fix) | Most tools emit only a rule ID; emit: risk description, concrete fix, reference | Low | High perceived quality increase for low cost |
| Multi-format secret validation hints | "This matches AWS key format — verify it is not a live credential" — adds context without API calls | Low | Training-data-based hints; no network calls |

---

## Anti-Features

Features to deliberately NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Cloud sync / remote telemetry | Directly contradicts the "100% local" core value | All data on-disk; no analytics, no phoning home |
| Secret validity checking via live API calls | Privacy risk, may trigger security alerts on tested accounts | Mark as "potential live credential — verify manually" |
| Multi-user / team collaboration | Out of scope; adds auth complexity | Single-user; team features belong in a future SaaS tier |
| Automatic remediation (auto-delete, auto-rotate) | Destructive git history ops are dangerous | Emit recommended remediation as text; let the user act |
| Scanning remote repositories | Out of scope; increases attack surface | Accept only local paths already on disk |
| SARIF output format | Complex standard primarily useful for GitHub Advanced Security (cloud) | JSON + HTML cover 100% of local use cases |
| Slack / PagerDuty / webhook alerting | Requires persistent daemon and network access | Use exit codes + JSON for integrations |
| Interactive TUI (ncurses/Textual) | High complexity when a web dashboard already exists | Web dashboard IS the interactive interface |

---

## Feature Dependencies

```
Shannon entropy detection
  → depends on: regex detection (entropy is secondary signal, not standalone)

Git history scan
  → depends on: finding deduplication (history scan multiplies raw count dramatically)

Commit timeline visualization
  → depends on: git history scan + per-finding commit SHA

Secret still-active indicator
  → depends on: git history scan + HEAD tree comparison

Export filtered view
  → depends on: web dashboard filtering + export pipeline

Per-finding context snippet
  → depends on: exact file + line number

Web dashboard
  → depends on: REST API (GET /api/report, POST /api/scan)
```

---

## MVP Recommendation

**Ship in v1 (table stakes + core differentiator cluster):**
1. Regex secret detection — AWS, GitHub, OpenAI, Stripe
2. Shannon entropy as secondary signal
3. Git history scan via GitPython
4. Finding deduplication (required before history scan is usable)
5. Exact file + line number + context snippet
6. Severity classification (Critical/High/Medium/Low)
7. False positive suppression via `vaultscan.yml`
8. IaC misconfiguration detection — Dockerfile, GitHub Actions, .env
9. JSON + HTML export
10. Web dashboard with severity cards, filters, commit timeline

**Defer to v2:**
- Secret still-active indicator (HEAD/history comparison)
- Export filtered view (filter state propagation)
- Scan-scoped inline ignores
- Detailed IaC fix descriptions

---

## Competitive Positioning

| Tool | Approach | Key Gap vs VaultScan |
|------|----------|---------------------|
| TruffleHog | Regex + entropy, git history, live verification | CLI-only, no web UI, no IaC |
| Gitleaks | Regex, git history, TOML config, SARIF | CLI-only, no entropy, no IaC, no web UI |
| detect-secrets | Baseline model, pre-commit hooks | No history traversal, no IaC, no web UI |
| Checkov | IaC-focused (Terraform, K8s, Dockerfile) | No secrets detection, no git history, no web UI |
| Trivy | Vuln + secrets + IaC, container-native | CLI-only, no web dashboard |
| GitGuardian | SaaS real-time monitoring | Cloud-based (violates local-only requirement) |

**VaultScan's unique position:** The only tool combining secrets + IaC + git history + web dashboard in a single local CLI tool.

---

## Key Findings

- **Finding deduplication is the most underrated table-stakes feature.** Git history scanning creates explosive finding counts without it.
- **The web dashboard + commit timeline is genuine whitespace.** No CLI-native tool (TruffleHog, Gitleaks, detect-secrets) has this.
- **Shannon entropy must be secondary to regex.** High false-positive rates on pure entropy make it unusable as a primary signal.
- **Live credential verification must never be built.** Creates severe privacy and operational risks for a local tool.
- **IaC + secrets together in one tool is rare.** VaultScan's three-layer pipeline as a unified scan is differentiated.
