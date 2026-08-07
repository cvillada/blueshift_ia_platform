# 📘 Documentação BlueShift IA Platform (Portal BlueShift)

> Documentação funcional completa do sistema — telas, campos, fluxos e API.
> Fonte: código real (blueshift_layer/) em 2026-08-06. Versão: 0.9.3.
> Exemplos de preenchimento são FICTÍCIOS (nunca dados reais de cliente).

---

## 1. Visão Geral

A BlueShift IA Platform é uma plataforma de IA **on-premise** (instalada dentro
da infraestrutura do cliente): dados, agentes, memória e histórico ficam 100%
no ambiente do cliente. Aplicação Python pura (Flask + SQLite), sem dependência
externa de motor de IA — os modelos podem ser locais (vLLM, LM Studio, Ollama)
ou externos (OpenAI, DeepSeek, OpenRouter) via API compatível com OpenAI.

Componentes principais:

| Componente | Função |
|:-----------|:-------|
| **Portal do Cliente** | Interface web (Camada 4) para administrar e monitorar a plataforma |
| **Agentes** | Orquestradores por área (vendas, suporte, financeiro, RH, operações) |
| **Conectores** | Fontes externas: API REST, servidores MCP (stdio/SSE), SQL (PG/MySQL/SQL Server/Oracle) |
| **RAG / Memória** | Base de conhecimento vetorial local (TF-IDF + similaridade cosseno) |
| **Skills** | Instruções de comportamento (SKILL.md) que guiam os agentes |
| **Canais** | Integração máquina-a-máquina com token próprio (API/webhook) |
| **Gateway** | OpenAI-compatível para chats externos (Open WebUI, apps) — porta 9003 |
| **Licença** | Validação por chave anual; offline (servidor mock incluso) |

---

## 2. Arquitetura

```
                    ┌─────────────────────┐
                    │   CLI (blueshift)    │  init · portal · mcp · status · update
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  🌐 PORTAL (Flask)   │  create_app() → porta 8080 (Docker: 8090)
                    └──────────┬──────────┘
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
             └──────────┘     └──────────┘
```

Módulos principais (blueshift_layer/):

| Arquivo | Responsabilidade |
|:--------|:-----------------|
| `portal/__init__.py` | App factory, CSRF global, CORS, retenção automática (LGPD) |
| `portal/views.py` | Todas as rotas/telas do portal (58 rotas) |
| `portal/db.py` | Acesso a dados (SQLite), migrações, seed demo, 23 tabelas |
| `portal/auth.py` | RBAC (login_required, admin_required, api_key_required) + rate limit |
| `portal/templates.py` | Layout (sidebar, temas claro/escuro/sistema), helpers HTML |
| `portal/agente.py` | Orquestrador: conectores → RAG → LLM → resposta |
| `portal/llm_client.py` | Cliente OpenAI-compatível (urllib puro) com fallback |
| `portal/memory.py` | Vetor TF-IDF (RAG) + busca por similaridade |
| `portal/mask.py` | Mascaramento LGPD (CPF, e-mail, telefone, nome, endereço, CNPJ) |
| `portal/sso.py` | Login federado OIDC |
| `connector_pack/registry.py` | Execução de conectores (API/MCP/SQL) |
| `license_client.py` | Validação de licença |
| `update_client.py` / `update_server.py` | Canal de atualizações aprovadas |

---

## 3. Como Executar

### 3.1 Local (desenvolvimento)

```bash
# ambiente virtual
python -m venv bp-venv && source bp-venv/bin/activate
pip install -e .

# sobe o portal (padrão: 0.0.0.0:8080)
blueshift portal

# ou com host/porta customizados
blueshift portal --host 0.0.0.0 --port 8080 --debug
```

O primeiro boot cria o banco `data/portal.db` e semeia o demo
(1 cliente, 5 usuários, 5 agentes, modelos e conectores de exemplo).

### 3.2 Docker (produção / entrega)

```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker volume create blueshift_data
docker run -d --name blueshift-platform -p 8090:8080 \
  -v blueshift_data:/data/blueshift \
  -e BLUESHIFT_PORTAL_DB=/data/blueshift/portal.db \
  -e BLUESHIFT_LICENSE=BS-DEV-teste123 \
  blueshift/platform blueshift portal
```

Ou via docker-compose (com `BLUESHIFT_AREAS` e `TZ=America/Sao_Paulo`):
```bash
docker compose up -d --build
```

Acesso: `http://localhost:8090/portal/login`

### 3.3 Variáveis de ambiente

| Variável | Padrão | Efeito |
|:---------|:-------|:-------|
| `BLUESHIFT_PORTAL_DB` | `data/portal.db` | Caminho do banco SQLite |
| `BLUESHIFT_PORTAL_SECRET` | aleatório | Secret key das sessões |
| `BLUESHIFT_PORTAL_SECURE` | vazio | `1/true` → cookie Secure (HTTPS) |
| `BLUESHIFT_AREAS` | vendas,suporte,financeiro,rh,operacoes | Áreas disponíveis |
| `BLUESHIFT_LICENSE` | vazio | Chave de ativação da instalação (validada no boot) |
| `BLUESHIFT_LICENSE_URL` | localhost:9000 | URL de validação de licença |
| `BLUESHIFT_UPDATE_URL` | localhost:9001 | Canal de atualização aprovado |
| `BLUESHIFT_ROUTER_MODEL` | vazio | Modelo de ROTEAMENTO dos conectores: **ID ou NOME** do modelo (o nome é o que aparece na tela Modelos IA, que também exibe o ID); vazio = modelo principal de cada agente; recomendado modelo local rápido (hermes-3-llama-3.1-8b) |
| `GATEWAY_PORT` | 9003 | Porta publicada do Gateway OpenAI-compatível (chats externos) |
| `GATEWAY_PUBLIC_URL` | vazio | URL pública do gateway exibida na tela (ex: `http://192.168.0.10:9003/v1`) — sem ela, usa o host da requisição. Chat externo em Docker na mesma máquina: `http://host.docker.internal:9003/v1` |
| `BLUESHIFT_SEED_DEMO` | 1 | `1` = dados demo XPTO (dev); `0` = banco limpo → primeira entrada vira Configuração inicial (cliente final) |
| `BLUESHIFT_DEV` | 1 no Docker | Modo dev (licença BS-DEV-*) |
| `TZ` | UTC | Fuso (usar `America/Sao_Paulo`) |

> O `.env.example` da raiz traz todas as variáveis com comentários — copie
> para `.env` antes de instalar. Sem Docker: `set -a; . ./.env; set +a` e
> rode `blueshift portal`.

