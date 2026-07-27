"""Autenticacao e controle de acesso (RBAC) do Portal BlueShift.

- login_required: qualquer usuario autenticado.
- admin_required: so admin (gerencia clientes/usuarios/faturas do portal).
- api_key_required: autenticacao por token de canal.
- rate_limit: protecao contra brute-force (login) e abuso (API).
- A auditoria é registrada em todo login e em acoes sensiveis (ver db.registrar_auditoria).

Hierarquia (PRD §6): admin > gestor > usuario > sistema.
"""
from __future__ import annotations

import time
from collections import defaultdict
from functools import wraps

from flask import session, redirect, url_for, flash, request
from . import db

# ──────────────────────────────────────────
# Rate limiter simples (em memoria)
# ──────────────────────────────────────────
_RATE: dict[str, list[float]] = defaultdict(list)
_RATE_LOGIN_MAX = 5       # tentativas
_RATE_LOGIN_WIN = 60      # janela em segundos
_RATE_LOGIN_BLOCK = 900   # bloqueio apos exceder (15 min)
_RATE_LOGIN_BLOCKED: dict[str, float] = {}

_RATE_API_MAX = 100       # requisicoes
_RATE_API_WIN = 60        # janela em segundos


def _rate_check(key: str, max_attempts: int, window: int) -> bool:
    """Retorna True se a requisicao pode prosseguir, False se estourou o limite."""
    now = time.time()
    # Limpa entradas antigas
    _RATE[key] = [t for t in _RATE[key] if now - t < window]
    if len(_RATE[key]) >= max_attempts:
        return False
    _RATE[key].append(now)
    return True


def rate_limit_login(f):
    """Limita tentativas de login por IP (5/min, bloqueia 15min).
    
    So conta tentativas POST (GET sempre passa livre).
    """

    @wraps(f)
    def _wrap(*args, **kwargs):
        ip = request.remote_addr or "desconhecido"
        key = f"login:{ip}"

        # Verifica se esta bloqueado
        if key in _RATE_LOGIN_BLOCKED:
            if time.time() - _RATE_LOGIN_BLOCKED[key] < _RATE_LOGIN_BLOCK:
                flash("Muitas tentativas de login. Tente novamente em 15 minutos.", "bad")
                # Renderiza a pagina de login sem re-aplicar o rate limit
                return f(*args, **kwargs)
            del _RATE_LOGIN_BLOCKED[key]

        # So conta tentativas POST (GET e so carregar pagina)
        if request.method == "POST" and not _rate_check(key, _RATE_LOGIN_MAX, _RATE_LOGIN_WIN):
            _RATE_LOGIN_BLOCKED[key] = time.time()
            flash("Muitas tentativas de login. Tente novamente em 15 minutos.", "bad")
            return f(*args, **kwargs)

        return f(*args, **kwargs)

    return _wrap


def rate_limit_api(f):
    """Limita requisicoes de API por token (100/min)."""

    @wraps(f)
    def _wrap(*args, **kwargs):
        token = extrair_token(request) or "anon"
        if not _rate_check(f"api:{token}", _RATE_API_MAX, _RATE_API_WIN):
            return {"erro": "limite de requisicoes excedido (100/min)"}, 429
        return f(*args, **kwargs)

    return _wrap


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
