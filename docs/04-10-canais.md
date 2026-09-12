### 5.10 Canais (/portal/canais) — cadastro da API de saída para sistemas externos

**Onde:** Cadastros → Canais. **Para que serve:** é aqui que se cadastra a
integração de SAÍDA com sistemas externos — a API que outro sistema chama
para falar com o agente, e o webhook que recebe a resposta.

**Propósito:** integração máquina-a-máquina. Cada canal tem **token próprio**
(`bs_chan_*`) para chamar a API do agente. **Página admin-only.**

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Cliente | ✅ | XPTO Seguros (Piloto) |
| Nome | ✅ | `API Vendas (Webhook)` |
| Tipo | ✅ | `API` / `Webhook` |
| Agente | ✅ | Agente Vendas |
| Webhook de saída (URL) | ❌ | `https://...` (recebe POST da resposta; bloqueia IPs internos) |
| Headers do webhook (JSON) | ❌ | `{"X-Webhook-Secret": "minha-chave"}` — para webhooks que exigem autenticação; qualquer header (X-Webhook-Secret, Authorization: Bearer ...) é enviado no POST junto com o Content-Type |

Ações na linha: **testar** (abre modal que chama a API com o token do canal —
aba 1. Agente com pergunta + resposta/modelo/tokens/webhook; aba 2. Feedback
com trace_id automático e 👍/👎), **editar**, **nova chave** (regenera token —
o anterior para de funcionar na hora), **revogar/reativar**.

A lista "Canais cadastrados" exibe a coluna **ID** (primeira coluna) — útil
para identificar o canal em auditoria/tracing.

**⚠️ Nunca use a chave de licença da plataforma como token de canal.**

**Webhook de saída com autenticação:** muitos webhooks reais (Slack, Zapier,
n8n, sistemas corporativos) exigem uma chave secreta. Preencha o campo
**Headers do webhook (JSON)** com o que o receptor pedir — ex:
`{"X-Webhook-Secret": "abc123"}` ou `{"Authorization": "Bearer token"}`.
O sistema envia esses headers no POST da resposta (junto com o
`Content-Type: application/json`). Evite colocar a chave na URL
(`?secret=...`) — ela vaza em logs.

**Anti-SSRF no webhook (segurança):** a URL do webhook de saída é validada
com `ipaddress` (não prefixos literais) e por resolução de DNS. São
bloqueados endereços internos/não públicos: 10/8, 172.16/12, 192.168/16,
CGNAT (100.64/10), loopback, link-local (inclui 169.254.169.254 — metadata
de nuvem AWS/GCP), multicast, IPv6 ULA/link-local, e hostnames que
RESOLVEM para IP interno (DNS rebinding). A validação vale no **criar**,
no **editar** e no **momento do envio** (URL cadastrada antes da correção
também é bloqueada).
