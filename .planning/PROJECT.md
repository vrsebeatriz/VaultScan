# VaultScan

## What This Is

VaultScan é um scanner local de secrets expostos e misconfigurações de IaC em repositórios Git. Analisa o código-fonte atual e o histórico de commits via pipeline em 3 camadas, exibindo os resultados em um dashboard visual com triagem por severidade. 100% local — nenhum dado sai da máquina.

## Core Value

Identificar secrets e misconfigurações antes que cheguem à produção, com evidência auditável exportável em HTML/JSON.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Usuário pode apontar um repositório Git local via CLI (`vaultscan scan /path`) ou campo no dashboard
- [ ] Secrets Scanner detecta padrões AWS, GitHub, OpenAI e Stripe via regex + entropia de Shannon
- [ ] IaC Scanner detecta misconfigurações em Dockerfile, GitHub Actions e arquivos .env
- [ ] Git History Scanner analisa commits anteriores via GitPython
- [ ] Filtro de falsos positivos por extensão, caminho e contexto
- [ ] Dashboard exibe findings com cards por severidade, filtros e timeline de commits
- [ ] API REST: POST /api/scan inicia varredura, GET /api/report retorna resultados
- [ ] Export de relatório em HTML e JSON
- [ ] Configuração via vaultscan.yml

### Out of Scope

- Integração com serviços remotos (CI/CD, GitHub Actions cloud) — projeto é 100% local
- Scan de repositórios remotos (apenas caminhos locais)
- Autenticação/multiusuário — ferramenta single-user local

## Context

- Design visual: Light glassmorphism ("Liquid Glass") — fundo claro, cards translucentes, sombra suave, Tailwind CSS
- Entry point dual: CLI (`vaultscan scan /path/to/repo`) abre o browser automaticamente; dashboard também aceita path via campo de texto
- Estrutura de código: `src/pipeline/`, `src/filters/`, `src/models/`, `src/export/`, `public/`
- Backend: Python 3.11 + FastAPI; Frontend: Vanilla JS + Tailwind CSS

## Constraints

- **Tech Stack**: Python 3.11 + FastAPI + Vanilla JS + Tailwind CSS — já decidido pelo usuário
- **Privacy**: Dados de scan nunca saem da máquina local
- **Dependencies**: GitPython para acesso ao histórico de commits

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Entropia de Shannon como sinal secundário de secrets | Complementa regex para detectar tokens não padronizados | — Pending |
| Light glassmorphism em vez de dark | Preferência visual do usuário | — Pending |
| Dual entry point CLI + Web UI | Flexibilidade: scan rápido via terminal ou exploração via browser | — Pending |
| vaultscan.yml para configuração | Permite customizar regras sem alterar código | — Pending |

## Evolution

Este documento evolui a cada transição de fase e milestone.

**Após cada fase** (via `/gsd-transition`):
1. Requisitos invalidados? → Mover para Out of Scope com motivo
2. Requisitos validados? → Mover para Validated com referência da fase
3. Novos requisitos? → Adicionar em Active
4. Decisões a registrar? → Adicionar em Key Decisions
5. "What This Is" ainda preciso? → Atualizar se necessário

**Após cada milestone** (via `/gsd-complete-milestone`):
1. Revisão completa de todas as seções
2. Core Value ainda é a prioridade certa?
3. Auditoria de Out of Scope — razões ainda válidas?
4. Atualizar Context com estado atual

---
*Last updated: 2026-06-11 após inicialização*
