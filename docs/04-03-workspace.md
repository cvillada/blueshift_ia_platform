### 5.3 Workspace (/portal/workspace)

**Onde:** menu Workspace.

**Propósito:** ambiente de trabalho por área (vendas, suporte, financeiro...).

- KPIs do topo: agentes, usuários e documentos da base de conhecimento da
  área selecionada; filtro **Área** (todas ou uma específica).
- **Tokens por agente** nos cards: total de tokens consumidos no período
  (formato compacto — `682k`), com seletor igual da Observabilidade
  [`1d | 7d | 30d | 90d`]; fonte = `uso_tokens.agente_id` → `agentes.area`
  (registros sem agente, chat de teste puro, ficam de fora).
- **Cards de agentes** da área: nome, status (ativo/pausado), modelo e
  fallback, skills e ações:
  - **testar agente**: abre o chat de teste do agente (pipeline completo
    conectores → RAG → LLM, com 👍/👎 feedback e 🔍 rastreio);
  - **fluxo**: abre o popup do **fluxo de execução** do agente (diagrama
    de fluxo horizontal, 100% offline, sem lib externa):
    `Entrada (Chat/API) → fontes de dados (conectores da área) → LLM
    (modelo + fallback) → skills (1 caixinha por skill) → Resposta →
    Envio (Chat/API)`.
    As caixinhas são **arrastáveis** (as linhas acompanham) e os dados
    são dinâmicos do agente (modelo, fallback, skills, conectores).
- Acesso: qualquer usuário autenticado.
