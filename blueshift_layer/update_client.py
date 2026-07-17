#!/usr/bin/env python3
"""Update Client: checa e aplica o Update Channel aprovado pela BlueShift.

Como usamos LAYER sobre Hermes, as atualizacoes do motor vem do proprio Hermes.
O BlueShift versiona sua camada (connectors, skills, installer).

Sem dependencias externas: usa urllib (padrao do projeto, 100% offline-friendly).
O canal e configurado via BLUESHIFT_UPDATE_URL (default: canal mock em dev).
"""
from __future__ import annotations

import os
import subprocess
import sys
import json
import urllib.request
import urllib.error

from . import __version__ as CURRENT_VERSION

UPDATE_URL = os.getenv("BLUESHIFT_UPDATE_URL", "http://localhost:9001/v1/channel")


def _http_get_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def check() -> dict:
    """Consulta o canal e retorna dict com a versao disponivel (ou erro)."""
    data = _http_get_json(UPDATE_URL)
    if not data:
        return {"disponivel": False, "motivo": "canal_indisponivel",
                "atual": CURRENT_VERSION}
    versao = data.get("version")
    return {
        "disponivel": bool(versao and versao != CURRENT_VERSION),
        "atual": CURRENT_VERSION,
        "disponivel_version": versao,
        "notes": data.get("notes", ""),
        "url": data.get("url", ""),
        "aprovado_por": data.get("aprovado_por", ""),
        "publicado_em": data.get("publicado_em", ""),
    }


def apply(version: str | None = None) -> dict:
    """Aplica a atualizacao da camada.

    Em producao: pip install blueshift-layer==version (ou troca de imagem Docker).
    Em dev (BLUESHIFT_DEV=1): faz dry-run e so simula, para nao quebrar o ambiente.
    """
    info = check()
    if not version:
        version = info.get("disponivel_version")
    if not version:
        return {"ok": False, "motivo": "nenhuma_versao_disponivel"}
    if version == CURRENT_VERSION:
        return {"ok": False, "motivo": "ja_na_versao_atual", "versao": version}

    if os.getenv("BLUESHIFT_DEV") == "1":
        return {"ok": True, "dry_run": True, "versao": version,
                "mensagem": f"[dev] aplicaria blueshift-layer=={version} (pip install simulado)"}

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", f"blueshift-layer=={version}"]
        )
        return {"ok": True, "versao": version}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "motivo": "falha_instalacao", "erro": str(e)}
