## 12. Perguntas Frequentes

**O modelo local não responde (erro de conexão)?**
Confirme que o LM Studio/vLLM está rodando no host e que a `base_url` do
modelo está correta. No Docker, `127.0.0.1` vira `host.docker.internal`.

**Preciso de um segundo servidor de modelo só para o roteamento?**
Não é obrigatório, mas é o **recomendado**: um modelo pequeno e rápido
dedicado (`BLUESHIFT_ROUTER_MODEL`) responde por quatro tarefas internas
(escolher conectores, extrair parâmetros, montar o spec do gráfico e gerar o
SELECT da Consulta inteligente) e roda em quase toda pergunta. Sem ele, essas
tarefas usam o modelo principal do agente — funciona, porém mais lento e mais
caro. Detalhes, perfil do modelo e pitfalls no §5.8 ("Modelo de roteamento").

**A resposta ficou lenta de repente, sem erro na tela?**
Verifique se o **modelo de roteamento ainda está no ar** (LM Studio fechado
após reiniciar o servidor é a causa clássica). No trace da resposta, a fase
`roteador_ms` mostra o tempo gasto no roteamento — se ela domina o total, o
problema é o roteador, não o RAG nem o banco.

**Posso misturar modelo local e externo?**
Sim — cada agente define o próprio `modelo_id`; a plataforma é agnóstica a
provedor (qualquer endpoint OpenAI-compatível).

**O agente responde "como se fosse outra área"?**
Verifique se o documento RAG tem `area` definida — docs sem área participam
de todas as áreas. Use o isolamento por área para evitar contaminação.

**Onde vejo o detalhamento de uma resposta (conectores, RAG, tokens)?**
Na página Auditoria, clique em **🔍 Rastreio** ao lado do registro. O modal
mostra também o **tempo por fase** (Roteador / Conectores / RAG / LLM em ms)
— útil para diagnosticar lentidão: se `conectores_ms` domina, é o conector;
se `llm_ms` domina, é o modelo/endpoint.

**Como medir se os modelos estão bons?**
Observabilidade (taxa de acerto, drift, custos) + Teste A/B com modelo juiz.

**Perdi o token de um canal?**
Use **nova chave** na página Canais — o token anterior para de funcionar
imediatamente.

**Meu webhook de saída exige uma chave secreta — o que faço?**
Preencha o campo **Headers do webhook (JSON)** do canal com o que o
receptor pedir: `{"X-Webhook-Secret": "abc"}` ou
`{"Authorization": "Bearer token"}`. Esses headers são enviados no POST
da resposta (não coloque a chave na URL — vaza em logs).

**Criei uma skill, mas ela não aparece nas telas (Skills/Agentes)?**
Skills criadas pela UI ficam no banco (persistem entre rebuilds do
container). Se a lista não mostra, recarregue a página. O catálogo
embarcado (template_skills/) é a base inicial; o banco domina por nome
quando os dois existem.

**Dados pessoais aparecem nas respostas?**
Ative as máscaras LGPD (tela LGPD). A saída é mascarada; o trace preserva o
original para auditoria (com retenção automática).

**O agente só responde quando coloco um parâmetro (ex: id_cliente)?**
Perguntas de ANÁLISE ("quem alugou mais e menos", "quantos por categoria",
"top 5") agora montam a consulta sozinhas: a **consulta inteligente** do
conector SQL descobre o schema real da fonte (tabelas/views + colunas) e
o LLM gera o SELECT (somente leitura, com LIMIT e validação de segurança).
O fluxo com parâmetros continua valendo para perguntas específicas
("aluguel do cliente 30"). Desligável por conector (checkbox "Consulta
inteligente" no cadastro/edição).

**O agente pode gerar gráficos?**
Sim — perguntas como "faça um gráfico de pizza/barras/linha" geram a
imagem automaticamente quando há dados dos conectores (barras para
comparação, pizza para proporções, linha para tendência). A imagem é
anexada à resposta (renderiza no Open WebUI e no teste de agente) e os
rótulos respeitam a máscara LGPD. Sem dados, o agente responde com a
análise textual.

---

*Documentação gerada a partir do código (2026-08-05). Em caso de divergência
entre este documento e o comportamento real, o código é a fonte da verdade —
atualize este arquivo na mesma entrega da mudança.*
