# BlueShift IA Platform (dev)

Camada empacotada sobre o Hermes-Agent (MIT) para entrega on-premise via Docker + license key.

## Setup
```bash
python3 -m venv bp-venv && source bp-venv/bin/activate
pip install -e .
blueshift --help
```

## Comandos
- `blueshift init <cliente>` — cria profile do cliente
- `blueshift activate <chave>` — valida license key
- `blueshift status` — mostra estado do container
- `blueshift update` — checa atualizacoes aprovadas
- `blueshift portal [--host 0.0.0.0] [--port 8080]` — sobe o Portal do Cliente (Camada 4)

## Portal do Cliente (Camada 4)
Dashboard web que gerencia, cadastra e monitora a plataforma. Roda 100% on-premise
(SQLite local fake, sem rede externa). Acesso: `blueshift portal` e abra
`http://localhost:8080/portal` (login demo: `admin` / `admin123`).

Telas:
- **Monitorar** — dashboard de saude por cliente (container, modelo local, latencia, tokens, conectores online/offline, erros 24h) (login)
- **Workspace** — painel por departamento (PRD §8-D): admin ve todas as areas; gestor/usuario ve so a sua area (vendas/suporte/financeiro/rh/operacoes). Mostra agentes, usuarios e base de conhecimento da area (login)
- **Clientes** — gerenciar + cadastrar (admin)
- **Usuários** — gerenciar + cadastrar, papeis: admin / gestor / usuario / sistema; cada usuario pode ser vinculado a uma AREA (admin)
- **Agentes** — Agent Factory: monta agentes reais a partir de Modelo de IA + Skills do catálogo + Conectores MCP; cada agente tem tela de teste (RAG + LLM real) (admin)
- **Memória** — memória persistente por usuário (banco vetorial local, isolada por login)
- **Conhecimento** — base de conhecimento do cliente / RAG (manual, política, base, contrato)
- **Modelos IA** — cadastro de LLMs por cliente (OpenAI-compatible: LM Studio, vLLM, Ollama), com status online/offline (admin)
- **Chat** — chat de teste do contexto dinâmico: recupera memória + RAG e envia ao modelo de IA cadastrado (100% on-premise)
- **Conectores** — Connector Pack (ERP/CRM/RH) por cliente. CRM e RH sao conectores REAIS (dados de exemplo locais, sem rede); ERP conecta a Postgres (demo/real via env, com fallback gracioso). O agente EXECUTA essas ferramentas e injeta os dados no contexto. Alem do uso interno pelo agente, os conectores sao expostos como **servidor MCP stdio** (`blueshift mcp`) em Python puro (JSON-RPC 2.0) para clientes externos (Claude Desktop, Cursor, outro Hermes) — sem libs externas.
- **Canais** — canal de integracao REAL (API/webhook): cada canal tem um token e aponta para 1 agente. Expoem `POST /portal/api/v1/agente` (auth Bearer) que recebe `{pergunta}` e responde em JSON via o agente (LLM + RAG + conectores). Opcionalmente, cada canal pode ter um **Webhook de saida** (URL que recebe a resposta via POST — item de integracao com sistemas externos). Admin cria/gere canais no Portal.
- **Atualizacoes** — Update Channel real: consulta o canal aprovado da BlueShift (`BLUESHIFT_UPDATE_URL`, mock na 9001 em dev) e mostra/instala a nova versao da camada (dry-run em dev, `pip install` em prod).

Canal real (PRD integracao): fora do Portal, qualquer sistema externo (site, CRM, Zapier, webhook) chama o agente com o token do canal. Exemplo:
```bash
curl -X POST http://localhost:8080/portal/api/v1/agente \
  -H "Authorization: Bearer bs_chan_xxx" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual o historico do cliente C001?"}'
# -> {"ok": true, "resposta": "...", "agente": "...", "modelo": "...", "contexto": [...], "ferramentas": [...],
#     "webhook": {"enviado": true, "status": 200}}   # se o canal tiver webhook de saida
```