---

## 4. Acesso e Papéis (RBAC)

| Papel | O que pode |
|:------|:-----------|
| **admin** | Tudo: CRUD completo, auditoria, observabilidade, canais, LGPD, SSO |
| **gestor** | Telas operacionais (monitorar, workspace, agentes, teste A/B) |
| **usuario** | Telas do dia a dia (workspace, chat, memória, conhecimento) |
| **sistema** | Ações via API (registrado em auditoria) |

Hierarquia: `admin > gestor > usuario > sistema`.

Tabela de permissões por rota (resumo):

| Tela | Acesso |
|:-----|:-------|
| Monitorar, Workspace, Usuários, Agentes, Skills, Uso de Tokens, Memória, Conhecimento, Chat, Teste A/B, Fine-Tuning | login_required |
| Clientes (novo/editar/suspender), Usuários (novo/editar/suspender), Agentes (novo/editar/excluir), Skills (novo/editar/excluir/gerar-ia/indexar-rag), Conectores (tudo), Modelos (tudo), Canais (tudo), Auditoria, Observabilidade, Alertas, LGPD, SSO config, Atualizações, Rastreio, Exportar JSONL | admin_required |
| API `/api/v1/agente`, `/api/v1/feedback/<id>` | token do canal (Bearer) |

---

## 5. Telas do Portal

### 5.1 Login (/portal/login)

**Propósito:** autenticar usuários do portal.

**Primeiro acesso (setup inicial):** se o banco não tem nenhum usuário admin
(instalação nova com `BLUESHIFT_SEED_DEMO=0`), a tela de login vira um
formulário de **Configuração inicial** — o cliente cadastra a própria empresa
e o administrador inicial. Depois disso, o login normal aparece. Campos:

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Nome da empresa | ✅ | `XPTO Seguros` | Nome comercial |
| Código | ✅ | `xpto` | Identificador único (minúsculas) |
| Razão social | ❌ | `XPTO Seguro S/A` | |
| E-mail de contato | ❌ | `ti@empresa.com.br` | |
| Nome do admin | ✅ | `Administrador Inicial` | |
| Login do admin | ✅ | `admin` | |
| Senha do admin | ✅ | `••••••` | Mínimo 6 caracteres |

**Login normal** (quando já existe admin):

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Login | ✅ | `admin` | Nome de usuário cadastrado |
| Senha | ✅ | `••••••` | Senha definida no cadastro |

- Botão **Entrar**: autentica e redireciona.
- Link **Entrar com SSO (OIDC)**: login federado (se configurado).
- Aviso de privacidade (LGPD) pode aparecer acima do card, se ativado nas
  configurações LGPD.
- Proteções: rate limit de 5 tentativas/min por IP (bloqueio de 15 min),
  senha com hash scrypt, CSRF no formulário.
- Botão de tema 🌙/☀️/💻 no topo direito (claro/escuro/sistema).

### 5.2 Monitorar (/portal/monitorar)

**Onde:** menu Monitorar (primeiro item da sidebar).

**Propósito:** visão geral do estado da plataforma (dashboard).

- 8 KPIs: Clientes, Usuários, Agentes, Modelos IA, Conectores, Canais,
  Tokens processados, Documentos RAG.
- Card de cada cliente: status, código, nº de agentes, chamadas LLM,
  saúde do container, latência, tokens.
- Acesso: qualquer usuário autenticado.

### 5.3 Workspace (/portal/workspace)

**Onde:** menu Workspace.

**Propósito:** ambiente de trabalho por área (vendas, suporte, financeiro...).

- KPIs do topo: agentes, usuários e documentos da base de conhecimento da
  área selecionada; filtro **Área** (todas ou uma específica).
- **Cards de agentes** da área: nome, status (ativo/pausado), modelo e
  fallback, skills e ações:
  - **testar agente**: abre o chat de teste do agente (pipeline completo
    conectores → RAG → LLM, com 👍/👎 feedback e 🔍 rastreio);
  - **fluxo**: abre o popup do **fluxo de execução** do agente (diagrama
    de fluxo horizontal, 100% offline, sem lib externa):
    `Entrada (Chat/API) → fontes de dados (conectores da área) → LLM
    (modelo + fallback) → skills (1 caixinha por skill) → Resposta →
    Envio (Chat/API)`.
    As caixinhas são **arrastáveis** (as linhas acompanham) e os dados
    são dinâmicos do agente (modelo, fallback, skills, conectores).
- Acesso: qualquer usuário autenticado.

### 5.4 Clientes (/portal/clientes)

**Onde:** Cadastros → Clientes.

**Propósito:** cadastro e gestão dos clientes (empresas contratantes).

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Código | ✅ | `xpto` | Identificador único (minúsculas/sem espaço) |
| Nome | ✅ | `XPTO Seguros (Piloto)` | Nome comercial |
| Empresa | ❌ | `XPTO Seguro S/A` | Razão social |
| Email de contato | ❌ | `ti@empresa.com.br` | E-mail do suporte técnico |
| Licença | ❌ | `BS-DEV-teste123` | Chave de licença |
| Status | ❌ | `ativo` | ativo / suspenso |

Ações na lista: **editar**, **suspender/reativar** (por cliente).
Ações admin-only. Auditoria registra criar/editar/alternar cliente.

### 5.5 Usuários (/portal/usuarios)

**Onde:** Cadastros → Usuários.

**Propósito:** gestão dos usuários com acesso ao portal.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Cliente | ✅ | XPTO Seguros (Piloto) | Já vem selecionado (primeira empresa cadastrada — on-premise) |
| Nome | ✅ | `Ana Suporte` | Nome completo |
| Login | ✅ | `ana` | Único no sistema |
| Senha | ✅ (novo) / ❌ (editar) | `••••••` | Em branco no editar = mantém atual |
| Área | ❌ | `suporte` | Área de atuação (vendas/suporte/financeiro/rh/operacoes) |
| Papel | ✅ | `usuario` | admin / gestor / usuario / sistema |

Ações na lista: **editar**, **suspender/reativar** (link de texto; quando
suspenso, o usuário não consegue logar). Auditoria registra as ações.

### 5.6 Agentes (/portal/agentes)

**Onde:** Cadastros → Agentes.

