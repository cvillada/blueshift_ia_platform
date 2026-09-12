### 5.13 Chat de teste (/portal/chat)

**Onde:** FORA do menu (ferramenta de debug — URL direta `/portal/chat`).
A aba "Chat" foi removida do menu Inteligência (v0.9.5): o teste real de
respostas é feito em **Agentes → testar** (pipeline completo: RAG +
conectores + gráficos + feedback + rastreio). Este chat continua
disponível por URL para isolar o contexto dinâmico (memória + RAG)
com um modelo cru.

**Propósito:** chat de teste com qualquer modelo cadastrado (sem pipeline de
agente — LLM direto, SEM conectores, SEM gráficos — perguntas de gráfico
recebem resposta textual do modelo).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Modelo de IA | ✅ | bonsai-8b |
| Pergunta | ✅ | `Qual o saldo do cliente C001?` |

Mostra a resposta do modelo. Acesso: login_required.
