### 5.7 Skills (/portal/skills)

**Onde:** Cadastros → Skills.

**Propósito:** catálogo de instruções (SKILL.md) que guiam o comportamento
dos agentes. O LLM recebe a **descrição** e o **corpo** de cada skill ANEXADA
ao agente no prompt do sistema — desde v0.10.16 (corpo limitado a 4.000
caracteres por skill; regras de formato/comportamento escritas no corpo são
enviadas e devem ser seguidas).

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Nome (identificador) | ✅ | `vendas` | Minúsculas, sem espaço (isidentifier) |
| Versão | ❌ | `1.0.0` | |
| Descrição | ✅ | regras de comportamento | Enviada SEMPRE ao LLM — guardrails aqui |
| Conteúdo (SKILL.md body) | ✅ | corpo markdown | Instruções detalhadas — enviado ao LLM (até 4.000 chars) |
| ✨ Gerar com IA | — | — | Botão que usa um modelo cadastrado para gerar o SKILL.md |

Ações: **editar**, **excluir** (vermelho), botão **Indexar no RAG**
(/portal/skills/indexar-rag) para a skill entrar na base de conhecimento.

**Dica (guardrails):** regras de comportamento vão na **descrição** (vai
sempre, sem corte) ou no **corpo** (vai até 4.000 chars). Exemplo:
```
PRIMEIRA skill.
REGRAS:
- NUNCA invente dados — use apenas os conectores
- NUNCA responda sobre RH ou politicas internas
- SEMPRE cite a fonte dos dados
```
**Campos do cadastro (nome técnico):** `nome` (identificador, minúsculo),
`version` (versão da skill — aparece no rótulo "Versão", padrão `1.0.0`),
`descricao` (vai no prompt do agente) e o corpo (`body`) do SKILL.md.
