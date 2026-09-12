### 5.4 Clientes (/portal/clientes)

**Onde:** Cadastros → Clientes.

**Propósito:** cadastro e gestão dos clientes (empresas contratantes).

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Código | ✅ | `xpto` | Identificador único (minúsculas/sem espaço) |
| Nome | ✅ | `XPTO Seguros (Piloto)` | Nome comercial |
| Empresa | ❌ | `XPTO Seguro S/A` | Razão social |
| Email de contato | ❌ | `ti@empresa.com.br` | E-mail do suporte técnico |
| Licença | ❌ | `BS-2026-XXXX` | Chave de ativação emitida pela BlueShift |
| Status | ❌ | `ativo` | ativo / suspenso |

Ações na lista: **editar**, **suspender/reativar** (por cliente).
Ações admin-only. Auditoria registra criar/editar/alternar cliente.
**Campos do cadastro (nome técnico):** `codigo` (identificador curto, ex. `xpto`),
`nome` (nome de exibição) e `razao_social`/`whatsapp` quando preenchidos.
