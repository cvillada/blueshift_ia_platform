#!/usr/bin/env python3
"""Valida a license key no License Server BlueShift.

MODO DEV: aponta para endpoint mockado (LICENSE_SERVER_URL).
Em producao, trocar pela URL real do License Server (backend BlueShift).
"""
import os
import requests

# Em dev, use um mock local. Em producao: https://license.blueshift.app/v1/validate
LICENSE_SERVER_URL = os.getenv("BLUESHIFT_LICENSE_URL", "http://localhost:9000/v1/validate")
TIMEOUT = 10


def validate(key: str) -> bool:
    """Retorna True se a chave for valida junto ao License Server."""
    if not key:
        return False
    # Chaves BS-DEV-* existem SO para desenvolvimento local (BLUESHIFT_DEV=1).
    # Em producao/cliente (DEV=0) NAO valem: a chave precisa ser emitida pela
    # BlueShift (cadastro da empresa -> chave oficial). Sem isso, qualquer
    # clone do repo publico "se licenciaria" com um prefixo qualquer.
    if key.startswith("BS-DEV-"):
        return os.getenv("BLUESHIFT_DEV") == "1"
    try:
        r = requests.post(LICENSE_SERVER_URL, json={"key": key}, timeout=TIMEOUT)
        return r.status_code == 200 and r.json().get("valid", False)
    except requests.RequestException:
        # Sem rede: bloqueia (modo "locked") - exceto em dev com flag.
        return os.getenv("BLUESHIFT_DEV") == "1"


def activate(key: str) -> dict:
    """Ativa a chave e retorna metadados (cliente, perfil, modelo autorizado)."""
    if not validate(key):
        return {"valid": False}
    return {"valid": True, "cliente": "demo", "perfil": "cliente_demo", "modelo": "finetuned-v1"}
