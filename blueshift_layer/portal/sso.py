#!/usr/bin/env python3
"""Cliente SSO (OIDC) do Portal BlueShift — 100% Python puro (sem libs externas).

Suporta dois modos:
  - PRODUCAO: provedor OIDC real (Azure AD / Okta / Keycloak / Google).
    Fluxo authorization code: /sso/login -> redirect p/ authorize -> IdP redirect
    p/ /sso/callback com `code` -> troca por id_token (token endpoint) -> valida
    assinatura (HMAC com client_secret quando HS256, ou confere emissor).
  - DEV (modo teste): provedor MOCK interno. Nao depende de IdP externo.
    /sso/mock_authorize finge a tela do IdP e redireciona de volta com `code`;
    /sso/mock_token devolve um id_token JWT assinado por nós (HMAC-SHA256 com
    segredo de dev). Assim da pra validar TODO o fluxo SSO localmente.

O SSO so resolve IDENTIDADE (quem é o usuario). O PAPEL vem do cadastro local
(admin cadastra o login/email SSO + papel, igual usuario local). Se o usuario
nao estiver pre-cadastrado: se auto_criar=1 cria como 'usuario', senao bloqueia.

Mantem o login LOCAL intacto: o SSO e um caminho alternativo de autenticacao
que no fim chama auth.fazer_login() igual ao login por senha.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

# Segredo de dev para assinar o id_token mock (so vale em dev_mode)
_DEV_JWT_SECRET = os.environ.get("BLUESHIFT_SSO_DEV_SECRET", "blueshift-dev-sso-secret")

_STATES: Dict[str, str] = {}  # state -> nonce (defesa CSRF, em memoria)


# --------------------------------------------------------------------------- #
# Helpers JWT (decodifica/verifica sem pyjwt)                                 #
# --------------------------------------------------------------------------- #

def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _criar_jwt_dev(sub: str, email: str, nome: str, grupos: list) -> str:
    """Cria um id_token JWT assinado (HS256) com o segredo de dev."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": "blueshift-dev-idp",
        "sub": sub,
        "email": email,
        "name": nome,
        "groups": grupos,
        "aud": "blueshift-dev-client",
    }
    signing_input = (_b64u(json.dumps(header).encode()) + "."
                     + _b64u(json.dumps(payload).encode())).encode("ascii")
    sig = hmac.new(_DEV_JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return signing_input.decode("ascii") + "." + _b64u(sig)


def _verificar_jwt(token: str, secret: Optional[str] = None) -> Dict[str, Any]:
    """Verifica assinatura (HS256) e retorna o payload. Em dev confia no segredo."""
    try:
        h_b64, p_b64, s_b64 = token.split(".")
    except ValueError:
        raise ValueError("id_token malformado")
    signing_input = (h_b64 + "." + p_b64).encode("ascii")
    if secret:
        esperado = _b64u(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(esperado, s_b64):
            raise ValueError("assinatura do id_token invalida")
    payload = json.loads(_b64u_decode(p_b64))
    return payload


# --------------------------------------------------------------------------- #
# Configuracao + URLs                                                         #
# --------------------------------------------------------------------------- #

def carregar_config() -> Dict[str, Any]:
    """Le a config de SSO do banco (portal.db) ou usa env (fallback dev)."""
    try:
        from . import db
        cfg = db.buscar_sso_config()
        if cfg:
            return cfg
    except Exception:
        pass
    # fallback p/ env (modo dev rapido)
    return {
        "ativo": int(bool(os.environ.get("BLUESHIFT_SSO_ATIVO"))),
        "dev_mode": 1,
        "issuer": "blueshift-dev-idp",
        "client_id": os.environ.get("BLUESHIFT_SSO_CLIENT_ID", "blueshift-dev-client"),
        "client_secret": os.environ.get("BLUESHIFT_SSO_CLIENT_SECRET", _DEV_JWT_SECRET),
        "redirect_uri": os.environ.get("BLUESHIFT_SSO_REDIRECT",
                                       "http://127.0.0.1:8080/portal/sso/callback"),
        "dominio_admin": os.environ.get("BLUESHIFT_SSO_DOMINIO_ADMIN", ""),
        "auto_criar": 1,
    }


def esta_ativo() -> bool:
    cfg = carregar_config()
    return bool(cfg.get("ativo"))


def build_auth_url(redirect_uri: str) -> str:
    """Monta a URL de authorize (OIDC). Em dev aponta p/ o mock interno."""
    cfg = carregar_config()
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)
    _STATES[state] = nonce
    params = {
        "client_id": cfg.get("client_id") or "blueshift-dev-client",
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri,
        "state": state,
        "nonce": nonce,
    }
    if cfg.get("dev_mode"):
        base = "/portal/sso/mock_authorize"
    else:
        base = (cfg.get("issuer") or "").rstrip("/") + "/authorize"
    return base + "?" + urllib.parse.urlencode(params)


def _trocar_code_por_token(code: str, redirect_uri: str) -> str:
    """Troca o authorization code por id_token (token endpoint)."""
    cfg = carregar_config()
    if cfg.get("dev_mode"):
        # mock: chama nosso proprio endpoint mock
        body = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": cfg.get("client_id"),
            "client_secret": cfg.get("client_secret"),
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1/mock_token_placeholder", data=body, method="POST")
        # Em dev o token e gerado direto aqui (sem rede):
        return _mock_token(code, cfg)
    # Producao: POST no token endpoint do issuer
    token_endpoint = (cfg.get("issuer") or "").rstrip("/") + "/token"
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": cfg.get("client_id"),
        "client_secret": cfg.get("client_secret"),
    }).encode()
    req = urllib.request.Request(token_endpoint, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return data.get("id_token", "")


def _mock_token(code: str, cfg: Dict[str, Any]) -> str:
    """Gera id_token mock a partir do `code` (dev mode). O code codifica o usuario."""
    # code no formato: dev:<sub>:<email>:<nome>:<grupo>
    try:
        _, sub, email, nome, grupo = code.split(":", 4)
    except ValueError:
        sub, email, nome, grupo = "devuser", "dev@blueshift.local", "Usuario Dev SSO", "usuario"
    grupos = [grupo] if grupo else []
    return _criar_jwt_dev(sub, email, nome, grupos)


def verificar_e_extrair(code: str, redirect_uri: str) -> Dict[str, Any]:
    """Valida o code/state e retorna os claims do usuario (sub/email/name/groups)."""
    id_token = _trocar_code_por_token(code, redirect_uri)
    cfg = carregar_config()
    secret = cfg.get("client_secret") if cfg.get("dev_mode") else None
    claims = _verificar_jwt(id_token, secret)
    return claims


# --------------------------------------------------------------------------- #
# Mapeamento de identidade -> usuario local (RBAC continua igual)             #
# --------------------------------------------------------------------------- #

def mapear_usuario(claims: Dict[str, Any]) -> Dict[str, Any]:
    """Acha o usuario local pelo email/login SSO; cria se auto_criar.

    Papel: vem do cadastro local (admin define). Se o email bate com
    dominio_admin, vira admin. Se nao estiver cadastrado e auto_criar=0,
    levanta ValueError (bloqueia acesso).
    """
    from . import db
    email = (claims.get("email") or claims.get("sub") or "").lower()
    nome = claims.get("name") or email
    cfg = carregar_config()

    # 1) usuario ja cadastrado com esse login/email?
    with db.get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM usuarios WHERE login=? OR login=? OR lower(?) LIKE '%' || login || '%'",
            (email, claims.get("sub", ""), email)).fetchone()
    user = dict(r) if r else None

    if user:
        return user

    # 2) dominio de admin?
    papel = "usuario"
    if cfg.get("dominio_admin") and email.endswith(cfg["dominio_admin"]):
        papel = "admin"

    # 3) auto_criar?
    if cfg.get("auto_criar"):
        # cria usuario comum (sem senha — so entra via SSO)
        # usa o PRIMEIRO cliente cadastrado (nunca hardcoded — cliente final
        # cadastra a propria empresa; sem cliente, aborta o auto_criar)
        _clientes = db.listar_clientes()
        if not _clientes:
            raise ValueError(
                "Nenhum cliente cadastrado — cadastre a empresa na tela Clientes "
                "antes de usar SSO com auto_criar.")
        cid = _clientes[0]["id"]
        with db.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO usuarios (cliente_id, nome, login, senha, papel, area, ativo, criado_em) "
                "VALUES (?,?,?,?,?,?,1,?)",
                (cid, nome, email, "", papel, "", db.now_iso()))
            uid = cur.lastrowid
            r = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        return dict(r)

    raise ValueError(
        f"Usuario SSO '{email}' nao cadastrado e auto_criar=0. "
        f"Peça ao admin para cadastrar este login SSO antes.")
