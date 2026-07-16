"""Autenticacao do Portal BlueShift (sessao simples, 100% local).

Admin do portal faz login e acessa gerenciar/cadastrar/monitorar.
Nenhuma senha trafega em rede externa — tudo fica no SQLite local.
"""
from __future__ import annotations

from functools import wraps

from flask import session, redirect, url_for, flash, request


def login_required(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para acessar o portal.", "warn")
            return redirect(url_for("portal.login", next=request.endpoint))
        return f(*args, **kwargs)

    return _wrap


def fazer_login(user: dict) -> None:
    session["user_id"] = user["id"]
    session["user_nome"] = user["nome"]
    session["user_papel"] = user["papel"]
    session["user_login"] = user["login"]


def fazer_logout() -> None:
    session.clear()
