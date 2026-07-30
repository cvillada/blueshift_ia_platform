<div align="center">

# 🔷 BlueShift IA Platform

**Plataforma própria de Inteligência Artificial on-premise — 100% Python, Flask standalone.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-Commercial-blue)](LICENSE)
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
| **RAG** | Auto-alimentado por consultas reais + import CSV/PDF |
| **Conectores** | Configuráveis: API REST, servidores MCP ou consultas SQL |
| **Skills IA** | Geração de skills com o próprio modelo cadastrado |
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
1   Usuário pergunta
    │
2   ▼
    Conectores da área  →  SQL / API REST / MCP stdio
    │   Parâmetros (id_cliente, email, datas) extraídos da pergunta
    │   * Placeholder {id_cliente} substituído pelos valores extraídos
    │
    ▼
3   RAG (TF-IDF)  ← sempre busca, top_k=2 se conectores ok, 4 se vazios
    │   * Skills indexadas também são encontráveis aqui
    │
    ▼
4   LLM + Skills + Dados + Contexto  →  Resposta (JSON)
    │   * Dados de sistema = FONTE PRIMÁRIA
    │   * Contexto RAG = FONTE SECUNDÁRIA
    │   * Modelo principal + fallback automático
    │
    ▼ (pós-resposta)
5   Auto-alimentação  →  Guarda pergunta + resposta na memória
    │   Próxima pergunta similar: etapa 2 responde direto, sem conector
    │
    ▼
6   Webhook (opcional)  →  POST resposta para URL externa (com retry 3x)
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
| **Conhecimento** | Base de conhecimento RAG (manual, política, contratos + CSV + PDF) | Login |
| Modelos IA | Cadastro de LLMs OpenAI-compatible (local e externo) | Admin |
| **Chat** | Teste do agente com RAG + LLM real | Login |
| **Conectores** | Cadastro de fontes externas (API, MCP, SQL) + Oracle + finalidade (Art. 26 LGPD) | Admin |
| **Canais** | API de integração com token + webhook de saída | Admin |
| **LGPD** | Conformidade na saída: anonimizar LLM/RAG, aviso de privacidade, finalidade por conector, retenção de logs | Admin |
| **Uso de Tokens** | Análise de consumo por cliente/modelo/origem | Admin |
| **Observabilidade** | Dashboard IA: KPI, drift, custos, feedback, alertas | Admin |
| **Teste A/B** | Reexecuta perguntas do feedback contra outro modelo e compara resultados com modelo juiz | Admin/Gestor |
| **Auditoria** | Rastreabilidade LGPD + 🔍 Rastreio passo a passo | Admin |
| **Fine-Tuning** | Documentação sobre formatos (GGUF/MLX), hardware e passo a passo | Login |
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
| 🔌 **MCP** | Servidor MCP via stdio (local) ou SSE (remoto, JSON-RPC 2.0) | `python mcp_server.py` / URL SSE + tool call |
| 🗄️ **SQL** | PostgreSQL, MySQL, SQL Server, **Oracle** via `oracledb` | `SELECT * FROM vw_clientes WHERE id = %s` |

Os parâmetros (`{id_cliente}`, `{email}`, `{data}`) são extraídos automaticamente da pergunta do usuário.

### 🧠 Base de Conhecimento (RAG)

| Mecanismo | Descrição |
|:----------|:----------|
| **Manual** | Adicionar documentos via formulário no portal |
| **CSV Import** | Upload de `.csv` com colunas `titulo,conteudo,fonte,area` |
| **PDF Import** | Upload de `.pdf` com extração automática de texto (PyMuPDF) |
| **RAG Auto-save** | Resultados de conectores são salvos automaticamente no RAG |
| **Skills no RAG** | Skills do catálogo podem ser indexadas no knowledge |
| **Monitor** | KPI cards: total docs, áreas, acessos, tamanho médio |
| **Export Fine-Tuning** | Exporta RAG como JSONL (formato `messages`) para MLX, HuggingFace, Unsloth, OpenAI |

