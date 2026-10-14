"""Gateway OpenAI-compatível da BlueShift (chats externos: Open WebUI,
LibreChat, apps custom...).

Implementa o protocolo OpenAI (`/v1/chat/completions` + `/v1/models`) e
traduz para a API de canal do portal (`POST /portal/api/v1/agente` com o
token do canal). O gateway lê a configuração direto do SQLite (volume
compartilhado com o portal) — não cria superfície nova no portal.

Modos por gateway (definidos na tela Gateway do portal):
  - completa   -> responde JSON OpenAI normal
  - streaming  -> responde SSE (streaming SIMULADO: o canal devolve a
                  resposta completa; o gateway a envia em chunks para o
                  chat externo ter o efeito de digitação)

O campo `stream` do CLIENTE tem prioridade (contrato OpenAI): `stream: true`
recebe SSE mesmo com o gateway em modo `completa`, e `stream: false` recebe
JSON mesmo com o gateway em modo `streaming`. O modo do gateway e apenas o
DEFAULT para clientes que nao mandam o campo (ex: Open WebUI manda
`stream: true`; SDKs/agentes mandam `stream: false`).

Sem tool calling: o gateway traduz para a API do canal, que devolve TEXTO.
Os `tools` enviados pelo cliente sao ignorados (nao ha tool_calls na
resposta) — este endpoint e para chat/integracao simples, nao para um
cliente de agente que executa ferramentas.

Segurança: o Authorization do chat externo deve ser o TOKEN de um canal
vinculado a um gateway ATIVO (Bearer bs_chan_*). Sem token valido -> 401,
em `/v1/chat/completions` E em `/v1/models` (a lista expoe os NOMES dos
agentes publicados). `/healthz` continua publico.
"""
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request

from flask import Flask, Response, jsonify, request

# Caminho do banco do portal (volume compartilhado)
_PORTAL_DB = os.environ.get("BLUESHIFT_PORTAL_DB", "data/portal.db")
# URL interna do portal (no compose: http://blueshift-platform:8080)
_PORTAL_URL = os.environ.get("GATEWAY_PORTAL_URL", "http://localhost:8080")


def _con():
    con = sqlite3.connect(_PORTAL_DB)
    con.row_factory = sqlite3.Row
    return con


def _gateways_ativos() -> list[dict]:
    """Gateways ativos com canal+token+agente (para /v1/models e roteamento)."""
    with _con() as con:
        # g.* (e nao a lista de colunas): o gateway le a config de um banco que
        # e migrado pelo PORTAL. Numa janela de deploy (gateway novo + banco
        # ainda sem a coluna) a lista explicita derrubaria TODA chamada com
        # OperationalError; com g.* a coluna que faltar cai no default do
        # `gw.get(...) or <padrao>` no ponto de uso (ex: max_chars_msg -> 400).
        rows = con.execute(
            """SELECT g.*,
                      c.token AS canal_token,
                      a.nome AS agente_nome, a.area AS agente_area
               FROM gateway_config g
               JOIN canais c ON c.id = g.canal_id
               LEFT JOIN agentes a ON a.id = c.agente_id
               WHERE g.ativo = 1 AND c.ativo = 1
               ORDER BY g.id"""
        ).fetchall()
    return [dict(r) for r in rows]


def _chamar_canal(token: str, pergunta: str, contexto: str = "",
                  tools: list | None = None, tool_choice=None,
                  tool_results: list | None = None) -> dict:
    """Chama a API do canal e devolve {ok, resposta, modelo, tool_calls,
    tokens, tempo_ms, erro}.

    contexto: mensagens anteriores da conversa (entram so no prompt do
    LLM; a memoria/trace gravam apenas a pergunta real).
    tools/tool_results: contrato de tool calling do cliente (so quando o
    gateway tem `permite_tools`) — a execucao da ferramenta e do cliente.
    """
    payload: dict = {"pergunta": pergunta, "origem": "gateway"}
    if contexto:
        payload["contexto"] = contexto
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    if tool_results:
        payload["tool_results"] = tool_results
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_PORTAL_URL}/portal/api/v1/agente",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        if out.get("ok"):
            return {"ok": True, "resposta": out.get("resposta", ""),
                    "modelo": out.get("modelo") or "blueShift",
                    "tool_calls": out.get("tool_calls") or None,
                    # tokens/tempo_ms vem da API do canal (o portal le do
                    # provedor). Descartar aqui zerava o usage do protocolo.
                    "tokens": out.get("tokens") or {},
                    "tempo_ms": out.get("tempo_ms") or 0}
        return {"ok": False, "resposta": "", "erro": out.get("erro") or "falha no agente"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "resposta": "", "erro": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "resposta": "", "erro": str(e)}


