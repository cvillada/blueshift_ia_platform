#!/usr/bin/env python3
"""Installer: cria o profile/diretório de configuração do cliente.

Cria a estrutura de pastas isoladas para skills e configurações de cada
cliente da BlueShift IA Platform. Não depende de nenhum motor externo.
"""
import os
from pathlib import Path


def create_profile(cliente: str):
    """Cria estrutura isolada do cliente (pastas, sem dependência externa)."""
    base = _base_dir()
    dest = base / cliente
    print(f"[installer] criando perfil do cliente: {cliente}")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "skills").mkdir(exist_ok=True)
    (dest / "config").mkdir(exist_ok=True)
    print(f"[installer] perfil {cliente} pronto em {dest}")
    return True


def _base_dir() -> Path:
    home = Path(os.getenv("HOME", "~"))
    return home / ".blueshift" / "profiles"
