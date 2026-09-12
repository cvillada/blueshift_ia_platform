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
