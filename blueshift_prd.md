# CL Agents — Product Requirements Document (PRD)

**Produto:** BlueShift IA Platform · **Marca de exibição:** **CL Agents** (by BlueShift IA Platform)
**Versão do documento:** 0.3 (alinhado à versão 0.11.1 do produto)
**Data:** 2026-09-12
**Autor:** Nei
**Base tecnológica:** Flask standalone, Python puro (sem dependência de motor externo de IA)

---

## 1. Resumo Executivo

O **CL Agents** (produto **BlueShift IA Platform**) é uma camada de inteligência
artificial **on-premise** entregue como **container Docker** que o cliente sobe na
própria infraestrutura. Ele instala, dentro do ambiente do cliente, uma plataforma
de agentes de IA com:

- modelos de linguagem **cadastrados pelo cliente** (locais ou externos);
- **memória persistente** e **base de conhecimento (RAG)** locais;
- **conectores** para os sistemas internos (APIs, bancos SQL, agentes remotos e
  servidores de ferramentas) configuráveis por **área** da empresa;
- controle de acesso por usuário/sistema, auditoria, observabilidade e LGPD.

**Marca:** a interface e o material comercial usam **CL Agents** (by BlueShift IA
Platform); documentação técnica e código seguem o nome **BlueShift IA Platform**.

**Modelo de entrega:** container Docker ativado por **chave de licença** emitida
pela BlueShift mediante cadastro da empresa.

**Modelo de cobrança:** **licença anual por empresa** (valor por cliente/tamanho) —
não por token nem mensalidade. Serviços (fine-tuning, retreino, suporte estendido,
treinamento) são contratados à parte, por proposta.

**Público-alvo:** qualquer segmento — a plataforma é genérica e parametrizável por
área, sem vertical obrigatória.

---

## 2. Licença e Conformidade Legal

| Item | Decisão |
|:-----|:--------|
| Licença | **Source-available** (copyright BlueShift) — repositório público para transparência, auditoria e atualização automática. A publicação **NÃO concede direito de uso** |
| Uso / instalação | Exige **contrato de licenciamento assinado** + **chave de ativação** emitida pela BlueShift (obtida no cadastro da empresa: razão social, CNPJ e contato) |
| Chaves de desenvolvimento | `BS-DEV-*` valem **somente** em dev (`BLUESHIFT_DEV=1`) — nunca em produção |
| Redistribuição / revenda | **Não permitida** — nunca migrar para MIT/Apache (concederia direito de revenda) |
| Serviços | Fine-tuning, retreino, suporte estendido e treinamento **não estão na licença** — contratados por proposta |
| Validação | Online contra o License Server da BlueShift (`BLUESHIFT_LICENSE_URL`); status visível na tela **Atualizações** |
| LGPD | A plataforma **não coleta** dados pessoais: os dados ficam no ambiente do cliente; quando ligado, o produto aplica **máscaras na saída** (CPF, CNPJ, e-mail, telefone, nome, endereço), exige **finalidade por conector** (Art. 26) e faz **retenção/expurgo** configurável |

---

## 3. Arquitetura do Produto (4 camadas)

```
CAMADA 4 — Experiência      → Portal do cliente (marca CL Agents): gerenciar, cadastrar, monitorar, documentação
CAMADA 3 — Operação         → Instalação Docker, License Server, Update via Git, monitoramento/logs
CAMADA 2 — Domínio          → Skills por área, Connector Pack configurável (API/A2A/MCP/SQL), roteamento por IA
CAMADA 1 — Motor/Núcleo     → Flask + SQLite + urllib (Python puro: TF-IDF para RAG, matplotlib embutido p/ gráficos)
```

---

## 4. Modelo de Entrega — Container Docker + Chave de Ativação

### 4.1 Fluxo de ativação e primeiro boot

```
1. Cliente recebe o pacote/imagem (registry privado ou pacote de instalação)
2. Sobe com o docker compose: BLUESHIFT_LICENSE=<chave> (+ PORTAL_PORT, etc.)
3. A instalação valida a chave no License Server da BlueShift (online)
4. Chave válida → plataforma ativa; a tela Atualizações mostra o status da licença
5. Banco limpo (BLUESHIFT_SEED_DEMO=0) → primeira entrada exibe a tela
   "Configuração inicial", que cria a empresa e o primeiro usuário admin
```

### 4.2 Componentes entregues

