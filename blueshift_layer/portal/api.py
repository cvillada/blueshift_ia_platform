"""Canal de API da BlueShift (Camada 4 — Integração).

Expõe os agentes como serviço HTTP para sistemas externos chamarem de verdade
(webhook do CRM, Zapier, frontend próprio, automação). Este é o "canal real":
substitui o "testar no Portal" por uma API autenticada por API key por cliente.

Endpoints:
    POST /api/v1/agentes/<id>/chat
        body: {"mensagem": "...", "usuario": "opcional", "id_cliente": "C001"}
        auth: header  Authorization: Bearer bs_live_xxxx
               ou       x-api-key: bs_live_xxxx
        retorna: {"ok", "resposta", "modelo", "agente", "contexto", "ferramentas", "erro"}

    GET  /api/v1/agentes            -> lista de agentes do cliente (meta)
    POST /api/v1/keys               -> gera API key (admin do Portal)

Tudo on-premise: valida a API key no SQLite local e invoca o orquestrador de
agentes (RAG + conectores MCP + LLM real) já existente.
"""
from __future__ import annotations

import functools
import json
import os
import secrets

from flask import Blueprint, request, jsonify, current_app, g

from . import db

bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _require_key(f):
    @functools.wraps(f)
    def _wrap(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        key = None
        if auth.lower().startswith("bearer "):
            key = auth[7:].strip()
        else:
            key = request.headers.get("x-api-key") or request.args.get("api_key")
        if not key:
            return jsonify({"ok": False, "erro": "API key ausente"}), 401
        row = db.buscar_api_key(key)
        if not row:
            return jsonify({"ok": False, "erro": "API key inválida"}), 403
        g.cliente_id = row["cliente_id"]
        return f(*args, **kwargs)
    return _wrap


@bp.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "canal": "api-v1"})


@bp.route("/agentes", methods=["GET"])
@_require_key
def listar_agentes():
    rows = db.listar_agentes(g.cliente_id)
    return jsonify({
        "ok": True,
        "agentes": [
            {"id": a["id"], "nome": a["nome"], "area": a["area"],
             "modelo": a["modelo"], "skills": a["skills"], "conectores": a["conectores"],
             "status": a["status"]}
            for a in rows
        ],
    })


@bp.route("/agentes/<int:aid>/chat", methods=["POST"])
@_require_key
def agente_chat(aid: int):
    from . import agente as agente_mod

    cliente_id = g.cliente_id
    body = request.get_json(silent=True) or {}
    mensagem = (body.get("mensagem") or "").strip()
    usuario = body.get("usuario") or "api"
    id_cliente = body.get("id_cliente") or "C001"

    if not mensagem:
        return jsonify({"ok": False, "erro": "campo 'mensagem' obrigatório"}), 400

    a = db.buscar_agente(aid)
    if not a or a["cliente_id"] != cliente_id:
        return jsonify({"ok": False, "erro": "agente não encontrado"}), 404

    out = agente_mod.responder(a, mensagem, usuario, id_cliente=id_cliente)
    db.registrar_auditoria(usuario, "sistema", "api_chat", alvo=a["nome"],
                           cliente_id=cliente_id, ip=request.remote_addr or "", detalhe=mensagem[:80])
    return jsonify({
        "ok": out["ok"],
        "resposta": out["content"],
        "modelo": out["model"],
        "agente": a["nome"],
        "contexto": [c["texto"] for c in out.get("contexto", [])],
        "ferramentas": [
            {"conector": f.get("conector"), "tool": f.get("tool"), "resultado": f.get("resultado")}
            for f in out.get("ferramentas", []) if "erro" not in f
        ],
        "erro": out.get("error"),
    })


@bp.route("/keys", methods=["POST"])
def gerar_key():
    """Gera uma API key para um cliente (uso administrativo / bootstrap)."""
    body = request.get_json(silent=True) or {}
    cid = int(body.get("cliente_id", 0))
    if not cid:
        cls = db.listar_clientes()
        cid = cls[0]["id"] if cls else 1
    chave = "bs_live_" + secrets.token_urlsafe(24)
    db.criar_api_key(cid, chave, body.get("descricao", "canal api"))
    return jsonify({"ok": True, "cliente_id": cid, "api_key": chave})
