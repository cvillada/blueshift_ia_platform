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
| Modo de resposta | ✅ | `completa` (JSON) / `streaming` (SSE) |
| Máx. mensagens de contexto | ❌ | `6` (últimas N mensagens enviadas ao agente) |
| Limite de contexto (tokens, aprox.) | ❌ | `400` (~4 chars = 1 token; corta as mensagens mais antigas primeiro) |
| Gateway ativo | ❌ | checkbox (pausa/reativa o endpoint) |

- **Streaming**: o canal devolve a resposta completa; o gateway a envia
  em chunks (SSE) — efeito de digitação no chat externo (streaming
  simulado; latência total igual).
- **Contexto da conversa**: o gateway repassa as mensagens anteriores do
  chat no campo `contexto` da API — o LLM entende referências ("e o
  dele?") sem repetir o ID. O trabalho de enviar o histórico é do
  sistema solicitante (Open WebUI já o faz). A memória e o RAG gravam
  apenas a última pergunta/resposta real (sem o contexto concatenado).
  Limites configuráveis por gateway (tela): **máx. mensagens** (padrão
  6) e **orçamento em tokens** (padrão 400 — ~4 chars = 1 token; as
  mensagens mais RECENTES entram primeiro, as antigas são cortadas).
- **Segurança**: o `Authorization` do chat externo precisa ser o token de
  um canal com gateway ATIVO (`Bearer bs_chan_*`) — o `model` escolhe o
  agente; o token valida a autenticação. Token inválido ou de canal sem
  gateway ativo → 401. (O Open WebUI usa uma conexão = uma chave para
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