```
blueshift_layer/            → código da plataforma
├── cli.py                  (CLI: blueshift portal | mcp | update | ...)
├── gateway.py              (Gateway OpenAI-compatível :9003 — chats externos)
├── license_client.py       (validação da chave)
├── license_server_mock.py  (License Server mock — somente dev)
├── update_client.py        (atualização via Git/tags — tela Atualizações)
├── http_auth.py            (OAuth2 client_credentials compartilhado: API/A2A/modelos)
├── portal/                 (Portal: telas, RBAC, auditoria, RAG, agente, LGPD, SSO)
├── connector_pack/         (engine de conectores + MCP server)
└── template_skills/        (skills de exemplo por área)
docs/                       → documentação (páginas navegáveis + convenção de escrita)
tools/                      → doc_check.py (gate doc × código) e docs_site.py (site interno)
data/                       → banco SQLite e arquivos persistidos (volume)
```

### 4.3 Isolamento

Registros isolados por `cliente_id` no SQLite + RBAC (papéis `admin`, `gestor`,
`usuario`, `sistema`). Cada canal de integração tem **token próprio e revogável**;
toda chamada é auditada (canal, agente, IP e pergunta resumida).

---

## 5. Funcionalidades do Produto

| Capacidade | O que o produto entrega |
|:-----------|:------------------------|
| Agentes | Agent Factory: agente = modelo principal (+ fallback) + skills + conectores da área |
| Modelos de IA | Qualquer endpoint OpenAI-compatível (local ou externo); campo **Modo da API** (`openai_chat` ou `responses` para agentes externos, ex. AIDP `/chat`) |
| Roteamento | Modelo pequeno dedicado (`BLUESHIFT_ROUTER_MODEL`) para 4 tarefas internas: escolher conectores, extrair parâmetros, montar o spec do gráfico e gerar o SELECT da consulta inteligente |
| Skills | Catálogo reutilizável por área; **corpo da skill vai ao prompt** (regras de formato/tom valem) |
| Memória | Persistente por usuário (TF-IDF + cosseno, Python puro) com export JSONL |
| Conhecimento (RAG) | Cadastro manual, import CSV/PDF; indexação de skills; **sem auto-alimentação** por conversas |
| Conectores | **API REST** (auth none/bearer/OAuth2, timeout, polling de job assíncrono, mapeamento de resposta), **A2A** (agente remoto), **MCP** (stdio/SSE) e **SQL** (PostgreSQL/MySQL/SQL Server/Oracle com SSL/wallet) — por área |
| Consulta inteligente | Quando a query fixa volta vazia e a pergunta pede análise, o agente monta o SELECT sobre o schema real (somente leitura + LIMIT) |
| Gráficos | Imagem gerada a partir dos dados reais dos conectores, anexada à resposta, com rótulos mascarados pela LGPD |
| Integração | API de canal (JSON) + **Gateway OpenAI-compatível** para Open WebUI/LibreChat + webhook de saída com retry |
| Governança | Auditoria completa, observabilidade (KPIs, tracing por fases, custo por tokens), alertas, feedback, teste A/B, arquivo morto (snapshot + corte) |
| LGPD | Máscaras na saída, finalidade por conector, aviso de privacidade, retenção automática |
| Documentação | Docs navegável dentro do produto (busca, páginas por tela) + Ajuda IA sobre a mesma fonte + guia de API para o TI do cliente + changelog por versão |

---

## 6. Controle de Acesso

### 6.1 Hierarquia

```
Admin → cria usuários, áreas, agentes, conectores e canais
  ├── Gestor  → opera cadastros e vê relatórios (sem ações de administração)
  ├── Usuário → conversa com os agentes da(s) sua(s) área(s), memória individual
  └── Sistema (API) → token de canal: escopo limitado, rate limit, auditável
```

### 6.2 Permissões e proteções

- Visibilidade por área (o usuário vê os agentes/skills da sua área);
- Canal = escopo mínimo de integração, com **token próprio** e revogável;
- Rate limits: 100 req/min por token na API, 30–60/min por IP nas rotas públicas
  (Ajuda), login 5/min com bloqueio temporário;
- Sessão com CSRF, hash de senha (scrypt), SSO OIDC opcional (Azure AD, Okta,
  Keycloak, Google) e 2FA quando configurado no provedor.

---

## 7. Modelos de IA (híbrido)

| Tipo | Onde roda | Quando usar |
|:-----|:---------|:-----------|
| **Local** | Servidor/GPU do cliente (llama.cpp, LM Studio, vLLM, Ollama) | Dados sensíveis, rotinas, custo previsível |
| **Externo opcional** | Provedores OpenAI-compatíveis (OpenRouter, DeepSeek, OpenAI) | Capacidade extra sob controle do cliente |