**Propósito:** criar e gerenciar os agentes de IA por área.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Cliente | ✅ | XPTO Seguros (Piloto) | Já vem selecionado (primeira empresa) |
| Nome do agente | ✅ | `Agente Vendas` | |
| Área | ✅ | `vendas` | Define quais conectores o agente enxerga |
| Modelo de IA (principal) | ✅ | `bonsai-8b` | Modelo cadastrado em Modelos IA |
| Modelo de IA (fallback) | ❌ | `hermes-3-llama-3.1-8b` | Usado se o principal falhar |
| Skills do catálogo | ❌ | vendas, suporte | Checkboxes das skills disponíveis |
| Status | ❌ | `ativo` | ativo / pausado |
| 🔒 Aplicar LGPD | checkbox | ativo por padrão | Anonimiza a resposta na saída |

Ações: **testar** (chat de teste com o pipeline completo: conectores → RAG →
LLM, com 👍/👎 feedback e 🔍 rastreio), **editar**, **excluir**.

**Checklist contextual (topo da página Agentes):** a plataforma mostra o que
o agente precisa, na ordem de configuração — `✓ Modelo IA (N)` · `Skills: N` ·
`Conectores: N`. Sem nenhum modelo cadastrado, aparece o aviso **"Comece por
aqui: cadastre um modelo em Modelos IA"** (com link) e o item vira
`✗ Modelo IA — cadastre aqui`.

**Ordem de configuração (menu Cadastros):** Clientes → Usuários → Modelos IA →
Skills → Agentes → Conectores → Canais — o menu segue a sequência de
montagem (base → modelo/skills → agente → entrega).

**Roteamento inteligente de conectores:** antes de executar os conectores
da área, uma IA curta (a mesma do agente, ou a apontada por
`BLUESHIFT_ROUTER_MODEL`) decide QUAL conector é relevante para a pergunta
— ou nenhum. Pergunta de norma/política → responde só com a Base de
Conhecimento (RAG), sem tocar nos conectores. Pergunta que cita um
conector (ex: "CEP", "hospedagem") → executa só ele. Voto majoritário de
3 tentativas; se a seleção falhar ou for ambígua, executa todos os
conectores da área (comportamento seguro — nunca deixa o agente sem
dados). A tela Atualizações mostra o modelo de roteamento e as áreas
configuradas (card "Configuração de ambiente").

**Extração de parâmetros por IA:** além do reconhecimento automático de
padrões (códigos como `C001`, `id_cliente=58`, e-mails, datas), a IA
também extrai os parâmetros da pergunta em linguagem natural (ex:
"id cliente igual a 58" → `customer_id='58'`). Vale para **todos os tipos
de conector** (API — URL/headers/body, MCP — args, SQL — WHERE), que
usam o mesmo mecanismo de placeholders `{param}`.

**Anti-alucinação:** quando os conectores retornam sem dados vivos, o
agente é instruído a NÃO inventar valores (datas, nomes, números, IDs) —
responde "não encontrei" e sugere reformular a pergunta (ex: informar
`id_cliente=58`).

**Importante:** os conectores do agente são herdados automaticamente da
**área** dele (não há mais checkboxes de ERP/CRM/RH no formulário).

### 5.7 Skills (/portal/skills)

**Onde:** Cadastros → Skills.

**Propósito:** catálogo de instruções (SKILL.md) que guiam o comportamento
dos agentes. O LLM recebe a **descrição** de cada skill no prompt do sistema.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Nome (identificador) | ✅ | `vendas` | Minúsculas, sem espaço (isidentifier) |
| Versão | ❌ | `1.0.0` | |
| Descrição | ✅ | regras de comportamento | É o que o LLM enxerga — coloque guardrails aqui |
| Conteúdo (SKILL.md body) | ✅ | corpo markdown | Instruções detalhadas |
| ✨ Gerar com IA | — | — | Botão que usa um modelo cadastrado para gerar o SKILL.md |

Ações: **editar**, **excluir** (vermelho), botão **Indexar no RAG**
(/portal/skills/indexar-rag) para a skill entrar na base de conhecimento.

**Dica (guardrails):** regras de comportamento vão na **descrição**:
```
PRIMEIRA skill.
REGRAS:
- NUNCA invente dados — use apenas os conectores
- NUNCA responda sobre RH ou politicas internas
- SEMPRE cite a fonte dos dados
```

### 5.8 Modelos IA (/portal/modelos) — cadastro de LLMs (locais e externos)

**Propósito:** cadastro dos modelos de IA (endpoints **OpenAI-compatíveis**)
que os agentes usam para responder — servidores **locais** (LM Studio,
vLLM, servidor do cliente) ou **externos** (OpenRouter, DeepSeek, OpenAI).
A plataforma é **agnóstica a provedor**: qualquer endpoint que fale o
protocolo OpenAI entra aqui.

**Como cadastrar um modelo de IA (resumo):** em Cadastros → Modelos IA →
"+ Novo modelo", preencha Nome, Endpoint (base_url), Modelo, Tipo e — se
externo — a API Key, e salve. O badge de status indica se o endpoint
respondeu (online) ou não (offline). Detalhe de cada campo abaixo.

**O que preencher em cada campo (passo a passo):**

| Campo | Obrigatório? | O que é | Exemplo |
|:------|:-----------:|:--------|:--------|
| Cliente | ✅ | Empresa dona do modelo (primeira já vem selecionada) | XPTO Seguros (Piloto) |
| Nome | ✅ | Nome de exibição — como aparece nas telas e no `BLUESHIFT_ROUTER_MODEL` | `bonsai-8b` |
| Endpoint (base_url) | ✅ | A **base** do servidor do modelo — o sistema acrescenta `/v1/chat/completions` na chamada e `/v1/models` no teste de status. ⚠️ NÃO colocar o `/chat/completions` no final (ver regra de ouro abaixo) | `http://127.0.0.1:1234` |
| Modelo | ✅ | O NOME exato do modelo dentro do servidor (o que o provedor documenta) | `bonsai-8b` ou `qwen/qwen3.7-flash` |
| Tipo | ✅ | `local` = servidor interno (sem chave) · `hibrido` = externo na nuvem (com chave) | `local` / `hibrido` |
| API Key | ❌ | Chave de autenticação — **obrigatória para externo** (OpenRouter/DeepSeek/OpenAI); deixe VAZIA para local | `sk-or-v1-...` |
| Max tokens | ❌ | Limite máximo de tokens da resposta (padrão 4096) | `4096` |
| Preço input (R$/1M tokens) | ❌ | Custo de entrada — alimenta o Cost Intelligence | `0.15` |
| Preço output (R$/1M tokens) | ❌ | Custo de saída — alimenta o Cost Intelligence | `0.60` |

**Exemplo 1 — modelo LOCAL (LM Studio no servidor do cliente):**

