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
