### 5.16 Observabilidade (/portal/observabilidade)

**Onde:** Operação → Observabilidade.

**Propósito:** dashboard de qualidade e custo dos agentes.

- **5 KPIs**: Chamadas, Taxa de Acerto, Latência Média, Tokens, Erros
  (filtro 1d/7d/30d/90d).
- **Sparkline** de chamadas por dia.
- **Alertas ativos** (thresholds configuráveis).
- **Drift Detection**: comparação com período anterior por modelo
  (taxa de acerto ↓>10% ou latência ↑>20% = alerta).
- **Cost Intelligence**: custo estimado por modelo (tokens × preço/1M).
- **Feedback recente**: tabela com 👍/👎, tipo (manual/api) e respostas.
- Botão **Processar métricas** (agrega tracing do dia; se vazio, busca os
  últimos 7 dias).
**Rastreio por resposta:** o modal de rastreio (`/portal/rastreio/<id>`) mostra,
para cada resposta, o tempo por fase (`roteador_ms`, `conectores_ms`, `rag_ms`,
`llm_ms`), os parâmetros extraídos, os conectores usados e o modelo. É a
principal ferramenta para investigar lentidão.
A rota `/portal/processar-metricas` recalcula as métricas diárias (interna —
executada pela tela/pelo agendador).
