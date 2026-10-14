### 5.11 Memória (/portal/memoria)

**Onde:** Inteligência → Memória.

**Propósito:** histórico de memória persistente por usuário/cliente.

- Toda resposta do agente grava a memória tipo **conversa**
  (`[Agente] P: ... | R: ...`) — histórico para auditoria e export.
- Tipos **preferência** e **contexto** (cadastro manual) alimentam o contexto
  do agente; memória tipo **conversa** NÃO entra no RAG (isolamento — não
  polui a base de conhecimento com trocas de chat).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Cliente | ✅ | XPTO Seguros (Piloto) |
| Tipo | ✅ | pergunta / resposta / nota |

- Lista com paginação (10/20/50/100/200 por página). O conteúdo de cada linha é
  **escapado e clampado**: memória pode receber texto longo (uma página inteira
  gerada no chat) e, sem clamp, uma linha ocupava a tela toda e escondia as
  outras; acima de ~300 caracteres o texto entra num **"ver mais"** (recurso
  nativo do navegador, sem JavaScript). O escape também fecha a porta de HTML
  injetado pela própria memória.
- **Exportar JSONL** (admin/gestor): baixa o histórico como
  `blueshift_memorias_Nregistros.jsonl` — conversas saem parseadas em
  `pergunta`/`resposta`; preferência/contexto saem como `conteudo`. Máscara
  LGPD aplicada quando ativada (mesma política do export de Conhecimento).
  Auditoria `memoria_exportar`.
- Acesso: login_required.
