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
| **Gateway OpenAI** | Chats externos (Open WebUI, LibreChat, apps) no protocolo padrão — porta 9003 |
| **Skills IA** | Geração de skills com o próprio modelo cadastrado |
| **Licenciamento** | Anual por empresa (não por token) |
| **Stack** | Python puro, Flask, SQLite — sem dependências pesadas |

---

## 🏗️ Arquitetura

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
                    │  💬 CHATS EXTERNOS  │
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
| **Workspace** | Painel por departamento com agentes e documentos da área; cards com **tokens por agente** (1d/7d/30d/90d) | Login |
| **Clientes** | Gerenciar e cadastrar clientes | Admin |
| **Usuários** | CRUD de usuários com papéis (admin/gestor/usuario/sistema) e área | Admin |
| **Áreas** | Cadastro de departamentos (banco; env `BLUESHIFT_AREAS` só seed inicial) | Admin |
| **Agentes** | Agent Factory: montar agente com modelo + skills + conectores | Admin |
| **Skills** | Catálogo de skills por área (SKILL.md) | Login |
| **Memória** | Memória persistente por usuário (banco vetorial local) | Login |
| **Conhecimento** | Base de conhecimento RAG (manual, política, contratos + CSV + PDF) | Login |
| **Docs** | Documentação completa (DOCUMENTACAO_PB.md) no menu lateral — mesma fonte do popup Ajuda | Login |
| Modelos IA | Cadastro de LLMs OpenAI-compatible (local e externo) | Admin |
| **Conectores** | Cadastro de fontes externas (API, MCP, SQL) + Oracle + finalidade (Art. 26 LGPD) | Admin |
| **Canais** | API de integração com token + webhook de saída | Admin |
| **Gateway** | Ativação do gateway OpenAI-compatível (canal + modo streaming/completa + limites de contexto) | Admin |
| **LGPD** | Conformidade na saída: anonimizar LLM/RAG, aviso de privacidade, finalidade por conector, retenção de logs | Admin |
| **Uso de Tokens** | Análise de consumo por cliente/modelo/origem | Admin |
| **Observabilidade** | Dashboard IA: KPI, drift, custos, feedback, alertas | Admin |
| **Teste A/B** | Reexecuta perguntas do feedback contra outro modelo e compara resultados com modelo juiz | Admin/Gestor |
| **Auditoria** | Rastreabilidade LGPD + 🔍 Rastreio passo a passo | Admin |
| **Arquivo Morto** | Snapshot selado do banco + corte manual (D-1 máx.) — controla o crescimento sem perder histórico (detalhes em [Limpeza e arquivo morto](#limpeza-e-arquivo-morto)) | Admin |
| **Fine-Tuning** | Documentação sobre formatos (GGUF/MLX), hardware e passo a passo | Login |
| **SSO (OIDC)** | Login federado (Azure AD, Okta, Keycloak, Google) | Admin |
| **Atualizações** | Update via Git (tags) — versão do repo + rebuild com dados preservados | Admin |

### 🤖 Agentes (Agent Factory)

- **Modelo principal + fallback automático** — se o endpoint principal falha, tenta o secundário
- **Skills do catálogo** — skills reutilizáveis por área
- **Conectores da área com ROTEAMENTO inteligente** — uma IA curta decide
  qual conector é relevante para cada pergunta (ou nenhum): pergunta de
  norma/política responde só com a Base de Conhecimento; pergunta que cita
  um conector (ex: "CEP") executa só ele. Configurável via
  `BLUESHIFT_ROUTER_MODEL` (recomendado: hermes-3-llama-3.1-8b local)
- **Extração de parâmetros por IA** — a IA extrai as chaves da pergunta em
  linguagem natural ("id cliente igual a 58" → `customer_id='58'`), para
  todos os tipos de conector (API/MCP/SQL) + anti-alucinação: sem dados,
  o agente diz "não encontrei" em vez de inventar
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

**Consulta inteligente (SQL):** quando a query fixa volta vazia e a pergunta pede
análise ("quem alugou mais e menos", "quantos por categoria"), o agente monta o
SELECT sozinho a partir do **schema real da fonte** (tabelas/views + colunas),
genérico por driver (MySQL/PostgreSQL/SQL Server/Oracle), com validação de
segurança (somente SELECT de leitura + LIMIT) e checkbox por conector na tela.

**Gráficos:** pedidos de gráfico (pizza/barras/linha) geram a imagem
automaticamente a partir dos dados dos conectores (matplotlib embutido), anexada
à resposta — renderiza no Open WebUI e no portal, com rótulos mascarados pela
LGPD.

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

- **Senhas com hash**: scrypt (salt 16 bytes, N=16384) — sem plaintext no banco; **mínimo 8 caracteres** (criar/editar usuário e setup inicial)
- **RBAC**: hierarquia `admin > gestor > usuario > sistema`
- **Rate limit**: login 5 tentativas/IP/min (bloqueio 15min) + API 100 req/token/min
- **Login falho**: registrado em auditoria (usuário tentado + IP) — detecta brute-force
- **CSRF**: token em todos os formulários do portal
- **XSS**: escape (html.escape) em toda renderização de dados — nomes, descrições, contexto RAG e resultados de conectores
- **Session hardening**: cookie HttpOnly + SameSite=Lax + timeout 30min + Secure (HTTPS)
- **SQL injection**: whitelist de colunas + queries parametrizadas
- **Path traversal**: nomes de skills validados como `isidentifier()`
- **Webhook URL (anti-SSRF)**: validação com `ipaddress` (bloqueia privado, CGNAT, link-local/metadata de nuvem, loopback, IPv6 interno) + resolução de DNS (DNS rebinding); vale no criar, editar e no momento do envio
- **Headers HTTP**: X-Content-Type-Options, X-Frame-Options: DENY, Referrer-Policy e Content-Security-Policy em todas as respostas
- **API Key de modelo**: nunca renderizada no HTML (máscara no editar)
- **SSO (OIDC)**: login federado opcional (mantém login local)
- **CORS**: headers configurados (Allow-Origin: \\*) — **somente nas rotas `/portal/api/*`** (páginas web não precisam)
- **Health check**: rota pública `/portal/healthz` para load balancer / HEALTHCHECK
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
| **Retenção automática de logs** | 15 | Limpeza periódica de auditoria (90d), tracing/uso_tokens (180d) e memórias (365d) via thread daemon — ou **Arquivo Morto** (snapshot + corte manual, sem perder histórico) |
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
# Modo desenvolvimento (BLUESHIFT_SEED_DEMO=1): Login: admin / admin123
# Cliente final (BLUESHIFT_SEED_DEMO=0): veja "Primeira instalação" abaixo
```

### Primeira instalação (cliente final)

A plataforma nasce com **banco limpo**: nenhuma empresa, nenhum usuário,
nenhum dado demo. Quem instala controla isso pela variável
`BLUESHIFT_SEED_DEMO` (default `1` para desenvolvimento — cria dados de
exemplo XPTO; defina `0` para o cliente final não receber nada).

Com o banco limpo, o primeiro acesso acontece assim:

1. Abra `http://localhost:8080/portal` (ou a porta/URL do deploy)
2. A tela de login vira um formulário de **Configuração inicial**
3. O cliente cadastra:
   - a própria **empresa** (nome, código, razão social, e-mail)
   - o **administrador inicial** (nome, login, senha — mínimo 6 caracteres)
4. Ao salvar, o portal autentica automaticamente e cai no Monitorar

Depois disso, o formulário de Configuração inicial **some para sempre** —
ninguém mais consegue reabrir o setup (só existe um admin). O login normal
volta a valer.

> ⚠️ Por segurança, em instalação de cliente final use sempre
> `BLUESHIFT_SEED_DEMO=0` e troque a senha do admin periodicamente.

```bash
# Exemplo: subir o portal limpo para um cliente
BLUESHIFT_SEED_DEMO=0 blueshift portal --port 8080
```

### Variáveis de ambiente

A configuração da instalação vive em variáveis de ambiente. O arquivo
[`.env.example`](.env.example) traz todas com comentários — copie para
`.env` antes de instalar. O `docker-compose.yml` usa as mesmas variáveis
(com defaults), e a tela **Atualizações** do portal mostra as principais
(card "Configuração de ambiente").

| Variável | Padrão | Efeito |
|:---------|:-------|:-------|
| `BLUESHIFT_LICENSE` | vazio | Chave de ativação (validada no boot) |
| `BLUESHIFT_AREAS` | vendas,suporte,financeiro,rh,operacoes | **Seed inicial** das áreas — depois a tela Cadastros → Áreas domina (banco) |
| `BLUESHIFT_SEED_DEMO` | 1 | `1` = dados demo XPTO (dev); `0` = banco limpo (setup inicial) |
| `BLUESHIFT_ROUTER_MODEL` | vazio | Modelo de ROTEAMENTO dos conectores: **ID ou NOME** do modelo (o nome aparece na tela Modelos IA); vazio = principal do agente; recomendado `hermes-3-llama-3.1-8b` (local) |
| `BLUESHIFT_LICENSE_URL` | localhost:9000 | URL de validação de licença |
| `BLUESHIFT_REPO_DIR` | /opt/blueshift/repo | Clone git do repo (Update via Git — tela Atualizações) |
| `GATEWAY_PORT` | 9003 | Porta publicada do Gateway OpenAI-compatível |
| `GATEWAY_PUBLIC_URL` | vazio | URL pública do gateway exibida na tela (ex: `http://192.168.0.10:9003/v1`); sem ela, usa o host da requisição |
| `BLUESHIFT_DEV` | 0 | **Produção/cliente = 0** (a tela Atualizações aplica a atualização de verdade); **dev = 1** (dry-run + licença BS-DEV-*) |
| `TZ` | UTC | Fuso (usar `America/Sao_Paulo`) |

Sem Docker (CLI direta), carregue o `.env` e suba:

```bash
cd blueshift_ia_platform
set -a; . ./.env; set +a
blueshift portal --port 8080
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
| `blueshift gateway [--port 9003]` | Sobe o Gateway OpenAI-compatível (chats externos) |

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
| **[SGL](https://docs.sglang.io/)** | Alto throughput, ideal para GPU | `http://127.0.0.1:8000` |

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
> **Áreas personalizadas:** cadastre as áreas na tela **Cadastros → Áreas**
> (banco). A variável `BLUESHIFT_AREAS` no `docker-compose.yml` serve apenas
> como seed inicial do primeiro boot.
>
> **MCP com Node.js:** para servidores MCP locais que dependem de Node.js (npm/npx), o container já inclui Node 20 e npm.
>
> **Update via Git:** o compose monta o repositório (padrão: o próprio
> diretório; produção: clone em `/opt/blueshift/repo`) e o `docker.sock`
> do host no portal. A tela **Atualizações** mostra a versão do repo e
> aplica a tag nova com `docker compose up -d --build` (dados preservados).

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

> **O compose sobe DOIS containers:** `blueshift-platform` (portal, :8090→8080)
> e `blueshift-gateway` (gateway OpenAI-compatível, :9003) — o gateway
> depende do portal e lê a configuração no mesmo volume `blueshift-data`.

### 🔀 Gateway OpenAI-compatível (chats externos)

O gateway expõe o protocolo padrão da OpenAI (`/v1/chat/completions` +
`/v1/models`) para chats externos — **Open WebUI**, LibreChat, apps
custom, OpenAI SDK/LangChain — e repassa ao agente via API do canal
(token `bs_chan_*`).

Para conectar o **Open WebUI** (container na mesma máquina):

```bash
# 1. No portal: Cadastros → Canais → crie o canal (ex: "API Vendas")
#    apontando para o agente desejado (o token bs_chan_* é a API Key)
# 2. No portal: Cadastros → Gateway → "Ativar gateway" (canal + modo:
#    Resposta completa JSON ou Streaming SSE) — o gateway precisa estar
#    ATIVO para responder
# 3. No Open WebUI (Admin → Connections → OpenAI API):
#      API URL: http://host.docker.internal:9003/v1
#      API Key: o token do canal (qualquer gateway ativo autentica)
#      Model:  agente:Agente Vendas  (o nome do agente)
```

- O `model` escolhe o agente; o token só valida a autenticação (qualquer
  chave de canal com gateway ativo funciona — o Open WebUI usa uma
  conexão = uma chave para vários modelos)
- **Contexto da conversa:** o gateway repassa as mensagens anteriores
  (limites configuráveis na tela: máx. mensagens + orçamento em tokens);
  a memória/RAG gravam sempre a última pergunta/resposta real
- Chat em outra máquina da rede: `http://IP_DO_SERVIDOR:9003/v1`
- Sem Docker: `set -a; . ./.env; set +a` + `blueshift gateway --port 9003`

---

## 📁 Estrutura do Projeto

```
blueshift_layer/                    ← Código principal da plataforma
├── cli.py                          ← Entry point CLI (blueshift)
├── gateway.py                      ← Gateway OpenAI-compatível (:9003, /v1)
├── license_client.py               ← Validação de license key
├── license_server_mock.py          ← License Server mock (Flask, :9000)
├── installer.py                    ← Cria perfil do cliente
├── update_client.py                ← Update via Git (tags) — versão + apply
├── update_server.py                ← Update Channel mock legado (Flask, :9001)
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

| Componente | Limite real | Causa |
|:-----------|:------------|:------|
| **LLM local** | 2-60s por chamada | Modelo/hardware — **o gargalo principal** (GPU via vLLM resolve) |
| **SQLite (WAL)** | 1 escrita por vez; leituras concorrentes liberadas | Single-writer — irrelevante na prática: ~3 escritas minúsculas por chamada de agente |
| **Portal (Werkzeug, threaded)** | Requisições concorrentes (I/O do LLM libera o GIL) | Servidor dev; para carga extrema, waitress/gunicorn (ver Tier 3) |
| **TF-IDF** (memória) | ~100k docs / ~500MB RAM | Índice carregado em RAM |
| **Busca vetorial** | O(n) = 50-200ms p/ 10k docs | Força bruta (cosseno), sem índice |

### Tiers

Os tiers são **orientativos para dimensionar a instalação do cliente**. "Acessos simultâneos" é a capacidade de **KV cache** do servidor LLM (vLLM) com o modelo indicado em Q4 e contexto médio de referência — quem passa do limite **entra na fila nativa do vLLM** (espera, não falha). Fórmula e tabela completa na seção [Capacidade de acessos simultâneos](#capacidade-de-acessos-simultaneos-kv-cache).

#### 🟢 TIER 1 — Pequeno (até 10 usuários, 1k docs, 500 queries/dia)

| Recurso | Especificação |
|:--------|:--------------|
| **CPU** | 2 vCPU |
| **RAM** | 8 GB |
| **Disco** | 50 GB SSD |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | Não (opcional: RTX 4060 8GB) |
| **Modelo LLM** | até 3B params (Q4, ~2GB RAM, CPU) |
| **Acessos simultâneos** | 1-2 (CPU; com GPU 8GB: 1-2 @ 8K ctx) |
| **Registros/dia** | ~1,5k (3 por query) — SQLite WAL + retenção LGPD: folga total |
| **Custo estimado** | ~R$ 80/mês (VPS) |

#### 🟡 TIER 2 — Médio (até 50 usuários, 10k docs, 5k queries/dia)

| Recurso | Especificação |
|:--------|:--------------|
| **CPU** | 4 vCPU |
| **RAM** | 16 GB |
| **Disco** | 200 GB SSD |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | RTX 4060 8GB (opcional, p/ vLLM) |
| **Modelo LLM** | até 8B params (Q4_K_M, ~5GB VRAM) |
| **Acessos simultâneos** | ~1-2 @ 8K ctx (8B Q4 em GPU 8GB); CPU: 1 |
| **Registros/dia** | ~15k — SQLite WAL + índices + retenção: folga |
| **Custo estimado** | ~R$ 250/mês (VPS) |

#### 🟠 TIER 3 — Grande (até 200 usuários, 50k docs, 20k queries/dia)

| Recurso | Especificação |
|:--------|:--------------|
| **CPU** | 8 vCPU |
| **RAM** | 32 GB |
| **Disco** | 500 GB SSD NVMe |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | NVIDIA RTX 4080/3090 24GB (recomendado, p/ vLLM) |
| **Modelo LLM** | até 14B params (Q4, ~9GB VRAM) |
| **Acessos simultâneos** | ~3 @ 32K ctx (8B Q4); ~1 @ 32K (14B Q4) — excedente na fila do vLLM |
| **Registros/dia** | ~60k — SQLite WAL + índices + retenção: aguenta |
| **Custo estimado** | ~R$ 800/mês (dedicated server) |

**O que precisa mudar neste tier:**
- **Nada na plataforma** — o salto é o modelo sair de CPU para **vLLM em GPU** (24GB+). SQLite já opera em WAL com índices de retenção.
- Opcional: servidor **waitress/gunicorn** para throughput HTTP acima do Werkzeug dev (1 processo threaded).

#### 🔴 TIER 4 — Enterprise (500+ usuários, 200k docs, 100k queries/dia)

| Recurso | Especificação |
|:--------|:--------------|
| **CPU** | 16 vCPU |
| **RAM** | 64 GB |
| **Disco** | 1 TB NVMe |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | NVIDIA RTX Pro 6000 128GB (ou 2x 24GB) |
| **Modelo LLM** | até 70B params (Q4, ~41GB VRAM, via vLLM) |
| **Acessos simultâneos** | ~25 @ 32K (8B Q4) / ~6 @ 32K (70B Q4); ~6 @ 128K (8B) — excedente na fila do vLLM |
| **Registros/dia** | ~300k — teto do desenho atual: ~18M linhas de tracing (180d) indexadas; SQLite WAL aguenta |
| **Custo estimado** | ~R$ 3.000+/mês (servidor dedicado) |

**O que precisa mudar neste tier:**
- **Único cenário que justifica PostgreSQL**: 2+ réplicas do portal gravando no mesmo banco (multi-writer). O desenho atual (1 portal + gateway stateless de leitura) não cruza esse limite — se o TI do cliente exigir, é estudo de migração escopado, não reescrita da camada de dados.
- Fila de tarefas async (Celery/RQ) só se houver webhook de saída em volume com retry persistente — hoje a entrega é síncrona com retry (3x, backoff) e a alternativa leve é thread em background.

### Resumo

| Tier | CPU | RAM | Disco | GPU (VRAM) | Acessos simultâneos* | Usuários | Registros/dia | Custo/mês |
|:----:|:---:|:---:|:-----:|:----------:|:--------------------:|:--------:|:-------------:|:---------:|
| 🟢 1 | 2 vCPU | 8 GB | 50 GB | Não | 1-2 (CPU) | 10 | ~1,5k | ~R$ 80 |
| 🟡 2 | 4 vCPU | 16 GB | 200 GB | RTX 4060 (8GB, opc.) | 1-2 @ 8K | 50 | ~15k | ~R$ 250 |
| 🟠 3 | 8 vCPU | 32 GB | 500 GB | RTX 4080/3090 (24GB) | ~3 @ 32K | 200 | ~60k | ~R$ 800 |
| 🔴 4 | 16 vCPU | 64 GB | 1 TB | RTX Pro 6000 (128GB) | ~25 @ 32K | 500+ | ~300k | ~R$ 3.000+ |

\* Acessos simultâneos = requisições que a GPU atende **ao mesmo tempo** (KV cache, modelo 8B Q4, fp16). Excedente **espera na fila do vLLM** — não falha.

> **Nota:** o maior gargalo não é o hardware — é o **LLM local** sem GPU. Um modelo 8B em CPU gera 5-15 tok/s. Uma resposta de 300 tokens leva 20-60 segundos. Para produção com muitos usuários, **GPU é essencial** (via vLLM).

### Capacidade de acessos simultâneos (KV cache)

Cada conversa ativa consome memória de **KV cache** na GPU. A conta (fp16):

```
KV por token = 2 × camadas × KV heads × head_dim × 2 bytes
Slots        = (VRAM − pesos − overhead) / (KV por token × contexto médio)
```

Custo de contexto por modelo (fp16):

| Modelo | KV/token | 8K ctx | 32K ctx | 128K ctx |
|:-------|:---------|:-------|:--------|:---------|
| 8B (Llama 3.1) | 128 KB | 1,0 GB | 4,2 GB | 16,8 GB |
| 14B (Qwen 2.5) | 192 KB | 1,5 GB | 6,3 GB | 25,2 GB |
| 32B (Qwen 2.5) | 256 KB | 2,1 GB | 8,4 GB | 33,6 GB |
| 70B (Llama 3.3) | 320 KB | 2,6 GB | 10,5 GB | 42,0 GB |

Slots simultâneos por GPU (modelo Q4, KV em fp16, overhead ~10% VRAM + 2GB, valores arredondados):

| GPU (VRAM) | 8B | 14B | 32B | 70B |
|:-----------|:---|:----|:----|:----|
| RTX 4060 (8GB) | 1 @ 8K | — | — | — |
| RTX 4060 Ti (16GB) | 7 @ 8K / 1 @ 32K | 2 @ 8K | — | — |
| RTX 4080/3090 (24GB) | 13 @ 8K / 3 @ 32K | 6 @ 8K / 1 @ 32K | — | — |
| RTX Pro 6000 (128GB) | 103 @ 8K / 25 @ 32K / 6 @ 128K | 66 @ 8K / 16 @ 32K / 4 @ 128K | 44 @ 8K / 11 @ 32K / 2 @ 128K | 27 @ 8K / 6 @ 32K / 1 @ 128K |

Exemplo (RTX Pro 6000 128GB): 100 requisições chegando juntas, modelo 8B Q4 — ~25 atendem em paralelo com contexto médio 32K e ~75 esperam na fila do vLLM; com contexto 128K cheio, ~6 atendem. O vLLM **não rejeita** — enfileira e atende conforme os slots liberam (limite de fila configurável).

Multiplicadores: KV cache em **FP8 dobra os slots**; contexto 32K (típico de RAG) rende 4-5x mais que 128K cheio. Modelo 70B Q4 **não cabe** em GPU de 24GB — só os pesos usam ~41GB.

### Capacidade de registros (SQLite)

Cada chamada de agente grava ~3 linhas: `tracing` + `uso_tokens` + `auditoria`. Com a retenção LGPD ativa (Configurações → LGPD; desligada por padrão), as tabelas são estáveis:

| Tabela | Retenção padrão | Tier 4 (100k queries/dia) |
|:-------|:----------------|:--------------------------|
| auditoria | 90 dias | ~9M linhas máx |
| tracing | 180 dias | ~18M linhas máx |
| uso_tokens | 180 dias (segue tracing) | ~18M linhas máx |
| metricas_diarias | sem retenção (agregado diário) | ~365 linhas/ano por agente+modelo |
| memories | 365 dias | conforme uso |

SQLite em modo **WAL** com índices em `criado_em` (tracing/feedback/auditoria) lê e filtra esse volume sem problema — point lookup + range por data. O limite real do SQLite **não é tamanho, é multi-writer**: 2+ processos gravando o mesmo arquivo. O desenho atual (1 portal + gateway stateless de leitura) não cruza esse limite. Se um dia houver 2+ réplicas do portal, **aí sim** PostgreSQL passa a fazer sentido — estudo de migração escopado, não reescrita.

### Limpeza e arquivo morto

Existem duas formas de controlar o crescimento — manuais e com critérios diferentes:

**1. Arquivo morto (tela Arquivo Morto, menu Operação — somente admin):** gera um snapshot selado do banco (`data/arquivo_morto/arquivo_morto_<execução>_<corte>.db` — primeira data = execução, segunda = corte) e remove do banco quente os registros com `criado_em <= corte`. Corte máximo = **ontem à meia-noite** (o dia corrente nunca é afetado). O fluxo pede confirmação mostrando as contagens antes de executar — **incluindo a confirmação de que o backup físico do portal.db foi feito** (o snapshot não substitui o backup); a cópia é feita antes do DELETE (falha na cópia = nada é apagado). Backup físico do banco principal é responsabilidade do cliente (volume).

| Tabela | Campo do corte | Critério |
|:-------|:---------------|:---------|
| tracing | criado_em | idade (≤ corte) |
| uso_tokens | criado_em | idade (≤ corte) |
| auditoria | criado_em | idade (≤ corte) |
| memories | criado_em | idade (≤ corte) |
| feedback | criado_em | idade (≤ corte) |
| teste_ab | criado_em | idade (≤ corte) |
| knowledge | acessos / ultimo_acesso | fonte importada (csv/pdf/...) **e** sem uso recente (`acessos = 0` ou `ultimo_acesso ≤ corte`) — fontes `manual` e `skill` (regras) nunca são afetadas |

Nunca entram: `metricas_diarias` (agregado perpétuo) e dados mestres (clientes, usuarios, agentes, modelos, skills, conectores, canais, áreas, api_keys, configs). Cada execução — sucesso **ou falha** — fica no histórico da tela (execução, corte, arquivo, movidos) **e na Auditoria** (menu Operação, `acao=arquivo_morto`: usuário, corte, arquivo, total movido). Snapshot duplicado no mesmo dia/corte é rejeitado (nada é sobrescrito).

**2. Limpeza automática (tela LGPD):** opcional (`retencao_auto`), roda a cada hora e faz **DELETE físico** com retenções configuráveis (auditoria 90d, tracing/uso_tokens 180d, memórias 365d). Desligada por padrão — só ativa se o cliente quiser descartar sem snapshot.

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
