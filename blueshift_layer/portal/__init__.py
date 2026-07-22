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

    db.init_db()
    db.seed_demo()
    app.register_blueprint(bp)

    @app.route("/")
    def _root():
        from flask import redirect, url_for

        return redirect(url_for("portal.monitorar"))

    return app


__all__ = ["create_app", "db", "bp", "verificar_autoria", "obter_hash_autoria"]