def _auth_token() -> str | None:
    """Extrai o Bearer token do Authorization."""
    h = request.headers.get("Authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return None


def _quer_stream(body: dict, gw: dict) -> bool:
    """O `stream` do cliente decide; sem o campo, vale o modo do gateway.

    Contrato OpenAI: `stream` e quem define a CODIFICACAO da resposta. O modo
    do gateway (tela Gateway) e apenas o DEFAULT para quem nao manda o campo.
    """
    pedido = body.get("stream")
    if isinstance(pedido, bool):
        return pedido
    return gw.get("modo") == "streaming"


# Marcadores do prompt de GERACAO DE TITULO que chats externos (Open WebUI)
# disparam em paralelo a cada conversa — nao sao perguntas reais do usuario.
_MARCADORES_TITULO = [
    "### task: generate a concise title",
    "generate a concise title summarizing",
    "### chat history:",
    "raw json object",
]


def _montar_contexto(messages: list[dict], max_msg: int = 6,
                     max_tokens: int = 400, max_chars_msg: int = 400) -> str:
    """Concatena as mensagens ANTERIORES (antes da ultima) como contexto.

    O trabalho de mandar o contexto e do sistema solicitante (Open WebUI
    ja envia o historico); o gateway repassa ao agente. Limites
    configuráveis por gateway (tela Gateway):
      - max_msg: ultimas N mensagens
      - max_tokens: orcamento TOTAL do contexto (aprox. 4 chars = 1 token)
      - max_chars_msg: trunca cada mensagem individual
    As mensagens MAIS RECENTES entram primeiro (corta as antigas) — são
    as que importam para referencias ("e o dele?").
    """
    candidatas = []
    for m in messages[:-1][-max_msg:]:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        txt = (m.get("content") or "").strip()
        if not txt:
            continue
        if len(txt) > max_chars_msg:
            txt = txt[:max_chars_msg] + "..."
        rotulo = "usuario" if role == "user" else "assistente"
        candidatas.append(f"{rotulo}: {txt}")

    # Orcamento em tokens (aprox. 4 chars/token): monta das MAIS RECENTES
    # para as antigas e depois inverte (ordem cronologica no contexto).
    orcamento_chars = max(max_tokens, 1) * 4
    escolhidas: list[str] = []
    total = 0
    for linha in reversed(candidatas):
        custo = len(linha)
        if escolhidas and total + custo > orcamento_chars:
            break
        escolhidas.append(linha)
        total += custo
    escolhidas.reverse()
    return "\n".join(escolhidas)


def _eh_pedido_titulo(pergunta: str) -> bool:
    p = pergunta.lower()
    return any(m in p for m in _MARCADORES_TITULO)


def _titulo_do_historico(pergunta: str) -> str:
    """Deriva um titulo curto da primeira mensagem USER do historico."""
    import re as _re
    m = _re.search(r"USER:\s*([^\n]+)", pergunta)
    if m:
        t = m.group(1).strip()
        return t[:40] + ("..." if len(t) > 40 else "")
    return "Conversa BlueShift"


_ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _usage_de(out: dict) -> dict:
    """usage no formato OpenAI a partir do que o CANAL informou.

    O portal devolve `tokens` na resposta da API do canal (o llm_client le o
    usage do provedor). Ate a v0.11.17 o gateway descartava esse dado e
    devolvia usage zerado fixo — o cliente agentico ficava sem medidor de
    contexto/custo e sem base para decidir compactacao (relato do Hermes,
    14/10: "usage=unavailable" em 100% das chamadas). Provedor que nao informa
    (alguns servidores locais) continua zero: zero honesto > numero inventado.
    """
    t = out.get("tokens") or {}
    pin = int(t.get("prompt_tokens", 0) or 0)
    pout = int(t.get("completion_tokens", 0) or 0)
    return {"prompt_tokens": pin, "completion_tokens": pout,
            "total_tokens": int(t.get("total_tokens", 0) or 0) or (pin + pout)}


def _quer_usage(body: dict) -> bool:
    """`stream_options.include_usage` do cliente (contrato OpenAI)."""
    so = body.get("stream_options")
    return bool(isinstance(so, dict) and so.get("include_usage"))


def _context_length() -> int | None:
    """Janela do MOTOR (tokens) publicada no catalogo, se configurada.

    A plataforma nao tem como descobrir a janela do modelo do agente (quem
    configura e o motor atras) e inventar um numero seria pior que omitir —
    omitido, o cliente cai no palpite proprio. Com BLUESHIFT_CONTEXT_WINDOW
    definida (o operador mede no motor dele; ex: 32768, 262144) o catalogo
    publica `context_length` e o cliente para de chutar.

    ATENCAO: este numero e a janela do MOTOR, nao o orcamento de contexto do
    gateway (`gateway_config.max_tokens`) — sao contas diferentes.
    """
    try:
        v = int(os.environ.get("BLUESHIFT_CONTEXT_WINDOW", "").strip() or 0)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _modelo_openai(gw: dict) -> dict:
    """Objeto `model` do protocolo (mesma forma na lista e no GET por id)."""
    item = {
        "id": f"agente:{gw['agente_nome'] or 'gateway'}",   # model id p/ o chat
        "object": "model",
        "created": int(time.time()),
        "owned_by": "blueshift",
    }
    ctx = _context_length()
    if ctx:
        item["context_length"] = ctx    # extensao (estilo OpenRouter)
    return item


def _resposta_openai(resposta: str, modelo: str, gw_id: int,
                     usage: dict | None = None) -> dict:
    """Monta o corpo no formato OpenAI (resposta completa)."""
    return {
        "id": f"chatcmpl-bs-{gw_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": modelo,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": resposta},
            "finish_reason": "stop",
        }],
        "usage": usage or dict(_ZERO_USAGE),
    }


