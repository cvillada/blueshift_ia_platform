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
| **Licença** | Anual por empresa — chave de ativação emitida pela BlueShift (cadastro da empresa); validação online contra o License Server BlueShift em produção |

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
| `portal/views.py` | Todas as rotas/telas do portal (60+ rotas) |
| `portal/db.py` | Acesso a dados (SQLite), migrações, seed demo, 24 tabelas |
| `portal/auth.py` | RBAC (login_required, admin_required, api_key_required) + rate limit |
| `portal/templates.py` | Layout (sidebar, temas claro/escuro/sistema), helpers HTML |
| `portal/agente.py` | Orquestrador: conectores → RAG → LLM → resposta |
| `portal/llm_client.py` | Cliente OpenAI-compatível (urllib puro) com fallback |
| `portal/memory.py` | Vetor TF-IDF (RAG) + busca por similaridade |
| `portal/mask.py` | Mascaramento LGPD (CPF, e-mail, telefone, nome, endereço, CNPJ) |
| `portal/sso.py` | Login federado OIDC |
| `connector_pack/registry.py` | Execução de conectores (API/MCP/SQL) |
| `license_client.py` | Validação de licença |
| `update_client.py` / `update_server.py` | Update via Git (tags) — update_client é o mecanismo; update_server é legado (mock de canal HTTP, não usado na tela) |

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

> **🔑 Antes de instalar em produção, solicite a chave de ativação** —
> cadastro da empresa (razão social, CNPJ e contato) → chave emitida na hora:
> **https://static.190.55.99.91.clients.your-server.de:9096/**
> (chave `BS-DEV-*` só vale em dev; produção sem chave real = não ativada).

```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker volume create blueshift_data
docker run -d --name blueshift-platform -p 8090:8080 \
  -v blueshift_data:/data/blueshift \
  -e BLUESHIFT_PORTAL_DB=/data/blueshift/portal.db \
  -e BLUESHIFT_LICENSE=SUA-CHAVE-DA-BLUESHIFT \
  blueshift/platform blueshift portal
```

> Em produção a validação é online contra o License Server da BlueShift:
> defina também `BLUESHIFT_LICENSE_URL=<url-da-pagina-de-solicitacao>/v1/validate`
> no `.env` (o default aponta para o mock local, que só conhece chaves de dev).

Ou via docker-compose (com `BLUESHIFT_AREAS` e `TZ=America/Sao_Paulo`):
```bash
docker compose up -d --build
```

> **Update via Git:** o compose monta o repositório (padrão: o próprio
> diretório do compose; em produção, um clone em `/opt/blueshift/repo`)
> e o `docker.sock` do host no container do portal — a tela
> Configurações → Atualizações lê a versão do repo e dispara o rebuild
> (dados preservados).

Acesso: `http://localhost:8090/portal/login`

### 3.3 Variáveis de ambiente

| Variável | Padrão | Efeito |
|:---------|:-------|:-------|
| `BLUESHIFT_PORTAL_DB` | `data/portal.db` | Caminho do banco SQLite |
| `BLUESHIFT_PORTAL_SECRET` | aleatório | Secret key das sessões |
| `BLUESHIFT_PORTAL_SECURE` | vazio | `1/true` → cookie Secure (HTTPS) |
| `BLUESHIFT_AREAS` | vendas,suporte,financeiro,rh,operacoes | **Seed inicial** das áreas — depois a tela Cadastros → Áreas domina (banco) |
| `BLUESHIFT_LICENSE` | vazio | **Chave de ativação emitida pela BlueShift** (cadastro da empresa — link na seção de instalação/licença deste documento); vazio = não ativada. `BS-DEV-*` só com `BLUESHIFT_DEV=1` |
| `BLUESHIFT_LICENSE_URL` | localhost:9000 | URL de validação de licença — produção/cliente: License Server da BlueShift (`<url-da-pagina-de-solicitacao>/v1/validate`); default = mock local (só dev) |
| `BLUESHIFT_REPO_DIR` | /opt/blueshift/repo | Diretório do clone git (Update via Git — tela Atualizações) |
| `BLUESHIFT_ROUTER_MODEL` | vazio | Modelo de **ROTEAMENTO** (ver §5.8 — modelo de roteamento): **ID ou NOME** do modelo (o nome é o que aparece na tela Modelos IA, que também exibe o ID); vazio = modelo principal de cada agente (**não recomendado** — encarece toda pergunta). Regra: **pequeno, inteligente e rápido** (INSTRUCT, nunca reasoning). Exemplos: `qwen3-4b-instruct-2507` (validado em produção) e `hermes-3-llama-3.1-8b` |
| `GATEWAY_PORT` | 9003 | Porta publicada do Gateway OpenAI-compatível (chats externos) |
| `GATEWAY_PUBLIC_URL` | vazio | URL pública do gateway exibida na tela (ex: `http://192.168.0.10:9003/v1`) — sem ela, usa o host da requisição. Chat externo em Docker na mesma máquina: `http://host.docker.internal:9003/v1` |
| `BLUESHIFT_PORTAL_SECRET` | vazio | Chave da SESSÃO do portal — deve ser **FIXA entre deploys** (sem ela, cada rebuild gera uma chave nova e derruba todos os logins; usuário logado cai com redirecionamento para o login no próximo clique). Trocar em produção e manter estável |
| `BLUESHIFT_SEED_DEMO` | 1 | `1` = dados demo XPTO (dev); `0` = banco limpo → primeira entrada vira Configuração inicial (cliente final) |
| `BLUESHIFT_DEV` | 0 | **Produção/cliente = 0** (a tela Atualizações aplica de verdade; chaves `BS-DEV-*` NÃO valem); dev = 1 (dry-run + licença BS-DEV-*) |
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
| Monitorar, Workspace, Docs, Usuários, Agentes, Skills, Uso de Tokens, Memória, Conhecimento, Chat, Teste A/B, Fine-Tuning | login_required |
| Clientes (novo/editar/suspender), Usuários (novo/editar/suspender), Áreas (tudo), Agentes (novo/editar/excluir), Skills (novo/editar/excluir/gerar-ia/indexar-rag), Conectores (tudo), Modelos (tudo), Canais (tudo), Auditoria, Observabilidade, Alertas, LGPD, SSO config, Atualizações, Rastreio, Exportar JSONL | admin_required |
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
| Senha do admin | ✅ | `••••••` | Mínimo 8 caracteres |

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
- **Tokens por agente** nos cards: total de tokens consumidos no período
  (formato compacto — `682k`), com seletor igual da Observabilidade
  [`1d | 7d | 30d | 90d`]; fonte = `uso_tokens.agente_id` → `agentes.area`
  (registros sem agente, chat de teste puro, ficam de fora).
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
| Licença | ❌ | `BS-2026-XXXX` | Chave de ativação emitida pela BlueShift |
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

