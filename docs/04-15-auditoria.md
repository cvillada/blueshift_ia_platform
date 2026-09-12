### 5.15 Auditoria (/portal/auditoria)

**Onde:** Operação → Auditoria.

**Propósito:** trilha de auditoria de todas as ações sensíveis (login, CRUDs,
testes A/B, imports, etc.).

Colunas: Usuário, Papel, Ação, Alvo, Cliente, IP, Detalhe, Quando.
- Filtro por usuário (dropdown).
- Link **🔍 Rastreio** em registros de execução de agente (abre modal com
  params, conectores, RAG, modelo, tokens e resposta).
- Paginação (padrão 50) e botão Limpar filtros.
- Retenção automática configurável (LGPD, padrão 90 dias).