| Campo | Valor |
|:------|:------|
| Nome | `bonsai-8b` |
| Endpoint (base_url) | `http://127.0.0.1:1234` |
| Modelo | `bonsai-8b` |
| Tipo | `local` |
| API Key | (vazio) |

**Exemplo 2 — modelo EXTERNO (OpenRouter na nuvem):**

| Campo | Valor |
|:------|:------|
| Nome | `qwen3.7-flash` |
| Endpoint (base_url) | `https://openrouter.ai/api` |
| Modelo | `qwen/qwen3.7-flash` |
| Tipo | `hibrido` |
| API Key | `sk-or-v1-...` (a chave do OpenRouter) |

**Para que servem os modelos cadastrados:**
- Cada **Agente** escolhe o modelo via `modelo_id` (tela Montar/Editar
  agente) — pode mesclar local e externo entre agentes;
- **Roteamento de conectores**: o `BLUESHIFT_ROUTER_MODEL` (ID ou NOME)
  aponta qual modelo decide a ferramenta (recomendado: local rápido);
- **Ajuda IA** e **geração de skills** usam o modelo selecionado.

**Dica:** no Docker, `127.0.0.1`/`localhost` é traduzido automaticamente para
`host.docker.internal` (o modelo roda no HOST, fora do container).

**Regra de ouro da `base_url`:** cadastre apenas a BASE — **sem** o
`/v1` e **sem** o `/chat/completions` no final. O sistema monta sozinho:

- Chamada: `{base}/v1/chat/completions`
- Teste de status: `{base}/v1/models`

Exemplos corretos por provedor:

| Provedor | base_url correta |
|:---------|:-----------------|
| OpenRouter | `https://openrouter.ai/api` |
| DeepSeek | `https://api.deepseek.com` |
| OpenAI | `https://api.openai.com` |
| LM Studio / vLLM local | `http://127.0.0.1:1234` |

⚠️ Se a URL for cadastrada com o endpoint completo (ex:
`https://openrouter.ai/api/v1/chat/completions`), o teste de status monta
`.../chat/completions/v1/models` → 404 e o modelo aparece **offline** —
mesmo com o nome e a chave corretos. Nesse caso, edite o modelo e remova
o `/v1/chat/completions` do final.

**Status online/offline:** o badge na lista testa `{base}/v1/models` a
cada carregamento. Offline geralmente significa: (a) URL errada (regra de
ouro acima); (b) servidor local desligado; (c) chave inválida ou sem
acesso ao provedor externo.

**Perguntas frequentes (FAQ):**

- **O que devo preencher no cadastro de modelos de IA?** Nome (exibição),
  Endpoint (a base do servidor, sem `/chat/completions`), Modelo (nome
  exato no provedor), Tipo (local ou híbrido) e, para externo, a API Key.
  O resto é opcional (max tokens, preços).
- **Preciso de chave de API para modelo local?** Não — local (LM Studio,
  vLLM, servidor do cliente) roda sem chave; a chave é obrigatória só
  para modelos externos (OpenRouter, DeepSeek, OpenAI).
- **Onde acho o nome exato do modelo?** Na documentação do provedor
  (ex: `qwen/qwen3.7-flash` no OpenRouter) ou na lista do servidor local.
- **Por que o modelo aparece offline?** URL errada (regra de ouro),
  servidor local desligado, ou chave inválida/sem acesso. O teste de
  status usa `{base}/v1/models`.

### 5.9 Conectores (/portal/conectores)

**Onde:** Cadastros → Conectores.

**Propósito:** cadastro de fontes externas de dados por área. Três tipos:
**API REST**, **MCP** (stdio local ou SSE remoto) e **SQL** (banco do cliente).

Campos comuns:

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Cliente | ✅ | XPTO Seguros (Piloto) — já vem selecionado (primeira empresa) |
| Área | ✅ | `vendas` |
| Nome | ✅ | `API Câmbio` |
| Tipo | ✅ | `api` / `mcp` / `sql` |
| Descrição | ❌ | O que este conector faz |
| Finalidade do tratamento (Art. 26 LGPD) | ⚠️ se exigido | Ex: Consultar dados cadastrais para o agente de vendas |

**Tipo API REST:**

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| URL | ✅ | `https://api.exemplo.com/v1/dados` |
| Método | ✅ | `GET` / `POST` |
| Headers (JSON) | ❌ | `{"User-Agent": "Mozilla/5.0"}` (recomendado — algumas APIs bloqueiam urllib) |
| Body (JSON, só POST) | ❌ | `{"id": "{id_cliente}"}` |

**Tipo MCP:**

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Transporte | ✅ | `stdio (local)` / `SSE (remoto)` |
| Comando (stdio) | ✅ | `python /opt/blueshift/mcp_server.py` |
| URL (SSE) | ✅ | `http://servidor:8000/mcp` |
| Ferramenta (tool) | ✅ | `erp_buscar_cliente` |
| Argumentos (JSON) | ❌ | `{"id_cliente": "{id_cliente}"}` |

**Tipo SQL:**

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Driver | ✅ | PostgreSQL / MySQL / SQL Server / Oracle |
| Host | ✅ | `host.docker.internal` |
| Porta | ✅ | `5432` (PG) / `3306` (MySQL) / `1433` (SQL Server) / `1521` (Oracle) |
| Banco | ✅ | `nome_do_banco` |
| Usuário | ✅ | `usuario` |
| Senha | ✅ | `senha` |
| DSN (avançado) | ❌ | `ERP_DSN` (variável de ambiente) ou DSN direto |
| Query SQL | ✅ | `SELECT * FROM clientes WHERE id = {id_cliente}` |

Botões especiais:
- **🔌 Testar Conexão**: valida driver/host/credenciais antes de salvar.
- **🤖 Gerar Query com IA**: modal que usa um modelo cadastrado para gerar a
  query a partir de uma descrição em linguagem natural.

**Placeholders `{param}`:** a query/URL/body/args aceita placeholders que são
substituídos automaticamente por valores extraídos da pergunta do usuário:
`{id_cliente}`, `{id_colab}`, `{id_pedido}`, `{email}`, `{data}` e qualquer
`chave=valor` informado na pergunta.

Ações na lista: **editar**, **excluir** (vermelho). Coluna Heartbeat mostra o
último status de execução. Filtros por Cliente e Área.

### 5.10 Canais (/portal/canais) — cadastro da API de saída para sistemas externos

**Onde:** Cadastros → Canais. **Para que serve:** é aqui que se cadastra a
integração de SAÍDA com sistemas externos — a API que outro sistema chama
para falar com o agente, e o webhook que recebe a resposta.

