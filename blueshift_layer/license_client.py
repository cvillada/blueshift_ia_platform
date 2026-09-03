#!/usr/bin/env python3
"""Valida a license key no License Server BlueShift.

O License Server e o backend da BlueShift que conhece as chaves emitidas
(cadastro da empresa na pagina de solicitacao -> chave). A URL e definida
via BLUESHIFT_LICENSE_URL: em dev aponta para o mock local (porta 9000);
em producao/cliente aponta para o License Server real da BlueShift.

Chaves BS-DEV-* existem SO para desenvolvimento local (BLUESHIFT_DEV=1):
em producao qualquer chave precisa ter sido emitida pela BlueShift.
"""
import os

import requests

LICENSE_SERVER_URL = os.getenv("BLUESHIFT_LICENSE_URL", "http://localhost:9000/v1/validate")
TIMEOUT = 10


def _consulta(key: str) -> dict | None:
    """POST no License Server. Retorna o JSON da resposta (ou None em falha)."""
    if not key:
        return None
    r = requests.post(LICENSE_SERVER_URL, json={"key": key}, timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def validate(key: str) -> bool:
    """Retorna True se a chave for valida junto ao License Server."""
    if not key:
        return False
    # Chaves BS-DEV-* existem SO para desenvolvimento local (BLUESHIFT_DEV=1).
    if key.startswith("BS-DEV-"):
        return os.getenv("BLUESHIFT_DEV") == "1"
    try:
        meta = _consulta(key)
        return bool(meta and meta.get("valid", False))
    except requests.RequestException:
        # Sem rede: bloqueia (modo "locked") - exceto em dev com flag.
        return os.getenv("BLUESHIFT_DEV") == "1"


def activate(key: str) -> dict:
    """Ativa a chave e devolve os METADADOS do License Server.

    Retorno do servidor (ex: {"valid": true, "cliente": "...", "perfil": "..."})
    e devolvido como esta — a tela usa cliente/perfil reais do cadastro. O
    perfil 'demo' so aparece como fallback em dev local (mock).
    """
    if not key:
        return {"valid": False}
    if key.startswith("BS-DEV-"):
        if os.getenv("BLUESHIFT_DEV") != "1":
            return {"valid": False}
        return {"valid": True, "cliente": "demo", "perfil": "cliente_demo",
                "modelo": "finetuned-v1"}
    try:
        meta = _consulta(key)
    except requests.RequestException:
        meta = None
    if not meta or not meta.get("valid"):
        return {"valid": False}
    meta.setdefault("cliente", "demo")
    meta.setdefault("perfil", "cliente")
    return meta