- **Fallback automático:** cada agente define um modelo secundário usado quando o
  principal falha ou está indisponível;
- **Modo da API:** `openai_chat` (padrão) ou `responses` — permite cadastrar um
  **agente externo** (ex.: Oracle AIDP `/chat`) como "modelo" da plataforma;
- **Modelo de roteamento** (obrigatório na prática): precisa ser **pequeno,
  inteligente e rápido** e **instruct (nunca reasoning** — modelo de raciocínio
  com limite de tokens cortado devolve vazio e multiplica a latência). Validado em
  produção: `qwen3-4b-instruct-2507` (LM Studio) — pergunta simples ~1,6 s (antes
  6–17 s). Sem ele, o roteamento usa o modelo principal do agente (mais lento/caro).

### 7-A. RAG (Retrieval-Augmented Generation)

Base de conhecimento local do cliente (documentos, políticas, contratos,
manuais), indexada em **TF-IDF + cosseno (Python puro)**:

- Cresce por **cadastro manual, import CSV/PDF e indexação de skills** — desde a
  v0.10.14 **não** recebe gravação automática de conversas/chamadas;
- Em tempo de inferência, os trechos relevantes são injetados no contexto;
- Export JSONL (com máscara LGPD) para fine-tuning; **sem libs externas**, 100%
  on-premise.

---

## 8. Skills e Conectores (Camada 2)

### 8.1 Skills (por área, parametrizáveis)

`vendas` · `suporte` · `financeiro` · `rh` · `operacoes` (e novas áreas criadas na
tela **Áreas**). A skill é um `SKILL.md` com descrição **e corpo** — ambos vão ao
prompt do agente (limite de 4.000 caracteres por skill).

### 8.2 Conectores (configuráveis pelo admin, por área)

| Tipo | Uso | Recursos |
|:-----|:----|:---------|
| 🌐 **API REST** | serviços HTTP/JSON, ERPs, cotações, Databricks/Snowflake por REST | auth none/bearer/OAuth2 (token com cache), timeout, **polling de job assíncrono**, **mapeamento da resposta** |
| 🤝 **A2A** | agentes publicados no protocolo Agent2Agent (Oracle Autonomous, AIDP `/a2a`) | `message/send`, agent card, auth OAuth2/bearer |
| 🔌 **MCP** | servidores de ferramentas (stdio local ou SSE remoto) | JSON-RPC 2.0, tool + argumentos com parâmetros |
| 🗄️ **SQL** | bancos do cliente e warehouses | PostgreSQL/MySQL/SQL Server/Oracle, SSL mode (Databricks), wallet Oracle Autonomous (mTLS), consulta inteligente |

**Roteamento:** antes de executar, uma IA curta decide **quais conectores da área**
são relevantes para a pergunta (ou nenhum) — pergunta de norma responde só com a
base de conhecimento. Se a seleção falhar, executa todos (nunca deixa o agente
sem dados).

---

## 8-B. Feature Matrix (visão de produto)

| Modelos & IA | Agentes & Contexto | Operações & Governança |
|:-------------|:-------------------|:-----------------------|
| Modelos locais e externos com fallback | Agent Factory e reaproveitamento | Auditoria e rastreabilidade |
| Roteamento por IA (conectores + parâmetros) | Contexto dinâmico (memória + RAG + conectores) | Observabilidade, custo por tokens e alertas |
| Fine-tuning (export JSONL) | Skills por área com corpo no prompt | RBAC, rate limit e tokens revogáveis |
| Memória por usuário | Segmentação por área | LGPD (máscaras, finalidade, retenção) |
| Teste A/B entre modelos | Conectores configuráveis (API/A2A/MCP/SQL) | Gateway OpenAI + API de canal + webhook |

---

## 8-C. Contexto Dinâmico

O contexto de cada resposta combina, sempre atualizado:

1. **Memória por usuário** — histórico persistente do usuário logado;
2. **RAG** — documentos do cliente recuperados em tempo de inferência;
3. **Conectores da área** — dados reais dos sistemas internos, escolhidos por
   roteamento por IA;
4. **Skills** — regras de comportamento/formato da área.

**Princípio:** o agente nunca responde "de cabeça" quando há dado atualizado
disponível; sem dados, ele diz que não encontrou (nunca inventa).

---

## 8-D. Segmentação

Segmentação por **área da empresa** (criadas na tela Áreas; `BLUESHIFT_AREAS`
serve como seed do primeiro boot).

