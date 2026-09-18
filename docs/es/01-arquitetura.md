<!-- sync: 01-arquitetura.md@30f31e485e9d | checar: python tools/readme_check.py -->
🌐 [Português](../01-arquitetura.md) · [English](../en/01-arquitetura.md) · **Español**

## 2. Arquitectura

```
                    ┌─────────────────────┐
                    │   CLI (blueshift)    │  init · portal · mcp · status · update
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  🌐 PORTAL (Flask)   │  create_app() → puerto 8080 (Docker: 8090)
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

Módulos principales (blueshift_layer/):

| Archivo | Responsabilidad |
|:--------|:-----------------|
| `portal/__init__.py` | App factory, CSRF global, CORS, retención automática (LGPD) |
| `portal/views.py` | Todas las rutas/pantallas del portal (60+ rutas) |
| `portal/db.py` | Acceso a datos (SQLite), migraciones, seed demo, 24 tablas |
| `portal/auth.py` | RBAC (login_required, admin_required, api_key_required) + rate limit |
| `portal/templates.py` | Layout (sidebar, temas claro/oscuro/sistema), helpers HTML |
| `portal/agente.py` | Orquestador: conectores → RAG → LLM → respuesta |
| `portal/llm_client.py` | Cliente compatible con OpenAI (urllib puro) con fallback |
| `portal/memory.py` | Vector TF-IDF (RAG) + búsqueda por similitud |
| `portal/mask.py` | Enmascaramiento LGPD (CPF, e-mail, teléfono, nombre, dirección, CNPJ) |
| `portal/sso.py` | Login federado OIDC |
| `connector_pack/registry.py` | Ejecución de conectores (API/MCP/SQL) |
| `license_client.py` | Validación de licencia |
| `update_client.py` / `update_server.py` | Update vía Git (tags) — update_client es el mecanismo; update_server es legado (mock de canal HTTP, no se usa en la pantalla) |

---
