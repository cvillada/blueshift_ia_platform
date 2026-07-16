#!/usr/bin/env python3
"""Update Client: checa o Update Channel aprovado pela BlueShift.

Como usamos LAYER sobre Hermes, as atualizacoes do motor vem do proprio Hermes.
O BlueShift so versiona sua camada (connectors, skills, installer).
"""
import requests

UPDATE_URL = "http://localhost:9001/v1/channel"  # mock em dev


def check():
    """Verifica se ha nova versao da camada BlueShift aprovada."""
    print("[update] checando Update Channel...")
    try:
        r = requests.get(UPDATE_URL, timeout=10)
        if r.status_code == 200:
            print(f"[update] versao disponivel: {r.json().get('version', 'desconhecida')}")
        else:
            print("[update] nenhuma atualizacao (canal vazio)")
    except requests.RequestException:
        print("[update] canal indisponivel (modo offline OK - Hermes continua funcionando)")


def apply(version: str):
    """Aplica atualizacao da camada (pip install da nova versao)."""
    print(f"[update] aplicando BlueShift {version}...")
    # Em producao: pip install blueshift-layer==version
    print("[update] concluido")
