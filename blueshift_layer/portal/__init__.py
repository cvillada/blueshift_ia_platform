"""Portal do Cliente BlueShift (Camada 4 — Experiência).

Gerencia, cadastra e monitora os clientes, usuarios, agentes e conectores
da BlueShift IA Platform. Roda 100% on-premise (SQLite local fake, sem rede
externa), seguindo o padrao da plataforma.

Uso:
    from blueshift_layer.portal import create_app
    app = create_app()
    app.run(port=5000)
"""
from __future__ import annotations

import os
import secrets

from . import db
from .views import bp


# ──────────────────────────────────────────
# Assinatura de autoria (HMAC-SHA256)
# Apenas o hash e a mensagem ficam no codigo.
# A chave secreta e mantida fora do repositorio.
# ──────────────────────────────────────────
_MENSAGEM_AUTORIA = "Autor: Claudnei Villada - 072026"
_HASH_AUTORIA = "88a20f0a44a81c0ac38f0490804f45f8ad07abf705dbd40123e2ef5b490e4cb8"


def verificar_autoria(chave: str) -> bool:
    """Verifica se a chave informada produz o mesmo hash da mensagem de autoria.

    Uso:
        from blueshift_layer.portal import verificar_autoria
        verificar_autoria("sua_chave_aqui")  # retorna True se a chave for correta
    """
    import hashlib
    import hmac
    esperado = hmac.new(chave.encode(), _MENSAGEM_AUTORIA.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, _HASH_AUTORIA)


def obter_hash_autoria() -> str:
    """Retorna o hash HMAC-SHA256 da autoria (64 chars hex)."""
    return _HASH_AUTORIA


def create_app() -> "Flask":
    """Factory do Portal. Inicializa o SQLite e registra o blueprint."""
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = os.environ.get("BLUESHIFT_PORTAL_SECRET") or secrets.token_hex(32)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 min
    # Secure: so em producao (HTTPS). Local HTTP sem Secure para nao quebrar testes.
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("BLUESHIFT_PORTAL_SECURE", "").lower() in ("1", "true")
    app.debug = False  # nunca rodar em debug em producao

    db.init_db()
    # Purge retroativo de contagio RAG: remove chunks com tag de tool_call
    # cru gravados antes do filtro de gravacao (best-effort, idempotente).
    try:
        _purge = db.purgar_conteudo_tool_call()
        if sum(_purge.values()):
            app.logger.info(
                f"[rag] purge tool_call: {_purge.get('knowledge', 0)} knowledge "
                f"+ {_purge.get('memories', 0)} memories removidos")
    except Exception:
        pass  # nunca derruba o boot
    # Seed demo: so quando BLUESHIFT_SEED_DEMO != "0". Em instalacao de cliente
    # final (sem BLUESHIFT_DEV), desligar nao cria dados demo de empresa —
    # o cliente cadastra a propria empresa na tela Clientes.
    if os.environ.get("BLUESHIFT_SEED_DEMO", "1") != "0":
        db.seed_demo()
    app.register_blueprint(bp)

    # ── Retencao automatica de logs (LGPD Art. 15) ──
    import threading as _threading

    def _limpeza_periodica():
        import time as _time
        while True:
            try:
                result = db.limpar_dados_antigos()
                total = sum(result.values())
                if total:
                    app.logger.info(
                        f"[lgpd] retencao: {result['auditoria']} auditoria + "
                        f"{result['tracing']} tracing + {result['uso_tokens']} uso_tokens + "
                        f"{result['memories']} memorias removidos"
                    )
            except Exception:
                pass  # falha silenciosa — best-effort
            _time.sleep(3600)  # 1 hora

    _t = _threading.Thread(target=_limpeza_periodica, daemon=True)
    _t.start()

    # ── CSRF protection for portal POST routes ──
    from flask import request, session, flash, redirect, url_for

    @app.before_request
    def _csrf_check():
        if request.method not in ("POST", "PUT", "DELETE"):
            return
        # Skip API routes (autenticadas por token, nao sessao)
        if request.path.startswith("/portal/api/"):
            return
        # Skip login POST (o rate limit ja protege)
        if request.path == "/portal/login":
            return
        # Skills gerar-ia e chamado via fetch (JSON), sem formulario padrao
        if request.path == "/portal/skills/gerar-ia":
            return
        if request.path == "/portal/conectores/testar-conexao":
            return
        if request.path == "/portal/conectores/gerar-query-ia":
            return
        token = (request.form or {}).get("_csrf_token", "")
        if not token or token != session.get("csrf_token", ""):
            flash("Sessão expirada ou requisição inválida. Tente novamente.", "bad")
            return redirect(url_for("portal.monitorar"))

    @app.after_request
    def _add_headers(response):
        # CORS aberto SOMENTE para a API de canal (integracao externa);
        # o portal web nao precisa de CORS "*" (paginas servidas na mesma origem)
        if request.path.startswith("/portal/api/"):
            response.headers.setdefault("Access-Control-Allow-Origin", "*")
            response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization")
            response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        # Headers de seguranca HTTP (M1 da auditoria 02/08)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # 'unsafe-inline' e necessario: o portal usa style/script inline nas
        # f-strings; data: e para os graficos embutidos nas respostas
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'",
        )
        return response

    @app.route("/")
    def _root():
        from flask import redirect, url_for

        return redirect(url_for("portal.monitorar"))

    return app


__all__ = ["create_app", "db", "bp", "verificar_autoria", "obter_hash_autoria"]
