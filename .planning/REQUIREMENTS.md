# VaultScan — Requirements

**Version:** v1
**Date:** 2026-06-11
**Status:** Active

---

## v1 Requirements

### Detection Engine

- [ ] **DET-01**: Usuário pode detectar secrets hardcoded usando regex para padrões AWS, GitHub, OpenAI e Stripe
- [ ] **DET-02**: Shannon entropy é calculada como sinal secundário para elevar findings de regex e detectar tokens não padronizados de alta entropia (nunca como detector standalone)
- [ ] **DET-03**: Findings idênticos (mesmo secret em múltiplos arquivos/commits) são deduplicados — o usuário vê 1 finding com N ocorrências, não N linhas
- [ ] **DET-04**: Cada finding inclui um context snippet com 3–5 linhas de código ao redor do match

### Severity & Classification

- [ ] **SEV-01**: Cada finding recebe uma classificação de severidade determinística: Critical / High / Medium / Low — com matriz documentada e rationale visível no dashboard
- [ ] **SEV-02**: Findings em `test/`, `docs/`, `*.spec.*`, `*fixture*`, `*mock*`, `README*` são automaticamente demovidos para LOW (nunca suprimidos — demovidos com motivo)

### False Positive Filters

- [ ] **FLT-01**: Filtro por extensão: arquivos `.lock`, `.min.js`, `.map`, `.svg`, `.png`, `.wasm`, `.bin` são excluídos da análise de entropia
- [ ] **FLT-02**: Filtro por caminho: `node_modules/`, `.git/`, `__pycache__/`, `.venv/`, `venv/`, `dist/`, `build/` são excluídos mandatoriamente (não overridável pelo usuário)
- [ ] **FLT-03**: Denylist de valores fake por tipo de token: `AKIAIOSFODNN7EXAMPLE` e equivalentes nunca são flaggados independente de pattern match
- [ ] **FLT-04**: Usuário pode configurar exclusões adicionais de caminho, extensão e padrão via `vaultscan.yml`

### IaC Scanner

- [ ] **IAC-01**: Dockerfile scanner detecta misconfigurações: `ENV VAR=literal_credential_value`, `FROM image:latest`, `ADD http://...`, `RUN curl | sh` — distingue `ENV VAR=valor` (flag) de `ENV VAR` sem valor (seguro)
- [ ] **IAC-02**: GitHub Actions scanner detecta: `uses: org/action@branch` como CRITICAL (mutable), `uses: org/action@tag` como MEDIUM, `uses: org/action@SHA` como seguro (não flaggado)
- [ ] **IAC-03**: .env scanner flagga arquivos `.env` APENAS quando rastreados no git index (via `git ls-files`) — arquivos no `.gitignore` não geram findings

### Git History Scanner

- [ ] **GIT-01**: Scanner percorre o histórico completo de commits do repositório com cap configurável via `vaultscan.yml` (default: 500 commits) — emite aviso quando cap é atingido
- [ ] **GIT-02**: Cada finding inclui campo `source` com valor `working_tree` ou `git_history`; findings de `git_history` são automaticamente demovidos 1 nível de severidade vs findings de `working_tree`
- [ ] **GIT-03**: Cada finding de git history inclui commit SHA, data do commit e mensagem do commit

### Configuration

- [ ] **CFG-01**: Usuário pode configurar o comportamento do scanner via `vaultscan.yml`: `exclude_paths`, `exclude_extensions`, `max_commits`, `entropy_threshold` por classe de caractere, e regras de ignore customizadas
- [ ] **CFG-02**: Config é validada por schema Pydantic na inicialização — chaves desconhecidas geram warning, não erro silencioso; summary da config é exibido no início do scan

### API REST

- [ ] **API-01**: `POST /api/scan` recebe `{ repo_path }`, valida que o path é um repositório git válido, dispara scan como BackgroundTask e retorna 202 com `scan_id` imediatamente — retorna 409 se scan já estiver em andamento
- [ ] **API-02**: `GET /api/status?scan_id=xxx` retorna status do scan: `running | complete | error` e percentual de progresso
- [ ] **API-03**: `GET /api/report?scan_id=xxx` retorna `ScanReport` JSON com findings (usando `masked_value` — nunca `matched_value` raw)

### Export

- [ ] **EXP-01**: `GET /api/export?scan_id=xxx&format=html` gera HTML standalone com findings; valores de secrets reduzidos a first-4 + `****` + last-4; inclui banner de aviso "não commitar este arquivo"
- [ ] **EXP-02**: `GET /api/export?scan_id=xxx&format=json` gera JSON completo do `ScanReport` para scripting e integração

