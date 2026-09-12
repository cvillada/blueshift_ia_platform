### 5.18 Teste A/B (/portal/teste-ab)

**Onde:** Inteligência → Teste A/B.

**Propósito:** comparar dois modelos na mesma pergunta (qualidade).
**Acesso:** usuários autenticados, mas a operação é restrita a **admin e
gestor** (validação de papel na rota).

**Passo 1 — Executar:** seleciona feedbacks recentes (checkbox) + modelo
alvo → reexecuta cada pergunta com o modelo alvo (pipeline completo do
agente; fallback usa o trace original se o agente foi excluído).

- Limite de **10 perguntas por execução** (cada uma roda o agente completo
  — conectores + RAG + LLM — e depois o juiz avalia; acima disso a espera
  fica inviável). O limite vale no cliente (JS avisa no 11º) e no servidor
  (POST com 11+ é rejeitado com aviso).
- Lista de feedbacks **paginada em 10 por página** (padrão auditoria),
  com filtro 👍 Úteis / 👎 Não úteis e navegação « ‹ 1 2 3 › ».

**Passo 2 — Analisar:** seleciona um modelo **juiz** → o juiz compara as
respostas A (original) e B (nova) e vota: **A, B ou EMPATE**, com
justificativa. Colore as células (verde = venceu, vermelho = perdeu) e exibe
badge de veredito.

**Julgamentos salvos:** cada veredito é salvo automaticamente na tabela
`teste_ab` (pergunta, respostas A/B, modelos, voto, justificativa, juiz,
quem criou, data) — vira matéria-prima para fine-tuning e benchmark.

**Exportar JSONL:** botão **📥 Exportar JSONL (N)** no topo da página
(aparece quando há julgamentos salvos). Gera `teste_ab_julgamentos_AAAAMMDD.jsonl`
com uma linha por julgamento:
`pergunta`, `resposta_original`, `resposta_novo_modelo`, `voto`,
`justificativa`, `modelo_original`, `modelo_novo`, `modelo_juiz`,
`criado_por`, `criado_em`.
- **Máscara LGPD aplicada** (CPF/email/telefone etc., conforme a tela LGPD)
  — os dados são reais e podem conter dados pessoais.
- Usos: benchmark pós-fine-tune (reexecutar as mesmas perguntas e
  comparar) ou conversão para SFT/DPO (voto vira chosen/rejected;
  descartar EMPATE).
- Auditoria registra a exportação (`teste_ab_exportar`).

- Requer 2+ modelos cadastrados com base_url válida.
**Observação técnica:** as respostas coletadas viajam em um campo oculto do
formulário (`resultados_json`) até a etapa de análise — não é um campo que o
operador preenche.
