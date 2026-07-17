#!/usr/bin/env python3
"""Update Channel Server (mock) da BlueShift.

Serve o "canal de atualizacao aprovado" da camada BlueShift (connectors,
skills, installer). Contrato com blueshift_layer/update_client.py:
  - GET /v1/channel  -> JSON com a versao aprovada da camada

Em producao este mock some: o client aponta para
https://update.blueshift.app/v1/channel e o backend real serve o canal.

A versao servida pode vir de um arquivo JSON (BLUESHIFT_CHANNEL_FILE) ou,
em dev, do valor embutido abaixo. Assim o "canal real" e so trocar o JSON.

Resposta:
  {"version": "0.2.0", "notes": "...", "url": "...", "aprovado_por": "BlueShift",
   "publicado_em": "2026-07-16"}
"""
import json
import os

from flask import Flask, jsonify, request

# Canal embutido (dev). Em prod vem do backend/arquivo.
CHANNEL_DEFAULT = {
    "version": "0.2.0",
    "notes": "Conectores CRM/RH reais, Agent Factory com modelo+skills+conectores, canal de API.",
    "url": "https://pypi.blueshift.app/blueshift-layer-0.2.0.tar.gz",
    "aprovado_por": "BlueShift QA",
    "publicado_em": "2026-07-16",
}

app = Flask(__name__)


def _channel() -> dict:
    f = os.getenv("BLUESHIFT_CHANNEL_FILE")
    if f and os.path.isfile(f):
        try:
            return json.load(open(f, encoding="utf-8"))
        except OSError:
            pass
    return CHANNEL_DEFAULT


@app.route("/v1/channel", methods=["GET"])
def channel():
    return jsonify(_channel()), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "service": "blueshift-update-channel"}), 200


def run(host: str = "0.0.0.0", port: int = 9001, debug: bool = False):
    """Sobe o mock. Porta 9001 casa com BLUESHIFT_UPDATE_URL do client."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    port = int(os.getenv("BLUESHIFT_UPDATE_PORT", "9001"))
    run(port=port, debug=os.getenv("BLUESHIFT_DEV") == "1")
