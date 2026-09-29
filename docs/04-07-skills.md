### 5.7 Skills (/portal/skills)

**Onde:** Cadastros → Skills.

**Propósito:** catálogo de instruções (SKILL.md) que guiam o comportamento
dos agentes. O LLM recebe a **descrição** e o **corpo** de cada skill ANEXADA
ao agente no prompt do sistema — o corpo vai até **8.000 caracteres por
skill** (ajustável pela env `BLUESHIFT_SKILL_BODY_MAX`; regras de
formato/comportamento escritas no corpo são enviadas e devem ser seguidas).

> **Histórico do limite:** era 4.000 caracteres fixos e cortava **em
> silêncio** 2 skills do catálogo real (5.259 e 4.826 chars). As regras de
> formato ficam no FIM do SKILL.md — exatamente o trecho que era perdido.
> 8.000 cobre o catálogo inteiro; acima disso o corpo é cortado e o prompt
> recebe a marca `[...corpo truncado...]`.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Nome (identificador) | ✅ | `vendas` | Minúsculas, sem espaço (isidentifier) |
| Versão | ❌ | `1.0.0` | |
| Descrição | ✅ | regras de comportamento | Enviada SEMPRE ao LLM — guardrails aqui |
| Conteúdo (SKILL.md body) | ✅ | corpo markdown | Instruções detalhadas — enviado ao LLM (até 8.000 chars, ver env abaixo) |
| ✨ Gerar com IA | — | — | Botão que usa um modelo cadastrado para gerar o SKILL.md |

Ações: **editar**, **excluir** (vermelho), botão **Indexar no RAG**
(/portal/skills/indexar-rag) para a skill entrar na base de conhecimento.

**Uma skill por agente:** no cadastro do agente a escolha é **radio** — uma
skill (ou **nenhuma**). Duas skills no mesmo agente entravam no prompt as duas
como obrigatórias, com regras potencialmente conflitantes; e não havia como
limpar a skill de um agente já salvo (a opção **nenhuma** resolve isso).

**Skill em uso não pode ser excluída** (integridade referencial): se algum
agente usa a skill, a exclusão é bloqueada com a lista de agentes afetados —
*"A skill 'rh' está em uso pelo(s) agente(s): Agente RH. Desvincule antes de
excluir."*. O mesmo nome é validado ao salvar o agente: **nome que não existe
no catálogo não é gravado** (erro visível na tela). Motivo: o vínculo
`agentes.skills` é uma lista de nomes **sem chave estrangeira**, então excluir
uma skill em uso deixava o agente com **referência pendurada** — as instruções
sumiam do prompt sem erro nenhum, ou o agente caía na cópia do arquivo
embarcado e **mudava de conteúdo sem aviso**.

**Skill que não resolve aparece na tela:** a lista de Agentes marca o agente
com `⚠️ não aplicada`, a tela de editar mostra o aviso com o nome, e o
**Rastreio** de cada execução registra o campo `skills_ausentes` (nomes que
não foram aplicados no prompt). Antes isso era silencioso.

**Env relacionada:**

| Variável | Padrão | O que é |
|:---------|:-------|:--------|
| `BLUESHIFT_SKILL_BODY_MAX` | `8000` | Limite de caracteres do **corpo** da skill enviado ao prompt (por skill). Ajustável sem rebuild da imagem |

**Dica (guardrails):** regras de comportamento vão na **descrição** (vai
sempre, sem corte) ou no **corpo** (vai até o limite acima). Exemplo:
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
