<div align="center">

<!-- sync: README.md@afb44662ecea | checar: python tools/readme_check.py -->
🌐 [Português](README.md) · **English** · [Español](README.es.md)

# 🔷 CL Agents - BlueShift IA Platform

**Your own on-premise Artificial Intelligence platform — 100% Python, Flask standalone.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-Commercial-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docker.com)

**On-premise deployment · Data 100% at the client · Hybrid models (local/external) · Agents per area · Annual license**

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Getting Started](#-getting-started)
- [CLI Commands](#-cli-commands)
- [Local AI Models](#-local-ai-models)
- [Docker](#-docker)
- [Installation without Docker (bare Linux)](#-installation-without-docker-bare-linux)
- [Project Structure](#-project-structure)
- [Technology Stack](#-technology-stack)
- [Recommended Hardware](#-recommended-hardware)
- [Documentation](#-documentation)
- [License](#-license)

---

## 🚀 Overview

**BlueShift IA Platform** is an artificial intelligence platform designed to be installed **inside the client's infrastructure** — datacenter, dedicated server or private cloud. Unlike SaaS, where data leaves the company, here **everything stays inside the client's environment**: data, agents, user memory and history.

### 🎯 Differentiators

| Feature | BlueShift |
|:---------------|:----------|
| **Data** | 100% on-premise — never leaves the client |
| **Models** | Hybrid: local (llama.cpp/LM Studio/vLLM/Ollama) or external (OpenRouter/DeepSeek/OpenAI); **API Mode** `openai_chat` or `responses` (external agents, e.g. AIDP `/chat`) |
| **Agents** | Per company area (sales, support, finance, HR, operations) |
| **Memory** | Persistent per user — local index using TF-IDF + cosine (no external vector database) |
| **RAG** | Curated knowledge: CSV/PDF import + manual entry (no auto-saving of conversations since v0.10.14) |
| **Connectors** | Configurable: REST API (with OAuth2/bearer and async job), A2A agents, MCP servers and SQL queries (TLS/wallet) |
| **OpenAI Gateway** | External chats (Open WebUI, LibreChat, apps) over the standard protocol — port 9003 |
| **AI Skills** | Skill generation using the registered model itself |
| **Documentation** | Docs navigable inside the product (search, one page per screen) + AI Help over the same source + API Reference and Changelog |
| **Licensing** | Annual per company (not per token) |
| **Stack** | Pure Python, Flask, SQLite — no heavy dependencies |

---

## 🏗️ Architecture

```
                    ┌─────────────────────┐
                    │   CLI (blueshift)    │
                    │  init · portal ·     │
                    │  mcp · gateway       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  🌐 PORTAL (Flask)   │
                    │  create_app() :8080  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  🔀 GATEWAY         │
                    │  /v1/chat/completions│
                    │  :9003 (OpenAI)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  💬 EXTERNAL CHATS  │
                    │  Open WebUI, apps   │
                    └────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌──────────┐         ┌──────────┐         ┌──────────┐
   │   AUTH   │         │  VIEWS   │         │   SSO    │
   │  auth.py │         │ views.py │         │  sso.py  │
   │   RBAC   │         │          │         │  OIDC    │
   └────┬─────┘         └────┬─────┘         └────┬─────┘
        │                   │                    │
        └───────────┬───────┴────────┬───────────┘
                    ▼                ▼
             ┌──────────┐     ┌──────────┐
             │  DB      │     │TEMPLATES │
             │  db.py   │     │templates │
             │ (SQLite) │     │   .py    │
             └────┬─────┘     └──────────┘
                  │
        ┌─────────┼──────────┐
        ▼         ▼          ▼
 ┌──────────┐ ┌──────┐ ┌──────────┐
 │  MEMORY  │ │ LLM  │ │  AGENT   │
 │ memory.py│ │client│ │ agente.py│
 │ (TF-IDF) │ │ .py  │ │Final Orq.│
 └──────────┘ └──────┘ └─────┬────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  CONNECTOR     │
                    │  PACK          │
                    │  registry.py   │
                    └───┬────┬────┬──┘
                        │    │    │
                 ┌──────┘    │    └──────┐
                 ▼           ▼           ▼
           ┌─────────┐ ┌────────┐ ┌────────┐
           │ 🌐 API  │ │ 🔌 MCP │ │ 🗄️ SQL │
           │ urllib  │ │ stdio  │ │psycopg │
           │ REST    │ │ JSON-  │ │SELECT  │
           │         │ │ RPC    │ │        │
           └─────────┘ └────────┘ └────────┘
```

### Agent Execution Flow

```
1   User asks
    │
2   ▼
    Area connectors  →  SQL / REST API / A2A / MCP
    │   Parameters (id_cliente, email, dates) extracted from the question
    │   * Placeholder {id_cliente} replaced by the extracted values
    │
    ▼
3   RAG (TF-IDF)  ← always searches, top_k=2 if connectors ok, 4 if empty
    │   * Indexed skills can also be found here
    │
    ▼
4   LLM + Skills + Data + Context  →  Answer (JSON)
    │   * System data = PRIMARY SOURCE
    │   * RAG context = SECONDARY SOURCE
    │   * Main model + automatic fallback
    │
    ▼ (post-answer)
5   Post-answer  →  Writes question + answer to history (conversation memory)
    │   Knowledge base: import/manual entry only (no auto-feed — v0.10.14)
    │
    ▼
6   Webhook (optional)  →  POST answer to an external URL (with 3x retry)
```

---

## ✨ Features

### 🖥️ Client Portal

| Screen | Description | Access |
|:-----|:----------|:-------|
| **Monitor (Monitorar)** | Health dashboard: clients, agents, models, tokens, connectors | Login |
| **Workspace (Workspace)** | Panel per department with the area's agents and documents; cards with **tokens per agent** (1d/7d/30d/90d) | Login |
| **Clients (Clientes)** | Manage and register clients | Admin |
| **Users (Usuários)** | User CRUD with roles (admin/gestor/usuario/sistema) and area | Admin |
| **Areas (Áreas)** | Department registration (database; env `BLUESHIFT_AREAS` is initial seed only) | Admin |
| **Agents (Agentes)** | Agent Factory: build an agent with model + skills + connectors | Admin |
| **Skills** | Skill catalog per area (SKILL.md) | Login |
| **Memory (Memória)** | Persistent memory per user (local vector database) | Login |
| **Knowledge (Conhecimento)** | RAG knowledge base (manual, policy, contracts + CSV + PDF) | Login |
| **Docs** | Full documentation (`docs/` folder) in the side menu — same pages as the AI Help popup; writing convention in `docs/README.md` | Login |
| AI Models (Modelos IA) | Registration of OpenAI-compatible LLMs (local and external) | Admin |
| **Connectors (Conectores)** | Registration of external sources (API, A2A, MCP, SQL) + OAuth2/bearer authentication, SSL/wallet, job polling + purpose (LGPD Art. 26) | Admin |
| **Channels (Canais)** | Integration API with token + outbound webhook | Admin |
| **Gateway** | Activation of the OpenAI-compatible gateway (channel + streaming/complete mode + context limits) | Admin |
| **LGPD** | Compliance on output: anonymize LLM/RAG, privacy notice, purpose per connector, log retention | Admin |
| **Token Usage (Uso de Tokens)** | Consumption analysis per client/model/origin | Admin |
| **Observability (Observabilidade)** | AI dashboard: KPI, drift, costs, feedback, alerts | Admin |
| **A/B Test (Teste A/B)** | Re-runs feedback questions against another model and compares the results with a judge model | Admin/Gestor |
| **Audit (Auditoria)** | LGPD traceability + 🔍 Step-by-step trace | Admin |
| **Cold Archive (Arquivo Morto)** | Sealed database snapshot + manual cutoff (max. D-1) — controls growth without losing history (details in [Cleanup and cold archive](#cleanup-and-cold-archive)) | Admin |
| **Fine-Tuning** | Documentation about formats (GGUF/MLX), hardware and step by step | Login |
| **SSO (OIDC)** | Federated login (Azure AD, Okta, Keycloak, Google) | Admin |
| **Updates (Atualizações)** | Update via Git (tags) — repo version + rebuild with data preserved | Admin |

### 🤖 Agents (Agent Factory)

- **Main model + automatic fallback** — if the main endpoint fails, it tries the secondary one
- **Catalog skills** — reusable skills per area
- **Area connectors with intelligent ROUTING** — a short AI pass decides
  which connector is relevant to each question (or none): a
  norm/policy question is answered with the Knowledge (Conhecimento) Base alone; a question that mentions
  a connector (e.g. "CEP") runs only that one. Configurable via
   `BLUESHIFT_ROUTER_MODEL` — use a **small, smart and fast** model
   (instruct, never reasoning); validated in production: `qwen3-4b-instruct-2507`
   (another example: `hermes-3-llama-3.1-8b`).
   The same model handles 4 internal tasks (choosing connectors, extracting
   parameters, the chart spec and the Smart Query (Consulta inteligente) SELECT)
- **AI parameter extraction** — the AI extracts the keys from the question in
  natural language ("customer id equals 58" → `customer_id='58'`), for
  all connector types (API/MCP/SQL) + anti-hallucination: with no data,
  the agent says "não encontrei" instead of making it up
- **Dynamic context** — RAG (memory + knowledge) + connector data injected into the prompt
- **Real-time test** — test screen with RAG + real LLM

### 🔌 External Connectors

Connectors are data sources configurable per **area** (sales, support, etc.):

| Type | Description | Example |
|:-----|:----------|:--------|
| 🌐 **REST API** | HTTP call via `urllib`, with authentication (bearer/OAuth2 client_credentials), configurable timeout, **async job polling** and response mapping | `GET https://api.externa.com/dados` |
| 🤝 **A2A** | Remote agent on the Agent2Agent protocol (e.g. Oracle Autonomous/AIDP `/a2a`) | `message/send` + agent card |
| 🔌 **MCP** | MCP server via stdio (local) or SSE (remote, JSON-RPC 2.0) | `python mcp_server.py` / SSE URL + tool call |
| 🗄️ **SQL** | PostgreSQL, MySQL, SQL Server, **Oracle** via `oracledb`, with SSL mode and wallet (Autonomous) | `SELECT * FROM vw_clientes WHERE id = %s` |

The parameters (`{id_cliente}`, `{email}`, `{data}`, `{pergunta}`) are extracted automatically from the user's question. Detailed configuration of each type: `docs/04-09-conectores.md`.

**Smart Query (Consulta inteligente) (SQL):** when the fixed query comes back empty and the question asks for
analysis ("who rented the most and the least", "how many per category"), the agent builds the
SELECT itself from the source's **real schema** (tables/views + columns),
generic per driver (MySQL/PostgreSQL/SQL Server/Oracle), with security
validation (read-only SELECT + LIMIT) and a per-connector checkbox on the screen.

**Charts:** chart requests (pie/bar/line) generate the image
automatically from the connector data (embedded matplotlib), attached
to the answer — it renders in Open WebUI and in the portal, with labels masked by
LGPD.

### 🧠 Knowledge Base (RAG)

| Mechanism | Description |
|:----------|:----------|
| **Manual** | Add documents via a form in the portal |
| **CSV Import** | Upload of `.csv` with columns `titulo,conteudo,fonte,area` |
| **PDF Import** | Upload of `.pdf` with automatic text extraction (PyMuPDF) |
| **No auto-save** | RAG does not receive automatic writes of conversations/connectors (since v0.10.14) — it grows through registration, CSV/PDF and skills |
| **Skills in RAG** | Catalog skills can be indexed into the knowledge base |
| **Monitor** | KPI cards: total docs, areas, accesses, average size |
| **Export Fine-Tuning** | Exports RAG as JSONL (format `messages`) for MLX, HuggingFace, Unsloth, OpenAI |

### ⚙️ Skills

- **Catalog per area**: reusable skills (sales, support, finance, HR, operations)
- **Persistent editing**: edited skills are saved in the database (Docker volume),
  surviving container rebuilds. The SKILL.md file works as a fallback.
- **AI generation**: create the skill content by describing in Portuguese what the agent should do
- **RAG indexing**: skills can be imported into the knowledge base (searchable via TF-IDF)

### 🔐 Security and Access Control

- **Hashed passwords**: scrypt (16-byte salt, N=16384) — no plaintext in the database; **minimum 8 characters** (user create/edit and initial setup)
- **RBAC**: hierarchy `admin > gestor > usuario > sistema`
- **Rate limit**: login 5 attempts/IP/min (15 min lockout) + API 100 req/token/min
- **Failed login**: recorded in the audit trail (attempted user + IP) — detects brute force
- **CSRF**: token in every portal form
- **XSS**: escaping (html.escape) on every data rendering — names, descriptions, RAG context and connector results
- **Session hardening**: HttpOnly cookie + SameSite=Lax + 30 min timeout + Secure (HTTPS)
- **SQL injection**: column whitelist + parameterized queries
- **Path traversal**: skill names validated with `isidentifier()`
- **Webhook URL (anti-SSRF)**: validation with `ipaddress` (blocks private, CGNAT, link-local/cloud metadata, loopback, internal IPv6) + DNS resolution (DNS rebinding); applies on create, edit and at send time
- **HTTP headers**: X-Content-Type-Options, X-Frame-Options: DENY, Referrer-Policy and Content-Security-Policy on every response
- **Model API Key**: never rendered in the HTML (masked when editing)
- **SSO (OIDC)**: optional federated login (keeps local login)
- **CORS**: headers configured (Allow-Origin: \\*) — **only on the `/portal/api/*` routes** (web pages do not need them)
- **Health check**: public route `/portal/healthz` for load balancer / HEALTHCHECK
- **LGPD audit trail**: every sensitive action is recorded
- **Channels with token**: each integration channel has its own key (regenerable)
- **Debug mode off**: no tracebacks in production
- **Isolation**: data separated by `cliente_id` + area

### 🔒 LGPD Compliance

| Feature | Articles | Description |
|:---------------|:--------|:----------|
| **Anonymize LLM answer** | 12, 13 | Masks CPF, CNPJ, email, phone, name and address in the agent's answer (chat, API, webhook) |
| **Anonymize RAG export** | 12, 13 | Personal data masked in the JSONL export of the knowledge base |
| **Privacy notice on login** | 9, 10 | Customizable text shown in the footer of the login screen |
| **Purpose of processing** | 26 | Required field per connector when enabled |
| **Automatic log retention** | 15 | Periodic cleanup of audit (90d), tracing/uso_tokens (180d) and memories (365d) via a daemon thread — or **Cold Archive (Arquivo Morto)** (snapshot + manual cutoff, without losing history) |
| **A/B test between models** | — | Re-runs feedback questions with another model and evaluates them via a judge model |

Configuration under **Registrations (Cadastros) > 🛡️ LGPD** and **A/B Test (Teste A/B)** in the main menu.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Git
- Docker (optional, for container deployment)

### Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/cvillada/blueshift_ia_platform.git
cd blueshift_ia_platform

# 2. Create and activate the virtual environment
python3 -m venv bp-venv && source bp-venv/bin/activate

# 3. Install the platform
pip install --upgrade pip
pip install -e .

# 4. Test the installation
blueshift --help
# Local dev (BLUESHIFT_DEV=1): any BS-DEV-* key activates. Production:
# the key is issued by BlueShift upon company registration
# (request it through the official channel — see the License section).
blueshift activate BS-DEV-local

# 5. Start the Portal
blueshift portal --port 8080
# Open: http://localhost:8080/portal
# Development mode (BLUESHIFT_SEED_DEMO=1): Login: admin / admin123
# End client (BLUESHIFT_SEED_DEMO=0): see "First installation" below
```

### First installation (end client)

The platform starts with a **clean database**: no company, no user,
no demo data. Whoever installs controls this through the
`BLUESHIFT_SEED_DEMO` variable (default `1` for development — it creates
XPTO sample data; set it to `0` so the end client receives nothing).

With a clean database, the first access works like this:

1. Open `http://localhost:8080/portal` (or the port/URL of the deployment)
2. The login screen becomes an **Initial setup (Configuração inicial)** form
3. The client registers:
   - their own **company** (name, code, legal name, e-mail)
   - the **initial administrator** (name, login, password — minimum 6 characters)
4. On save, the portal logs in automatically and lands on the Monitor (Monitorar)

After that, the Initial setup form **disappears forever** —
nobody can reopen the setup again (there is only one admin). Normal login
applies again.

> ⚠️ For security, in end-client installations always use
> `BLUESHIFT_SEED_DEMO=0` and rotate the admin password periodically.

```bash
# Example: start a clean portal for a client
BLUESHIFT_SEED_DEMO=0 blueshift portal --port 8080
```

### Environment variables

The installation configuration lives in environment variables. The file
[`.env.example`](.env.example) brings all of them with comments — copy it to
`.env` before installing. The `docker-compose.yml` uses the same variables
(with defaults), and the portal's **Updates (Atualizações)** screen shows the main ones
("Environment configuration" card).

| Variable | Default | Effect |
|:---------|:-------|:-------|
| `BLUESHIFT_LICENSE` | empty | **Activation key issued by BlueShift** — obtained at company registration (see the [License](#-license) section); empty = platform not activated. `BS-DEV-*` is valid only in dev (`BLUESHIFT_DEV=1`) |
| `BLUESHIFT_AREAS` | vendas,suporte,financeiro,rh,operacoes | **Initial seed** of the areas — afterwards the Registrations (Cadastros) → Areas (Áreas) screen takes over (database) |
| `BLUESHIFT_SEED_DEMO` | 1 | `1` = XPTO demo data (dev); `0` = clean database (initial setup) |
| `BLUESHIFT_ROUTER_MODEL` | empty | **ROUTING** model — **ID or NAME** (the name appears on the AI Models (Modelos IA) screen); empty = the agent's main model (not recommended). Rule: **small, smart and fast** (instruct, never reasoning). Examples: `qwen3-4b-instruct-2507` (validated) and `hermes-3-llama-3.1-8b` |
| `BLUESHIFT_LICENSE_URL` | localhost:9000 | License validation URL — **production/client: point it to the BlueShift License Server** (the same base as the request page, e.g. `<url>/v1/validate`); default = local mock (dev only) |
| `BLUESHIFT_REPO_DIR` | /opt/blueshift/repo | Git clone of the repo (Update via Git — Updates (Atualizações) screen) |
| `GATEWAY_PORT` | 9003 | Published port of the OpenAI-compatible Gateway |
| `GATEWAY_PUBLIC_URL` | empty | Public gateway URL shown on the screen (e.g. `http://192.168.0.10:9003/v1`); without it, the request host is used |
| `BLUESHIFT_DEV` | 0 | **Production/client = 0** (the Updates (Atualizações) screen applies the update for real); **dev = 1** (dry-run + BS-DEV-* license) |
| `TZ` | UTC | Timezone (use `America/Sao_Paulo`) |

Without Docker (direct CLI), load the `.env` and start it:

```bash
cd blueshift_ia_platform
set -a; . ./.env; set +a
blueshift portal --port 8080
```

---

## 📟 CLI Commands

| Command | Description |
|:--------|:----------|
| `blueshift init <cliente>` | Creates the client profile |
| `blueshift activate <chave>` | Validates the license key |
| `blueshift status` | Shows the container state |
| `blueshift update` | Checks for approved updates |
| `blueshift portal [--port 8080]` | Starts the Client Portal |
| `blueshift mcp` | Starts the MCP stdio server (connectors) |
| `blueshift gateway [--port 9003]` | Starts the OpenAI-compatible Gateway (external chats) |

### Channel API Usage Example

```bash
curl -X POST http://localhost:8080/portal/api/v1/agente \
  -H "Authorization: Bearer bs_chan_seu_token_aqui" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual o histórico do cliente C001?"}'
```

Response:
```json
{
  "ok": true,
  "resposta": "O cliente C001 possui 3 interações...",
  "pergunta": "Qual o histórico do cliente C001?",
  "agente": "Agente Vendas",
  "modelo": "qwen3-4b-instruct-2507",
  "feedback_url": "http://localhost:8080/portal/api/v1/feedback/123",
  "erro": null,
  "tokens": {"total_tokens": 345, "prompt_tokens": 200, "completion_tokens": 145},
  "tempo_ms": 2340
}
```

### Answer Feedback (optional)

The API answer includes `feedback_url` — a URL to record whether the answer was useful.

**Endpoint:** `POST /portal/api/v1/feedback/<trace_id>`

**Body (JSON):**
```json
{"util": true}   // or false
```

**Example:**
```bash
curl -X POST http://localhost:8080/portal/api/v1/feedback/123 \
  -H "Authorization: Bearer <TOKEN_DO_CANAL>" \
  -H "Content-Type: application/json" \
  -d '{"util": true}'
```

**Response:**
```json
{"ok": true, "feedback_id": 1}
```

> The `tipo` field in the database will be `"api"` (via curl) or `"manual"` (via the 👍/👎 buttons on the Agents (Agentes) → Testar screen). Its use is **optional** — the API works without feedback. The data appears on the Observability (Observabilidade) Dashboard.

### Scheduling Metric Aggregation

The observability dashboard consolidates data from the `tracing` and `feedback` tables into the `metricas_diarias` table. Aggregation is done manually with the **"Process metrics" (Processar métricas)** button on the dashboard itself.

To automate it (e.g. run every day at 2 a.m.), add this to the server's crontab:

```cron
0 2 * * * cd /opt/blueshift && python3 -c "from blueshift_layer.portal import db; db.agregar_metricas_diarias()"
```

Or inside Docker:

```bash
docker exec blueshift-platform python3 -c "from blueshift_layer.portal import db; db.agregar_metricas_diarias()"
```

---

## 🤖 Local AI Models

BlueShift is 100% compatible with any **OpenAI-compatible** server. You can use local models (recommended for on-premise) or external ones.

### Local Server Options

| Server | Description | Default port |
|:---------|:----------|:-------------|
| **[LM Studio](https://lmstudio.ai)** | GUI to download and run GGUF models | `http://127.0.0.1:1234` |
| **[Ollama](https://ollama.com)** | Simple CLI to run local models | `http://127.0.0.1:11434` |
| **[llama.cpp](https://github.com/ggerganov/llama.cpp)** | Lightweight C++ engine, via `llama-server` | `http://127.0.0.1:8080` |
| **[vLLM](https://github.com/vllm-project/vllm)** | High throughput, ideal for GPU | `http://127.0.0.1:8000` |
| **[SGL](https://docs.sglang.io/)** | High throughput, ideal for GPU | `http://127.0.0.1:8000` |

### Setup with LM Studio (recommended for dev)

```bash
# 1. Download LM Studio from https://lmstudio.ai
# 2. In the "Discover" tab, search for and download a GGUF model

# ROUTING model (recommended, validated in production):
#   Qwen3-4B-Instruct-2507 (Q4, ~2,6 GB)
#   → Search in LM Studio: "qwen3-4b-instruct-2507"
#
# Alternative examples (instruct, NEVER reasoning):
#   - hermes-3-llama-3.1-8b (8B instruct, great at format/JSON)
#   - Qwen2.5-3B-Instruct (middle ground)
#   - Qwen2.5-0.5B-Instruct (modest installation; it does not do the text-to-SQL)
#
# For the MAIN model (the one that writes the answer) use the best you have:
# Llama 3.1 8B Instruct, Qwen 2.5 7B/14B, Mistral, etc.

# 3. In the "Local Server" tab:
#    - Select the downloaded model
#    - Enable "Cross-Origin-Resource-Sharing (CORS)"
#    - Enable "Start Server"
#    - Port: 1234 (default)

# 4. In the BlueShift Portal, go to AI Models (Modelos IA) and register:
#    - Name: qwen3-4b-instruct-2507
#    - Endpoint: http://host.docker.internal:1234 (if you are on Docker)
#               or http://127.0.0.1:1234 (if running locally)
#    - Model: qwen3-4b-instruct-2507 (or the exact name the server expects)
#    - Type: Local
```

> ⚠️ **On Docker:** the container needs to reach LM Studio on the host. Use `host.docker.internal` instead of `127.0.0.1`. On Linux, use `--add-host=host.docker.internal:host-gateway`.

### Setup with Ollama

```bash
# 1. Install Ollama: https://ollama.com
# 2. Download a model:
ollama pull llama3.2:3b
ollama pull phi4:14b
# 3. Start the server (it already starts automatically on macOS):
ollama serve
# 4. In the Portal, register:
#    - Name: llama3.2
#    - Endpoint: http://host.docker.internal:11434
#    - Model: llama3.2:3b
#    - Type: Local
```

### External Models (OpenAI-compatible)

If you prefer to use external APIs instead of local models:

| Provider | Endpoint | API Key |
|:---------|:---------|:--------|
| **DeepSeek** | `https://api.deepseek.com` | ✅ Required |
| **OpenRouter** | `https://openrouter.ai/api/v1` | ✅ Required |
| **OpenAI** | `https://api.openai.com/v1` | ✅ Required |
| **NVIDIA NIM** | `https://integrate.api.nvidia.com/v1` | ✅ Required |

In the Portal, register it as **Type: Hybrid** and fill in the API Key.

---

## 🐳 Docker

### Installation via Installer (recommended)

```bash
cp .env.example .env          # adjust BLUESHIFT_LICENSE
./install.sh                  # docker compose up -d --build
```

Open `http://localhost:8080/portal`.

> **Client installation (clean database):** with `BLUESHIFT_SEED_DEMO=0` the first
> entry opens the **Initial setup (Configuração inicial)** screen, which creates the company and the first
> admin (there is no demo data). The `admin` / `admin123` is only the
> demo user of dev mode (`BLUESHIFT_SEED_DEMO=1`).

> **AI models are not bundled.** After starting the platform, register the models on the **AI Models (Modelos IA)** screen — local (vLLM/LM Studio/Ollama) or external (DeepSeek/OpenRouter/OpenAI).
>
> **Custom areas:** register the areas on the **Registrations (Cadastros) → Areas (Áreas)**
> screen (database). The `BLUESHIFT_AREAS` variable in the `docker-compose.yml` serves only
> as the initial seed of the first boot.
>
> **MCP with Node.js:** for local MCP servers that depend on Node.js (npm/npx), the container already includes Node 20 and npm.
>
> **Update via Git:** the compose file mounts the repository (default: the directory
> itself; production: a clone at `/opt/blueshift/repo`) and the host's `docker.sock`
> into the portal. The **Updates (Atualizações)** screen shows the repo version and
> applies the new tag with `docker compose up -d --build` (data preserved).

### Manual

```bash
# 1. Build the image
docker build -t blueshift/platform -f docker/Dockerfile .

# 2. Create a volume for data persistence
docker volume create blueshift_data

# 3. Start the container with the volume mounted
docker run -d --name blueshift-platform \
  -p 8080:8080 \
  -v blueshift_data:/data/blueshift \
  -e BLUESHIFT_PORTAL_DB=/data/blueshift/portal.db \
  -e BLUESHIFT_LICENSE=SUA-CHAVE-DA-BLUESHIFT \
  blueshift/platform blueshift portal
```

> **Data persistence:** the SQLite database and other data live in the `blueshift_data` volume.
> You can rebuild the container (`docker build` + `docker stop` + `docker rm` + `docker run`)
> and the data (clients, users, agents, connectors, edited skills, RAG documents) is preserved.
> For backup: `docker run --rm -v blueshift_data:/data -v $(pwd):/backup alpine tar czf /backup/blueshift_backup.tar.gz -C /data .`

> **The compose file starts TWO containers:** `blueshift-platform` (portal, :8090→8080)
> and `blueshift-gateway` (OpenAI-compatible gateway, :9003) — the gateway
> depends on the portal and reads the configuration from the same `blueshift-data` volume.

### 🔀 OpenAI-compatible Gateway (external chats)

The gateway exposes the standard OpenAI protocol (`/v1/chat/completions` +
`/v1/models`) to external chats — **Open WebUI**, LibreChat, custom
apps, OpenAI SDK/LangChain — and forwards to the agent through the Channel
API (token `bs_chan_*`).

To connect **Open WebUI** (container on the same machine):

```bash
# 1. In the portal: Registrations (Cadastros) → Channels (Canais) → create the channel (e.g. "API Vendas")
#    pointing to the desired agent (the bs_chan_* token is the API Key)
# 2. In the portal: Registrations (Cadastros) → Gateway → "Activate gateway" ("Ativar gateway") (channel + mode:
#    Full JSON response or SSE Streaming) — the gateway must be
#    ACTIVE to answer
# 3. In Open WebUI (Admin → Connections → OpenAI API):
#      API URL: http://host.docker.internal:9003/v1
#      API Key: the channel token (any active gateway authenticates)
#      Model:  agente:Agente Vendas  (the agent name)
```

- The `model` chooses the agent; the token only validates authentication (any
  channel key with an active gateway works — Open WebUI uses one
  connection = one key for several models)
- **Conversation context:** the gateway forwards the previous messages
  (limits configurable on the screen: max. messages + token budget);
  memory/RAG always store the last real question/answer
- Chat from another machine on the network: `http://IP_DO_SERVIDOR:9003/v1`
- Without Docker: `set -a; . ./.env; set +a` + `blueshift gateway --port 9003`

---

## 🖥️ Installation without Docker (bare Linux)

The product runs **100% without Docker**: it is pure Python (Flask standalone). For
clients who prefer to run it directly on a Linux server (no containers):

```bash
# 1. Clone the repo (the SAME clone used by Update)
sudo mkdir -p /opt/blueshift/repo && sudo chown $USER /opt/blueshift/repo
git clone https://github.com/cvillada/blueshift_ia_platform.git /opt/blueshift/repo
cd /opt/blueshift/repo

# 2. Virtual environment + dependencies
python3 -m venv .venv
.venv/bin/pip install -e .

# 3. systemd service (/etc/systemd/system/blueshift.service)
#    [Unit]
#    Description=CL Agents — BlueShift IA Platform
#    After=network.target
#
#    [Service]
#    WorkingDirectory=/opt/blueshift/repo
#    Environment=BLUESHIFT_PORTAL_DB=/opt/blueshift/data/portal.db
#    Environment=BLUESHIFT_LICENSE=SUA-CHAVE
#    Environment=BLUESHIFT_LICENSE_URL=<url-da-pagina-de-solicitacao>/v1/validate
#    Environment=BLUESHIFT_REPO_DIR=/opt/blueshift/repo
#    ExecStart=/opt/blueshift/repo/.venv/bin/blueshift portal --port 8080
#    Restart=always
#
#    [Install]
#    WantedBy=multi-user.target

sudo systemctl daemon-reload && sudo systemctl enable --now blueshift
# Open: http://<servidor>:8080/portal
```

**Button-based update (Updates (Atualizações) screen) works without Docker:** the portal
detects that it runs outside a container (`/.dockerenv` absent) and the
**Apply** button runs `git fetch + checkout` of the tag in the repo and restarts the service
via `systemctl restart blueshift` — with the same "downloaded but not
applied" warning and a log at `/opt/blueshift/update.log`.

Variables specific to bare mode:
- `BLUESHIFT_REPO_DIR=/opt/blueshift/repo` — repo clone (this is already the default)
- `BLUESHIFT_SERVICE_NAME=blueshift` — systemd service name (default
  `blueshift`); if your service has another name, set it here

> **Note:** without systemd on the host, the button does the checkout and the log guides the
> manual restart — the screen shows "downloaded but NOT applied" until the service
> restarts. Docker remains the recommended delivery mode; bare is
> for Linux servers without containers.

## 📁 Project Structure

```
blueshift_layer/                    ← Main platform code
├── cli.py                          ← CLI entry point (blueshift)
├── gateway.py                      ← OpenAI-compatible Gateway (:9003, /v1)
├── license_client.py               ← License key validation
├── license_server_mock.py          ← Mock License Server (Flask, :9000)
├── installer.py                    ← Creates the client profile
├── update_client.py                ← Update via Git (tags) — version + apply
├── update_server.py                ← Legacy mock Update Channel (Flask, :9001)
├── config/
│   └── default_config.yaml         ← Default container config
├── portal/                         ← 🌐 Client Portal (Flask)
│   ├── __init__.py                 ← create_app() factory
│   ├── db.py                       ← SQLite (single point of data)
│   ├── views.py                    ← Routes and screens
│   ├── auth.py                     ← Authentication + RBAC
│   ├── templates.py                ← HTML/CSS/JS layout
│   ├── memory.py                   ← RAG (TF-IDF + cosine, pure Python)
│   ├── llm_client.py               ← OpenAI-compatible LLM client (urllib)
│   ├── agente.py                   ← Agent orchestrator
│   ├── mask.py                     ← LGPD masking (CPF, email, name, etc.)
│   └── sso.py                      ← OIDC federated login
├── connector_pack/                 ← 🔌 External connectors
│   ├── registry.py                 ← API/MCP/SQL engine
│   ├── mcp_server.py               ← MCP stdio (JSON-RPC 2.0)
│   ├── mcp_erp.py                  ← ERP (Postgres)
│   ├── mcp_crm.py                  ← CRM (sample data)
│   └── mcp_rh.py                   ← HR (sample data)
└── template_skills/                ← ⚙️ Skills per area (fallback; saved in the database for persistence)
    ├── vendas/SKILL.md
    ├── suporte/SKILL.md
    ├── financeiro/SKILL.md
    ├── rh/SKILL.md
    └── operacoes/SKILL.md

docs/                               ← 📚 Documentation (navigable pages — Docs + AI Help; EN translations in `docs/en/`: pages 00, 01, 02 and 12)
├── README.md                       ← Writing convention (where to document each change)
├── 00-…13-*.md                     ← Content (one page per topic/screen) + API Reference + Changelog
├── _TEMPLATE.md                    ← Template for a new page
├── _mapa_apelidos.json             ← Technical field ↔ screen label (automatic check)
├── _pendentes.json                 ← Known check debt
└── _publico.txt                    ← Curation of the internal documentation site

tools/
├── doc_check.py                    ← Doc × code gate (routes, fields, variables, tables, versions)
└── docs_site.py                    ← Generates the documentation site for internal use (not published)

docker/
├── Dockerfile                      ← Container image
└── entrypoint.sh                   ← Starts License + Update + Portal
```

---

## 🛠️ Technology Stack

| Category | Technology |
|:----------|:-----------|
| **Language** | Python 3.11+ |
| **Framework** | Flask 3.1 |
| **Database** | SQLite (on-premise, no network dependency) |
| **LLM Client** | pure urllib (OpenAI-compatible) |
| **RAG** | TF-IDF + cosine similarity (pure Python, no numpy) |
| **PDF Extraction** | PyMuPDF (text extraction for RAG) |
| **MCP** | JSON-RPC 2.0 over stdio (pure Python) |
| **SSO** | OIDC via urllib + HMAC (no OAuth libs) |
| **Authentication** | local login/password + federated SSO |
| **Container** | Docker (Python 3.11-slim) |
| **Postgres** | Optional (via `psycopg` for the ERP connector) |

### Python Dependencies

```
flask>=3.1          # Web framework
requests>=2.31      # HTTP client (license_client)
pyyaml>=6.0         # YAML config
mcp>=1.0            # FastMCP (connectors)
psycopg[binary]>=3.1 # Postgres (ERP connector, optional)
PyMuPDF>=1.28       # PDF text extraction (RAG)
```

---

## 💻 Recommended Hardware

### Platform bottlenecks

| Component | Real limit | Cause |
|:-----------|:------------|:------|
| **Local LLM** | 2-60s per call | Model/hardware — **the main bottleneck** (GPU via vLLM solves it) |
| **SQLite (WAL)** | 1 write at a time; concurrent reads allowed | Single-writer — irrelevant in practice: ~3 tiny writes per agent call |
| **Portal (Werkzeug, threaded)** | Concurrent requests (LLM I/O releases the GIL) | Dev server; for extreme load, waitress/gunicorn (see Tier 3) |
| **TF-IDF** (memory) | ~100k docs / ~500MB RAM | Index loaded in RAM |
| **Vector search** | O(n) = 50-200ms for 10k docs | Brute force (cosine), no index |

### Tiers

The tiers are **guidelines for sizing the client installation**. "Concurrent accesses" is the **KV cache** capacity of the LLM server (vLLM) with the indicated model in Q4 and a reference average context — anyone over the limit **enters vLLM's native queue** (waits, does not fail). Formula and complete table in the [Concurrent access capacity](#concurrent-access-capacity-kv-cache) section.

#### 🟢 TIER 1 — Small (up to 10 users, 1k docs, 500 queries/day)

| Resource | Specification |
|:--------|:--------------|
| **CPU** | 2 vCPU |
| **RAM** | 8 GB |
| **Disk** | 50 GB SSD |
| **OS** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | No (optional: RTX 4060 8GB) |
| **LLM model** | up to 3B params (Q4, ~2GB RAM, CPU) |
| **Concurrent accesses** | 1-2 (CPU; with an 8GB GPU: 1-2 @ 8K ctx) |
| **Records/day** | ~1,5k (3 per query) — SQLite WAL + LGPD retention: plenty of headroom |
| **Estimated cost** | ~R$ 80/month (VPS) |

#### 🟡 TIER 2 — Medium (up to 50 users, 10k docs, 5k queries/day)

| Resource | Specification |
|:--------|:--------------|
| **CPU** | 4 vCPU |
| **RAM** | 16 GB |
| **Disk** | 200 GB SSD |
| **OS** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | RTX 4060 8GB (optional, for vLLM) |
| **LLM model** | up to 8B params (Q4_K_M, ~5GB VRAM) |
| **Concurrent accesses** | ~1-2 @ 8K ctx (8B Q4 on an 8GB GPU); CPU: 1 |
| **Records/day** | ~15k — SQLite WAL + indexes + retention: headroom |
| **Estimated cost** | ~R$ 250/month (VPS) |

#### 🟠 TIER 3 — Large (up to 200 users, 50k docs, 20k queries/day)

| Resource | Specification |
|:--------|:--------------|
| **CPU** | 8 vCPU |
| **RAM** | 32 GB |
| **Disk** | 500 GB SSD NVMe |
| **OS** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | NVIDIA RTX 4080/3090 24GB (recommended, for vLLM) |
| **LLM model** | up to 14B params (Q4, ~9GB VRAM) |
| **Concurrent accesses** | ~3 @ 32K ctx (8B Q4); ~1 @ 32K (14B Q4) — the excess goes to the vLLM queue |
| **Records/day** | ~60k — SQLite WAL + indexes + retention: it holds |
| **Estimated cost** | ~R$ 800/month (dedicated server) |

**What needs to change in this tier:**
- **Nothing in the platform** — the jump is moving the model from CPU to **vLLM on GPU** (24GB+). SQLite already runs in WAL with retention indexes.
- Optional: a **waitress/gunicorn** server for HTTP throughput above the Werkzeug dev server (1 threaded process).

#### 🔴 TIER 4 — Enterprise (500+ users, 200k docs, 100k queries/day)

| Resource | Specification |
|:--------|:--------------|
| **CPU** | 16 vCPU |
| **RAM** | 64 GB |
| **Disk** | 1 TB NVMe |
| **OS** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | NVIDIA RTX Pro 6000 128GB (or 2x 24GB) |
| **LLM model** | up to 70B params (Q4, ~41GB VRAM, via vLLM) |
| **Concurrent accesses** | ~25 @ 32K (8B Q4) / ~6 @ 32K (70B Q4); ~6 @ 128K (8B) — the excess goes to the vLLM queue |
| **Records/day** | ~300k — ceiling of the current design: ~18M indexed tracing rows (180d); SQLite WAL holds |
| **Estimated cost** | ~R$ 3.000+/month (dedicated server) |

**What needs to change in this tier:**
- **The only scenario that justifies PostgreSQL**: 2+ portal replicas writing to the same database (multi-writer). The current design (1 portal + stateless read gateway) does not cross that limit — if the client's IT requires it, it is a scoped migration study, not a rewrite of the data layer.
- An async task queue (Celery/RQ) only if there is high-volume outbound webhook traffic with persistent retry — today delivery is synchronous with retry (3x, backoff) and the lightweight alternative is a background thread.

### Summary

| Tier | CPU | RAM | Disk | GPU (VRAM) | Concurrent accesses* | Users | Records/day | Cost/month |
|:----:|:---:|:---:|:-----:|:----------:|:--------------------:|:--------:|:-------------:|:---------:|
| 🟢 1 | 2 vCPU | 8 GB | 50 GB | No | 1-2 (CPU) | 10 | ~1,5k | ~R$ 80 |
| 🟡 2 | 4 vCPU | 16 GB | 200 GB | RTX 4060 (8GB, opt.) | 1-2 @ 8K | 50 | ~15k | ~R$ 250 |
| 🟠 3 | 8 vCPU | 32 GB | 500 GB | RTX 4080/3090 (24GB) | ~3 @ 32K | 200 | ~60k | ~R$ 800 |
| 🔴 4 | 16 vCPU | 64 GB | 1 TB | RTX Pro 6000 (128GB) | ~25 @ 32K | 500+ | ~300k | ~R$ 3.000+ |

\* Concurrent accesses = requests the GPU serves **at the same time** (KV cache, 8B Q4 model, fp16). The excess **waits in the vLLM queue** — it does not fail.

> **Note:** the biggest bottleneck is not the hardware — it is the **local LLM** without a GPU. An 8B model on CPU generates 5-15 tok/s. A 300-token answer takes 20-60 seconds. For production with many users, **a GPU is essential** (via vLLM).

### Concurrent access capacity (KV cache)

Every active conversation consumes **KV cache** memory on the GPU. The math (fp16):

```
KV per token = 2 × layers × KV heads × head_dim × 2 bytes
Slots        = (VRAM − weights − overhead) / (KV per token × average context)
```

Context cost per model (fp16):

| Model | KV/token | 8K ctx | 32K ctx | 128K ctx |
|:-------|:---------|:-------|:--------|:---------|
| 8B (Llama 3.1) | 128 KB | 1,0 GB | 4,2 GB | 16,8 GB |
| 14B (Qwen 2.5) | 192 KB | 1,5 GB | 6,3 GB | 25,2 GB |
| 32B (Qwen 2.5) | 256 KB | 2,1 GB | 8,4 GB | 33,6 GB |
| 70B (Llama 3.3) | 320 KB | 2,6 GB | 10,5 GB | 42,0 GB |

Concurrent slots per GPU (Q4 model, KV in fp16, ~10% VRAM overhead + 2GB, rounded values):

| GPU (VRAM) | 8B | 14B | 32B | 70B |
|:-----------|:---|:----|:----|:----|
| RTX 4060 (8GB) | 1 @ 8K | — | — | — |
| RTX 4060 Ti (16GB) | 7 @ 8K / 1 @ 32K | 2 @ 8K | — | — |
| RTX 4080/3090 (24GB) | 13 @ 8K / 3 @ 32K | 6 @ 8K / 1 @ 32K | — | — |
| RTX Pro 6000 (128GB) | 103 @ 8K / 25 @ 32K / 6 @ 128K | 66 @ 8K / 16 @ 32K / 4 @ 128K | 44 @ 8K / 11 @ 32K / 2 @ 128K | 27 @ 8K / 6 @ 32K / 1 @ 128K |

Example (RTX Pro 6000 128GB): 100 requests arriving together, 8B Q4 model — ~25 are served in parallel with an average 32K context and ~75 wait in the vLLM queue; with a full 128K context, ~6 are served. vLLM **does not reject** — it queues and serves as slots free up (configurable queue limit).

Multipliers: KV cache in **FP8 doubles the slots**; a 32K context (typical of RAG) yields 4-5x more than a full 128K. A 70B Q4 model **does not fit** in a 24GB GPU — the weights alone use ~41GB.

### Record capacity (SQLite)

Every agent call writes ~3 rows: `tracing` + `uso_tokens` + `auditoria`. With LGPD retention enabled (Settings (Configurações) → LGPD; off by default), the tables are stable:

| Table | Default retention | Tier 4 (100k queries/day) |
|:-------|:----------------|:--------------------------|
| auditoria | 90 days | ~9M rows max |
| tracing | 180 days | ~18M rows max |
| uso_tokens | 180 days (follows tracing) | ~18M rows max |
| metricas_diarias | no retention (daily aggregate) | ~365 rows/year per agent+model |
| memories | 365 days | depending on usage |

SQLite in **WAL** mode with indexes on `criado_em` (tracing/feedback/auditoria) reads and filters that volume without a problem — point lookup + range by date. SQLite's real limit **is not size, it is multi-writer**: 2+ processes writing the same file. The current design (1 portal + stateless read gateway) does not cross that limit. If there are ever 2+ portal replicas, **then** PostgreSQL starts to make sense — a scoped migration study, not a rewrite.

### Cleanup and cold archive

There are two ways to control growth — both manual and with different criteria:

**1. Cold archive (screen Cold Archive (Arquivo Morto), Operation menu — admin only):** generates a sealed snapshot of the database (`data/arquivo_morto/arquivo_morto_<execução>_<corte>.db` — first date = run, second = cutoff) and removes from the hot database the records with `criado_em <= corte`. Maximum cutoff = **yesterday at midnight** (the current day is never affected). The flow asks for confirmation showing the counts before executing — **including confirmation that the physical backup of portal.db was made** (the snapshot does not replace the backup); the copy is made before the DELETE (a failed copy = nothing is deleted). The physical backup of the main database is the client's responsibility (volume).

| Table | Cutoff field | Criteria |
|:-------|:---------------|:---------|
| tracing | criado_em | age (≤ cutoff) |
| uso_tokens | criado_em | age (≤ cutoff) |
| auditoria | criado_em | age (≤ cutoff) |
| memories | criado_em | age (≤ cutoff) |
| feedback | criado_em | age (≤ cutoff) |
| teste_ab | criado_em | age (≤ cutoff) |
| knowledge | acessos / ultimo_acesso | imported source (csv/pdf/...) **and** no recent use (`acessos = 0` or `ultimo_acesso ≤ corte`) — `manual` and `skill` sources (rules) are never affected |

Never included: `metricas_diarias` (perpetual aggregate) and master data (clients, users, agents, models, skills, connectors, channels, areas, api_keys, configs). Every run — success **or failure** — stays in the screen's history (run, cutoff, file, moved) **and in the Audit (Auditoria)** trail (Operation menu, `acao=arquivo_morto`: user, cutoff, file, total moved). A duplicate snapshot on the same day/cutoff is rejected (nothing is overwritten).

**2. Automatic cleanup (LGPD screen):** optional (`retencao_auto`), runs every hour and performs a **physical DELETE** with configurable retentions (audit 90d, tracing/uso_tokens 180d, memories 365d). Off by default — it only activates if the client wants to discard without a snapshot.

---

## 📚 Documentation

The documentation lives in **`docs/`** (one page per topic/screen) and is the **single
source** for three places: the portal's **Docs** menu, the **AI Help (Ajuda IA)** popup and the internal
documentation site.

| Page | Audience | Content |
|:-------|:----------|:---------|
| `docs/en/00-visao-geral.md`, `docs/en/01-arquitetura.md`, `docs/en/02-como-executar.md` (EN) and `docs/00-…03-*.md` (PT) | operator | overview, architecture, how to run, access and roles |
| `docs/04-*.md` | operator | **one page per screen** of the portal (fields, step by step, examples, pitfalls) |
| `docs/05-…07-*.md` | operator/IT | channel API, connectors and the agent/RAG flow |
| `docs/en/12-api-reference.md` (EN) and `docs/12-api-reference.md` (PT) | **client IT** | integration reference: portal API, OpenAI Gateway, authentication, errors and limits |
| `docs/13-changelog.md` | everyone | version history (every release goes to the top) |

**When you change the product, document it in the same commit:**

```bash
python tools/doc_check.py            # fails if any code change is left undocumented
python tools/doc_check.py --lista    # known debt
```

The check compares **routes, form fields, environment variables, database
tables and version tags** against the pages — currently with full coverage. Writing
convention, page template and "where to document each type of change":
**`docs/README.md`**.

**Internal documentation site** (present/print/take offline to a demo):

```bash
./bp-venv/bin/python tools/docs_site.py       # generates dist/docs_site/ (self-contained, with search)
./bp-venv/bin/python tests/test_docs_site.py  # validates curation, links and JS
```

The curation of what goes into the site is explicit in `docs/_publico.txt`. **The site is not
published** — internal use.

The full documentation set lives in `docs/` (Portuguese, single source). EN/ES translations: `docs/en/` and `docs/es/` (pages 00, 01, 02 and 12).

---

## 📄 License

This project is **source-available**: the repository is
public for transparency, auditing and automatic updates of
licensed installations — publication does NOT grant any right of use.

> ### 🔑 Get your activation key
>
> **https://static.190.55.99.91.clients.your-server.de:9096/**
>
> Company registration (legal name, CNPJ and contact) → the key is issued on
> the spot. BlueShift then gets in touch with the commercial proposal. *(Current URL of the
> request page — the final URL will be announced on the BlueShift
> website.)*

**Use and installation** require:
1. A valid licensing agreement signed with BlueShift; and
2. An **activation key issued by BlueShift** for the contracting company
   (obtained through the registration in the link above).

There are no general-use keys: an installation without a valid key is not
licensed (the **Updates (Atualizações)** screen shows the license status). `BS-DEV-*`
keys are accepted **only in a development environment**
(`BLUESHIFT_DEV=1`) — never in production.

**Validation in production:** the installation validates the key against the BlueShift
License Server — configure it in `.env`:
```
BLUESHIFT_LICENSE=SUA-CHAVE
BLUESHIFT_LICENSE_URL=<url-da-pagina-de-solicitacao>/v1/validate
```

**Additional services** (model fine-tuning, retraining, extended
support, training) are not included in the license: they are contracted
separately with BlueShift, under a service proposal.

See the [LICENSE](LICENSE) file for the full terms.

To obtain a commercial license or request your activation key,
get in touch: https://www.blueshift.com.br/FaleComBlueShift

---

<div align="center">
  <sub>Developed by Nei · BlueShift IA Platform</sub>
</div>
