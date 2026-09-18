<!-- sync: 12-api-reference.md@976b627c7b1f | checar: python tools/readme_check.py -->
🌐 [Português](../12-api-reference.md) · **English** · [Español](../es/12-api-reference.md)

## 12. API Reference (integration)

Reference for the customer's IT team to integrate CL Agents. There are **two
entry points**:

| Entry point | What for | Authentication | Default port |
|:--------|:---------|:-------------|:------------:|
| **Portal API** (`/portal/api/v1/*`) | The customer's system calls the agent (JSON) | **Channel** token | 8090 |
| **OpenAI-compatible Gateway** (`/v1/*`) | Chats and tools that speak the OpenAI protocol (Open WebUI, LibreChat, apps) | **Channel** token with an active gateway | 9003 |

**Authentication** — the token is the **channel token** (`bs_chan_*`), generated in
Registry (Cadastros) → Channels (Canais) (*new key* — *nova chave* — button). Send it in
`Authorization: Bearer <token> the portal API also accepts `?token=<token>`.
⚠️ The **license key does not work** as a channel token — they are different
credentials, and each channel has its own token (individually revocable).

### 12.1 POST /portal/api/v1/agente — call the agent

```
POST /portal/api/v1/agente
Authorization: Bearer bs_chan_...
Content-Type: application/json

{"pergunta": "Quais os top 5 produtos mais vendidos de 2026?"}
```

| Field | Required | What it is |
|:------|:-----------:|:--------|
| `pergunta` | ✅ | Question text (no question → HTTP 400) |
| `usuario` | ❌ | Identification of who asked (max. 40 chars; default `canal:<id>`) |
| `id_cliente` | ❌ | Value that feeds the `{id_cliente}` placeholders of the connectors |
| `contexto` | ❌ | Previous messages of the conversation (they only go into the prompt; memory stores the real question) |
| `origem` | ❌ | Marks the origin (e.g.: `gateway`); with `gateway` the platform records automatic feedback of type `gateway` |

Response (clean JSON — no context and no tools):

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

- `tempo_ms` is the total pipeline time (RAG + connectors + model);
- `webhook` only appears when the channel has an outbound webhook configured —
  **best-effort** delivery with exponential retry (2 s, 4 s); if it fails, the
  agent's response is still delivered (`{"enviado": false, "motivo": "..."}`);
- the call is recorded in the **Audit (Auditoria)** and becomes a **trace** (visible in
  Observability (Observabilidade) / Tracking (Rastreio)).

Example with `curl`:

```bash
curl -X POST http://HOST:8090/portal/api/v1/agente \
  -H "Authorization: Bearer bs_chan_..." \
  -H "Content-Type: application/json" \
  -d '{"pergunta":"Quais os filmes alugados pelo id_cliente=21?"}'
```

### 12.2 POST /portal/api/v1/feedback/&lt;trace_id&gt; — record feedback

```
POST /portal/api/v1/feedback/123
Content-Type: application/json

{"util": true, "tipo": "api"}
```

| Field | Required | What it is |
|:------|:-----------:|:--------|
| `util` | ❌ | `true` (default) = useful; `false` = not useful |
| `tipo` | ❌ | `api` (default, integration) · `manual` (button in the UI) · `gateway` (automatic from external chats) |

Response: `{"ok": true, "feedback_id": 1}` — **404** if the `trace_id` does not exist.
The `trace_id` comes in the `feedback_url` of the agent's response.

### 12.3 OpenAI-compatible Gateway (`:9003`)

It serves external chats that speak the OpenAI protocol. The **agent is chosen by
the `model` field** (`agente:<agent name>`); the token only authenticates (it can be
the same token for several agents, as Open WebUI does).

**List agents published as models:**

```
GET /v1/models
```

```json
{"object":"list","data":[{"id":"agente:Agente Vendas","object":"model","owned_by":"blueshift"}]}
```

**Chat (OpenAI format):**

```
POST /v1/chat/completions
Authorization: Bearer bs_chan_...
Content-Type: application/json

{"model":"agente:Agente Vendas","messages":[{"role":"user","content":"Olá"}]}
```

- the **last user message** becomes the agent's question;
- if the channel is in **streaming** mode, the response is SSE
  (`text/event-stream`) with chunks in the `chat.completion.chunk` format,
  ending with `data: [DONE]`;
- requests for a **conversation title** (an extra call that Open WebUI makes) are
  answered right away, without spending tokens or recording a trace;
- every conversation generates automatic feedback of type `gateway` (it appears in
  Observability (Observabilidade) and in A/B Testing (Teste A/B), separate from manual feedback).

Errors: **400** without user message · **401** invalid token or inactive
gateway · **404** no active gateway · **502** agent failure.

**Typical configuration in Open WebUI:** base URL `http://HOST:9003/v1`,
key = channel token, and the models appear as `agente:<name>`.

### 12.4 Infrastructure and help

| Endpoint | Method | Auth | What for |
|:---------|:------:|:----:|:---------|
| `/healthz` (portal) | GET | public | Portal health check (returns database state and version) |
| `/healthz` (gateway) | GET | public | Gateway health check |
| `/portal/api/ajuda/modelos` | GET | public | Lists the models available for the Help (Ajuda) popup |
| `/portal/api/ajuda` | POST | public | Help (Ajuda) popup: `{"pergunta": "..."}` → answer based on the documentation |

### 12.5 Errors and limits

| HTTP | When it happens | Body |
|:----:|:----------------|:------|
| 400 | `pergunta` missing (portal) or no user message (gateway) | `{"ok": false, "erro": "..."}` / `{"error": {"message": ...}}` |
| 401 | Token missing/invalid or gateway paused | `{"ok": false, "erro": "..."}` |
| 404 | Agent/trace does not exist (portal) or no active gateway | `{"ok": false, "erro": "..."}` |
| 429 | Request limit exceeded | `{"erro": "limite de requisicoes excedido (100/min)"}` |
| 502 | The model did not respond | `{"ok": false, "erro": "..."}` |

Default limits: **100 req/min** per token on the agent and feedback APIs;
**30/min per IP** on Help and **60/min per IP** on the popup's model list;
login **5/min** with temporary lockout (brute-force protection).

**Security and LGPD notes:** each channel has its own revocable token; every
API call is audited (channel, agent, IP and summarized question); the LGPD masks,
when enabled, are applied **in the response** (the platform does not store
personal data from the source system — it queries the source on the spot).