### ⚙️ Skills

- **Catálogo por área**: skills reutilizáveis (vendas, suporte, financeiro, RH, operações)
- **Edição persistente**: skills editadas são salvas no banco de dados (volume Docker),
  sobrevivendo a rebuilds do container. O arquivo SKILL.md funciona como fallback.
- **Geração com IA**: crie o conteúdo da skill descrevendo em português o que o agente deve fazer
- **Indexação no RAG**: skills podem ser importadas para a base de conhecimento (buscáveis por TF-IDF)

### 🔐 Segurança e Controle de Acesso

- **Senhas com hash**: scrypt (salt 16 bytes, N=16384) — sem plaintext no banco
- **RBAC**: hierarquia `admin > gestor > usuario > sistema`
- **Rate limit**: login 5 tentativas/IP/min (bloqueio 15min) + API 100 req/token/min
- **CSRF**: token em todos os formulários do portal
- **Session hardening**: cookie HttpOnly + SameSite=Lax + timeout 30min + Secure (HTTPS)
- **SQL injection**: whitelist de colunas + queries parametrizadas
- **Path traversal**: nomes de skills validados como `isidentifier()`
- **Webhook URL**: bloqueio de IPs internos (localhost, 10.x, 192.168.x)
- **SSO (OIDC)**: login federado opcional (mantém login local)
- **CORS**: headers configurados (Allow-Origin: \*)
- **Auditoria LGPD**: toda ação sensível é registrada
- **Canais com token**: cada canal de integração tem chave própria (regenerável)
- **Debug mode desligado**: sem tracebacks em produção
- **Isolamento**: dados separados por `cliente_id` + área

### 🔒 Conformidade LGPD

| Funcionalidade | Artigos | Descrição |
|:---------------|:--------|:----------|
| **Anonimizar resposta do LLM** | 12, 13 | Mascara CPF, CNPJ, email, telefone, nome e endereço na resposta do agente (chat, API, webhook) |
| **Anonimizar exportação RAG** | 12, 13 | Dados pessoais mascarados na exportação JSONL da base de conhecimento |
| **Aviso de privacidade no login** | 9, 10 | Texto personalizável exibido no rodapé da tela de login |
| **Finalidade do tratamento** | 26 | Campo obrigatório por conector quando ativado |
| **Retenção automática de logs** | 15 | Limpeza periódica de auditoria (90d), tracing (180d) e memórias (365d) via thread daemon |
| **Teste A/B entre modelos** | — | Reexecuta perguntas do feedback com outro modelo e avalia via modelo juiz |

Configuração em **Cadastros > 🛡️ LGPD** e **Teste A/B** no menu principal.

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
  "resposta": "O cliente C001 possui 3 interações...",
  "pergunta": "Qual o histórico do cliente C001?",
  "agente": "Agente Vendas",
  "modelo": "hermes-3-llama-3.1-8b",
  "feedback_url": "http://localhost:8080/portal/api/v1/feedback/123",
  "erro": null,
  "tokens": {"total_tokens": 345, "prompt_tokens": 200, "completion_tokens": 145},
  "tempo_ms": 2340
}
```

### Feedback da Resposta (opcional)

A resposta da API inclui `feedback_url` — uma URL para registrar se a resposta foi útil.

**Endpoint:** `POST /portal/api/v1/feedback/<trace_id>`

**Body (JSON):**
```json
{"util": true}   // ou false
```

**Exemplo:**
```bash
curl -X POST http://localhost:8080/portal/api/v1/feedback/123 \
  -H "Authorization: Bearer <TOKEN_DO_CANAL>" \
  -H "Content-Type: application/json" \
  -d '{"util": true}'