# Teto PADRAO de rodadas de ferramenta por TAREFA (configuravel por gateway na
# tela Gateway: `max_rodadas_tools`). Teto de seguranca: sem ele um cliente
# mal-comportado conversa com o agente indefinidamente — responder texto
# encerra o laco. A contagem e por TAREFA (ver _rodadas_da_tarefa), nao da
# conversa inteira.
MAX_RODADAS_TOOLS = 8


def _rodadas_da_tarefa(messages: list[dict]) -> int:
    """Rodadas de ferramenta DA TAREFA ATUAL (nao da conversa inteira).

    O cliente agentico resenvia o historico completo a cada rodada: contar
    todas as mensagens `role:"tool"` fazia o teto ACUMULAR entre perguntas —
    depois de N rodadas somadas, qualquer pergunta nova ja nascia bloqueada
    (medido no piloto, 14/10). O teto existe para o laco de UMA tarefa.

    Corte = ultima mensagem de usuario COM texto; o que veio depois dela sao
    as rodadas da tarefa em curso. Historico sem nenhuma mensagem de usuario
    com texto cai no comportamento antigo (conta tudo).
    """
    corte = 0
    for i, m in enumerate(messages):
        if m.get("role") == "user" and (m.get("content") or "").strip():
            corte = i
    return sum(1 for m in messages[corte + 1:] if m.get("role") == "tool")


def _tool_results_de(messages: list[dict]) -> list[dict]:
    """Extrai os resultados de ferramenta que o cliente ja executou.

    No contrato OpenAI cada execucao volta como {"role":"tool",
    "tool_call_id":..., "content":...}; o NOME da ferramenta esta na
    mensagem do assistente (tool_calls) que veio antes.
    """
    nomes: dict[str, str] = {}
    saida: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "assistant":
            for tc in (m.get("tool_calls") or []):
                if isinstance(tc, dict):
                    nomes[str(tc.get("id") or "")] = (
                        (tc.get("function") or {}).get("name") or "")
        elif role == "tool":
            cid = str(m.get("tool_call_id") or "")
            saida.append({"name": nomes.get(cid) or m.get("name") or "ferramenta",
                          "content": m.get("content") or ""})
    return saida


