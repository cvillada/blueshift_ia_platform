<!-- sync: 12-api-reference.md@976b627c7b1f | checar: python tools/readme_check.py -->
🌐 [Português](../12-api-reference.md) · [English](../en/12-api-reference.md) · **Español**

## 12. API Reference (integración)

Referencia para que el equipo de TI del cliente integre CL Agents. Existen **dos
puntos de entrada**:

| Entrada | Para qué | Autenticación | Puerto predeterminado |
|:--------|:---------|:-------------|:------------:|
| **API del Portal** (`/portal/api/v1/*`) | El sistema del cliente llama al agente (JSON) | Token de **canal** | 8090 |
| **Gateway compatible con OpenAI** (`/v1/*`) | Chats y herramientas que hablan el protocolo OpenAI (Open WebUI, LibreChat, apps) | Token de **canal** con gateway activo | 9003 |

**Autenticación** — el token es el **token del canal** (`bs_chan_*`), generado en
Registros → Canales (Cadastros → Canais) con el botón *nova chave*. Envíelo en
`Authorization: Bearer <token>`; la API del portal también acepta `?token=<token>`.
⚠️ La **clave de licencia no sirve** como token de canal — son credenciales
diferentes, y cada canal tiene su propio token (revocable individualmente).

### 12.1 POST /portal/api/v1/agente — llamar al agente

```
POST /portal/api/v1/agente
Authorization: Bearer bs_chan_...
Content-Type: application/json

{"pergunta": "¿Cuáles son los 5 productos más vendidos de 2026?"}
```

| Campo | Obligatorio | Qué es |
|:------|:-----------:|:--------|
| `pergunta` | ✅ | Texto de la pregunta (sin pregunta → HTTP 400) |
| `usuario` | ❌ | Identificación de quien preguntó (máx. 40 caracteres; predeterminado `canal:<id>`) |
| `id_cliente` | ❌ | Valor que alimenta los placeholders `{id_cliente}` de los conectores |
| `contexto` | ❌ | Mensajes anteriores de la conversación (entran solo en el prompt; la memoria guarda la pregunta real) |
| `origem` | ❌ | Marca el origen (ej.: `gateway`); con `gateway` la plataforma registra feedback automático del tipo `gateway` |

Respuesta (JSON limpio — sin contexto ni herramientas):

```json
{
  "ok": true,
  "resposta": "1) ...",
  "pergunta": "¿Cuáles son los 5 productos más vendidos de 2026?",
  "agente": "Agente Vendas",
  "modelo": "qwen3-4b-instruct-2507",
  "feedback_url": "http://host:8090/portal/api/v1/feedback/123",
  "erro": null,
  "tokens": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
  "tempo_ms": 1542,
  "webhook": {"enviado": true, "status": 200}
}
```

- `tempo_ms` es el tiempo total del pipeline (RAG + conectores + modelo);
- `webhook` solo aparece cuando el canal tiene webhook de salida configurado —
  envío **best-effort** con retry exponencial (2 s, 4 s); si falla, la respuesta
  del agente se entrega igual (`{"enviado": false, "motivo": "..."}`);
- la llamada queda registrada en la **Auditoría (Auditoria)** y se convierte en
  **trace** (visible en Observabilidad / Rastreo (Observabilidade / Rastreio)).

Ejemplo con `curl`:

```bash
curl -X POST http://HOST:8090/portal/api/v1/agente \
  -H "Authorization: Bearer bs_chan_..." \
  -H "Content-Type: application/json" \
  -d '{"pergunta":"¿Cuáles son las películas alquiladas por el id_cliente=21?"}'
```

### 12.2 POST /portal/api/v1/feedback/&lt;trace_id&gt; — registrar feedback

```
POST /portal/api/v1/feedback/123
Content-Type: application/json

{"util": true, "tipo": "api"}
```

| Campo | Obligatorio | Qué es |
|:------|:-----------:|:--------|
| `util` | ❌ | `true` (predeterminado) = útil; `false` = no útil |
| `tipo` | ❌ | `api` (predeterminado, integración) · `manual` (botón en la UI) · `gateway` (automático de chats externos) |

Respuesta: `{"ok": true, "feedback_id": 1}` — **404** si el `trace_id` no existe.
El `trace_id` viene en el `feedback_url` de la respuesta del agente.

### 12.3 Gateway compatible con OpenAI (`:9003`)

Atiende chats externos que hablan el protocolo OpenAI. El **agente se elige por el
campo `model`** (`agente:<nombre del agente>`); el token solo autentica (puede ser
el mismo token para varios agentes, como lo hace Open WebUI).

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

{"model":"agente:Agente Vendas","messages":[{"role":"user","content":"Hola"}]}
```

- el **último mensaje del usuario** pasa a ser la pregunta del agente;
- si el canal está en modo **streaming**, la respuesta es SSE
  (`text/event-stream`) con chunks en el formato `chat.completion.chunk`,
  y termina en `data: [DONE]`;
- las peticiones de **título de conversación** (llamada extra que hace Open WebUI)
  se responden al instante, sin gastar tokens ni grabar trace;
- cada conversación genera feedback automático del tipo `gateway` (aparece en la
  Observabilidad y en la Prueba A/B (Teste A/B), separado del feedback manual).

Errores: **400** sin mensaje de usuario · **401** token inválido o de gateway
inactivo · **404** ningún gateway activo · **502** fallo en el agente.

**Configuración típica en Open WebUI:** URL base `http://HOST:9003/v1`,
clave = token del canal, y los modelos aparecen como `agente:<nombre>`.

### 12.4 Infraestructura y ayuda

| Endpoint | Método | Auth | Para qué |
|:---------|:------:|:----:|:---------|
| `/healthz` (portal) | GET | pública | Health check del portal (devuelve el estado de la base y la versión) |
| `/healthz` (gateway) | GET | pública | Health check del gateway |
| `/portal/api/ajuda/modelos` | GET | pública | Lista los modelos disponibles para el popup de Ayuda (Ajuda) |
| `/portal/api/ajuda` | POST | pública | Popup de Ayuda: `{"pergunta": "..."}` → respuesta basada en la documentación |

### 12.5 Errores y límites

| HTTP | Cuándo ocurre | Cuerpo |
|:----:|:----------------|:------|
| 400 | `pergunta` ausente (portal) o sin mensaje de usuario (gateway) | `{"ok": false, "erro": "..."}` / `{"error": {"message": ...}}` |
| 401 | Token ausente/inválido o gateway en pausa | `{"ok": false, "erro": "..."}` |
| 404 | Agente/trace inexistente (portal) o ningún gateway activo | `{"ok": false, "erro": "..."}` |
| 429 | Límite de peticiones excedido | `{"erro": "limite de requisicoes excedido (100/min)"}` |
| 502 | El modelo no respondió | `{"ok": false, "erro": "..."}` |

Límites predeterminados: **100 req/min** por token en las APIs de agente y feedback;
**30/min por IP** en la Ayuda y **60/min por IP** en la lista de modelos del popup;
login **5/min** con bloqueo temporal (protección contra fuerza bruta).

**Notas de seguridad y LGPD:** cada canal tiene token propio y revocable; toda
llamada de API es auditada (canal, agente, IP y pregunta resumida); las máscaras
de LGPD, cuando están activadas, se aplican **en la respuesta** (la plataforma no
almacena datos personales del sistema de origen — consulta la fuente en el momento).
