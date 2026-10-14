### 5.23 Gateway (/portal/gateway) — OpenAI-compatível para chats externos

**Onde:** Cadastros → Gateway.

**Propósito:** conecta **chats externos** (Open WebUI, LibreChat, apps
custom, OpenAI SDK/LangChain) à plataforma falando o **protocolo padrão
OpenAI** (`/v1/chat/completions`). O gateway repassa a pergunta ao agente
via **API do canal** (token próprio) — com todo o pipeline (roteamento de
conectores, skills, RAG, LGPD). O gateway sobe junto com a plataforma
(container irmão no mesmo compose, porta 9003).

**Como ativar (passo a passo):**
1. Crie um canal na tela Canais apontando para o agente desejado (ex:
   Agente Vendas) e copie o token `bs_chan_*`;
2. Cadastros → Gateway → **Ativar gateway**: Nome, Canal vinculado,
   Modo de resposta (`Resposta completa` ou `Streaming`) e salvar;
3. No chat externo (ex: Open WebUI → Configurações → Conexões → OpenAI
   API): API URL = `http://<servidor>:9003/v1` · API Key = **o token do
   canal** · Model = `agente:<nome do agente>` (lista em `/v1/models`).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| Nome | ✅ | `Gateway Vendas (Open WebUI)` |
| Canal vinculado | ✅ | `API Vendas` (o token autentica o chat externo) |
| Modo de resposta | ✅ | `completa` (JSON) / `streaming` (SSE) — é o **padrão**; o campo `stream` da requisição tem prioridade |
| Máx. mensagens de contexto | ❌ | `6` (últimas N mensagens enviadas ao agente) |
| Limite de contexto (tokens, aprox.) | ❌ | `400` (~4 chars = 1 token; corta as mensagens mais antigas primeiro). Teto do campo: `64000` |
| Máx. caracteres por mensagem (`max_chars_msg`) | ❌ | `400` — corte de **cada** mensagem do histórico (faixa 100–20000). Suba junto com o orçamento para histórico rico (ex: `8000`) |
| Permitir tool calling | ❌ | checkbox (`permite_tools`) — repassa os `tools` do cliente ao agente e devolve `tool_calls`; **quem executa a ferramenta é o cliente**. Padrão: desligado |
| Gateway ativo | ❌ | checkbox (pausa/reativa o endpoint) |

- **Streaming**: o canal devolve a resposta completa; o gateway a envia
  em chunks (SSE) — efeito de digitação no chat externo (streaming
  simulado; latência total igual). Quem decide SSE x JSON é o **campo
  `stream` da requisição**: `stream: true` recebe SSE e `stream: false`
  recebe JSON, **mesmo que o modo configurado diga o contrário**; o *Modo
  de resposta* vale quando o cliente não manda o campo (Open WebUI manda
  `stream: true`, SDKs/agentes mandam `stream: false`).
- **Tool calling (opcional, por gateway)**: com `permitir tool calling` ligado
  na tela, o gateway repassa ao agente as **ferramentas do cliente** (`tools`,
  contrato OpenAI) e devolve as chamadas como `tool_calls` — em JSON
  (`finish_reason: "tool_calls"`) ou em SSE (`delta.tool_calls`), conforme o
  `stream` do cliente. **Quem executa a ferramenta é o cliente**: a plataforma
  não roda nada; o resultado volta na chamada seguinte como mensagem
  `role: "tool"` e entra no prompt do modelo. Teto de **8 rodadas** por conversa
  (ao estourar, resposta em texto para encerrar o laço). Vale o aviso: o modelo
  do agente precisa **emitir tool call** — modelos pequenos "instruct"
  normalmente respondem texto e nunca chamam a ferramenta.
- **Sem tool calling (padrão)**: o gateway repassa a pergunta ao agente e
  devolve **texto** — os `tools` que um cliente agêntico (CLI/agente com
  ferramentas) manda no corpo são ignorados e a resposta sai sem `tool_calls`.
  Para o agente CL Agents entrar como **ferramenta** de um agente do cliente
  (o sentido inverso), use a **API do portal**
  (`POST /portal/api/v1/agente`, ver página *API Reference*).
