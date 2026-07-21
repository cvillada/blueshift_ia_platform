# BlueShift IA Platform (dev)

Plataforma própria de IA on-premise — Flask standalone 100% Python, sem dependência de motor externo. Deploy via Docker + license key.

## Setup
```bash
python3 -m venv bp-venv && source bp-venv/bin/activate
pip install -e .
blueshift --help
```

## Comandos
- `blueshift init <cliente>` — cria perfil do cliente
- `blueshift activate <chave>` — valida license key
- `blueshift status` — mostra estado do container
- `blueshift update` — checa atualizações aprovadas
- `blueshift portal [--host 0.0.0.0] [--port 8080]` — sobe o Portal do Cliente
- `blueshift mcp` — sobe o servidor MCP stdio (conectores CRM/RH/ERP)

## Portal do Cliente
Dashboard web que gerencia, cadastra e monitora a plataforma. Roda 100% on-premise
(SQLite local, sem rede externa). Acesso: `blueshift portal` e abra
`http://localhost:8080/portal` (login demo: `admin` / `admin123`).

Telas:
- **Monitorar** — dashboard de saúde por cliente (container, modelo local, latência, tokens, conectores online/offline, erros 24h) (login)
- **Workspace** — painel por departamento: admin vê todas as áreas; gestor/usuário vê só a sua área (vendas/suporte/financeiro/rh/operações). Mostra agentes, usuários e base de conhecimento da área (login)
- **Clientes** — gerenciar + cadastrar (admin)
- **Usuários** — gerenciar + cadastrar, papéis: admin / gestor / usuário / sistema; cada usuário pode ser vinculado a uma ÁREA (admin)
- **Agentes** — Agent Factory: monta agentes reais a partir de Modelo de IA (principal + **fallback** automático) + Skills do catálogo + Conectores MCP; cada agente tem tela de teste (RAG + LLM real) (admin)
- **Memória** — memória persistente por usuário (banco vetorial local, isolada por login)
- **Conhecimento** — base de conhecimento do cliente / RAG (manual, política, base, contrato)
- **Modelos IA** — cadastro de LLMs por cliente (OpenAI-compatible: local, servidor interno ou externo), com status online/offline (admin)
- **Chat** — chat de teste do contexto dinâmico: recupera memória + RAG e envia ao modelo de IA cadastrado (100% on-premise)
- **Conectores** — Connector Pack (ERP/CRM/RH) por cliente. CRM e RH são conectores REAIS (dados de exemplo locais, sem rede); ERP conecta a Postgres (demo/real via env, com fallback gracioso). O agente EXECUTA essas ferramentas e injeta os dados no contexto. Além do uso interno pelo agente, os conectores são expostos como **servidor MCP stdio** (`blueshift mcp`) em Python puro (JSON-RPC 2.0) para clientes externos (Claude Desktop, Cursor, outro Hermes) — sem libs externas.
- **Canais** — canal de integração REAL (API/webhook): cada canal tem um token e aponta para 1 agente. Expõem `POST /portal/api/v1/agente` (auth Bearer) que recebe `{pergunta}` e responde em JSON via o agente (LLM + RAG + conectores). Opcionalmente, cada canal pode ter um **Webhook de saída** (URL que recebe a resposta via POST — item de integração com sistemas externos). Admin cria/gerencia canais no Portal.
- **Atualizações** — Update Channel real: consulta o canal aprovado da BlueShift (`BLUESHIFT_UPDATE_URL`, mock na 9001 em dev) e mostra/instala a nova versão da camada (dry-run em dev, `pip install` em prod).

Canal real (integração): fora do Portal, qualquer sistema externo (site, CRM, Zapier, webhook) chama o agente com o token do canal. Exemplo:
```bash
curl -X POST http://localhost:8080/portal/api/v1/agente \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual o histórico do cliente C001?"}'
# -> {"ok": true, "resposta": "...", "agente": "...", "modelo": "...", "contexto": [...], "ferramentas": [...],
#     "webhook": {"enviado": true, "status": 200}}   # se o canal tiver webhook de saída
```

Modelo híbrido: o cadastro de Modelos IA aceita qualquer endpoint OpenAI-compatible — local (vLLM/LM Studio/Ollama) ou externo (OpenAI/Claude/DeepSeek) via `api_key` opcional. O `llm_client.py` envia o Bearer token quando presente.

- **Uso de Tokens** — análise de consumo de tokens por chamada ao LLM (cliente, modelo, origem, prompt/completion). Cobrança é contrato anual externo (info estática exibida na tela) (admin)
- **Auditoria** — rastreabilidade LGPD: todo login e ação sensível é registrado (admin)
- **SSO (OIDC)** — login federado opcional (admin configura o provedor; mantém o login local). Modo dev com IdP mock interno para teste.

