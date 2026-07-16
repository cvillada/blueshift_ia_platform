#!/usr/bin/env python3
"""Installer: cria o profile do cliente no Hermes no 1o boot.

Como BlueShift e LAYER sobre Hermes, o installer apenas invoca:
  hermes profile create <cliente>
e popula as pastas de skills/connectors dentro do profile.
"""
import os
import subprocess
from pathlib import Path

HERMES_BIN = os.getenv("HERMES_BIN", "hermes")
PROFILES_DIR = Path(os.getenv("HOME", "~")) / ".hermes" / "profiles"


def create_profile(cliente: str):
    """Cria profile isolado do cliente no Hermes."""
    print(f"[installer] criando profile Hermes: {cliente}")
    try:
        subprocess.run([HERMES_BIN, "profile", "create", cliente], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[installer] erro ao criar profile: {e}")
        return False
    # Popular templates de skill e connectors no profile
    dest = PROFILES_DIR / cliente / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    print(f"[installer] profile {cliente} pronto em {PROFILES_DIR / cliente}")
    return True


def populate_templates(cliente: str):
    """Copia template_skills para o profile do cliente (parametrizavel por area da empresa)."""
    src = Path(__file__).resolve().parent / "template_skills"
    dest = PROFILES_DIR / cliente / "skills"
    if src.exists():
        for skill in src.iterdir():
            if skill.is_dir():
                print(f"[installer] skill disponivel: {skill.name}")
    print(f"[installer] templates prontos em {dest}")
