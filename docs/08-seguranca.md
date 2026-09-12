## 9. Segurança (implementado)

| Item | Detalhe |
|:-----|:--------|
| Senhas | Hash **scrypt** (stdlib) + migração automática de legado |
| Secret key | `BLUESHIFT_PORTAL_SECRET` ou aleatória por boot |
| SQL injection | Queries parametrizadas (?) + whitelist de colunas em updates |
| CSRF | Token em todos os formulários + validação global (exceto rotas `/portal/api/*` e exceções nomeadas) |
| Rate limit | Login 5/min/IP (bloqueio 15 min); API 100/min/token |
| Sessão | HttpOnly, SameSite=Lax, timeout 30 min, Secure condicional |
| XSS | `templates.h()` (html.escape) nos valores dinâmicos |
| Path traversal | Skills validam nome com `isidentifier()` |
| Webhook SSRF | Anti-SSRF com `ipaddress` (is_global): bloqueia privado, CGNAT, link-local/metadata de nuvem, loopback, IPv6 ULA/link-local + DNS rebinding (resolve o hostname); validado no criar, editar e no momento do envio |
| Headers HTTP | X-Content-Type-Options, X-Frame-Options: DENY, Referrer-Policy, Content-Security-Policy; CORS "*" só nas rotas /portal/api/* |
| API Key de modelo | Nunca renderizada no HTML (máscara no editar; campo vazio = mantém atual) |
| Senha mínima | 8 caracteres (criar/editar usuário e setup inicial) |
| Login falho | Registrado em auditoria (usuário tentado + IP) — detecta brute-force |
| Health check | Rota pública `/portal/healthz` (200/503 + estado do banco) para load balancer / HEALTHCHECK |
| MCP traceback | Mensagem genérica (sem detalhes de exceção) |
| Erros LLM | Mensagem amigável, sem stack trace |

---
