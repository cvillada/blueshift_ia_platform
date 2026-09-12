### 5.6 Agentes (/portal/agentes)

**Onde:** Cadastros → Agentes.

**Propósito:** criar e gerenciar os agentes de IA por área.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Cliente | ✅ | XPTO Seguros (Piloto) | Já vem selecionado (primeira empresa) |
| Nome do agente | ✅ | `Agente Vendas` | |
| Área | ✅ | `vendas` | Define quais conectores o agente enxerga |
| Modelo de IA (principal) | ✅ | `bonsai-8b` | Modelo cadastrado em Modelos IA |
| Modelo de IA (fallback) | ❌ | `hermes-3-llama-3.1-8b` | Usado se o principal falhar |
| Skills do catálogo | ❌ | vendas, suporte | Checkboxes das skills disponíveis |
| Status | ❌ | `ativo` | ativo / pausado |
| 🔒 Aplicar LGPD | checkbox | ativo por padrão | Anonimiza a resposta na saída |

Ações: **testar** (chat de teste com o pipeline completo: conectores → RAG →
LLM, com 👍/👎 feedback e 🔍 rastreio), **editar**, **excluir**.

**Checklist contextual (topo da página Agentes):** a plataforma mostra o que
o agente precisa, na ordem de configuração — `✓ Modelo IA (N)` · `Skills: N` ·
`Conectores: N`. Sem nenhum modelo cadastrado, aparece o aviso **"Comece por
aqui: cadastre um modelo em Modelos IA"** (com link) e o item vira
`✗ Modelo IA — cadastre aqui`.

**Ordem de configuração (menu Cadastros):** Clientes → Usuários → Modelos IA →
Skills → Agentes → Conectores → Canais — o menu segue a sequência de
montagem (base → modelo/skills → agente → entrega).

**Roteamento inteligente de conectores:** antes de executar os conectores
da área, uma IA curta (a mesma do agente, ou a apontada por
`BLUESHIFT_ROUTER_MODEL` — ver §5.8, "Modelo de roteamento") decide QUAL
conector é relevante para a pergunta
— ou nenhum. Pergunta de norma/política → responde só com a Base de
Conhecimento (RAG), sem tocar nos conectores. Pergunta que cita um
conector (ex: "CEP", "hospedagem") → executa só ele. Voto majoritário de
3 tentativas; se a seleção falhar ou for ambígua, executa todos os
conectores da área (comportamento seguro — nunca deixa o agente sem
dados). A tela Atualizações mostra o modelo de roteamento e as áreas
configuradas (card "Configuração de ambiente").

**Extração de parâmetros por IA:** além do reconhecimento automático de
padrões (códigos como `C001`, `id_cliente=58`, e-mails, datas), a IA
também extrai os parâmetros da pergunta em linguagem natural (ex:
"id cliente igual a 58" → `customer_id='58'`). Vale para **todos os tipos
de conector** (API — URL/headers/body, MCP — args, SQL — WHERE), que
usam o mesmo mecanismo de placeholders `{param}`.

**Anti-alucinação:** quando os conectores retornam sem dados vivos, o
agente é instruído a NÃO inventar valores (datas, nomes, números, IDs) —
responde "não encontrei" e sugere reformular a pergunta (ex: informar
`id_cliente=58`).

**Importante:** os conectores do agente são herdados automaticamente da
**área** dele (não há mais checkboxes de ERP/CRM/RH no formulário).
**Modelo secundário (fallback):** o campo `modelo_secundario_id` define o modelo
usado quando o principal falha ou está indisponível. Sem ele, o agente responde
apenas com o modelo principal e devolve o erro quando ele não responde.
