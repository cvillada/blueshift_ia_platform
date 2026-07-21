<div align="center">

# 🔷 BlueShift IA Platform

**Plataforma própria de Inteligência Artificial on-premise — 100% Python, Flask standalone.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docker.com)

**Deploy on-premise · Dados 100% no cliente · Modelos híbridos (local/externo) · Agentes por área · Licença anual**

</div>

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura)
- [Funcionalidades](#-funcionalidades)
- [Começando](#-começando)
- [Comandos CLI](#-comandos-cli)
- [Portal do Cliente](#-portal-do-cliente)
- [Agentes e Conectores](#-agentes-e-conectores)
- [Docker](#-docker)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Stack Tecnológica](#-stack-tecnológica)
- [Licença](#-licença)

---

## 🚀 Visão Geral

A **BlueShift IA Platform** é uma plataforma de inteligência artificial projetada para ser instalada **dentro da infraestrutura do cliente** — datacenter, servidor dedicado ou nuvem privada. Diferente de SaaS onde os dados saem da empresa, aqui **tudo fica dentro do ambiente do cliente**: dados, agentes, memória dos usuários e histórico.

### 🎯 Diferenciais

| Característica | BlueShift |
|:---------------|:----------|
| **Dados** | 100% on-premise — nunca saem do cliente |
| **Modelos** | Híbrido: local (vLLM/LM Studio/Ollama) ou externo (OpenAI/DeepSeek/Claude) |
| **Agentes** | Por área da empresa (vendas, suporte, financeiro, RH, operações) |
| **Memória** | Persistente por usuário — banco vetorial local (TF-IDF + cosseno) |
| **Conectores** | Configuráveis: API REST, servidores MCP ou consultas SQL |
| **Licenciamento** | Anual por empresa (não por token) |
| **Stack** | Python puro, Flask, SQLite — sem dependências pesadas |

---

## 🏗️ Arquitetura

```
                    ┌─────────────────────┐
                    │   CLI (blueshift)    │
                    │  init · portal · mcp │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  🌐 PORTAL (Flask)   │
                    │  create_app() :8080  │
                    └──────────┬──────────┘
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
 │  MEMORY  │ │ LLM  │ │  AGENTE  │
 │ memory.py│ │client│ │ agente.py│
 │ (TF-IDF) │ │ .py  │ │Orq. Final│
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

### Fluxo de Execução do Agente

```
1️⃣ Usuário pergunta  →  2️⃣ RAG (TF-IDF)  →  3️⃣ Conectores da área  →  4️⃣ LLM + contexto  →  5️⃣ Resposta
                           (memória +          (API/MCP/SQL com         (modelo de IA          (JSON)
                            knowledge)           params extraídos        configurado)
                                                 da pergunta)
```

---

## ✨ Funcionalidades

### 🖥️ Portal do Cliente

| Tela | Descrição | Acesso |
|:-----|:----------|:-------|
| **Monitorar** | Dashboard de saúde: clientes, agentes, modelos, tokens, conectores | Login |
| **Workspace** | Painel por departamento com agentes e documentos da área | Login |
| **Clientes** | Gerenciar e cadastrar clientes | Admin |
| **Usuários** | CRUD de usuários com papéis (admin/gestor/usuario/sistema) e área | Admin |
| **Agentes** | Agent Factory: montar agente com modelo + skills + conectores | Admin |
| **Skills** | Catálogo de skills por área (SKILL.md) | Login |
| **Memória** | Memória persistente por usuário (banco vetorial local) | Login |
| **Conhecimento** | Base de conhecimento RAG (manual, política, contratos) | Login |
| **Modelos IA** | Cadastro de LLMs OpenAI-compatible (local e externo) | Admin |
| **Chat** | Teste do agente com RAG + LLM real | Login |
| **Conectores** | Cadastro de fontes externas (API, MCP, SQL) por área | Admin |
| **Canais** | API de integração com token + webhook de saída | Admin |
| **Uso de Tokens** | Análise de consumo por cliente/modelo/origem | Admin |
| **Auditoria** | Rastreabilidade LGPD de ações sensíveis | Admin |
| **SSO (OIDC)** | Login federado (Azure AD, Okta, Keycloak, Google) | Admin |
| **Atualizações** | Update Channel da plataforma | Admin |

### 🤖 Agentes (Agent Factory)

- **Modelo principal + fallback automático** — se o endpoint principal falha, tenta o secundário
- **Skills do catálogo** — skills reutilizáveis por área
- **Conectores da área** — executa automaticamente as fontes externas configuradas
- **Contexto dinâmico** — RAG (memória + knowledge) + dados de conectores injetados no prompt
- **Teste em tempo real** — tela de teste com RAG + LLM real

### 🔌 Conectores Externos

Conectores são fontes de dados configuráveis por **área** (vendas, suporte, etc.):

| Tipo | Descrição | Exemplo |
|:-----|:----------|:--------|
| 🌐 **API REST** | Chamada HTTP via `urllib` | `GET https://api.externa.com/dados` |
| 🔌 **MCP** | Servidor MCP via stdio (JSON-RPC 2.0) | `python mcp_server.py` + tool call |
| 🗄️ **SQL** | Consulta SQL via `psycopg` | `SELECT * FROM vw_clientes WHERE id = %s` |

Os parâmetros (`{id_cliente}`, `{email}`, `{data}`) são extraídos automaticamente da pergunta do usuário.

### 🔐 Segurança e Controle de Acesso

- **RBAC**: hierarquia `admin > gestor > usuario > sistema`
- **SSO (OIDC)**: login federado opcional (mantém login local)
- **Auditoria LGPD**: toda ação sensível é registrada
- **Canais com token**: cada canal de integração tem chave própria (regenerável)
- **Isolamento**: dados separados por `cliente_id` + área

---

## 🚀 Começando

### Pré-requisitos

- Python 3.11+
- Git
- Docker (opcional, para deploy em container)

### Setup Local

```bash
# 1. Clone o repositório
git clone https://github.com/cvillada/blueshift_ia_platform.git
cd blueshift_ia_platform

# 2. Crie e ative o ambiente virtual
python3 -m venv bp-venv && source bp-venv/bin/activate

# 3. Instale a plataforma
pip install --upgrade pip
pip install -e .

# 4. Teste a instalação
blueshift --help
blueshift activate BS-DEV-teste123   # deve mostrar LICENSE OK

# 5. Suba o Portal
blueshift portal --port 8080
# Acesse: http://localhost:8080/portal
# Login: admin / admin123
```

---

## 📟 Comandos CLI

| Comando | Descrição |
|:--------|:----------|
| `blueshift init <cliente>` | Cria perfil do cliente |
| `blueshift activate <chave>` | Valida license key |
| `blueshift status` | Mostra estado do container |
| `blueshift update` | Checa atualizações aprovadas |
| `blueshift portal [--port 8080]` | Sobe o Portal do Cliente |
| `blueshift mcp` | Sobe servidor MCP stdio (conectores) |

### Exemplo de Uso da API de Canal

```bash
curl -X POST http://localhost:8080/portal/api/v1/agente \
  -H "Authorization: Bearer bs_chan_seu_token_aqui" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual o histórico do cliente C001?"}'
```

Resposta:
```json
{
  "ok": true,
  "resposta": "O cliente C001 possui 3 interações no CRM...",
  "agente": "Agente Vendas",
  "modelo": "bonsai-4b",
  "contexto": [...],
  "ferramentas": [...],
  "webhook": {"enviado": true, "status": 200}
}
```

---

## 🐳 Docker

### Instalação via Installer (recomendado)

```bash
cp .env.example .env          # ajuste BLUESHIFT_LICENSE
./install.sh                  # docker compose up -d --build
```

Acesse `http://localhost:8080/portal` (login: `admin` / `admin123`).

> **Modelos de IA não vêm embutidos.** Após subir a plataforma, cadastre os modelos na tela **Modelos IA** — local (vLLM/LM Studio/Ollama) ou externo (DeepSeek/OpenRouter/OpenAI).

### Manual

```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker run -d --name blueshift-platform \
  -p 8080:8080 \
  -e BLUESHIFT_LICENSE=BS-DEV-teste123 \
  blueshift/platform blueshift portal
```

---

## 📁 Estrutura do Projeto

```
blueshift_layer/                    ← Código principal da plataforma
├── cli.py                          ← Entry point CLI (blueshift)
├── license_client.py               ← Validação de license key
├── license_server_mock.py          ← License Server mock (Flask, :9000)
├── installer.py                    ← Cria perfil do cliente
├── update_client.py                ← Update Channel
├── update_server.py                ← Update Channel mock (Flask, :9001)
├── config/
│   └── default_config.yaml         ← Config padrão do container
├── portal/                         ← 🌐 Portal do Cliente (Flask)
│   ├── __init__.py                 ← Factory create_app()
│   ├── db.py                       ← SQLite (ponto único de dados)
│   ├── views.py                    ← Rotas e telas
│   ├── auth.py                     ← Autenticação + RBAC
│   ├── templates.py                ← Layout HTML/CSS/JS
│   ├── memory.py                   ← RAG (TF-IDF + cosseno, Python puro)
│   ├── llm_client.py               ← Client LLM OpenAI-compatible (urllib)
│   ├── agente.py                   ← Orquestrador do agente
│   └── sso.py                      ← Login federado OIDC
├── connector_pack/                 ← 🔌 Conectores externos
│   ├── registry.py                 ← Engine API/MCP/SQL
│   ├── mcp_server.py               ← MCP stdio (JSON-RPC 2.0)
│   ├── mcp_erp.py                  ← ERP (Postgres)
│   ├── mcp_crm.py                  ← CRM (dados de exemplo)
│   └── mcp_rh.py                   ← RH (dados de exemplo)
└── template_skills/                ← ⚙️ Skills por área
    ├── vendas/SKILL.md
    ├── suporte/SKILL.md
    ├── financeiro/SKILL.md
    ├── rh/SKILL.md
    └── operacoes/SKILL.md

docker/
├── Dockerfile                      ← Imagem do container
└── entrypoint.sh                   ← Sobe License + Update + Portal
```

---

## 🛠️ Stack Tecnológica

| Categoria | Tecnologia |
|:----------|:-----------|
| **Linguagem** | Python 3.11+ |
| **Framework** | Flask 3.1 |
| **Banco de Dados** | SQLite (on-premise, sem dependência de rede) |
| **LLM Client** | urllib puro (OpenAI-compatible) |
| **RAG** | TF-IDF + similaridade de cosseno (Python puro, sem numpy) |
| **MCP** | JSON-RPC 2.0 sobre stdio (Python puro) |
| **SSO** | OIDC via urllib + HMAC (sem libs OAuth) |
| **Autenticação** | Login/senha local + SSO federado |
| **Container** | Docker (Python 3.11-slim) |
| **Postgres** | Opcional (via `psycopg` para conector ERP) |

### Dependências Python

```
flask>=3.1          # Framework web
requests>=2.31      # HTTP client (license_client)
pyyaml>=6.0         # YAML config
mcp>=1.0            # FastMCP (conectores)
psycopg[binary]>=3.1 # Postgres (conector ERP, opcional)
```

---

## 📄 Licença

Este projeto é distribuído sob licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<div align="center">
  <sub>Desenvolvido por Nei · BlueShift IA Platform</sub>
</div>