def _chunk(gw_id: int, modelo: str, delta: dict, finish: str | None = None,
           usage: dict | None = None) -> str:
    """Um pedaco SSE no formato OpenAI (chat.completion.chunk).

    `usage` no chunk e campo do proprio schema do chunk (a OpenAI so preenche
    no ultimo, quando `stream_options.include_usage`); clientes que leem usage
    do chunk final passam a ter o numero em vez de nada.
    """
    corpo = {"id": f"chatcmpl-bs-{gw_id}", "object": "chat.completion.chunk",
             "created": int(time.time()), "model": modelo,
             "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage is not None:
        corpo["usage"] = usage
    return f"data: {json.dumps(corpo, ensure_ascii=False)}\n\n"


def _sse_usage(gw_id: int, modelo: str, usage: dict) -> str:
    """Chunk final de usage (contrato OpenAI com `stream_options.include_usage`).

    Vem com `choices: []` — e assim que o cliente OpenAI-parseado le a
    contagem sem confundir com conteudo.
    """
    corpo = {"id": f"chatcmpl-bs-{gw_id}", "object": "chat.completion.chunk",
             "created": int(time.time()), "model": modelo, "choices": [],
             "usage": usage}
    return f"data: {json.dumps(corpo, ensure_ascii=False)}\n\n"


def _resposta_openai_tools(tool_calls: list, modelo: str, gw_id: int,
                           usage: dict | None = None) -> dict:
    """Corpo OpenAI com tool_calls (finish_reason=tool_calls, content nulo)."""
    limpos = [{
        "id": tc.get("id") or f"call_bs_{gw_id}_{i}",
        "type": "function",
        "function": {"name": (tc.get("function") or {}).get("name") or "",
                     "arguments": (tc.get("function") or {}).get("arguments") or "{}"},
    } for i, tc in enumerate(tool_calls) if isinstance(tc, dict)]
    return {
        "id": f"chatcmpl-bs-{gw_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": modelo,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": None, "tool_calls": limpos},
            "finish_reason": "tool_calls",
        }],
        "usage": usage or dict(_ZERO_USAGE),
    }


