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


def _chave_login(ip: str | None = None) -> str:
    """Chave do limiter de login (por IP)."""
    return f"login:{ip or (request.remote_addr or 'desconhecido')}"


def login_bloqueado(ip: str | None = None) -> bool:
    """True se o IP esta bloqueado por tentativas FALHAS (15 min)."""
    chave = _chave_login(ip)
    inicio = _RATE_LOGIN_BLOCKED.get(chave)
    if not inicio:
        return False
    if time.time() - inicio < _RATE_LOGIN_BLOCK:
        return True
    _RATE_LOGIN_BLOCKED.pop(chave, None)  # bloqueio venceu
    return False


def login_registrar_falha(ip: str | None = None) -> None:
    """Conta uma tentativa de login FALHA (5 em 60 s -> bloqueio de 15 min).

    v0.11.9 — o contador saiu do decorador e passou a ser chamado pela VIEW,
    porque antes ele somava TODO POST de login, inclusive os BEM-SUCEDIDOS:
    entrar e sair 5 vezes em um minuto bloqueava o usuario legitimo (e a suite
    local, que faz dezenas de logins validos em segundos, so passava porque o
    bloqueio nao interrompia nada — era justamente o defeito corrigido aqui).
    Quem precisa ser freado e o erro de senha; acerto zera (`login_ok`).
    """
    chave = _chave_login(ip)
    agora = time.time()
    # Conta a falha e zera o que saiu da janela. Nao usa _rate_check aqui de
    # proposito: ele so RECUSA a requisicao seguinte, o que deixava passar 6
    # falhas antes de bloquear. A regra e "5 falhas -> bloqueio imediato".
    historico = [t for t in _RATE[chave] if agora - t < _RATE_LOGIN_WIN]
    historico.append(agora)
    _RATE[chave] = historico
    if len(historico) >= _RATE_LOGIN_MAX:
        _RATE_LOGIN_BLOCKED[chave] = agora


def login_ok(ip: str | None = None) -> None:
    """Login bem-sucedido zera as falhas do IP (nao pune quem acerta)."""
    chave = _chave_login(ip)
    _RATE_LOGIN_BLOCKED.pop(chave, None)
    _RATE.pop(chave, None)


def rate_limit_login(f):
    """Interrompe o POST de login de um IP bloqueado (v0.11.9).

    So faz a CHECAGEM: o contador vive em `login_registrar_falha()`, chamado
    pela view quando a credencial e recusada. GET sempre passa (a tela de login
    precisa abrir para o usuario ler o aviso).
    """

    @wraps(f)
    def _wrap(*args, **kwargs):
        if login_bloqueado():
            if request.method == "POST":
                # NAO processa a credencial: antes a view era chamada e
                # autenticava mesmo com o limite estourado (bloqueio era so
                # aviso). Redireciona para o GET do login, que mostra o aviso —
                # se o GET tambem redirecionasse, viraria laco de redirect.
                flash("Muitas tentativas de login. Tente novamente em 15 minutos.", "bad")
                return redirect(url_for("portal.login"))
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


def rate_limit_por_ip(max_attempts: int = 60, window: int = 60):
    """Limita requisicoes por IP (para rotas publicas sem token, ex: Ajuda).

    Retorna JSON 429 quando estoura. NAO usa sessao nem token.
    """

    def decorator(f):
        @wraps(f)
        def _wrap(*args, **kwargs):
            ip = request.remote_addr or "desconhecido"
            if not _rate_check(f"ip:{ip}", max_attempts, window):
                return {"erro": f"limite de requisicoes excedido ({max_attempts}/{window}s)"}, 429
            return f(*args, **kwargs)

        return _wrap

    return decorator


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


# ──────────────────────────────────────────
# RBAC por tela (v0.11.9)
# ──────────────────────────────────────────
# Telas administrativas: quem nao e admin nao abre NEM PARA LER. Antes, escrever
# ja era protegido (@admin_required) mas a LEITURA nao: um usuario comum abria
# /portal/usuarios e via logins e papeis (achado da varredura de 2026-09-30).
# Esta lista e a FONTE UNICA: o hook de acesso (portal/__init__.py) e o menu
# (templates._nav) consultam a mesma funcao, entao menu e rota nunca divergem.
TELAS_ADMIN = (
    "clientes", "usuarios", "areas", "modelos", "skills", "agentes", "conectores",
    "canais", "gateway", "teste-ab", "fine-tuning", "observabilidade", "auditoria",
    "uso-tokens", "arquivo-morto", "alertas-config", "lgpd", "sso/config",
    "atualizacoes", "processar-metricas",
)


def tela_admin(caminho: str) -> bool:
    """True se o caminho e de uma tela administrativa (sob /portal/)."""
    p = (caminho or "").split("?")[0]
    if not p.startswith("/portal/"):
        return False
    p = p[len("/portal/"):]
    return any(p == t or p.startswith(t + "/") for t in TELAS_ADMIN)


def pode_ver(papel: str, caminho: str) -> bool:
    """Admin ve tudo; os demais papeis nao veem tela administrativa."""
    return papel == "admin" or not tela_admin(caminho)
