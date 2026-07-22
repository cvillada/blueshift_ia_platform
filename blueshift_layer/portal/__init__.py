"""Portal do Cliente BlueShift (Camada 4 — Experiência).

Gerencia, cadastra e monitora os clientes, usuarios, agentes e conectores
da BlueShift IA Platform. Roda 100% on-premise (SQLite local fake, sem rede
externa), seguindo o padrao da plataforma.

Uso:
    from blueshift_layer.portal import create_app
    app = create_app()
    app.run(port=5000)

Assinatura de autoria HMAC-SHA256 embutida.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from .views import bp

# ──────────────────────────────────────────
# Assinatura de autoria (HMAC-SHA256)
# ──────────────────────────────────────────
_MENSAGEM_AUTORIA = "Autor: Claudnei Villada - 072026"
_CHAVE_AUTORIA = "cvil556556"
_ASSINATURA_AUTORIA = "88a20f0a44a81c0ac38f0490804f45f8ad07abf705dbd40123e2ef5b490e4cb8"


def verificar_autoria() -> bool:
    """Verifica se a assinatura HMAC-SHA256 confere com a mensagem de autoria."""
    esperado = hmac.new(_CHAVE_AUTORIA.encode(), _MENSAGEM_AUTORIA.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, _ASSINATURA_AUTORIA)


def obter_assinatura() -> str:
    """Retorna a assinatura HMAC-SHA256 da autoria (64 chars hex)."""
    return _ASSINATURA_AUTORIA


from . import db


def create_app() -> "Flask":
    """Factory do Portal. Inicializa o SQLite e registra o blueprint."""
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = "blueshift-portal-dev"  # em prod: BLUESHIFT_PORTAL_SECRET no .env

    db.init_db()
    db.seed_demo()
    app.register_blueprint(bp)

    @app.route("/")
    def _root():
        from flask import redirect, url_for

        return redirect(url_for("portal.monitorar"))

    return app


__all__ = ["create_app", "db", "bp", "verificar_autoria", "obter_assinatura"]
