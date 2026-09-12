## 12. API Reference (integração)

Referência para o time de TI do cliente integrar o CL Agents. Existem **dois
pontos de entrada**:

| Entrada | Para quê | Autenticação | Porta padrão |
|:--------|:---------|:-------------|:------------:|
| **API do Portal** (`/portal/api/v1/*`) | O sistema do cliente chama o agente (JSON) | Token de **canal** | 8090 |
| **Gateway OpenAI-compatível** (`/v1/*`) | Chats e ferramentas que falam o protocolo OpenAI (Open WebUI, LibreChat, apps) | Token de **canal** com gateway ativo | 9003 |

**Autenticação** — o token é o **token do canal** (`bs_chan_*`), gerado em
Cadastros → Canais (botão *nova chave*). Envie em
`Authorization: Bearer <token>`; a API do portal também aceita `?token=<token>`.
⚠️ A **chave de licença não serve** como token de canal — são credenciais
diferentes, e cada canal tem o seu token (revogável individualmente).

### 12.1 POST /portal/api/v1/agente — chamar o agente

```
POST /portal/api/v1/agente
Authorization: Bearer bs_chan_...
Content-Type: application/json

{"pergunta": "Quais os top 5 produtos mais vendidos de 2026?"}
```

| Campo | Obrigatório | O que é |
|:------|:-----------:|:--------|
| `pergunta` | ✅ | Texto da pergunta (sem pergunta → HTTP 400) |
| `usuario` | ❌ | Identificação de quem perguntou (máx. 40 chars; padrão `canal:<id>`) |
| `id_cliente` | ❌ | Valor que alimenta os placeholders `{id_cliente}` dos conectores |
| `contexto` | ❌ | Mensagens anteriores da conversa (entram só no prompt; a memória grava a pergunta real) |
| `origem` | ❌ | Marca a origem (ex.: `gateway`); com `gateway` a plataforma registra feedback automático do tipo `gateway` |

Resposta (JSON limpo — sem contexto nem ferramentas):

```json
{
  "ok": true,
  "resposta": "1) ...",
  "pergunta": "Quais os top 5 produtos mais vendidos de 2026?",
  "agente": "Agente Vendas",
  "modelo": "qwen3-4b-instruct-2507",
  "feedback_url": "http://host:8090/portal/api/v1/feedback/123",
  "erro": null,
  "tokens": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
  "tempo_ms": 1542,
  "webhook": {"enviado": true, "status": 200}
}
```

- `tempo_ms` é o tempo total do pipeline (RAG + conectores + modelo);
- `webhook` só aparece quando o canal tem webhook de saída configurado —
  envio **best-effort** com retry exponencial (2 s, 4 s); se falhar, a resposta
  do agente continua sendo entregue (`{"enviado": false, "motivo": "..."}`);
- a chamada é registrada na **Auditoria** e vira **trace** (visível em
  Observabilidade / Rastreio).

Exemplo com `curl`:

```bash
curl -X POST http://HOST:8090/portal/api/v1/agente \
  -H "Authorization: Bearer bs_chan_..." \
  -H "Content-Type: application/json" \
  -d '{"pergunta":"Quais os filmes alugados pelo id_cliente=21?"}'
```

### 12.2 POST /portal/api/v1/feedback/&lt;trace_id&gt; — registrar feedback

```
POST /portal/api/v1/feedback/123
Content-Type: application/json

{"util": true, "tipo": "api"}
```

| Campo | Obrigatório | O que é |
|:------|:-----------:|:--------|
| `util` | ❌ | `true` (padrão) = útil; `false` = não útil |
| `tipo` | ❌ | `api` (padrão, integração) · `manual` (botão na UI) · `gateway` (automático de chats externos) |

Resposta: `{"ok": true, "feedback_id": 1}` — **404** se o `trace_id` não existir.
O `trace_id` vem no `feedback_url` da resposta do agente.

### 12.3 Gateway OpenAI-compatível (`:9003`)

Serve chats externos que falam o protocolo OpenAI. O **agente é escolhido pelo
campo `model`** (`agente:<nome do agente>`); o token apenas autentica (pode ser
o mesmo token para vários agentes, como o Open WebUI faz).

**Listar agentes publicados como modelos:**

```
GET /v1/models
```

```json
{"object":"list","data":[{"id":"agente:Agente Vendas","object":"model","owned_by":"blueshift"}]}
```

**Conversar (formato OpenAI):**

```
POST /v1/chat/completions
Authorization: Bearer bs_chan_...
Content-Type: application/json

{"model":"agente:Agente Vendas","messages":[{"role":"user","content":"Olá"}]}
```

- a **última mensagem do usuário** vira a pergunta do agente;
- se o canal estiver em modo **streaming**, a resposta é SSE
  (`text/event-stream`) com chunks no formato `chat.completion.chunk`,
  terminando em `data: [DONE]`;
- pedidos de **título de conversa** (chamada extra que o Open WebUI faz) são
  respondidos na hora, sem gastar tokens nem gravar trace;
- cada conversa gera feedback automático do tipo `gateway` (aparece na
  Observabilidade e no Teste A/B, separado do feedback manual).

Erros: **400** sem mensagem de usuário · **401** token inválido ou de gateway
inativo · **404** nenhum gateway ativo · **502** falha no agente.

**Configuração típica no Open WebUI:** URL base `http://HOST:9003/v1`,
chave = token do canal, e os modelos aparecem como `agente:<nome>`.

### 12.4 Infraestrutura e ajuda

| Endpoint | Método | Auth | Para quê |
|:---------|:------:|:----:|:---------|
| `/healthz` (portal) | GET | pública | Health check do portal (retorna estado do banco e versão) |
| `/healthz` (gateway) | GET | pública | Health check do gateway |
| `/portal/api/ajuda/modelos` | GET | pública | Lista modelos disponíveis para o popup de Ajuda |
| `/portal/api/ajuda` | POST | pública | Popup de Ajuda: `{"pergunta": "..."}` → resposta baseada na documentação |

### 12.5 Erros e limites

| HTTP | Quando acontece | Corpo |
|:----:|:----------------|:------|
| 400 | `pergunta` ausente (portal) ou sem mensagem de usuário (gateway) | `{"ok": false, "erro": "..."}` / `{"error": {"message": ...}}` |
| 401 | Token ausente/inválido ou gateway pausado | `{"ok": false, "erro": "..."}` |
| 404 | Agente/trace inexistente (portal) ou nenhum gateway ativo | `{"ok": false, "erro": "..."}` |
| 429 | Limite de requisições excedido | `{"erro": "limite de requisicoes excedido (100/min)"}` |
| 502 | O modelo não respondeu | `{"ok": false, "erro": "..."}` |

Limites por padrão: **100 req/min** por token nas APIs de agente e feedback;
**30/min por IP** na Ajuda e **60/min por IP** na lista de modelos do popup;
login **5/min** com bloqueio temporário (proteção contra força bruta).

**Notas de segurança e LGPD:** cada canal tem token próprio e revogável; toda
chamada de API é auditada (canal, agente, IP e pergunta resumida); as máscaras
de LGPD, quando ligadas, são aplicadas **na resposta** (a plataforma não
armazena dados pessoais do sistema de origem — ela consulta a fonte na hora).