### 5.5-A Áreas (/portal/areas)

**Onde:** Cadastros → Áreas.

**Propósito:** cadastro dos departamentos da empresa (vendas, suporte,
financeiro, RH, operações...). As áreas alimentam o Workspace, os agentes,
os conectores, os documentos RAG e o campo "Área" dos usuários.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Nome | ✅ | `vendas` | Minúsculas, sem espaços (padrão de identificador) |

- **Fonte dos dados:** o cadastro vive no BANCO (tabela `areas`). A
  variável `BLUESHIFT_AREAS` do ambiente serve apenas como **seed inicial**
  do primeiro boot — depois disso a tela domina (criar/renomear/excluir
  não exige rebuild nem mexer em `.env`).
- A lista mostra a **contagem de uso** (usuários, conectores e documentos
  da área).
- **Renomear/excluir não altera registros existentes** — eles mantêm o
  texto da área no registro; apenas os seletores passam a usar o nome novo
  (ou deixam de oferecer a área excluída). Excluir todas as áreas faz o
  sistema voltar ao seed padrão (nunca fica vazio).
- Auditoria registra criar/editar/excluir área.

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
`BLUESHIFT_ROUTER_MODEL` — ver §5.8, "Modelo de roteamento") decide QUAL
conector é relevante para a pergunta
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
dos agentes. O LLM recebe a **descrição** e o **corpo** de cada skill ANEXADA
ao agente no prompt do sistema — desde v0.10.16 (corpo limitado a 4.000
caracteres por skill; regras de formato/comportamento escritas no corpo são
enviadas e devem ser seguidas).

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Nome (identificador) | ✅ | `vendas` | Minúsculas, sem espaço (isidentifier) |
| Versão | ❌ | `1.0.0` | |
| Descrição | ✅ | regras de comportamento | Enviada SEMPRE ao LLM — guardrails aqui |
| Conteúdo (SKILL.md body) | ✅ | corpo markdown | Instruções detalhadas — enviado ao LLM (até 4.000 chars) |
| ✨ Gerar com IA | — | — | Botão que usa um modelo cadastrado para gerar o SKILL.md |

Ações: **editar**, **excluir** (vermelho), botão **Indexar no RAG**
(/portal/skills/indexar-rag) para a skill entrar na base de conhecimento.

**Dica (guardrails):** regras de comportamento vão na **descrição** (vai
sempre, sem corte) ou no **corpo** (vai até 4.000 chars). Exemplo:
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
| Modo da API | ✅ | `openai_chat` (padrão — o sistema acrescenta `/v1/chat/completions`) · `responses` (OpenAI Responses: posta **direto** na base_url cadastrada — para agentes externos como Oracle AIDP `/chat`) | `openai_chat` |
| API Key | ❌ | Chave de autenticação — **obrigatória para externo** (OpenRouter/DeepSeek/OpenAI); deixe VAZIA para local | `sk-or-v1-...` |
| Max tokens | ❌ | Limite máximo de tokens da resposta (padrão 4096) | `4096` |
| Temperatura | ❌ | Criatividade da resposta (0.0 = determinístico, 1.0 = criativo; padrão 0.3). O roteador de conectores e o extrator de parâmetros usam 0.0 sempre | `0.3` |
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
- **Roteamento** (`BLUESHIFT_ROUTER_MODEL`) — ver o bloco abaixo;
- **Ajuda IA** e **geração de skills** usam o modelo selecionado.

#### Modelo de roteamento (`BLUESHIFT_ROUTER_MODEL`) — o que ele faz e qual usar

A plataforma tem uma etapa de **roteamento** antes de chamar o modelo que
escreve a resposta. Configure um modelo **dedicado, pequeno e rápido** para
ela — de preferência local. Sem essa variável, o roteamento cai no **modelo
principal de cada agente**, o que encarece e atrasa TODA pergunta.

**As quatro tarefas que usam esse modelo** (é o mesmo modelo nas quatro):

| # | Tarefa | Onde | Tipo de saída | Peso |
|:-:|:-------|:-----|:--------------|:-----|
| 1 | **Escolher os conectores** relevantes da área (ou nenhum) | `agente.py` (`_selecionar_conectores`) — voto majoritário de 3 tentativas | um número | classificação, 1 token |
| 2 | **Extrair os parâmetros** da pergunta (`{id_cliente}`, `{email}`, `{data}`…) | `agente.py` (`_extrair_parametros_ia`) | JSON minúsculo | extração |
| 3 | **Montar o spec do gráfico** (tipo, título, dados) | `agente.py` (`_especificar_grafico`) | JSON pequeno (≤20 pontos) | geração curta |
| 4 | **Gerar o SELECT da Consulta inteligente** (text-to-SQL sobre o schema real) | `connector_pack/registry.py` (`_gerar_sql_ia`) | SQL, ~300 tokens | **geração de verdade** |

**Perfil obrigatório do modelo de roteamento — pequeno, inteligente e rápido:**
> O roteador precisa ser **pequeno** (cabe no servidor do cliente, sem GPU dedicada),
> **inteligente** (entende a pergunta e acerta escolher — ou não escolher — o
> conector certo, mesmo com sinônimos) e **rápido** (a latência dele é a latência
> de TODA pergunta). Se faltar qualquer um dos três, o roteamento vira gargalo.

- **Pequeno** — roda em quase toda pergunta, no mesmo servidor da plataforma, sem exigir GPU dedicada (4B–8B quantizado já é "pequeno" para esse papel; 0,5B é o piso);
- **Inteligente** — entende a pergunta e acerta **escolher, não escolher, ou escolher mais de um** conector, inclusive com sinônimos ("faturamento" → conector de vendas). É aqui que o 0,5B tropeça; 3B–8B instruct acerta bem;
- **Rápido** — a latência do roteador é a latência de TODA pergunta. Referência: ~0,3–0,5 s por voto no 4B em GPU;
- **INSTRUCT, nunca reasoning** — modelo de raciocínio gasta os tokens "pensando" e, com o limite cortado, devolve **vazio**; o roteador então repete a chamada (256→512) e a conta explode: medimos **16 s de 17 s** de uma resposta só por causa disso (modelo 9B reasoning);
- **Temperatura 0 / determinístico** — a plataforma já chama com temperatura 0.0; o prompt pede resposta curta e objetiva;
- **Contexto modesto basta** (o prompt é a pergunta + uma lista curta de conectores), mas para a **tarefa 4** (SQL) o modelo precisa ter alguma competência de geração — um 0,5B dá conta de 1–3, **não** da 4. Se o roteador for muito pequeno, a Consulta inteligente tende a falhar (e o agente cai no comportamento seguro de responder sem o dado).

