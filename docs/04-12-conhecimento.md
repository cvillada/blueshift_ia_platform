### 5.12 Conhecimento (/portal/conhecimento) — RAG

**Onde:** Inteligência → Conhecimento.

**Propósito:** base de conhecimento vetorial que complementa o contexto do
agente (fonte SECUNDÁRIA — os conectores são a fonte primária).

Criar documento (manual):

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Cliente | ✅ | XPTO Seguros (Piloto) |
| Área | ❌ | `vendas` (isola o doc na área — vazio = vale para todas) |
| Título | ✅ | `Política de reembolso` |
| Categoria | ✅ | `base_conhecimento` |
| Fonte | ❌ | `manual` |
| Conteúdo | ✅ | texto do documento |

Importações em massa:
- **CSV**: colunas `titulo`, `conteudo`, `fonte`, `area` (aceita capitalizadas).
- **PDF**: extrai texto (PyMuPDF) e quebra em chunks de 2000 caracteres
  automaticamente; PDF só de imagem não tem texto extraído.

Ações: **editar**, **excluir**, **Exportar JSONL** (formato de fine-tuning;
com anonimização LGPD se ativada). Colunas: acessos e último acesso.

A base NÃO recebe auto-gravação de conversas (desde v0.10.14): cresce apenas
por cadastro manual, import CSV/PDF e indexação de skills. Documentos legados
"RAG auto:" de versões anteriores permanecem e são parseados no Exportar JSONL.
Filtros por Cliente, Área, Categoria, Fonte.