Controle de acesso: hierarquia admin > gestor > usuário > sistema. Rotas de
gerenciamento exigem papel admin; usuários comuns só conseguem ver dashboards
e gerenciar a própria memória (isolada por login).

Contexto Dinâmico: a Memória por usuário e a Base de Conhecimento (RAG)
alimentam o "contexto dinâmico" do agente. O banco vetorial é local (TF-IDF + cosseno
em Python puro, sem libs externas), entregando similaridade sem dependência de rede.

## SSO (OIDC) — Login Federado

O Portal suporta login federado via OIDC (Azure AD, Okta, Keycloak, Google) SEM
substituir o login local — ambos convivem. O SSO só resolve IDENTIDADE; o PAPEL
vem do cadastro local (RBAC admin/gestor/usuário/sistema continua igual).

- Admin configura em **SSO (OIDC)**: liga/desliga, preenche `issuer`, `client_id`,
  `client_secret`, `redirect_uri` e opcionalmente um domínio de admin.
- Fluxo: botão "Entrar com SSO" na tela de login -> redirect ao IdP -> callback
  troca o `code` por um `id_token` (JWT) -> o usuário é mapeado (por email/login)
  ou criado automaticamente se `auto_criar=1`.
- Implementado 100% em Python puro (urllib + JWT HMAC via hashlib, sem libs).
- **Modo dev**: um IdP mock interno (`/sso/mock_authorize`) permite validar TODO o
  fluxo SSO localmente, sem um provedor real. Ideal para demonstrações e testes.

## Docker
O container sobe o License Server mock (porta 9000) + Update Channel (porta 9001) + Portal (8080).

### Installer de cliente (recomendado)
```bash
cp .env.example .env          # ajuste BLUESHIFT_LICENSE e as portas
./install.sh                  # docker compose up -d --build + aguarda health
```
Acesse `http://localhost:8080/portal` (login demo: `admin` / `admin123`).

**Modelos de IA NÃO vêm embutidos.** O installer sobe a plataforma; o cliente cadastra
os próprios modelos na tela **Modelos IA** (local vLLM/LM Studio/Ollama, ou externo
DeepSeek/OpenRouter/OpenAI/Claude). Cada agente define qual modelo usa.

### Manual (sem installer)
```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker run -e BLUESHIFT_LICENSE=BS-DEV-teste123 blueshift/platform            # status
docker run -e BLUESHIFT_LICENSE=BS-DEV-teste123 -p 8080:8080 \
       blueshift/platform blueshift portal                                    # portal
```
Em produção o License Server mock é substituído pelo backend real
(`BLUESHIFT_LICENSE_URL` aponta para `https://license.blueshift.app/v1/validate`).

## Estrutura
```
blueshift_layer/
  cli.py                  comandos init/activate/status/update/portal/mcp
  license_client.py       valida chave no License Server
  license_server_mock.py  License Server mock (Flask, porta 9000)
  installer.py            cria perfil do cliente no 1º boot
  update_client.py        checa/aplica Update Channel aprovado (urllib puro)
  update_server.py        Update Channel Server mock (Flask, porta 9001)
  portal/                 Portal do Cliente
    __init__.py           app factory create_app()
    db.py                 acesso único ao SQLite (clientes, usuarios, agentes, conectores, uso_tokens, contratos, auditoria, memories, knowledge, modelos, canais)
    auth.py               sessão + RBAC (login_required / admin_required)
    views.py              rotas/telas
    templates.py          layout dark/azul da marca
    memory.py             banco vetorial local (TF-IDF + cosseno, Python puro) — Memória + RAG
    llm_client.py         client LLM OpenAI-compatible (urllib puro)
    agente.py             orquestrador do Agent Factory: liga modelo + skills + RAG e executa o agente
    sso.py                login federado OIDC (Python puro)
  connector_pack/         servidores MCP (erp, crm, rh) — conectores reais
    registry.py           instancia e executa ferramentas dos conectores
    mcp_server.py         servidor MCP stdio (Python puro, JSON-RPC 2.0) — expõe CRM/RH/ERP
    mcp_erp.py            conector ERP (Postgres ou fallback exemplo)
    mcp_crm.py            conector CRM (dados de exemplo)
    mcp_rh.py             conector RH (dados de exemplo)
  template_skills/        skills por área (vendas, suporte, financeiro, rh, operacoes)
docker/
  Dockerfile              imagem do container
  entrypoint.sh           sobe License Server + Update Channel + app
install.sh               bootstrap: valida Docker, cria .env, sobe via compose
```