> Regra prática de escolha: **menor modelo que ainda acerta a seleção**. Comece
> com 3B–4B instruct; suba para 8B (`hermes-3-llama-3.1-8b`) se o entendimento
> ficar fraco; só desça para 0,5B em instalação muito modesta, ciente de que a
> Consulta inteligente (tarefa 4) pode falhar.

**Validado em produção:** `qwen3-4b-instruct-2507` em LM Studio (aprox. 2,6 GB,
Q4) — resultado medido: pergunta simples **1,6 s** no total (era 6–17 s) e
pergunta com conector **3,4 s** (era 22,5 s); os votos do roteador caem para
~0,3–0,5 s.

**Outros modelos que atendem** (todos INSTRUCT, temperatura 0):
- `hermes-3-llama-3.1-8b` — 8B instruct, já usado como referência da plataforma;
  excelente em seguir formato/JSON. Roda bem quando o servidor tem GPU (você já
  tem 2× RTX 5070 Ti): é mais "inteligente" no entendimento, um pouco mais lento
  que o 4B no primeiro token;
- `Qwen2.5-3B-Instruct` — meio-termo entre tamanho e acerto;
- `Qwen3-4B` **com o "pensamento" desligado** (`/no_think`) — mesma família, mas
  obrigatoriamente sem reasoning;
- `Qwen2.5-0.5B-Instruct` — para instalações muito modestas (CPU fraca), aceitando
  as limitações: pode errar o caso "nenhum", escorregar no formato e não dá conta
  do text-to-SQL (tarefa 4).

**O que NÃO usar como roteador:** modelo de resposta do agente (grande/ reasoning),
modelo de 7B+ reasoning e qualquer coisa com "thinking" ligado por padrão.

**Como configurar:**
1. Cadastre o modelo na tela **Modelos IA** (ex.: `qwen3-4b-instruct-2507`, endpoint do LM Studio/vLLM, tipo **local**);
2. Na instalação, defina `BLUESHIFT_ROUTER_MODEL` com o **ID ou o NOME** desse modelo (o nome é o que aparece na tela Modelos IA);
3. Confira em **Atualizações → Configuração de ambiente** qual modelo de roteamento está em uso (mostra o nome e o ID);
4. Se deixar vazio, o roteamento usa o modelo principal do agente — funciona, mas não é o recomendado.

**Pitfalls operacionais (aprendidos em produção):**
- **LM Studio é aplicativo com interface** — se o servidor reiniciar e o LM Studio não subir, o roteamento volta para o modelo principal **sem erro visível** (o sintoma é só lentidão). Em cliente/produção, hospede o modelo de roteamento como **serviço** (llama-server via systemd) ou garanta o autostart;
- **Nunca use o modelo grande/resposta como roteador** — além do custo, é onde o reasoning cortado gera respostas vazias e o famoso retry;
- Se o roteamento **falhar ou for ambíguo, a plataforma executa todos os conectores da área** (comportamento seguro — o agente nunca fica sem dados);
- Catálogo de conectores grande aumenta o prompt do roteamento: mantenha **descrições curtas e distintas** por conector (é a descrição que o roteador lê).

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

### 5.9 Conectores (/portal/conectores) — como configurar cada tipo

**Onde:** Cadastros → Conectores.

**Propósito:** ligar os agentes de uma **Área** às fontes externas de dados
(APIs, agentes remotos, servidores MCP e bancos SQL). O agente herda
**todos os conectores ativos da sua área** — não existe vínculo manual
conector↔agente; para um conector valer para o agente de vendas, basta
cadastrá-lo na área `vendas`.

**Como o agente usa o conector (fluxo):**
1. O usuário pergunta (API, Open WebUI, teste do portal).
2. A plataforma extrai os parâmetros da pergunta (`{id_cliente}`, `{email}`,
   datas, `chave=valor`) e seleciona os conectores da área.
3. Cada conector é executado (API/A2A/MCP/SQL) — **falha de um conector não
   derruba a resposta**: o erro é registrado e o agente segue.
4. O resultado entra como **dados de sistema** no contexto do modelo.
5. O modelo responde; cada execução atualiza `status` e `ultimo_heartbeat`
   do conector (colunas Status e Heartbeat da lista).

**Passo a passo (qualquer tipo):**
1. Cadastros → Conectores → preencha **Cliente**, **Área**, **Nome** e **Tipo**.
2. Preencha os campos do tipo escolhido (seções abaixo).
3. Preencha a **Descrição** (aparece na lista; ajuda a saber o que o conector faz).
4. Preencha a **Finalidade do tratamento (Art. 26 LGPD)** — obrigatória quando
   o cliente tem a LGPD ligada para conectores em Configurações → LGPD.
5. Salve. O conector entra ativo para a área.
6. Valide: **🗄️ SQL** tem o botão **🔌 Testar Conexão** (roda a query e mostra
   OK/erro); **API/A2A/MCP** são validados pelo chat de teste do agente
   (Agentes → testar, ou Canal → testar) com uma pergunta que use o conector.
7. Acompanhe **Status** e **Heartbeat** na lista. Se der erro, veja
   "Problemas comuns" no fim desta seção.

**Campos comuns a todos os tipos:**

| Campo | Obrigatório | O que é | Exemplo |
|:------|:-----------:|:--------|:--------|
| Cliente | ✅ | Empresa dona do conector (a primeira já vem selecionada) | XPTO Seguros (Piloto) |
| Área | ✅ | Área do agente que vai herdar o conector | `vendas` |
| Nome | ✅ | Nome de exibição na lista | `API Câmbio` |
| Tipo | ✅ | `api` · `a2a` · `mcp` · `sql` | `api` |
| Descrição | ❌ | Resumo do que o conector faz | Cotações de câmbio do dia |
| Finalidade do tratamento (Art. 26 LGPD) | ⚠️ se exigido | Para que os dados são tratados | Consultar dados cadastrais do cliente |

---

#### 🌐 Tipo API REST (`api`)

**Quando usar:** qualquer serviço HTTP/JSON — APIs internas, ERPs, cotações,
Databricks/Snowflake por REST, agentes Oracle AIDP no caminho `/chat`.

