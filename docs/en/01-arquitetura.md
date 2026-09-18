<!-- sync: 01-arquitetura.md@30f31e485e9d | checar: python tools/readme_check.py -->
🌐 [Português](../01-arquitetura.md) · **English** · [Español](../es/01-arquitetura.md)

## 2. Architecture

```
                    ┌─────────────────────┐
                    │   CLI (blueshift)    │  init · portal · mcp · status · update
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  🌐 PORTAL (Flask)   │  create_app() → port 8080 (Docker: 8090)
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

Main modules (blueshift_layer/):

| File | Responsibility |
|:--------|:-----------------|
| `portal/__init__.py` | App factory, global CSRF, CORS, automatic retention (LGPD) |
| `portal/views.py` | All portal routes/screens (60+ routes) |
| `portal/db.py` | Data access (SQLite), migrations, demo seed, 24 tables |
| `portal/auth.py` | RBAC (login_required, admin_required, api_key_required) + rate limit |
| `portal/templates.py` | Layout (sidebar, light/dark/system themes), HTML helpers |
| `portal/agente.py` | Orchestrator: connectors → RAG → LLM → response |
| `portal/llm_client.py` | OpenAI-compatible client (pure urllib) with fallback |
| `portal/memory.py` | TF-IDF vector (RAG) + similarity search |
| `portal/mask.py` | LGPD masking (CPF, e-mail, phone, name, address, CNPJ) |
| `portal/sso.py` | Federated OIDC login |
| `connector_pack/registry.py` | Connector execution (API/MCP/SQL) |
| `license_client.py` | License validation |
| `update_client.py` / `update_server.py` | Update via Git (tags) — update_client is the mechanism; update_server is legacy (HTTP channel mock, not used in the UI) |

---