**Propósito:** integração máquina-a-máquina. Cada canal tem **token próprio**
(`bs_chan_*`) para chamar a API do agente. **Página admin-only.**

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Cliente | ✅ | XPTO Seguros (Piloto) |
| Nome | ✅ | `API Vendas (Webhook)` |
| Tipo | ✅ | `API` / `Webhook` |
| Agente | ✅ | Agente Vendas |
| Webhook de saída (URL) | ❌ | `https://...` (recebe POST da resposta; bloqueia IPs internos) |
| Headers do webhook (JSON) | ❌ | `{"X-Webhook-Secret": "minha-chave"}` — para webhooks que exigem autenticação; qualquer header (X-Webhook-Secret, Authorization: Bearer ...) é enviado no POST junto com o Content-Type |

Ações na linha: **testar** (abre modal que chama a API com o token do canal —
aba 1. Agente com pergunta + resposta/modelo/tokens/webhook; aba 2. Feedback
com trace_id automático e 👍/👎), **editar**, **nova chave** (regenera token —
o anterior para de funcionar na hora), **revogar/reativar**.

**⚠️ Nunca use a chave de licença da plataforma como token de canal.**

**Webhook de saída com autenticação:** muitos webhooks reais (Slack, Zapier,
n8n, sistemas corporativos) exigem uma chave secreta. Preencha o campo
**Headers do webhook (JSON)** com o que o receptor pedir — ex:
`{"X-Webhook-Secret": "abc123"}` ou `{"Authorization": "Bearer token"}`.
O sistema envia esses headers no POST da resposta (junto com o
`Content-Type: application/json`). Evite colocar a chave na URL
(`?secret=...`) — ela vaza em logs.

### 5.11 Memória (/portal/memoria)

**Onde:** Inteligência → Memória.

**Propósito:** histórico de memória persistente por usuário/cliente — base do
contexto do agente (auto-alimentação: pergunta+resposta são salvas).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Cliente | ✅ | XPTO Seguros (Piloto) |
| Tipo | ✅ | pergunta / resposta / nota |

- Lista com paginação (10/20/50/100/200 por página).
- Acesso: login_required.

### 5.12 Conhecimento (/portal/conhecimento) — RAG

**Onde:** Inteligência → Conhecimento.

**Propósito:** base de conhecimento vetorial que complementa o contexto do
agente (fonte SECUNDÁRIA — os conectores são a fonte primária).

Criar documento (manual):

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Cliente | ✅ | XPTO Seguros (Piloto) |
| Área | ❌ | `vendas` (isola o doc na área — vazio = vale para todas) |
| Título | ✅ | `Política de reembolso` |
| Categoria | ✅ | `base_conhecimento` |
| Fonte | ❌ | `manual` |
| Conteúdo | ✅ | texto do documento |

Importações em massa:
- **CSV**: colunas `titulo`, `conteudo`, `fonte`, `area` (aceita capitalizadas).
- **PDF**: extrai texto (PyMuPDF) e quebra em chunks de 2000 caracteres
  automaticamente; PDF só de imagem não tem texto extraído.

Ações: **editar**, **excluir**, **Exportar JSONL** (formato de fine-tuning;
com anonimização LGPD se ativada). Colunas: acessos e último acesso.
Filtros por Cliente, Área, Categoria, Fonte.

### 5.13 Chat (/portal/chat)

**Onde:** Inteligência → Chat.

**Propósito:** chat de teste com qualquer modelo cadastrado (sem pipeline de
agente — LLM direto).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Modelo de IA | ✅ | bonsai-8b |
| Pergunta | ✅ | `Qual o saldo do cliente C001?` |

Mostra a resposta do modelo. Acesso: login_required.

### 5.14 Uso de Tokens (/portal/uso-tokens)

**Onde:** Operação → Uso de Tokens.

**Propósito:** consumo de tokens e custos por agente/modelo (fonte para cobrança e
monitoramento). Tabela com paginação e filtros. Acesso: login_required.

### 5.15 Auditoria (/portal/auditoria)

**Onde:** Operação → Auditoria.

**Propósito:** trilha de auditoria de todas as ações sensíveis (login, CRUDs,
testes A/B, imports, etc.).

Colunas: Usuário, Papel, Ação, Alvo, Cliente, IP, Detalhe, Quando.
- Filtro por usuário (dropdown).
- Link **🔍 Rastreio** em registros de execução de agente (abre modal com
  params, conectores, RAG, modelo, tokens e resposta).
- Paginação (padrão 50) e botão Limpar filtros.
- Retenção automática configurável (LGPD, padrão 90 dias).

### 5.16 Observabilidade (/portal/observabilidade)

**Onde:** Operação → Observabilidade.

**Propósito:** dashboard de qualidade e custo dos agentes.

- **5 KPIs**: Chamadas, Taxa de Acerto, Latência Média, Tokens, Erros
  (filtro 1d/7d/30d/90d).
- **Sparkline** de chamadas por dia.
- **Alertas ativos** (thresholds configuráveis).
- **Drift Detection**: comparação com período anterior por modelo
  (taxa de acerto ↓>10% ou latência ↑>20% = alerta).
- **Cost Intelligence**: custo estimado por modelo (tokens × preço/1M).
- **Feedback recente**: tabela com 👍/👎, tipo (manual/api) e respostas.
- Botão **Processar métricas** (agrega tracing do dia; se vazio, busca os
  últimos 7 dias).

### 5.17 Alertas (configuração) (/portal/alertas-config)

**Onde:** Configurações → Alertas.

**Propósito:** thresholds dos alertas de observabilidade (salvos no banco).

| Chave | Padrão | Descrição |
|:------|:------:|:----------|
| taxa_acerto_min | 70 | Taxa de acerto mínima (%) em 7 dias |
| latencia_max | 1000 | Latência máxima (ms) — para modelos locais considerar 5000+ |
| erros_max | 5 | Erros máximos por dia |

### 5.18 Teste A/B (/portal/teste-ab)

**Onde:** Inteligência → Teste A/B.

**Propósito:** comparar dois modelos na mesma pergunta (qualidade).
**Acesso:** usuários autenticados, mas a operação é restrita a **admin e
gestor** (validação de papel na rota).

**Passo 1 — Executar:** seleciona feedbacks recentes (checkbox) + modelo
alvo → reexecuta cada pergunta com o modelo alvo (pipeline completo do
agente; fallback usa o trace original se o agente foi excluído).

- Limite de **10 perguntas por execução** (cada uma roda o agente completo
  — conectores + RAG + LLM — e depois o juiz avalia; acima disso a espera
  fica inviável). O limite vale no cliente (JS avisa no 11º) e no servidor
  (POST com 11+ é rejeitado com aviso).
