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
