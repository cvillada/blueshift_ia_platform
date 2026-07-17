"""Autenticacao e controle de acesso (RBAC) do Portal BlueShift.

- login_required: qualquer usuario autenticado.
- admin_required: so admin (gerencia clientes/usuarios/faturas do portal).
- A auditoria é registrada em todo login e em acoes sensiveis (ver db.registrar_auditoria).

Hierarquia (PRD §6): admin > gestor > usuario > sistema.
"""
from __future__ import annotations

from functools import wraps

from flask import session, redirect, url_for, flash, request
from . import db


def login_required(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para acessar o portal.", "warn")
            return redirect(url_for("portal.login", next=request.endpoint))
        return f(*args, **kwargs)

    return _wrap


def admin_required(f):
    """So o papel 'admin' pode executar a acao (gerenciar a plataforma)."""

    @wraps(f)
    def _wrap(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para acessar o portal.", "warn")
            return redirect(url_for("portal.login"))
        if session.get("user_papel") != "admin":
            flash("Acesso restrito ao administrador.", "bad")
            return redirect(url_for("portal.monitorar"))
        return f(*args, **kwargs)

    return _wrap


def fazer_login(user: dict) -> None:
    session["user_id"] = user["id"]
    session["user_nome"] = user["nome"]
    session["user_papel"] = user["papel"]
    session["user_login"] = user["login"]
    session["user_area"] = user.get("area") or ""


def fazer_logout() -> None:
    session.clear()


def papel_atual() -> str:
    return session.get("user_papel", "")


def area_atual() -> str:
    """Área do usuário logado (vendas/suporte/financeiro/rh/operacoes) ou '' (admin/geral)."""
    return session.get("user_area", "")


def extrair_token(req) -> str | None:
    """Extrai o token de um request de API (Bearer header ou ?token=)."""
    authz = req.headers.get("Authorization", "")
    if authz.lower().startswith("bearer "):
        return authz.split(" ", 1)[1].strip()
    return req.args.get("token") or req.form.get("token")


def api_key_required(f):
    """Autentica uma chamada de maquina-a-maquina via token de canal (Bearer/?token=).

    Usado pelos endpoints de canal real (webhook/API). Nao usa sessao de browser.
    """
    @wraps(f)
    def _wrap(*args, **kwargs):
        token = extrair_token(request)
        if not token:
            return {"erro": "token ausente"}, 401
        canal = db.buscar_canal_por_token(token)
        if not canal:
            return {"erro": "token invalido"}, 401
        return f(canal, *args, **kwargs)

    return _wrap