- **Contexto da conversa**: o gateway repassa as mensagens anteriores do
  chat no campo `contexto` da API — o LLM entende referências ("e o
  dele?") sem repetir o ID. O trabalho de enviar o histórico é do
  sistema solicitante (Open WebUI já o faz). A memória e o RAG gravam
  apenas a última pergunta/resposta real (sem o contexto concatenado).
  Três limites configuráveis por gateway (tela): **máx. mensagens**
  (padrão 6 — últimas N), **orçamento em tokens** (padrão 400, teto do
  campo 64000 — ~4 chars = 1 token) e **máx. caracteres por mensagem**
  (`max_chars_msg`, padrão 400, faixa 100–20000 — corte de CADA mensagem
  do histórico). As mensagens mais RECENTES entram primeiro, as antigas
  são cortadas. Atenção ao diagnóstico: com o padrão 400 o gargalo é a
  **truncação por mensagem**, não o orçamento (que só passa a morder
  acima de ~77 mensagens nesse valor) — um cliente de agente perde
  tool output e trechos grandes. Para histórico rico, suba
  `max_chars_msg` (ex: 8000) **e** o orçamento junto, senão o orçamento
  corta as antigas. O que **não** entra no contexto: mensagens
  `role:"system"` do cliente (vale o prompt do próprio agente) e as
  mensagens `assistant` que só carregam `tool_calls` (o contrato de
  execução vai por `tool_results`).
- **Resultado de ferramenta no prompt**: com `permitir tool calling`
  ligado, os `role:"tool"` do cliente **não** passam pelo contexto —
  chegam ao agente pelo bloco "RESULTADO DAS FERRAMENTAS", com o nome
  resolvido pelo `tool_call_id` e o conteúdo **íntegro** vindo do
  gateway (sem duplicação no contexto). O corte por resultado é do
  portal, não é por gateway: env `BLUESHIFT_TOOL_RESULT_MAX` (padrão
  2000 chars por resultado; `0` desliga o corte), mesma mecânica de
  `BLUESHIFT_SKILL_BODY_MAX`. Suba essa env no container da plataforma
  para tool output grande (arquivo, CLI, web) — ela vale para qualquer
  consumidor da API do canal que mande `tool_results`.
- **Segurança**: o `Authorization` do chat externo precisa ser o token de
  um canal com gateway ATIVO (`Bearer bs_chan_*`) — o `model` escolhe o
  agente; o token valida a autenticação. Token inválido ou de canal sem
  gateway ativo → 401, **no chat e na lista de modelos** (`/v1/models`
  devolve os nomes dos agentes publicados — não é público; só
  `/healthz` fica aberto). (O Open WebUI usa uma conexão = uma chave para
  vários modelos — qualquer chave de gateway ativo funciona para todos.)
- **Feedback default**: interações vindas do gateway registram feedback
  automático `util` com tipo `gateway` — entram na Observabilidade
  (taxa de acerto) e no Teste A/B, distinguíveis do feedback
  manual/implicito/api pela coluna tipo.
- Endpoint exibido na tela: `http://<host>:9003/v1` (ou `GATEWAY_PUBLIC_URL`
  se definida). Chat externo em Docker na mesma máquina: use
  `http://host.docker.internal:9003/v1` (`host.docker.internal` é o caminho
  do host visto de dentro do Docker).
- **Rodar sem Docker (SO direto):** o gateway é um comando da CLI como o
  portal — `set -a; . ./.env; set +a` + `blueshift gateway --port 9003`
  (com `GATEWAY_PORTAL_URL` apontando para o portal, ex:
  `http://localhost:8080`).

Exemplo de chamada (formato OpenAI):

```bash
curl -X POST http://localhost:9003/v1/chat/completions \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{"model": "agente:Agente Vendas",
       "messages": [{"role": "user", "content": "Qual o saldo do cliente C001?"}]}'
```

Exemplo com ferramentas (tool calling ligado neste gateway) — a resposta volta
com `finish_reason: "tool_calls"` (o cliente executa a ferramenta e chama de
novo mandando o resultado como `role: "tool"`):

```bash
curl -X POST http://localhost:9003/v1/chat/completions \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{"model": "agente:Agente Vendas",
       "messages": [{"role": "user", "content": "Qual o status do pedido 4471?"}],
       "tools": [{"type": "function", "function": {"name": "consultar_pedido",
                  "parameters": {"type": "object",
                                 "properties": {"numero": {"type": "string"}},
                                 "required": ["numero"]}}}]}'
```
