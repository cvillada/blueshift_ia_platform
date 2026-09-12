## 8. Fluxo do Agente e RAG

Hierarquia no `agente.responder()`:

1. **Conectores da área (selecionados por IA)** — o roteamento escolhe
   quais executar (ou nenhum); executa SQL/API/MCP com os parâmetros
   extraídos (regex + IA).
2. **RAG complementar** — sempre busca na base (top_k=2 se conectores ok,
   top_k=4 se não).
3. **LLM** — prompt com skills (descrições) + dados dos conectores + contexto
   RAG. Prioriza dados do conector (fonte primária) sobre RAG (secundária).

Detalhes:
- **Memória de conversa**: pergunta+resposta são salvas na memória (tipo
  'conversa') a cada resposta — histórico/auditoria/export, fora do RAG.
- **Base de conhecimento SEM auto-feed (v0.10.14)**: o knowledge só recebe
  conteúdo intencional (cadastro manual, import CSV/PDF, skills indexadas).
  Antes, respostas com dados de conectores eram gravadas automaticamente
  ("RAG auto:") — comportamento removido; documentos legados continuam na
  base e são reconhecidos no export JSONL.
- **Isolamento por área**: docs RAG com `area` definida só aparecem para a
  mesma área; docs sem área valem para todas.
- **Filtro por cliente**: contexto RAG é filtrado pelo `id_cliente` da
  pergunta quando encontrado.
- **Fallback de modelo**: se o modelo principal falhar, usa o secundário.
- **Tracing**: cada execução gera um trace completo (params, conectores, RAG,
  modelo, tokens, resposta, tempo_ms) — visível na auditoria via 🔍 Rastreio.
  Além do tempo total, o trace guarda o tempo por **fase** (ms):
  `roteador_ms` (votos de seleção de conectores + extração de params por IA),
  `conectores_ms` (execução real), `rag_ms` (busca no conhecimento) e
  `llm_ms` (chamadas de resposta/fallback/gráfico) — o modal de rastreio
  exibe os quatro. Fase que não rodou (ou falhou antes do marco) fica 0.
- **LGPD**: se ativado, a resposta é mascarada na saída (o trace guarda o
  original para auditoria).

---