- Lista de feedbacks **paginada em 10 por página** (padrão auditoria),
  com filtro 👍 Úteis / 👎 Não úteis e navegação « ‹ 1 2 3 › ».

**Passo 2 — Analisar:** seleciona um modelo **juiz** → o juiz compara as
respostas A (original) e B (nova) e vota: **A, B ou EMPATE**, com
justificativa. Colore as células (verde = venceu, vermelho = perdeu) e exibe
badge de veredito.

**Julgamentos salvos:** cada veredito é salvo automaticamente na tabela
`teste_ab` (pergunta, respostas A/B, modelos, voto, justificativa, juiz,
quem criou, data) — vira matéria-prima para fine-tuning e benchmark.

**Exportar JSONL:** botão **📥 Exportar JSONL (N)** no topo da página
(aparece quando há julgamentos salvos). Gera `teste_ab_julgamentos_AAAAMMDD.jsonl`
com uma linha por julgamento:
`pergunta`, `resposta_original`, `resposta_novo_modelo`, `voto`,
`justificativa`, `modelo_original`, `modelo_novo`, `modelo_juiz`,
`criado_por`, `criado_em`.
- **Máscara LGPD aplicada** (CPF/email/telefone etc., conforme a tela LGPD)
  — os dados são reais e podem conter dados pessoais.
- Usos: benchmark pós-fine-tune (reexecutar as mesmas perguntas e
  comparar) ou conversão para SFT/DPO (voto vira chosen/rejected;
  descartar EMPATE).
- Auditoria registra a exportação (`teste_ab_exportar`).

- Requer 2+ modelos cadastrados com base_url válida.

### 5.19 LGPD (/portal/lgpd) — configuração das máscaras de dados pessoais

**Onde:** Configurações → LGPD (configurar as máscaras).

**Propósito:** conformidade na SAÍDA da informação (a origem/coleta é
responsabilidade do sistema conectado). Admin-only.

| Configuração | Padrão | Efeito |
|:-------------|:------:|:-------|
| Anonimizar resposta do LLM | off | Mascara a resposta visível ao usuário/API |
| Anonimizar exportação RAG | off | Mascara no JSONL exportado |
| Mask CPF | on | `123.456.789-00` → `***.789-00` |
| Mask E-mail | on | `usuario@dom.com` → `u***@dom.com` |
| Mask Telefone | on | `(11) 91234-5678` → `(11) ****-5678` |
| Mask Nome | off | `Joao Silva` → `Joao S*****` |
| Mask Endereço | off | `Rua X, 123` → `Rua X, ***` |
| Mask CNPJ | off | `11.222.333/0001-88` → `**.222.333/0001-**` |
| Aviso de privacidade no login | off | Exibe texto no login |
| Finalidade por conector | off | Exige campo finalidade no cadastro |
| Retenção automática | off | Expurgo programado (auditoria 90d, tracing 180d, memórias 365d) |

**Importante:** o tracing e a memória preservam o conteúdo ORIGINAL (para
auditoria e investigação) — a máscara é aplicada apenas na saída visível.
A retenção automática cobre o expurgo.

### 5.20 Fine-Tuning (/portal/fine-tuning)

**Onde:** Inteligência → Fine-Tuning.

**Propósito:** documentação inline sobre fine-tuning de modelos (quando fazer,
formatos GGUF/MLX/SafeTensors/AWQ/GPTQ, tipos Full FT/LoRA/QLoRA, hardware
recomendado, dados via export JSONL, serviço BlueShift). Não executa treino —
é um serviço contratado à parte.

### 5.21 Atualizações (/portal/atualizacoes) — versão e configuração de ambiente

**Onde:** Configurações → Atualizações.

**Propósito:** canal de atualizações aprovadas da plataforma. Mostra a versão
instalada e se há nova versão disponível no canal (`update_server` na porta
9001). Admin-only.

**Card "Configuração de ambiente":** exibe as configurações ativas da
instalação:
- **Modelo de roteamento configurado** — o `BLUESHIFT_ROUTER_MODEL`
  resolvido (nome + ID, ou "(não encontrado)" se a env apontar um modelo
  inexistente; vazio = modelo principal de cada agente);
- **Áreas configuradas** — a lista do `BLUESHIFT_AREAS` (ou o padrão do
  sistema). Cada linha mostra a variável de ambiente de origem.

### 5.22 SSO (OIDC) (/portal/sso/config)

**Onde:** Configurações → SSO (OIDC).

**Propósito:** login federado (Azure AD, Okta, Keycloak, Google).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| SSO ativo | checkbox | |
| Modo dev (IdP mock) | checkbox | Teste sem provedor real |
| Criar usuário automaticamente | checkbox | Se não cadastrado |
| Issuer (URL base do IdP) | ✅ | `https://login.microsoftonline.com/.../v2.0` |
| Client ID | ✅ | GUID do app |
| Client Secret | ✅ | Segredo do app |
| Redirect URI | ✅ | `http://host:8080/portal/sso/callback` |
| Domínio de admin | ❌ | `@suaempresa.com.br` (emails deste domínio viram admin) |

Fluxo: `/sso/login` → IdP → callback com `code` → troca por id_token →
validação (HMAC HS256 ou emissor) → sessão criada. Defesa CSRF via `state` +
`nonce`. Em modo dev, o token é gerado localmente (sem rede).

### 5.23 Gateway (/portal/gateway) — OpenAI-compatível para chats externos

**Onde:** Cadastros → Gateway.

**Propósito:** conecta **chats externos** (Open WebUI, LibreChat, apps
custom, OpenAI SDK/LangChain) à plataforma falando o **protocolo padrão
OpenAI** (`/v1/chat/completions`). O gateway repassa a pergunta ao agente
via **API do canal** (token próprio) — com todo o pipeline (roteamento de
conectores, skills, RAG, LGPD). O gateway sobe junto com a plataforma
(container irmão no mesmo compose, porta 9003).

**Como ativar (passo a passo):**
1. Crie um canal na tela Canais apontando para o agente desejado (ex:
   Agente Vendas) e copie o token `bs_chan_*`;
2. Cadastros → Gateway → **Ativar gateway**: Nome, Canal vinculado,
   Modo de resposta (`Resposta completa` ou `Streaming`) e salvar;
3. No chat externo (ex: Open WebUI → Configurações → Conexões → OpenAI
   API): API URL = `http://<servidor>:9003/v1` · API Key = **o token do
   canal** · Model = `agente:<nome do agente>` (lista em `/v1/models`).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Nome | ✅ | `Gateway Vendas (Open WebUI)` |