def _sse_tool_calls(gw_id: int, modelo: str, tool_calls: list,
                    usage: dict | None = None, include_usage: bool = False):
    """SSE de tool_calls — o cliente monta nome/arguments a partir do delta."""
    def gen():
        yield _chunk(gw_id, modelo, {"role": "assistant"})
        for i, tc in enumerate(tool_calls):
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            yield _chunk(gw_id, modelo, {"tool_calls": [{
                "index": i,
                "id": tc.get("id") or f"call_bs_{gw_id}_{i}",
                "type": "function",
                "function": {"name": fn.get("name") or "",
                             "arguments": fn.get("arguments") or "{}"},
            }]})
        if usage is not None:
            yield _chunk(gw_id, modelo, {}, finish="tool_calls", usage=usage)
        else:
            yield _chunk(gw_id, modelo, {}, finish="tool_calls")
        if include_usage and usage is not None:
            yield _sse_usage(gw_id, modelo, usage)
        yield "data: [DONE]\n\n"
    return gen()


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True, "servico": "blueshift-gateway"})

    @app.get("/v1/models")
    def v1_models():
        gws = _gateways_ativos()
        # Auth: MESMO contrato do chat — o token precisa ser de um canal com
        # gateway ativo. A lista expoe os NOMES dos agentes publicados
        # (inventario da empresa): sem token valido -> 401.
        if _auth_token() not in {g["canal_token"] for g in gws}:
            return jsonify({"error": {"message": "token invalido",
                                      "type": "authentication_error"}}), 401
        return jsonify({"object": "list", "data": [_modelo_openai(g) for g in gws]})

    @app.get("/v1/models/<path:model_id>")
    def v1_model(model_id: str):
        """Um modelo do catalogo (mesmo objeto da lista).

        Existia so a LISTA: cliente agentico que consulta o modelo por id
        (pratica comum para ler a janela de contexto) recebia 404 e caia no
        palpite proprio (relato Hermes, 14/10: chute de 256k).
        """
        gws = _gateways_ativos()
        if _auth_token() not in {g["canal_token"] for g in gws}:
            return jsonify({"error": {"message": "token invalido",
                                      "type": "authentication_error"}}), 401
        alvo = (model_id or "").removeprefix("agente:")
        gw = next((g for g in gws if (g["agente_nome"] or "") == alvo), None)
        if gw is None:
            return jsonify({"error": {"message": f"modelo '{model_id}' nao encontrado",
                                      "type": "invalid_request_error",
                                      "code": "model_not_found"}}), 404
        return jsonify(_modelo_openai(gw))

    @app.post("/v1/chat/completions")
    def v1_chat():
        # v0.11.9 — ORDEM: autenticar antes de validar o corpo. Antes, uma
        # chamada sem token e com corpo invalido respondia 400 (e sem gateway
        # configurado, 404) — revelando comportamento do endpoint a quem nao
        # esta autenticado, e trocando o contrato de erro. 401 primeiro.
        token = _auth_token()
        gws = _gateways_ativos()
        tokens_validos = {g["canal_token"] for g in gws}
        if not token or token not in tokens_validos:
            return jsonify({"error": {"message": "token invalido",
                                      "type": "authentication_error"}}), 401

        body = request.get_json(silent=True) or {}
        messages = body.get("messages") or []
        # Ultima mensagem do usuario vira a pergunta do agente
        pergunta = ""
        for m in reversed(messages):
            if m.get("role") == "user" and (m.get("content") or "").strip():
                pergunta = m["content"].strip()
                break
        if not pergunta:
            return jsonify({"error": {"message": "mensagem de usuario obrigatoria",
                                      "type": "invalid_request_error"}}), 400

        if not gws:
            return jsonify({"error": {"message": "nenhum gateway ativo configurado",
                                      "type": "server_error"}}), 404

        # Escolhe o gateway: pelo model pedido (nome do agente) ou o primeiro
        model_pedido = body.get("model") or ""
        gw = None
        if model_pedido:
            alvo = model_pedido.removeprefix("agente:")
            gw = next((g for g in gws if (g["agente_nome"] or "") == alvo), None)
        if gw is None:
            gw = gws[0]

        # Auth: o token precisa pertencer a um canal com gateway ATIVO
        # (qualquer um). O Open WebUI usa UMA conexao (uma chave) para
        # varios modelos — o model escolhe o agente; o token valida a
        # autenticacao. Token de outro canal/gateway pausado -> 401.
        # Chats externos (ex: Open WebUI) fazem uma chamada EXTRA para gerar o
        # TITULO da conversa. Nao e pergunta real — responder direto com um
        # titulo (sem chamar o agente): nao grava trace/memoria/conhecimento
        # e nao gasta tokens.
        if _eh_pedido_titulo(pergunta):
            titulo = json.dumps({"title": _titulo_do_historico(pergunta)},
                                ensure_ascii=False)
            modelo = gw["agente_nome"] or "blueshift"
            if _quer_stream(body, gw):
                def gen_titulo():
                    yield 'data: {"id":"chatcmpl-bs-%d","object":"chat.completion.chunk",' \
                          '"model":"%s","choices":[{"index":0,"delta":{"role":"assistant"},' \
                          '"finish_reason":null}]}\n\n' % (gw["id"], modelo)
                    yield 'data: {"id":"chatcmpl-bs-%d","object":"chat.completion.chunk",' \
                          '"model":"%s","choices":[{"index":0,"delta":{"content":%s},' \
                          '"finish_reason":null}]}\n\n' % (gw["id"], modelo, titulo)
                    yield 'data: {"id":"chatcmpl-bs-%d","object":"chat.completion.chunk",' \
                          '"model":"%s","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n' \
                          % (gw["id"], modelo)
                    yield "data: [DONE]\n\n"
                return Response(gen_titulo(), mimetype="text/event-stream")
            return jsonify(_resposta_openai(titulo, modelo, gw["id"]))

        # --- Tool calling (ferramentas do CLIENTE) --------------------------
        # O switch `permite_tools` do gateway libera o repasse de `tools` do
        # cliente para o modelo do agente. A plataforma NAO executa nada: o
        # cliente executa e devolve o resultado como messages[].role="tool".
        tools = body.get("tools") if isinstance(body.get("tools"), list) else None
        tool_choice = body.get("tool_choice")
        if not gw.get("permite_tools"):
            tools, tool_choice = None, None   # gateway sem a permissao: ignora
        max_rodadas = int(gw.get("max_rodadas_tools") or MAX_RODADAS_TOOLS)
        rodadas = _rodadas_da_tarefa(messages)
        if tools and rodadas >= max_rodadas:
            # Teto de seguranca: sem isso um cliente mal-comportado conversa
            # com o agente indefinidamente. Responder texto encerra o laco.
            out = {"ok": True, "resposta":
                   f"Limite de {max_rodadas} rodadas de ferramenta por tarefa "
                   "atingido — respondi com o que ja tenho.",
                   "modelo": gw["agente_nome"] or "blueshift", "tool_calls": None}
        else:
            out = _chamar_canal(
                gw["canal_token"], pergunta,
                contexto=_montar_contexto(
                    messages,
                    max_msg=int(gw.get("max_mensagens") or 6),
                    max_tokens=int(gw.get("max_tokens") or 400),
                    max_chars_msg=int(gw.get("max_chars_msg") or 400),
                ),
                tools=tools, tool_choice=tool_choice,
                tool_results=_tool_results_de(messages) if tools else None)
        if not out["ok"]:
            return jsonify({"error": {"message": out.get("erro") or "falha no agente",
                                      "type": "server_error"}}), 502

        modelo = out.get("modelo") or gw["agente_nome"] or "blueshift"
        # usage REAL (tokens do provedor, via canal). Antes: zero fixo em toda
        # resposta e nenhum usage no stream.
        usage = _usage_de(out)
        inc_usage = _quer_usage(body)

        # O agente decidiu CHAMAR uma ferramenta: repassa no contrato OpenAI
        # (JSON ou SSE com delta.tool_calls) — quem executa e o cliente.
        if out.get("tool_calls"):
            if _quer_stream(body, gw):
                return Response(_sse_tool_calls(gw["id"], modelo, out["tool_calls"],
                                                usage, inc_usage),
                                mimetype="text/event-stream")
            return jsonify(_resposta_openai_tools(out["tool_calls"], modelo, gw["id"],
                                                 usage))

        if _quer_stream(body, gw):
            # Streaming SIMULADO: envia a resposta completa em chunks (SSE)
            def gen():
                yield 'data: {"id":"chatcmpl-bs-%d","object":"chat.completion.chunk",' \
                      '"model":"%s","choices":[{"index":0,"delta":{"role":"assistant"},' \
                      '"finish_reason":null}]}\n\n' % (gw["id"], modelo)
                pedacos = [out["resposta"][i:i + 24]
                           for i in range(0, len(out["resposta"]), 24)] or [""]
                for p in pedacos:
                    pj = json.dumps({"content": p}, ensure_ascii=False)
                    yield f'data: {{"id":"chatcmpl-bs-{gw["id"]}","object":"chat.completion.chunk","model":"{modelo}","choices":[{{"index":0,"delta":{pj},"finish_reason":null}}]}}\n\n'
                    time.sleep(0.015)
                yield _chunk(gw["id"], modelo, {}, finish="stop", usage=usage)
                if inc_usage:
                    yield _sse_usage(gw["id"], modelo, usage)
                yield "data: [DONE]\n\n"

            return Response(gen(), mimetype="text/event-stream")

        return jsonify(_resposta_openai(out["resposta"], modelo, gw["id"], usage))

    return app


def run(host: str = "0.0.0.0", port: int = 9003) -> None:
    app = create_app()
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    run()