### Dashboard Web

- [ ] **UI-01**: Dashboard exibe severity cards com contagem de findings por nível (Critical / High / Medium / Low) na carga inicial do scan
- [ ] **UI-02**: Usuário pode filtrar findings por severidade, tipo de scanner (secrets / iac / git_history) e arquivo
- [ ] **UI-03**: Dashboard exibe commit timeline mostrando quando cada secret entrou no repositório
- [ ] **UI-04**: Dashboard exibe indicador de progresso do scan em tempo real (SSE ou polling de `GET /api/status`)
- [ ] **UI-05**: Resultados de findings são paginados (máximo 50 por página) para evitar freeze do DOM

### CLI & Entry Point

- [ ] **CLI-01**: `vaultscan scan /path/to/repo` inicia o servidor FastAPI, dispara o scan e abre o dashboard no browser automaticamente
- [ ] **CLI-02**: CLI retorna exit code 1 se findings forem encontrados, exit code 0 se o repositório estiver limpo
- [ ] **CLI-03**: Usuário pode especificar o path do repositório via campo de texto no dashboard (alternativa ao CLI)

---

## v2 (Deferred)

- Secret still-active indicator (compara HEAD vs git_history para mostrar se secret ainda está ativo)
- Export de view filtrada (exportar somente os findings visíveis após aplicar filtros do dashboard)
- Scan-scoped inline ignores (`# vaultscan:ignore` em linha)
- Detailed IaC fix descriptions (descrição do risco + fix recomendado por regra)
- `detect-secrets` como camada opcional de detecção adicional

---

## Out of Scope

- Integração com serviços remotos (CI/CD cloud, GitHub Actions cloud) — 100% local
- Scan de repositórios remotos — somente caminhos locais no disco
- Autenticação/multiusuário — single-user local tool
- Cloud sync ou telemetria de qualquer tipo — nenhum dado sai da máquina
- Verificação de validade de credentials via API calls — cria risco de privacidade e alertas de segurança
- Auto-remediation (auto-delete, auto-rotate) — operações destrutivas no histórico git são perigosas
- Slack / PagerDuty / webhook alerting — requer daemon persistente e acesso de rede
- SARIF output format — padrão enterprise para CI cloud; irrelevante para uso local
- TUI interativa (ncurses/Textual) — o dashboard web já é a interface interativa

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| CFG-01 | Phase 1: Foundation | Pending |
| CFG-02 | Phase 1: Foundation | Pending |
| FLT-01 | Phase 1: Foundation | Pending |
| FLT-02 | Phase 1: Foundation | Pending |
| FLT-03 | Phase 1: Foundation | Pending |
| FLT-04 | Phase 1: Foundation | Pending |
| SEV-01 | Phase 1: Foundation | Pending |
| SEV-02 | Phase 1: Foundation | Pending |
| DET-01 | Phase 2: Secrets Scanner | Pending |
| DET-02 | Phase 2: Secrets Scanner | Pending |
| DET-03 | Phase 2: Secrets Scanner | Pending |
| DET-04 | Phase 2: Secrets Scanner | Pending |
| GIT-01 | Phase 3: Git History Scanner | Pending |
| GIT-02 | Phase 3: Git History Scanner | Pending |
| GIT-03 | Phase 3: Git History Scanner | Pending |
| IAC-01 | Phase 4: IaC Scanner | Pending |
| IAC-02 | Phase 4: IaC Scanner | Pending |
| IAC-03 | Phase 4: IaC Scanner | Pending |
| API-01 | Phase 5: API + Orchestrator | Pending |
| API-02 | Phase 5: API + Orchestrator | Pending |
| API-03 | Phase 5: API + Orchestrator | Pending |
| UI-01 | Phase 6: Web Dashboard | Pending |
| UI-02 | Phase 6: Web Dashboard | Pending |
| UI-03 | Phase 6: Web Dashboard | Pending |
| UI-04 | Phase 6: Web Dashboard | Pending |
| UI-05 | Phase 6: Web Dashboard | Pending |
| EXP-01 | Phase 7: Export + CLI | Pending |
| EXP-02 | Phase 7: Export + CLI | Pending |
| CLI-01 | Phase 7: Export + CLI | Pending |
| CLI-02 | Phase 7: Export + CLI | Pending |
| CLI-03 | Phase 7: Export + CLI | Pending |
