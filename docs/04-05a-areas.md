### 5.5-A Áreas (/portal/areas)

**Onde:** Cadastros → Áreas.

**Propósito:** cadastro dos departamentos da empresa (vendas, suporte,
financeiro, RH, operações...). As áreas alimentam o Workspace, os agentes,
os conectores, os documentos RAG e o campo "Área" dos usuários.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Nome | ✅ | `vendas` | Minúsculas, sem espaços (padrão de identificador) |

- **Fonte dos dados:** o cadastro vive no BANCO (tabela `areas`). A
  variável `BLUESHIFT_AREAS` do ambiente serve apenas como **seed inicial**
  do primeiro boot — depois disso a tela domina (criar/renomear/excluir
  não exige rebuild nem mexer em `.env`).
- A lista mostra a **contagem de uso** (usuários, conectores e documentos
  da área).
- **Renomear/excluir não altera registros existentes** — eles mantêm o
  texto da área no registro; apenas os seletores passam a usar o nome novo
  (ou deixam de oferecer a área excluída). Excluir todas as áreas faz o
  sistema voltar ao seed padrão (nunca fica vazio).
- Auditoria registra criar/editar/excluir área.