Modelo híbrido (PRD §7): o cadastro de Modelos IA aceita qualquer endpoint OpenAI-compatible — local (LM Studio/vLLM) ou externo (OpenAI/Claude/Gemini) via `api_key` opcional. O `llm_client.py` envia o Bearer token quando presente.
- **Billing** — faturas / licenca anual por empresa (admin)
- **Suporte** — chamados tecnicos (qualquer usuario pode abrir)
- **Auditoria** — rastreabilidade LGPD: todo login e acao sensivel e registrado (admin)
- **SSO (OIDC)** — login federado opcional (admin configura o provedor; mantem o login local). Modo dev com IdP mock interno para teste.

Controle de acesso (PRD §6): hierarquia admin > gestor > usuario > sistema. Rotas de
gerenciamento exigem papel admin; usuarios comuns so conseguem ver dashboards, abrir
chamados e gerenciar a propria memoria (isolada por login).

Contexto Dinamico (PRD §8-C): a Memoria por usuario e a Base de Conhecimento (RAG)
alimentam o "contexto dinamico" do agente. O banco vetorial e local (TF-IDF + cosseno
em Python puro, sem libs externas), entregando similaridade sem dependencia de rede.

## SSO (OIDC) — Login Federado

O Portal suporta login federado via OIDC (Azure AD, Okta, Keycloak, Google) SEM
substituir o login local — ambos convivem. O SSO so resolve IDENTIDADE; o PAPEL
vem do cadastro local (RBAC admin/gestor/usuario/sistema continua igual).

- Admin configura em **SSO (OIDC)**: liga/desliga, preenche `issuer`, `client_id`,
  `client_secret`, `redirect_uri` e opcionalmente um dominio de admin.
- Fluxo: botao "Entrar com SSO" na tela de login -> redirect ao IdP -> callback
  troca o `code` por um `id_token` (JWT) -> o usuario e mapeado (por email/login)
  ou criado automaticamente se `auto_criar=1`.
- Implementado 100% em Python puro (urllib + JWT HMAC via hashlib, sem libs).
- **Modo dev**: um IdP mock interno (`/sso/mock_authorize`) permite validar TODO o
  fluxo SSO localmente, sem um provedor real. Ideal para demonstracoes e testes.

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
Em producao o License Server mock e substituido pelo backend real
(`BLUESHIFT_LICENSE_URL` aponta para `https://license.blueshift.app/v1/validate`).

## Estrutura
```
blueshift_layer/
  cli.py                  comandos init/activate/status/update/portal/mcp
  license_client.py       valida chave no License Server
  license_server_mock.py  License Server mock (Flask, porta 9000)
  installer.py            cria profile do cliente no 1o boot
  update_client.py        checa/aplica Update Channel aprovado (urllib puro)
  update_server.py        Update Channel Server mock (Flask, porta 9001)
  portal/                 Portal do Cliente (Camada 4)
    __init__.py           app factory create_app()
    db.py                 acesso unico ao SQLite (clientes, usuarios, agentes, conectores, faturas, chamados, auditoria, memories, knowledge, modelos)
    auth.py               sessao + RBAC (login_required / admin_required)
    views.py              rotas/telas
    templates.py          layout dark/azul da marca
    memory.py             banco vetorial local (TF-IDF + cosseno, Python puro) — Memoria + RAG
    llm_client.py         client LLM OpenAI-compatible (urllib puro) — fala com LM Studio / vLLM / Ollama
    agente.py             orquestrador do Agent Factory: liga modelo + skills + RAG e executa o agente
  connector_pack/         servidores MCP (erp, crm, rh) — conectores reais
    registry.py           instancia e executa ferramentas dos conectores
    mcp_server.py         servidor MCP stdio (Python puro, JSON-RPC 2.0) — expoe CRM/RH/ERP
  template_skills/        skills por area (vendas, suporte, financeiro, rh)
docker/
  Dockerfile              imagem (Hermes + camada + entrypoint)
  entrypoint.sh           sobe License Server + Update Channel + app
docker-compose.yml       installer de cliente (sobe tudo em 1 container, volumes persistentes)
.env.example             template de variaveis (license, portas, update url)
install.sh               bootstrap: valida Docker, cria .env, sobe via compose
```
