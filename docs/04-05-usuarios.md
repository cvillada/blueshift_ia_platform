### 5.5 Usuários (/portal/usuarios)

**Onde:** Cadastros → Usuários.

**Propósito:** gestão dos usuários com acesso ao portal.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Cliente | ✅ | XPTO Seguros (Piloto) | Já vem selecionado (primeira empresa cadastrada — on-premise) |
| Nome | ✅ | `Ana Suporte` | Nome completo |
| Login | ✅ | `ana` | Único no sistema |
| Senha | ✅ (novo) / ❌ (editar) | `••••••` | Em branco no editar = mantém atual |
| Área | ❌ | `suporte` | Área de atuação (vendas/suporte/financeiro/rh/operacoes) |
| Papel | ✅ | `usuario` | admin / gestor / usuario / sistema |

Ações na lista: **editar**, **suspender/reativar** (link de texto; quando
suspenso, o usuário não consegue logar). Auditoria registra as ações.
