## 9. Segurança (implementado)

| Item | Detalhe |
|:-----|:--------|
| Senhas | Hash **scrypt** (stdlib) + migração automática de legado |
| Segredo de sessão | `BLUESHIFT_PORTAL_SECRET`; **vazio → o portal gera e guarda** em `.portal_secret` (0600, ao lado do banco, dentro do volume) — a sessão sobrevive ao restart e não oscila entre processos. O instalador gera um segredo na primeira instalação; o valor de exemplo do `.env.example` é público e, se estiver em uso, o portal **avisa no log e segue** (não derruba instalação existente) |
| RBAC | Telas de cadastro e configuração exigem papel **admin** (Clientes, Usuários, Áreas, Modelos IA, Skills, Agentes, Conectores, Canais, Gateway, Auditoria, LGPD, SSO, Atualizações, Teste A/B, Fine-tuning, Uso de tokens, Arquivo morto, Observabilidade, Alertas, Processar métricas). A lista é **fonte única** (`auth.TELAS_ADMIN`): a rota e o **menu** consultam a mesma função, então o menu nunca oferece o que a rota nega. `gestor`/`usuario` ficam com Monitorar, Chat, Memória, Conhecimento, Docs e Workspace |
| SQL injection | Queries parametrizadas (?) + whitelist de colunas em updates. **Conector SQL:** a consulta usa **binding de parâmetro** (`%s`, `:1` no Oracle) — valor vindo da pergunta **nunca** entra no texto do SQL; a conexão roda em **sessão somente-leitura** (Postgres `read_only`, MySQL `SET SESSION TRANSACTION READ ONLY`) e há **denylist** de funções perigosas (`pg_read_file`, `dblink`, `pg_sleep`, `COPY … TO`, `xp_cmdshell`, `LOAD_FILE`, `SLEEP(`, `BENCHMARK(`…). A **query fixa é validada ao salvar**: uma instrução, começando em `SELECT`/`WITH` |
| CSRF | Token em todos os formulários + validação global (exceto rotas `/portal/api/*` e exceções nomeadas) |
| Rate limit | Login: **5 falhas/min por IP → bloqueio de 15 min** — só a tentativa **falha** consome o orçamento e a requisição bloqueada **não processa a credencial** (a tela de login continua abrindo, sem laço). API: 100/min por token; rotas públicas de Ajuda: por IP |
| Sessão | HttpOnly, SameSite=Lax, timeout 30 min, Secure condicional (`BLUESHIFT_PORTAL_SECURE=1` em HTTPS) |
| XSS | `templates.h()` (html.escape) nos valores dinâmicos e **`templates.j()`** dentro de JavaScript inline (`onclick`, `onchange`): o escape de HTML sozinho não basta porque o navegador decodifica o atributo antes do JS interpretar — uma aspa no nome do recurso fechava a string |
| Path traversal | Skills validam nome com `isidentifier()` |
| Webhook SSRF | Anti-SSRF com `ipaddress` (is_global): bloqueia privado, CGNAT, link-local/metadata de nuvem, loopback, IPv6 ULA/link-local + DNS rebinding (resolve o hostname); validado no criar, editar e no momento do envio |
| Headers HTTP | X-Content-Type-Options, X-Frame-Options: DENY, Referrer-Policy, Content-Security-Policy; CORS "*" só nas rotas /portal/api/* |
| API Key de modelo | Nunca renderizada no HTML (máscara no editar; campo vazio = mantém atual) |
| Senha mínima | 8 caracteres (criar/editar usuário e setup inicial) |
| Login falho | Registrado em auditoria (usuário tentado + IP) — detecta brute-force |
| Health check | Rota pública `/portal/healthz` (200/503 + estado do banco) para load balancer / HEALTHCHECK |
| MCP traceback | Mensagem genérica (sem detalhes de exceção) |
| Erros LLM | Mensagem amigável, sem stack trace cru; resposta do provedor sem `choices` é explicada em português (não vaza o nome do campo) |
| Erro interno | `500` tem resposta apresentável — página em português no portal e JSON em `/portal/api/*`; o traceback fica no log do container para o suporte |
| Gateway (OpenAI-compatible) | Autentica **antes** de validar o corpo: sem token válido a resposta é sempre `401` (não revela se há gateway configurado nem validação de payload) |

### Postura e limites (leia junto)

- **O produto roda on-premise, na rede do cliente.** Achados que exigem acesso
  prévio à rede (porta, banco, arquivo) são de severidade menor que os achados
  pós-login (injeção, RBAC, CSRF) — é essa a régua usada para priorizar.
- **Senha do banco do conector** fica em texto puro no `portal.db`: a proteção é
  a permissão do arquivo no sistema operacional (volume Docker) e o perímetro do
  cliente. Manter a coluna cifrada exigiria guardar a chave de decifragem no
  mesmo servidor — o ganho é pequeno para o modelo de ameaça on-premise.
- **Ações destrutivas exigem `POST` com token da sessão** (v0.11.10): excluir,
  suspender, revogar, regenerar chave e pausar gateway são formulários — `GET`
  nessas rotas responde `405`. Link `GET` que muda estado era CSRF na prática: o
  navegador prefetcha, scanner de e-mail segue link e o clique acidental executa
  (foi assim que uma varredura de rotas suspendeu o próprio admin durante os
  testes). O `SameSite=Lax` do cookie continua como segunda camada.
- **Sem token, sem sessão:** toda tela sob `/portal/` exige login (a lista de
  telas administrativas vale para todos os papéis, inclusive leitura).

---