| Campo | Obrigatório | O que é | Exemplo |
|:------|:-----------:|:--------|:--------|
| URL | ✅ | Endpoint completo (aceita `{param}`) | `https://api.exemplo.com/v1/cambio?data={data}` |
| Método | ✅ | `GET` ou `POST` | `GET` |
| Headers (JSON) | ❌ | Cabeçalhos extras em JSON | `{"User-Agent": "Mozilla/5.0"}` |
| Body (JSON, só POST) | ❌ | Corpo enviado no POST (aceita `{param}`) | `{"id": "{id_cliente}"}` |
| Autenticação | ❌ | `none` (padrão — vale o que estiver nos Headers) · `bearer` · `oauth2` | `oauth2` |
| Token | ❌ | Token fixo (só `bearer`) | `eyJhbGci...` |
| Token URL | ❌ | Endpoint do token (só `oauth2`) | `https://login.exemplo.com/oauth2/token` |
| Client ID / Client Secret | ❌ | Credenciais do `oauth2` (client_credentials) | `cliente-xpto` / •••• |
| Scope | ❌ | Escopo pedido ao provedor (opcional) | `api://escopo/.default` |
| Timeout (segundos) | ❌ | Limite por requisição — padrão **15** | `30` |
| Job assíncrono (polling) | ❌ | Para APIs que respondem "processando" (ver abaixo) | — |
| Mapear resposta | ❌ | Caminho do pedaço útil do JSON (ver abaixo) | `data.rows` |

**Autenticação — os três modos:**
- `none` — a plataforma não mexe em cabeçalho nenhum: use **Headers** para
  mandar `Authorization`, `X-API-Key` etc.
- `bearer` — a plataforma envia `Authorization: Bearer <Token>` em cada chamada.
- `oauth2` — fluxo **client_credentials**: a plataforma pede o token na
  **Token URL** com `client_id`/`client_secret` (+ `scope`, se houver), **cacheia
  em memória** e renova automaticamente ~30 s antes do `expires_in`. Não é preciso
  gerar token na mão nem reiniciar nada ao trocar a senha do client.
- Na **edição**, os campos de segredo (Token, Client Secret) em branco
  **mantêm o valor anterior** — só digite se quiser trocar.

**Job assíncrono (polling) — quando a API responde "processando":**
Serviços como o Databricks SQL Statements, o Snowflake SQL API e várias APIs
OCI devolvem primeiro um **id de job** e o resultado só depois. Preencha:

| Campo | Exemplo | Para que serve |
|:------|:--------|:---------------|
| URL de consulta do job | `https://api.exemplo.com/v1/jobs/{job_id}` | Onde consultar o andamento (`{job_id}` é substituído pelo id) |
| Campo do id na 1ª resposta | `statementHandle` | Onde está o id na resposta inicial |
| Campo do status | `status` | Campo que diz se o job terminou |
| Status concluído | `SUCCEEDED` | Valor que indica sucesso (comparação sem diferenciar maiúsculas) |
| Status de erro | `FAILED` | Valor que indica falha |
| Intervalo (s) | `2` | Espera entre consultas (padrão 2 s) |
| Máximo (s) | `60` | Tempo máximo de espera (padrão 60 s) |

Comportamento: sem `URL de consulta do job` a plataforma faz **uma chamada só**
(igual ao comportamento antigo). Com polling, ela consulta de `intervalo` em
`intervalo`; ao ver o status de sucesso, usa a **resposta final**; no status de
erro ou ao estourar o **Máximo**, o conector devolve `{"erro": ...}` e o agente
segue respondendo (sem dado do conector).

**Mapear resposta (evita poluir o contexto):** caminho pontilhado dentro do JSON.
Exemplos: `data.rows`, `result.data`, `dados.0.itens`. Vazio = a resposta inteira
vai ao modelo. Use sempre que a API devolver metadados/paginação junto do dado.

**Exemplos de configuração API:**

| Cenário | Preenchimento |
|:--------|:--------------|
| API simples com GET | URL `https://api.exemplo.com/v1/cambio?data={data}` · Método `GET` · Headers `{"User-Agent": "Mozilla/5.0"}` |
| API com token fixo | idem + Autenticação `bearer` + Token |
| API com OAuth2 | Autenticação `oauth2` + Token URL + Client ID/Secret (+ Scope) |
| Databricks SQL (REST) | URL `https://<workspace>/api/2.0/sql/statements` · Método `POST` · Headers `{"Content-Type": "application/json"}` · Body `{"warehouse_id": "...", "statement": "SELECT ..."}` · Auth `bearer` (PAT) · Polling: URL `.../statements/{job_id}` · Campo do id `statement_id` · Status `state` · Concluído `SUCCEEDED` · Erro `FAILED` · Mapear `result.data_array` |
| Oracle AIDP (agente `/chat`) | URL `https://gateway.aidp.<região>.oci.oraclecloud.com/agentendpoint/<id>/chat` · POST · Auth `oauth2` (ou `bearer`) · Mapear conforme a resposta. **Alternativa recomendada:** cadastrar como **Modelo IA** com `Modo = responses` (seção 5.8) e usar o agente AIDP como cérebro do agente |

---

#### 🤝 Tipo A2A — agente remoto (`a2a`)

**Quando usar:** conversar com **agentes publicados** no protocolo Agent2Agent —
ex.: Oracle Autonomous AI Database (A2A server) e Oracle AIDP (`/a2a`). A pergunta
vira uma mensagem A2A e a resposta do agente remoto entra como dado no contexto.

| Campo | Obrigatório | O que é | Exemplo |
|:------|:-----------:|:--------|:--------|
| URL do agente A2A | ✅ | Endpoint `/a2a` do agente publicado | `https://gateway.aidp.<região>.oci.oraclecloud.com/agentendpoint/<id>/a2a` |
| Método | ✅ | Método A2A — padrão `message/send` | `message/send` |
| Timeout (s) | ❌ | Limite por chamada — padrão **30** | `60` |
| Agent Card | ❌ | URL do `agent-card.json` (só registro/diagnóstico) | `https://.../agent-card.json` |
| Mensagem (template) | ❌ | Texto enviado; vazio = a pergunta do usuário. Aceita `{pergunta}` e `{param}` | `Responda: {pergunta}` |
| Autenticação | ❌ | `none` · `bearer` · `oauth2` (igual ao tipo API) | `oauth2` |

O que a plataforma envia (JSON-RPC 2.0):