| Canal vinculado | ✅ | `API Vendas` (o token autentica o chat externo) |
| Modo de resposta | ✅ | `completa` (JSON) / `streaming` (SSE) |
| Máx. mensagens de contexto | ❌ | `6` (últimas N mensagens enviadas ao agente) |
| Limite de contexto (tokens, aprox.) | ❌ | `400` (~4 chars = 1 token; corta as mensagens mais antigas primeiro) |
| Gateway ativo | ❌ | checkbox (pausa/reativa o endpoint) |

- **Streaming**: o canal devolve a resposta completa; o gateway a envia
  em chunks (SSE) — efeito de digitação no chat externo (streaming
  simulado; latência total igual).
- **Contexto da conversa**: o gateway repassa as mensagens anteriores do
  chat no campo `contexto` da API — o LLM entende referências ("e o
  dele?") sem repetir o ID. O trabalho de enviar o histórico é do
  sistema solicitante (Open WebUI já o faz). A memória e o RAG gravam
  apenas a última pergunta/resposta real (sem o contexto concatenado).
  Limites configuráveis por gateway (tela): **máx. mensagens** (padrão
  6) e **orçamento em tokens** (padrão 400 — ~4 chars = 1 token; as
  mensagens mais RECENTES entram primeiro, as antigas são cortadas).
- **Segurança**: o `Authorization` do chat externo precisa ser o token de
  um canal com gateway ATIVO (`Bearer bs_chan_*`) — o `model` escolhe o
  agente; o token valida a autenticação. Token inválido ou de canal sem
  gateway ativo → 401. (O Open WebUI usa uma conexão = uma chave para
  vários modelos — qualquer chave de gateway ativo funciona para todos.)
- Endpoint exibido na tela: `http://<host>:9003/v1` (ou `GATEWAY_PUBLIC_URL`
  se definida). Chat externo em Docker na mesma máquina: use
  `http://host.docker.internal:9003/v1` (`host.docker.internal` é o caminho
  do host visto de dentro do Docker).
- **Rodar sem Docker (SO direto):** o gateway é um comando da CLI como o
  portal — `set -a; . ./.env; set +a` + `blueshift gateway --port 9003`
  (com `GATEWAY_PORTAL_URL` apontando para o portal, ex:
  `http://localhost:8080`).

Exemplo de chamada (formato OpenAI):

```bash
curl -X POST http://localhost:9003/v1/chat/completions \
  -H "Authorization: Bearer bs_chan_xxx" \
  -H "Content-Type: application/json" \
  -d '{"model": "agente:Agente Vendas",
       "messages": [{"role": "user", "content": "Qual o saldo do cliente C001?"}]}'
```

---

## 6. API de Canal (integração máquina-a-máquina)

### 6.1 Chamar o agente

```
POST /portal/api/v1/agente
Authorization: Bearer <TOKEN_DO_CANAL>
Content-Type: application/json

{"pergunta": "Qual o histórico do cliente C001?"}
```

Resposta (JSON limpa — sem contexto/ferramentas):

```json
{
  "ok": true,
  "resposta": "...",
  "pergunta": "...",
  "agente": "Agente Vendas",
  "modelo": "bonsai-8b",
  "feedback_url": "http://localhost:8080/portal/api/v1/feedback/123",
  "erro": null,
  "tokens": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
  "tempo_ms": 1542,
  "webhook": {"enviado": true, "status": 200}
}
```

- Campos opcionais no body: `usuario` (máx 40 chars), `id_cliente`,
  `contexto` (mensagens anteriores da conversa — entram SÓ no prompt do
  LLM para manter o contexto; a memória/trace gravam apenas a pergunta
  real). Ex:
  ```json
  {"pergunta": "e o aluguel anterior dele?",
   "contexto": "usuario: qual o ultimo aluguel do id_cliente=30\nassistente: foi RIDGEMONT SUBMARINE."}
  ```
- Erros: 401 (token ausente/inválido), 400 (sem pergunta), 404 (agente).
- Rate limit: 100 req/min por token.
- Se o canal tiver webhook de saída, a resposta também é POSTada lá
  (retry exponencial 2s/4s, best-effort). O campo `webhook` da resposta
  informa o resultado do envio (`{"enviado": false, "motivo": ...}` se
  falhou — não quebra a resposta da API). Headers extras configurados no
  canal (ex: `X-Webhook-Secret`) são enviados no POST.

### 6.2 Enviar feedback

```
POST /portal/api/v1/feedback/<trace_id>
Content-Type: application/json

{"util": true, "tipo": "api"}
```

Resposta: `{"ok": true, "feedback_id": 1}` — ou 404 se o trace não existir.
O `tipo` diferencia manual (UI) de api (curl/integração).

---

## 7. Conectores — como funcionam

1. O usuário faz uma pergunta ao agente.
2. **Roteamento inteligente**: uma IA curta (a do agente, ou a de
   `BLUESHIFT_ROUTER_MODEL`) decide QUAIS conectores da área executar —
   ou nenhum (pergunta de norma/política responde só com a base RAG).
   Voto majoritário de 3 tentativas; falha/ambiguidade → executa todos
   (seguro). Detalhes na §5.6.
3. `_extrair_parametros()` extrai automaticamente: códigos (`C001`,
   `PED-99`), e-mails, datas, `chave=valor`, números após palavras-chave.
   A **IA complementa** o que o regex não reconheceu (linguagem natural:
   "id cliente igual a 58" → `{id_cliente} = 58`).
4. Os conectores escolhidos são executados (tolerante a falhas — um
   conector com erro não derruba os outros; heartbeat atualizado).
5. Placeholders `{param}` são substituídos pelos valores extraídos.
6. Resultados viram o contexto do prompt (FONTE PRIMÁRIA).
7. **Anti-alucinação**: se os conectores rodarem sem dados vivos, o
   agente é instruído a NÃO inventar valores — responde "não encontrei"
   e sugere reformular (ex: informar `id_cliente=58`).

Extração de parâmetros (exemplos):

| Pergunta | Parâmetros extraídos |
|:---------|:---------------------|
| `cliente id 3` | `{id_cliente} = 3` |
| `PED-99` | `{id_pedido} = PED-99` |
| `FUNC42` | `{id_func} = FUNC42` |
| `user@email.com` | `{email} = user@email.com` |
| `2026-07-22` | `{data} = 2026-07-22` |
| `rental_id=10437` | `{rental_id} = 10437` |
| `title='RACER EGG'` | `{title} = RACER EGG` |

Se nenhum parâmetro for encontrado, o placeholder fica literal (e o banco
retorna vazio — honesto, sem forçar valor padrão).

---

## 8. Fluxo do Agente e RAG

Hierarquia no `agente.responder()`:

1. **Conectores da área (selecionados por IA)** — o roteamento escolhe
   quais executar (ou nenhum); executa SQL/API/MCP com os parâmetros
   extraídos (regex + IA).
2. **RAG complementar** — sempre busca na base (top_k=2 se conectores ok,
   top_k=4 se não).
3. **LLM** — prompt com skills (descrições) + dados dos conectores + contexto
   RAG. Prioriza dados do conector (fonte primária) sobre RAG (secundária).

Detalhes:
- **Auto-alimentação**: pergunta+resposta são salvas na memória (sempre) e no
  knowledge base (dedup TF-IDF).
- **Isolamento por área**: docs RAG com `area` definida só aparecem para a
  mesma área; docs sem área valem para todas.
- **Filtro por cliente**: contexto RAG é filtrado pelo `id_cliente` da
  pergunta quando encontrado.
- **Fallback de modelo**: se o modelo principal falhar, usa o secundário.
- **Tracing**: cada execução gera um trace completo (params, conectores, RAG,
  modelo, tokens, resposta, tempo_ms) — visível na auditoria via 🔍 Rastreio.
- **LGPD**: se ativado, a resposta é mascarada na saída (o trace guarda o
  original para auditoria).

---

## 9. Segurança (implementado)

| Item | Detalhe |
|:-----|:--------|
| Senhas | Hash **scrypt** (stdlib) + migração automática de legado |
| Secret key | `BLUESHIFT_PORTAL_SECRET` ou aleatória por boot |
| SQL injection | Queries parametrizadas (?) + whitelist de colunas em updates |
| CSRF | Token em todos os formulários + validação global (exceto rotas `/portal/api/*` e exceções nomeadas) |
| Rate limit | Login 5/min/IP (bloqueio 15 min); API 100/min/token |
| Sessão | HttpOnly, SameSite=Lax, timeout 30 min, Secure condicional |
| XSS | `templates.h()` (html.escape) nos valores dinâmicos |
| Path traversal | Skills validam nome com `isidentifier()` |
| Webhook SSRF | Bloqueia localhost, 10.x, 172.16.x, 192.168.x |
| MCP traceback | Mensagem genérica (sem detalhes de exceção) |
| Erros LLM | Mensagem amigável, sem stack trace |

---

## 10. Banco de Dados (SQLite)

23 tabelas principais:

| Tabela | Conteúdo |
|:-------|:---------|
| clientes | Empresas contratantes |
| usuarios | Usuários do portal (papel, área, ativo) |
| agentes | Agentes por área (modelo principal/secundário, skills) |
| conectores | Fontes externas (config JSON, área, finalidade) |
| health | Saúde do container por cliente |
| uso_tokens | Consumo de tokens por execução |
| contratos | Contratos/licença |
| skills | Skills persistentes (dual-write com arquivo) |
| tracing | Execuções completas (rastreio) |
| auditoria | Trilha de ações sensíveis |
| feedback | Avaliações 👍/👎 (tipo manual/api) |
| metricas_diarias | Agregações diárias (observabilidade) |
| alertas_config | Thresholds de alerta |
| custos_modelo | Preços por modelo |
| memories | Memória persistente (auto-alimentação) |
| knowledge | Base RAG (docs, área, acessos) |
| modelos | Modelos OpenAI-compatíveis |
| api_keys | Chaves de API (legado) |
| canais | Canais de integração (token próprio) |
| gateway_config | Gateways OpenAI-compatíveis (canal vinculado, modo streaming/completa) |
| sso_config | Configuração OIDC |
| lgpd_config | Configurações LGPD (chave/valor) |
| teste_ab | Julgamentos do Teste A/B (pergunta, respostas A/B, voto, justificativa, modelos) |

Índices nas tabelas mais consultadas (auditoria, memories, knowledge).
Backup: copiar o arquivo `portal.db` (o volume Docker `blueshift_data`
persiste entre rebuilds).

---

## 11. CLI

| Comando | Descrição |
|:--------|:----------|
| `blueshift init <cliente>` | Cria profile de cliente |
| `blueshift activate <chave>` | Valida licença |
| `blueshift status` | Estado do container |
| `blueshift update` | Checa atualizações aprovadas |
| `blueshift portal [--host --port --debug]` | Sobe o portal |
| `blueshift mcp` | Sobe o servidor MCP stdio |

---

## 12. Perguntas Frequentes

**O modelo local não responde (erro de conexão)?**
Confirme que o LM Studio/vLLM está rodando no host e que a `base_url` do
modelo está correta. No Docker, `127.0.0.1` vira `host.docker.internal`.

**Posso misturar modelo local e externo?**
Sim — cada agente define o próprio `modelo_id`; a plataforma é agnóstica a
provedor (qualquer endpoint OpenAI-compatível).

**O agente responde "como se fosse outra área"?**
Verifique se o documento RAG tem `area` definida — docs sem área participam
de todas as áreas. Use o isolamento por área para evitar contaminação.

**Onde vejo o detalhamento de uma resposta (conectores, RAG, tokens)?**
Na página Auditoria, clique em **🔍 Rastreio** ao lado do registro.

**Como medir se os modelos estão bons?**
Observabilidade (taxa de acerto, drift, custos) + Teste A/B com modelo juiz.

**Perdi o token de um canal?**
Use **nova chave** na página Canais — o token anterior para de funcionar
imediatamente.

**Meu webhook de saída exige uma chave secreta — o que faço?**
Preencha o campo **Headers do webhook (JSON)** do canal com o que o
receptor pedir: `{"X-Webhook-Secret": "abc"}` ou
`{"Authorization": "Bearer token"}`. Esses headers são enviados no POST
da resposta (não coloque a chave na URL — vaza em logs).

**Criei uma skill, mas ela não aparece nas telas (Skills/Agentes)?**
Skills criadas pela UI ficam no banco (persistem entre rebuilds do
container). Se a lista não mostra, recarregue a página. O catálogo
embarcado (template_skills/) é a base inicial; o banco domina por nome
quando os dois existem.

**Dados pessoais aparecem nas respostas?**
Ative as máscaras LGPD (tela LGPD). A saída é mascarada; o trace preserva o
original para auditoria (com retenção automática).

---

*Documentação gerada a partir do código (2026-08-05). Em caso de divergência
entre este documento e o comportamento real, o código é a fonte da verdade —
atualize este arquivo na mesma entrega da mudança.*
