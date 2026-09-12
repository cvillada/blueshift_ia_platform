"""Autenticacao HTTP compartilhada do CL Agents (OAuth2 client_credentials).

Usado pelo conector API, pelo conector A2A e pelos modelos externos (AIDP/
Oracle Responses). Sem dependencias novas: urllib + json + time.

O cache e por processo: (token_url, client_id, scope) -> (expira_em, token),
com renovacao 30s antes do vencimento. O deploy padrao roda 1 worker.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_CACHE: dict[tuple, tuple[float, str]] = {}


def token_oauth2(config: dict) -> tuple[str, str]:
    """Busca (e cacheia) access_token via OAuth2 client_credentials.

    Returns:
        (token, erro) — erro vazio quando ok.
    """
    token_url = (config.get("token_url") or "").strip()
    client_id = (config.get("client_id") or "").strip()
    client_secret = config.get("client_secret") or ""
    scope = (config.get("scope") or "").strip()
    if not (token_url and client_id and client_secret):
        return "", "oauth2: token_url, client_id e client_secret sao obrigatorios"
    chave = (token_url, client_id, scope)
    agora = time.time()
    cache = TOKEN_CACHE.get(chave)
    if cache and cache[0] > agora + 5:
        return cache[1], ""
    dados = {"grant_type": "client_credentials",
             "client_id": client_id, "client_secret": client_secret}
    if scope:
        dados["scope"] = scope
    req = urllib.request.Request(
        token_url, data=urllib.parse.urlencode(dados).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=int(config.get("timeout") or 15)) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return "", f"oauth2: HTTP {e.code} ao obter token ({e.reason})"
    except urllib.error.URLError as e:
        return "", f"oauth2: falha ao contatar {token_url} ({e.reason})"
    except Exception as e:  # noqa: BLE001
        return "", f"oauth2: {e}"
    token = out.get("access_token") if isinstance(out, dict) else None
    if not token:
        return "", "oauth2: resposta do token sem access_token"
    try:
        expira = float(out.get("expires_in") or 3600)
    except (TypeError, ValueError):
        expira = 3600.0
    TOKEN_CACHE[chave] = (agora + max(expira - 30.0, 30.0), token)
    return token, ""


def aplicar_auth(headers: dict, config: dict) -> tuple[dict, str]:
    """Aplica a autenticacao configurada aos headers. Retorna (headers, erro).

    auth: none (default — headers como estao) | bearer | oauth2
    """
    auth = (config.get("auth") or "none").strip().lower()
    if auth == "bearer":
        tok = (config.get("token") or "").strip()
        if not tok:
            return headers, "auth bearer: campo token vazio"
        headers["Authorization"] = f"Bearer {tok}"
    elif auth == "oauth2":
        tok, erro = token_oauth2(config)
        if erro:
            return headers, erro
        headers["Authorization"] = f"Bearer {tok}"
    return headers, ""