| Dimensão | Implementação |
|:---------|:--------------|
| Dados | Conectores e documentos pertencem a uma área |
| Acesso | Permissões e agentes liberados por área |
| Usuários | Vinculados à(s) sua(s) área(s) |

---

## 8-E. Agent Factory e Reaproveitamento

- **Agente** = modelo (principal + fallback) + skills + conectores da área;
- **Skill** = unidade reutilizável (`SKILL.md` + corpo) parametrizável por área;
- **Reaproveitamento:** o agente é montado a partir do catálogo — não reescrito
  por cliente; o mesmo agente serve para novos clientes trocando modelos/áreas.

---

## 8-F. Observabilidade, Rastreabilidade e Monitoramento

| Capacidade | O que entrega |
|:-----------|:-------------|
| **Rastreabilidade** | Auditoria completa: quem perguntou, qual agente, conectores usados, parâmetros extraídos e resposta |
| **Observabilidade** | KPIs, custo por tokens, feedback (manual/API/gateway), teste A/B e **tracing por fases** por resposta (roteador, conectores, RAG, modelo) |
| **Monitoramento** | Health do portal/gateway, heartbeat dos conectores, alertas configuráveis e arquivo morto (snapshot + corte de dados antigos) |

**Princípio:** todo acesso a dado do cliente é auditável (quem + quando + o quê).

---

## 8-G. Setup de Desenvolvimento

- **Repositório único** (`bp-proj`) com venv próprio (`bp-venv`) e `pip install -e .`;
- **Documentação:** `README.md` (entrada), **`docs/`** (documentação navegável,
  dentro do produto) e este PRD;
- **Qualidade:** `tools/doc_check.py` (gate que impede código sem documentação) e
  `tests/` (testes locais de regressão);
- **Release:** `git tag` + Release no GitHub; a instalação atualiza pela tela
  **Atualizações** (update via Git, dados preservados).

Passo a passo completo: **`README.md`**.

---

## 10. Pendências / Decisões em aberto

| Item | Status | Próximo passo |
|:-----|:------|:--------------|
| Licença source-available + chave por cadastro | ✅ v0.10.11/0.10.12 | URL definitiva da página de solicitação no site da BlueShift |
| LGPD (máscaras, finalidade, retenção) | ✅ v0.8.0 / F1–F6 | — |
| Conector Oracle (thin) | ✅ v0.8.1 | — |
| Teste A/B entre modelos | ✅ v0.8.1 | — |
| Fine-tuning (export JSONL) | ✅ v0.8.1 | Engine de treino é serviço externo (não faz parte do produto) |
| MCP remoto (SSE) + editar/suspender usuários | ✅ pós-v0.8.1 | — |
| Ajuda IA sobre a documentação | ✅ v0.9.1 | — |
| Tema claro/escuro/sistema, Workspace e tokens por agente | ✅ v0.9.x | — |
| Latência: instrumentação por fases + RAG sem auto-feed + export JSONL de memórias | ✅ v0.10.14 | Cache do RAG por versão (escala) |
| Guard de resposta (`tool_call`/`think` crus) | ✅ v0.10.15 | — |
| Corpo das skills no prompt | ✅ v0.10.16 | — |
| Connector Pack: OAuth2/bearer, polling + mapeamento, A2A, SSL/wallet, Modo `responses` | ✅ v0.11.0 | Validação fim-a-fim com credenciais reais de Databricks/Autonomous/AIDP |
| Documentação navegável + Ajuda IA na mesma fonte + API Reference + Changelog + gate doc × código | ✅ v0.11.1 | Site interno de documentação (não publicado por decisão) |
| Snowflake | ⏳ decisão pendente | Dependência pesada (`snowflake-connector-python`) x REST com polling — decidir com o cliente |
| A2A completo (streaming e multi-turno) | ⏳ fase 2 | Implementar quando houver caso de uso |
| Modelo de roteamento embutido na plataforma | ⏳ avaliado | Hoje: modelo externo dedicado (LM Studio/llama-server); embutir exigiria binário + pesos na imagem |
| Oracle AIDP / Autonomous como fonte de dados | ⏳ validar com o cliente | Precisa de credenciais para teste fim-a-fim |

---

## 12. Resumo para investidor/cliente (one-liner)

> "CL Agents (BlueShift IA Platform) é uma plataforma de IA que você instala DENTRO
> da sua empresa — funciona em qualquer segmento. Seus dados não saem. Modelos
> cadastrados por você, com opção local. Conecta nos seus sistemas (API, banco,
> agentes e ferramentas) e responde com dados reais, com auditoria e LGPD. Licença
> anual por empresa, não por token."