```json
{"jsonrpc": "2.0", "id": 1, "method": "message/send",
 "params": {"message": {"role": "user", "messageId": "<id>",
   "parts": [{"kind": "text", "text": "<mensagem>"}]}}}
```

A resposta é lida de forma tolerante: a plataforma procura o texto em
`result.artifacts[].parts[].text` (e também em `messages`/`parts`). Erro de
protocolo (`error` no JSON-RPC), HTTP ou timeout viram `{"erro": ...}` e o agente
segue respondendo. **Limite atual:** sem streaming (SSE) e sem multi-turno —
cada pergunta é uma mensagem independente.

---

#### 🔌 Tipo MCP (`mcp`)

**Quando usar:** expor **ferramentas** de um servidor MCP (Model Context
Protocol) ao agente — local (subprocesso) ou remoto (HTTP/SSE). O servidor MCP
de exemplo do produto é `mcp_server.py` (JSON-RPC 2.0 puro, sem dependências).

| Campo | Obrigatório | O que é | Exemplo |
|:------|:-----------:|:--------|:--------|
| Transporte | ✅ | `stdio (local)` ou `SSE (remoto)` | `stdio` |
| Comando (stdio) | ✅ | Linha de comando que sobe o servidor | `python /opt/blueshift/mcp_server.py` |
| URL (SSE) | ✅ | Endpoint MCP remoto | `http://servidor:8000/mcp` |
| Ferramenta (tool) | ✅ | Nome da ferramenta a chamar | `erp_buscar_cliente` |
| Argumentos (JSON) | ❌ | Argumentos (aceitam `{param}`) | `{"id_cliente": "{id_cliente}"}` |

Observações: o **comando roda dentro do container** do portal — use caminhos que
existam na imagem (o `mcp_server.py` é embutido; bancos de dados locais devem ser
alcançados por `host.docker.internal`, não `127.0.0.1`). O timeout do MCP é fixo
em **30 s**; erro/timeout devolve `{"erro": ...}` sem derrubar a resposta.

---

#### 🗄️ Tipo SQL (`sql`)

**Quando usar:** consultar diretamente o banco do cliente (ou um banco
gerenciado) com uma query fixa que aceita parâmetros da pergunta. Quando a query
volta vazia e a pergunta pede análise, entra a **Consulta inteligente** (abaixo).

| Campo | Obrigatório | O que é | Exemplo |
|:------|:-----------:|:--------|:--------|
| Driver | ✅ | `PostgreSQL` · `MySQL` · `SQL Server` · `Oracle` | `PostgreSQL` |
| Host | ✅ | Servidor do banco (use `host.docker.internal` para o host da máquina) | `host.docker.internal` |
| Porta | ✅ | Padrões: 5432 (PG) · 3306 (MySQL) · 1433 (SQL Server) · 1521 (Oracle) | `5432` |
| Banco | ✅ | Nome do banco (Oracle: **service_name**) | `vendas` |
| Usuário | ✅ | Usuário do banco | `consulta_bi` |
| Senha | ✅ | Senha do usuário (na edição, em branco mantém a anterior) | •••• |
| DSN (variável de ambiente) | ❌ | Nome de uma env var com o DSN completo | `ERP_DSN` |
| DSN direto | ❌ | DSN literal (quando houver) | `host=10.0.0.5 dbname=vendas user=x` |
| SSL mode | ❌ | TLS do PostgreSQL — **necessário** para Databricks SQL Warehouse e Postgres gerenciados | `require` |
| Pasta do wallet (Oracle) | ❌ | Wallet descompactado no servidor (mTLS do Autonomous) | `/opt/blueshift/wallets/meuadb` |
| Senha do wallet | ❌ | Senha do wallet (quando aplicável) | •••• |
| Query SQL | ✅ | Consulta com placeholders | `SELECT * FROM clientes WHERE id = {id_cliente}` |
| Consulta inteligente | ❌ | Checkbox (padrão LIGADO) — análise automática sobre o schema real | ✅ |

**Driver x biblioteca x caminho:** PostgreSQL usa `psycopg`; MySQL, `pymysql`;
SQL Server, `pymssql`; Oracle, `oracledb`. Se o driver não estiver instalado na
imagem, o conector responde com erro (`ImportError`) e o agente segue — o
instalador do cliente já traz os quatro. Toda conexão tem **connect_timeout de
5 s** (conector pendurado não trava o agente).

**Consulta inteligente:** quando a query fixa volta vazia **E** a pergunta pede
análise/agregação ("quem alugou mais e menos", "quantos por categoria", "top 5",
"total por..."), o agente monta o SELECT sozinho olhando o **schema real da fonte**
(tabelas/views + colunas — nunca os dados):
1. Descobre o schema por driver (information_schema / user_tab_columns),
   priorizando a tabela/view usada na query do conector;
2. O LLM (modelo de roteamento) monta o SELECT no dialeto do banco;
3. **Validação de segurança**: somente SELECT de leitura — rejeita DDL/DML
   (`;` separa múltiplos SELECTs legítimos, cada um validado), comentários,
   UNION, INTO; força `LIMIT 50` quando faltar;
4. Executa e devolve os dados ao LLM final (fonte primária).

Desligar o checkbox = comportamento antigo (só a query fixa).

**Exemplos de configuração SQL:**

| Cenário | Preenchimento |
|:--------|:--------------|
| Postgres local (Sakila/demo) | Driver `PostgreSQL` · Host `host.docker.internal` · Porta `5432` · Banco/usuário/senha do banco |
| MySQL local | Driver `MySQL` · Porta `3306` |
| SQL Server | Driver `SQL Server` · Porta `1433` |
| **Databricks SQL Warehouse** | Driver `PostgreSQL` · Host `dbc-xxxx.cloud.databricks.com` · Porta `443` · Banco `/sql/1.0/warehouses/<id>` · Usuário `token` · Senha = PAT · SSL mode `require` |
| **Oracle Autonomous AI Database** | Driver `Oracle` · Host/DSN e service_name do Autonomous · Pasta do wallet (wallet descompactado no servidor) · Senha do wallet · Select AI via SQL funciona por aqui |
| Oracle "normal" | Driver `Oracle` · Host · Porta `1521` · Banco = service_name — sem wallet, igual sempre foi |

---

**Placeholders `{param}`:** URL, body, argumentos do MCP, query SQL, template do
A2A e query gerada aceitam placeholders substituídos por valores extraídos da
pergunta: `{id_cliente}`, `{id_colab}`, `{id_pedido}`, `{email}`, `{data}`,
`{pergunta}` (texto integral da pergunta — útil no A2A) e qualquer `chave=valor`
informado na pergunta. ⚠️ Use **um placeholder por conector** quando a fonte não
aceitar múltiplos valores na mesma posição (consultas multi-valor podem travar).

