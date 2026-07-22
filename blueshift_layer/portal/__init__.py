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

from . import db
from .views import bp


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


__all__ = ["create_app", "db", "bp"]
