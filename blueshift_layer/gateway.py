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

Segurança: o Authorization do chat externo deve ser o TOKEN do canal
vinculado (Bearer bs_chan_*). Sem token valido -> 401.
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
        rows = con.execute(
            """SELECT g.id, g.nome, g.modo, g.max_mensagens, g.max_tokens,
                      c.token AS canal_token,
                      a.nome AS agente_nome, a.area AS agente_area
               FROM gateway_config g
               JOIN canais c ON c.id = g.canal_id
               LEFT JOIN agentes a ON a.id = c.agente_id
               WHERE g.ativo = 1 AND c.ativo = 1
               ORDER BY g.id"""
        ).fetchall()
    return [dict(r) for r in rows]


def _chamar_canal(token: str, pergunta: str, contexto: str = "") -> dict:
    """Chama a API do canal e devolve {ok, resposta, modelo, erro}.

    contexto: mensagens anteriores da conversa (entram so no prompt do
    LLM; a memoria/trace gravam apenas a pergunta real).
    """
    payload: dict = {"pergunta": pergunta, "origem": "gateway"}
    if contexto:
        payload["contexto"] = contexto
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
                    "modelo": out.get("modelo") or "blueShift"}
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


def _resposta_openai(resposta: str, modelo: str, gw_id: int) -> dict:
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
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True, "servico": "blueshift-gateway"})

    @app.get("/v1/models")
    def v1_models():
        gws = _gateways_ativos()
        data = [{
            "id": f"agente:{g['agente_nome'] or 'gateway'}",  # model id p/ o chat
            "object": "model",
            "created": int(time.time()),
            "owned_by": "blueshift",
        } for g in gws]
        return jsonify({"object": "list", "data": data})

    @app.post("/v1/chat/completions")
    def v1_chat():
        token = _auth_token()
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

        gws = _gateways_ativos()
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
        tokens_validos = {g["canal_token"] for g in gws}
        if not token or token not in tokens_validos:
            return jsonify({"error": {"message": "token invalido",
                                      "type": "authentication_error"}}), 401

        # Chats externos (ex: Open WebUI) fazem uma chamada EXTRA para gerar o
        # TITULO da conversa. Nao e pergunta real — responder direto com um
        # titulo (sem chamar o agente): nao grava trace/memoria/conhecimento
        # e nao gasta tokens.
        if _eh_pedido_titulo(pergunta):
            titulo = json.dumps({"title": _titulo_do_historico(pergunta)},
                                ensure_ascii=False)
            modelo = gw["agente_nome"] or "blueshift"
            if gw["modo"] == "streaming":
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

        out = _chamar_canal(
            gw["canal_token"], pergunta,
            contexto=_montar_contexto(
                messages,
                max_msg=int(gw.get("max_mensagens") or 6),
                max_tokens=int(gw.get("max_tokens") or 400),
            ))
        if not out["ok"]:
            return jsonify({"error": {"message": out.get("erro") or "falha no agente",
                                      "type": "server_error"}}), 502

        modelo = out.get("modelo") or gw["agente_nome"] or "blueshift"

        if gw["modo"] == "streaming":
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
                yield 'data: {"id":"chatcmpl-bs-%d","object":"chat.completion.chunk",' \
                      '"model":"%s","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n' \
                      % (gw["id"], modelo)
                yield "data: [DONE]\n\n"

            return Response(gen(), mimetype="text/event-stream")

        return jsonify(_resposta_openai(out["resposta"], modelo, gw["id"]))

    return app


def run(host: str = "0.0.0.0", port: int = 9003) -> None:
    app = create_app()
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    run()