**Botões e validação:**
- **🔌 Testar Conexão** (tipo SQL, admin): abre a conexão e roda a query
  informada, mostrando OK/erro — valida driver, host, porta, credenciais,
  **SSL mode** e **wallet** do Oracle. É o teste mais rápido antes de salvar.
- **🤖 Gerar Query com IA** (tipo SQL): um modelo cadastrado escreve a query a
  partir de uma descrição em linguagem natural ("listar clientes ativos com saldo
  acima de 1000"); o resultado é revisado por você antes de entrar no campo.
- **API / A2A / MCP**: valide pelo chat de teste do agente (uma pergunta que
  dependa do conector) e confira o **Heartbeat** na lista.

**Segurança, segredos e LGPD:**
- Segredos (senha do banco, token, client secret, senha do wallet) são gravados
  no banco do cliente, **mascarados na edição** e nunca reexibidos; em branco =
  mantém o valor atual.
- A **Finalidade do tratamento** é exigida quando a LGPD está configurada para
  conectores (Art. 26) e fica registrada na auditoria.
- Toda ação de cadastro/edição/exclusão de conector é registrada na Auditoria.
- Na **Consulta inteligente** o agente lê apenas o *schema* (nomes de
  tabelas/colunas), nunca os dados, para montar a query; a validação garante
  somente leitura com LIMIT.

**Problemas comuns:**

| Sintoma | Causa provável | O que fazer |
|:--------|:---------------|:------------|
| HTTP 401/403 na API | Auth não configurada ou token vencido | Usar `bearer`/`oauth2` (ou mandar o `Authorization` nos Headers); conferir Client ID/Secret e Scope |
| HTTP 400/415 | Faltou `Content-Type: application/json` | Adicionar nos Headers (o produto já envia JSON, mas alguns gateways exigem o header explícito) |
| Conector não devolve dados | Área errada, placeholder não casou com a pergunta, ou status de erro no job | Conferir a área do agente, a grafia do `{param}` e, em polling, o par **Status concluído/Status de erro** |
| Timeout / demora | API lenta ou job longo | Aumentar **Timeout**; em job assíncrono, ajustar **Máximo (s)** e **Intervalo** |
| Resposta enorme poluindo a resposta do agente | JSON inteiro indo ao modelo | Preencher **Mapear resposta** (ex.: `data.rows`) |
| Erro de SSL no Postgres/Databricks | TLS exigido | Preencher **SSL mode** (`require`) |
| Oracle Autonomous não conecta | Wallet ausente ou caminho errado | Descompactar o wallet no servidor e informar a **pasta** + senha do wallet (caminho visto **de dentro do container**) |
| "Connection refused" em API/banco local | `127.0.0.1` dentro do container é o próprio container | Usar `host.docker.internal` (ou o IP/hostname real do serviço) |
| MCP não responde | Comando inexistente na imagem ou tool com nome errado | Testar o comando dentro do container; conferir o nome exato da tool (timeout de 30 s) |

**Limites e roadmap:** Snowflake (dependência a decidir com o cliente); A2A com
streaming/multi-turno; polling cobre consulta por `GET` no job. Demais tipos
seguem como estão: qualquer evolução entra como campo **opcional** — sem mudar o
comportamento dos conectores já configurados.

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

A lista "Canais cadastrados" exibe a coluna **ID** (primeira coluna) — útil
para identificar o canal em auditoria/tracing.

**⚠️ Nunca use a chave de licença da plataforma como token de canal.**

**Webhook de saída com autenticação:** muitos webhooks reais (Slack, Zapier,
n8n, sistemas corporativos) exigem uma chave secreta. Preencha o campo
**Headers do webhook (JSON)** com o que o receptor pedir — ex:
`{"X-Webhook-Secret": "abc123"}` ou `{"Authorization": "Bearer token"}`.
O sistema envia esses headers no POST da resposta (junto com o
`Content-Type: application/json`). Evite colocar a chave na URL
(`?secret=...`) — ela vaza em logs.

**Anti-SSRF no webhook (segurança):** a URL do webhook de saída é validada
com `ipaddress` (não prefixos literais) e por resolução de DNS. São
bloqueados endereços internos/não públicos: 10/8, 172.16/12, 192.168/16,
CGNAT (100.64/10), loopback, link-local (inclui 169.254.169.254 — metadata
de nuvem AWS/GCP), multicast, IPv6 ULA/link-local, e hostnames que
RESOLVEM para IP interno (DNS rebinding). A validação vale no **criar**,
no **editar** e no **momento do envio** (URL cadastrada antes da correção
também é bloqueada).

### 5.11 Memória (/portal/memoria)

**Onde:** Inteligência → Memória.

**Propósito:** histórico de memória persistente por usuário/cliente.

- Toda resposta do agente grava a memória tipo **conversa**
  (`[Agente] P: ... | R: ...`) — histórico para auditoria e export.
- Tipos **preferência** e **contexto** (cadastro manual) alimentam o contexto
  do agente; memória tipo **conversa** NÃO entra no RAG (isolamento — não
  polui a base de conhecimento com trocas de chat).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Cliente | ✅ | XPTO Seguros (Piloto) |
| Tipo | ✅ | pergunta / resposta / nota |

- Lista com paginação (10/20/50/100/200 por página).
- **Exportar JSONL** (admin/gestor): baixa o histórico como
  `blueshift_memorias_Nregistros.jsonl` — conversas saem parseadas em
  `pergunta`/`resposta`; preferência/contexto saem como `conteudo`. Máscara
  LGPD aplicada quando ativada (mesma política do export de Conhecimento).
  Auditoria `memoria_exportar`.
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

A base NÃO recebe auto-gravação de conversas (desde v0.10.14): cresce apenas
por cadastro manual, import CSV/PDF e indexação de skills. Documentos legados
"RAG auto:" de versões anteriores permanecem e são parseados no Exportar JSONL.
Filtros por Cliente, Área, Categoria, Fonte.

### 5.13 Chat de teste (/portal/chat)

**Onde:** FORA do menu (ferramenta de debug — URL direta `/portal/chat`).
A aba "Chat" foi removida do menu Inteligência (v0.9.5): o teste real de
respostas é feito em **Agentes → testar** (pipeline completo: RAG +
conectores + gráficos + feedback + rastreio). Este chat continua
disponível por URL para isolar o contexto dinâmico (memória + RAG)
com um modelo cru.

**Propósito:** chat de teste com qualquer modelo cadastrado (sem pipeline de
agente — LLM direto, SEM conectores, SEM gráficos — perguntas de gráfico
recebem resposta textual do modelo).

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

**Propósito:** update da plataforma a partir do **Git** (tags de versão).
Mostra a versão instalada (tag do repo) e se há tag nova disponível no
remoto. Admin-only.

**Como funciona:**
- O servidor mantém um **clone fixo** do repositório (padrão
  `/opt/blueshift/repo` — variável `BLUESHIFT_REPO_DIR`; no compose o repo
  é montado no container junto com o `docker.sock` do host)
- Versão instalada = `git describe --tags` do repo (ex: `v0.9.3`)
- Versão disponível = tags do remoto (`git ls-remote`), ordenadas por
  versão; a mais recente diferente da instalada aparece como atualização
- **Aplicar atualização** roda `update.sh <tag>` em background:
  `git fetch` + `git checkout <tag>` + `docker compose up -d --build`
  (dados preservados — volumes intactos). O portal reinicia ao concluir;
  log em `/opt/blueshift/update.log`
- A configuração da instalação (ex.: `BLUESHIFT_LICENSE_URL`, chave de
  licença, roteador) é **repassada ao portal recriado** via env do próprio
  container em execução — o update não depende do compose ler o `.env` do
  host (que falhava de dentro do container irmão e fazia a licença cair no
  mock `localhost:9000`, exibindo "inválida" após todo update)
- Em dev (`BLUESHIFT_DEV=1`) o botão faz **dry-run** (mostra o comando,
  não derruba o ambiente); se o remoto for inacessível (repo privado sem
  credencial), usa as tags locais como referência
- Se o repo não existir, a tela avisa "repo não encontrado" (sem quebrar)

**Card "Configuração de ambiente":** exibe as configurações ativas da
instalação:
- **Modelo de roteamento configurado** — o `BLUESHIFT_ROUTER_MODEL`
  resolvido (nome + ID, ou "(não encontrado)" se a env apontar um modelo
  inexistente; vazio = modelo principal de cada agente);
- **Áreas configuradas** — a lista do cadastro Cadastros → Áreas (banco;
  a env `BLUESHIFT_AREAS` serve só como seed inicial do primeiro boot).

**Card "Atualização manual (se o botão falhar)":** traz os comandos para
atualizar na mão a partir do **host** do servidor (útil quando o botão
erra por rede, repo sujo ou imagem que não troca):
1. descobrir a pasta do repo no host (`docker inspect` do mount
   `/opt/blueshift/repo`);
2. `git fetch origin --tags && git checkout vX.Y.Z && docker compose up -d --build`;
3. conferir com `docker ps` + `git describe --tags`.
Inclui também o caminho **sem Docker** (`bash update_bare.sh vX.Y.Z`, Linux
direto) e o aviso de nunca rodar `docker compose down -v` (apaga o volume
de dados). O diagnóstico de "repo não encontrado" (dubious ownership) é o
`safe.directory` do git no container — o entrypoint já configura; o
container irmão do update pula o entrypoint, então o fix pode ser aplicado
à mão com `docker exec` quando necessário.

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
- **Feedback default**: interações vindas do gateway registram feedback
  automático `util` com tipo `gateway` — entram na Observabilidade
  (taxa de acerto) e no Teste A/B, distinguíveis do feedback
  manual/implicito/api pela coluna tipo.
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
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{"model": "agente:Agente Vendas",
       "messages": [{"role": "user", "content": "Qual o saldo do cliente C001?"}]}'
```

### 5.24 Docs (/portal/docs) — documentação no menu lateral

**Onde:** item fixo **Docs** na sidebar (abaixo de Configurações, fora de
submenu).

**Propósito:** documentação completa da plataforma renderizada como página.

- Renderiza o **mesmo `DOCUMENTACAO_PB.md`** que alimenta o popup Ajuda (❓
  no topo) — um único arquivo serve os dois; edite o `.md` para atualizar
  ambos (montado por volume no Docker, sem rebuild).
- Índice de seções no topo com navegação por âncora (clique e vai direto
  à seção).
- Conversão markdown→HTML própria (stdlib puro): tabelas, blocos de
  código, listas e links renderizados; todo conteúdo é escapado (seguro).
- Acesso: qualquer usuário autenticado (`login_required`).

---

### 5.25 Arquivo Morto (/portal/arquivo-morto) — snapshot + corte de dados

**Onde:** menu **Operação → Arquivo Morto** (somente **admin** — `admin_required`).

**Propósito:** controlar o crescimento do banco sem perder histórico: gera um
**snapshot selado** do banco (cópia íntegra) e remove do banco quente os
registros até a data de corte.

**Fluxo:**

1. Informe a **data de corte** (registros com `criado_em ≤ corte` serão
   arquivados). O máximo permitido é **ontem à meia-noite (D-1)** — o dia
   corrente nunca é afetado.
2. Clique em **Arquivar**: o sistema mostra a **confirmação com as contagens**
   por tabela (quantos registros serão movidos) e o nome do snapshot.
3. **Confirme o backup**: marque que o backup físico do portal.db foi realizado
   (o snapshot **não** substitui o backup — responsabilidade do cliente). Sem
   essa confirmação, o botão não executa.
4. Confirme: o sistema gera o snapshot e limpa o quente, **na ordem segura**
   (cópia primeiro; se a cópia falhar, nada é apagado).

**Snapshot:** `data/arquivo_morto/arquivo_morto_<execução>_<corte>.db` (primeira
data = execução, segunda = corte). É uma cópia íntegra do banco inteiro naquele
momento e fica **selada** — o sistema nunca mais grava nela (use para auditoria
ou dataset de treinamento). Backup físico do banco principal é responsabilidade
do cliente (volume).

**Tabelas afetadas (DELETE por idade — `criado_em ≤ corte`):**

| Tabela | Critério |
|:-------|:---------|
| tracing | idade (≤ corte) |
| uso_tokens | idade (≤ corte) |
| auditoria | idade (≤ corte) |
| memories | idade (≤ corte) |
| feedback | idade (≤ corte) |
| teste_ab | idade (≤ corte) |
| knowledge | fonte importada (csv/pdf/...) **e** sem uso recente (`acessos = 0` ou `ultimo_acesso ≤ corte`) — fontes `manual` e `skill` (regras/skills) **nunca** são afetadas |

**Nunca são afetadas:** `metricas_diarias` (agregado perpétuo de custos) e dados
mestres (clientes, usuários, agentes, modelos, skills, conectores, canais,
áreas, api_keys, configurações).

**Controle e auditoria:**

- Cada execução fica no **histórico da tela** (execução, corte, arquivo, movidos
  por tabela, status).
- Cada execução — sucesso **ou falha** — também é registrada na **Auditoria**
  (menu Operação): usuário, corte, arquivo gerado e total movido
  (`acao=arquivo_morto`).
- Executar duas vezes no mesmo dia com o mesmo corte é rejeitado (o snapshot já
  existe — nada é sobrescrito).

> A limpeza automática opcional (tela LGPD, `retencao_auto`) faz **DELETE
> físico** com retenções configuráveis e continua independente do arquivo morto.

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
- **Memória de conversa**: pergunta+resposta são salvas na memória (tipo
  'conversa') a cada resposta — histórico/auditoria/export, fora do RAG.
- **Base de conhecimento SEM auto-feed (v0.10.14)**: o knowledge só recebe
  conteúdo intencional (cadastro manual, import CSV/PDF, skills indexadas).
  Antes, respostas com dados de conectores eram gravadas automaticamente
  ("RAG auto:") — comportamento removido; documentos legados continuam na
  base e são reconhecidos no export JSONL.
- **Isolamento por área**: docs RAG com `area` definida só aparecem para a
  mesma área; docs sem área valem para todas.
- **Filtro por cliente**: contexto RAG é filtrado pelo `id_cliente` da
  pergunta quando encontrado.
- **Fallback de modelo**: se o modelo principal falhar, usa o secundário.
- **Tracing**: cada execução gera um trace completo (params, conectores, RAG,
  modelo, tokens, resposta, tempo_ms) — visível na auditoria via 🔍 Rastreio.
  Além do tempo total, o trace guarda o tempo por **fase** (ms):
  `roteador_ms` (votos de seleção de conectores + extração de params por IA),
  `conectores_ms` (execução real), `rag_ms` (busca no conhecimento) e
  `llm_ms` (chamadas de resposta/fallback/gráfico) — o modal de rastreio
  exibe os quatro. Fase que não rodou (ou falhou antes do marco) fica 0.
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
| Webhook SSRF | Anti-SSRF com `ipaddress` (is_global): bloqueia privado, CGNAT, link-local/metadata de nuvem, loopback, IPv6 ULA/link-local + DNS rebinding (resolve o hostname); validado no criar, editar e no momento do envio |
| Headers HTTP | X-Content-Type-Options, X-Frame-Options: DENY, Referrer-Policy, Content-Security-Policy; CORS "*" só nas rotas /portal/api/* |
| API Key de modelo | Nunca renderizada no HTML (máscara no editar; campo vazio = mantém atual) |
| Senha mínima | 8 caracteres (criar/editar usuário e setup inicial) |
| Login falho | Registrado em auditoria (usuário tentado + IP) — detecta brute-force |
| Health check | Rota pública `/portal/healthz` (200/503 + estado do banco) para load balancer / HEALTHCHECK |
| MCP traceback | Mensagem genérica (sem detalhes de exceção) |
| Erros LLM | Mensagem amigável, sem stack trace |

---

## 10. Banco de Dados (SQLite)

24 tabelas principais:

| Tabela | Conteúdo |
|:-------|:---------|
| clientes | Empresas contratantes |
| usuarios | Usuários do portal (papel, área, ativo) |
| areas | Áreas/departamentos (cadastro no banco; env BLUESHIFT_AREAS só seed inicial) |
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
| memories | Histórico por usuário (conversa grava a cada resposta; preferência/contexto alimentam o RAG) |
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

**Preciso de um segundo servidor de modelo só para o roteamento?**
Não é obrigatório, mas é o **recomendado**: um modelo pequeno e rápido
dedicado (`BLUESHIFT_ROUTER_MODEL`) responde por quatro tarefas internas
(escolher conectores, extrair parâmetros, montar o spec do gráfico e gerar o
SELECT da Consulta inteligente) e roda em quase toda pergunta. Sem ele, essas
tarefas usam o modelo principal do agente — funciona, porém mais lento e mais
caro. Detalhes, perfil do modelo e pitfalls no §5.8 ("Modelo de roteamento").

**A resposta ficou lenta de repente, sem erro na tela?**
Verifique se o **modelo de roteamento ainda está no ar** (LM Studio fechado
após reiniciar o servidor é a causa clássica). No trace da resposta, a fase
`roteador_ms` mostra o tempo gasto no roteamento — se ela domina o total, o
problema é o roteador, não o RAG nem o banco.

**Posso misturar modelo local e externo?**
Sim — cada agente define o próprio `modelo_id`; a plataforma é agnóstica a
provedor (qualquer endpoint OpenAI-compatível).

**O agente responde "como se fosse outra área"?**
Verifique se o documento RAG tem `area` definida — docs sem área participam
de todas as áreas. Use o isolamento por área para evitar contaminação.

**Onde vejo o detalhamento de uma resposta (conectores, RAG, tokens)?**
Na página Auditoria, clique em **🔍 Rastreio** ao lado do registro. O modal
mostra também o **tempo por fase** (Roteador / Conectores / RAG / LLM em ms)
— útil para diagnosticar lentidão: se `conectores_ms` domina, é o conector;
se `llm_ms` domina, é o modelo/endpoint.

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

**O agente só responde quando coloco um parâmetro (ex: id_cliente)?**
Perguntas de ANÁLISE ("quem alugou mais e menos", "quantos por categoria",
"top 5") agora montam a consulta sozinhas: a **consulta inteligente** do
conector SQL descobre o schema real da fonte (tabelas/views + colunas) e
o LLM gera o SELECT (somente leitura, com LIMIT e validação de segurança).
O fluxo com parâmetros continua valendo para perguntas específicas
("aluguel do cliente 30"). Desligável por conector (checkbox "Consulta
inteligente" no cadastro/edição).

**O agente pode gerar gráficos?**
Sim — perguntas como "faça um gráfico de pizza/barras/linha" geram a
imagem automaticamente quando há dados dos conectores (barras para
comparação, pizza para proporções, linha para tendência). A imagem é
anexada à resposta (renderiza no Open WebUI e no teste de agente) e os
rótulos respeitam a máscara LGPD. Sem dados, o agente responde com a
análise textual.

---

*Documentação gerada a partir do código (2026-08-05). Em caso de divergência
entre este documento e o comportamento real, o código é a fonte da verdade —
atualize este arquivo na mesma entrega da mudança.*