```

**Resposta:**
```json
{"ok": true, "feedback_id": 1}
```

> O campo `tipo` no banco será `"api"` (via curl) ou `"manual"` (via botões 👍/👎 na tela de Agentes → Testar). O uso é **opcional** — a API funciona sem o feedback. Os dados aparecem no Dashboard de Observabilidade.

### Agendamento da Agregação de Métricas

O dashboard de observabilidade consolida dados das tabelas `tracing` e `feedback` na tabela `metricas_diarias`. A agregação é feita manualmente pelo botão **"Processar métricas"** no próprio dashboard.

Para automatizar (ex: rodar todo dia às 2h da manhã), adicione no crontab do servidor:

```cron
0 2 * * * cd /opt/blueshift && python3 -c "from blueshift_layer.portal import db; db.agregar_metricas_diarias()"
```

Ou dentro do Docker:

```bash
docker exec blueshift-platform python3 -c "from blueshift_layer.portal import db; db.agregar_metricas_diarias()"
```

---

## 🤖 Modelos Locais de IA

A BlueShift é 100% compatível com qualquer servidor **OpenAI-compatible**. Você pode usar modelos locais (recomendado para on-premise) ou externos.

### Opções de Servidor Local

| Servidor | Descrição | Porta padrão |
|:---------|:----------|:-------------|
| **[LM Studio](https://lmstudio.ai)** | GUI para baixar e rodar modelos GGUF | `http://127.0.0.1:1234` |
| **[Ollama](https://ollama.com)** | CLI simples para rodar modelos locais | `http://127.0.0.1:11434` |
| **[llama.cpp](https://github.com/ggerganov/llama.cpp)** | Engine C++ leve, via `llama-server` | `http://127.0.0.1:8080` |
| **[vLLM](https://github.com/vllm-project/vllm)** | Alto throughput, ideal para GPU | `http://127.0.0.1:8000` |

### Setup com LM Studio (recomendado para dev)

```bash
# 1. Baixe o LM Studio em https://lmstudio.ai
# 2. Na aba "Discover", busque e baixe um modelo GGUF

# Modelo usado nos testes de desenvolvimento:
#   NousResearch/Hermes-3-Llama-3.1-8B (Q4_K_M, ~5.5 GB)
#   → Buscar no LM Studio: "hermes-3-llama-3.1-8b"
#
# Alternativas leves:
#   - Llama 3.1 8B Instruct
#   - Mistral 7B v0.3
#   - Qwen 2.5 7B Instruct

# 3. Na aba "Local Server":
#    - Selecione o modelo baixado
#    - Ative "Cross-Origin-Resource-Sharing (CORS)"
#    - Ative "Start Server"
#    - Porta: 1234 (padrão)

# 4. No Portal BlueShift, vá em Modelos IA e cadastre:
#    - Nome: Hermes-3-Llama-3.1-8B
#    - Endpoint: http://host.docker.internal:1234 (se estiver no Docker)
#               ou http://127.0.0.1:1234 (se estiver rodando local)
#    - Modelo: hermes-3-llama-3.1-8b (ou o nome exato que o servidor espera)
#    - Tipo: Local
```

> ⚠️ **No Docker:** o container precisa acessar o LM Studio no host. Use `host.docker.internal` no lugar de `127.0.0.1`. Em Linux, use `--add-host=host.docker.internal:host-gateway`.

### Setup com Ollama

```bash
# 1. Instale o Ollama: https://ollama.com
# 2. Baixe um modelo:
ollama pull llama3.2:3b
ollama pull phi4:14b
# 3. Inicie o servidor (já inicia automático no macOS):
ollama serve
# 4. No Portal, cadastre:
#    - Nome: llama3.2
#    - Endpoint: http://host.docker.internal:11434
#    - Modelo: llama3.2:3b
#    - Tipo: Local
```

### Modelos Externos (OpenAI-compatible)

Se preferir usar APIs externas em vez de modelos locais:

| Provedor | Endpoint | API Key |
|:---------|:---------|:--------|
| **DeepSeek** | `https://api.deepseek.com` | ✅ Necessária |
| **OpenRouter** | `https://openrouter.ai/api/v1` | ✅ Necessária |
| **OpenAI** | `https://api.openai.com/v1` | ✅ Necessária |
| **NVIDIA NIM** | `https://integrate.api.nvidia.com/v1` | ✅ Necessária |

No Portal, cadastre como **Tipo: Híbrido** e preencha a API Key.

---

## 🐳 Docker

### Instalação via Installer (recomendado)

```bash
cp .env.example .env          # ajuste BLUESHIFT_LICENSE
./install.sh                  # docker compose up -d --build
```

Acesse `http://localhost:8080/portal` (login: `admin` / `admin123`).

> **Modelos de IA não vêm embutidos.** Após subir a plataforma, cadastre os modelos na tela **Modelos IA** — local (vLLM/LM Studio/Ollama) ou externo (DeepSeek/OpenRouter/OpenAI).
>
> **Áreas personalizadas:** edite a variável `BLUESHIFT_AREAS` no `docker-compose.yml` para customizar as áreas da empresa. Padrão: `vendas,suporte,financeiro,rh,operacoes`.
>
> **MCP com Node.js:** para servidores MCP locais que dependem de Node.js (npm/npx), o container já inclui Node 20 e npm.

### Manual

```bash
# 1. Build da imagem
docker build -t blueshift/platform -f docker/Dockerfile .

# 2. Crie um volume para persistencia dos dados
docker volume create blueshift_data

# 3. Suba o container com volume montado
docker run -d --name blueshift-platform \
  -p 8080:8080 \
  -v blueshift_data:/data/blueshift \
  -e BLUESHIFT_PORTAL_DB=/data/blueshift/portal.db \
  -e BLUESHIFT_LICENSE=BS-DEV-teste123 \
  blueshift/platform blueshift portal
```

> **Persistencia de dados:** o banco SQLite e demais dados ficam no volume `blueshift_data`.
> Você pode rebuildar o container (`docker build` + `docker stop` + `docker rm` + `docker run`)
> que os dados (clientes, usuarios, agentes, conectores, skills editadas, documentos RAG) sao preservados.
> Para backup: `docker run --rm -v blueshift_data:/data -v $(pwd):/backup alpine tar czf /backup/blueshift_backup.tar.gz -C /data .`

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
│   ├── mask.py                     ← Mascaramento LGPD (CPF, email, nome, etc.)
│   └── sso.py                      ← Login federado OIDC
├── connector_pack/                 ← 🔌 Conectores externos
│   ├── registry.py                 ← Engine API/MCP/SQL
│   ├── mcp_server.py               ← MCP stdio (JSON-RPC 2.0)
│   ├── mcp_erp.py                  ← ERP (Postgres)
│   ├── mcp_crm.py                  ← CRM (dados de exemplo)
│   └── mcp_rh.py                   ← RH (dados de exemplo)
└── template_skills/                ← ⚙️ Skills por área (fallback; salvos no banco p/ persistencia)
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
| **PDF Extraction** | PyMuPDF (extração de texto para RAG) |
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
PyMuPDF>=1.28       # PDF text extraction (RAG)
```

---

## 💻 Hardware Recomendado

### Gargalos da plataforma

| Componente | Limite | Causa |
|:-----------|:-------|:------|
| **SQLite** | ~50 escritas concorrentes | Single-writer (lock de tabela) |
| **TF-IDF** (memória) | ~100k docs / ~500MB RAM | Índice carregado em RAM |
| **Flask** (threaded) | ~20 req/s concorrentes | GIL + threads síncronas |
| **LLM local** | 2-60s por chamada | Dependente do modelo/hardware |
| **Busca vetorial** | O(n) = 50-200ms p/ 10k docs | Força bruta (cosseno), sem índice |

### Tiers

#### 🟢 TIER 1 — Pequeno (até 10 usuários, 1k docs, 500 queries/dia)

| Recurso | Especificação |
|:--------|:--------------|
| **CPU** | 2 vCPU |
| **RAM** | 8 GB |
| **Disco** | 50 GB SSD |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **Modelo LLM** | até 3B params (Q4, ~2GB RAM) |
| **Custo estimado** | ~R$ 80/mês (VPS) |

#### 🟡 TIER 2 — Médio (até 50 usuários, 10k docs, 5k queries/dia)

| Recurso | Especificação |
|:--------|:--------------|
| **CPU** | 4 vCPU |
| **RAM** | 16 GB |
| **Disco** | 200 GB SSD |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **Modelo LLM** | até 8B params (Q4_K_M, ~5GB RAM) |
| **Custo estimado** | ~R$ 250/mês (VPS) |

#### 🟠 TIER 3 — Grande (até 200 usuários, 50k docs, 20k queries/dia)

| Recurso | Especificação |
|:--------|:--------------|
| **CPU** | 8 vCPU |
| **RAM** | 32 GB |
| **Disco** | 500 GB SSD NVMe |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | NVIDIA RTX 4060+ (opcional, p/ vLLM) |
| **Modelo LLM** | até 14B params (Q4, ~9GB RAM) |
| **Custo estimado** | ~R$ 800/mês (dedicated server) |

**O que precisa mudar neste tier:**
- Flask → **Gunicorn + workers** (4-8 workers)
- TF-IDF O(n) → **ChromaDB** (HNSW index) ou SQLite FTS5
- SQLite → **PostgreSQL** (já tem suporte via psycopg)
- Adicionar **Redis** para cache de RAG

#### 🔴 TIER 4 — Enterprise (500+ usuários, 200k docs, 100k queries/dia)

| Recurso | Especificação |
|:--------|:--------------|
| **CPU** | 16 vCPU |
| **RAM** | 64 GB |
| **Disco** | 1 TB NVMe |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | 1-2x NVIDIA RTX 4090 / A4000+ |
| **Modelo LLM** | até 70B params (via vLLM com GPU) |
| **Custo estimado** | ~R$ 3.000+/mês (servidor dedicado) |

**O que precisa mudar neste tier:**
- Flask puro → **FastAPI** + async
- TF-IDF → **ChromaDB / Qdrant / pgvector**
- SQLite → **PostgreSQL + pgvector**
- LLM em CPU → **vLLM** em GPU (50x mais rápido)
- Cache → **Redis**
- Fila → **Celery / RQ** para tarefas async
- Monitor → **Prometheus + Grafana**

### Resumo

| Tier | CPU | RAM | Disco | GPU | Usuários | Custo/mês |
|:----:|:---:|:---:|:-----:|:---:|:--------:|:---------:|
| 🟢 1 | 2 vCPU | 8 GB | 50 GB | Não | 10 | ~R$ 80 |
| 🟡 2 | 4 vCPU | 16 GB | 200 GB | Opc. | 50 | ~R$ 250 |
| 🟠 3 | 8 vCPU | 32 GB | 500 GB | Rec. | 200 | ~R$ 800 |
| 🔴 4 | 16 vCPU | 64 GB | 1 TB | Sim | 500+ | ~R$ 3.000+ |

> **Nota:** o maior gargalo não é o hardware — é o **LLM local** sem GPU. Um modelo 8B em CPU gera 5-15 tok/s. Uma resposta de 300 tokens leva 20-60 segundos. Para produção com muitos usuários, **GPU é essencial** (via vLLM).

---

## 📄 Licença

Este projeto é distribuído sob **licença comercial de uso corporativo restrito**.
O uso do software é permitido apenas para pessoas jurídicas com contrato
de licenciamento válido e assinado com a BlueShift.

Veja o arquivo [LICENSE](LICENSE) para os termos completos.

Para obter uma licença comercial, entre em contato.

---

<div align="center">
  <sub>Desenvolvido por Nei · BlueShift IA Platform</sub>
</div>
