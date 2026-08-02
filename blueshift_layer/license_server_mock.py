#!/usr/bin/env python3
"""License Server mockado em Flask — para desenvolvimento local da BlueShift.

Contrato casado com blueshift_layer/license_client.py:
  - Recebe POST /v1/validate  com body JSON {"key": "<chave>"}
  - Responde JSON {"valid": true|false, ...metadados}

Em producao este mock some: o client aponta para
https://license.blueshift.app/v1/validate e o backend real valida a chave.

Chaves aceitas no mock (dev):
  - Qualquer chave com prefixo "BS-DEV-"  -> valid=true
  - Chaves cadastradas em LICENSE_DB      -> valid=true com metadados do cliente
  - Demais                               -> valid=false

Metadados de ativacao (iguais ao retorno de license_client.activate):
  cliente, perfil, modelo.
"""
import json
import os

from flask import Flask, jsonify, request

# Banco falso de licencas (em memoria). Em prod seria consulta ao backend.
LICENSE_DB = {
    "BS-PROD-XPTO-SEGURO-001": {
        "cliente": "XPTO Seguro",
        "perfil": "cliente_seguradora",
        "modelo": "finetuned-v1",
    },
    "BS-PROD-BANCO-INTER-002": {
        "cliente": "Banco Inter",
        "perfil": "cliente_banco",
        "modelo": "finetuned-v1",
    },
    "BS-PROD-TRIAL-003": {
        "cliente": "Trial 30d",
        "perfil": "cliente_trial",
        "modelo": "finetuned-v1",
    },
}

DEV_PREFIX = "BS-DEV-"

app = Flask(__name__)


def _lookup(key: str) -> dict | None:
    """Devolve os metadados da licenca se a chave for valida, senao None."""
    if not key:
        return None
    if key.startswith(DEV_PREFIX):
        return {"cliente": "demo", "perfil": "cliente_demo", "modelo": "finetuned-v1"}
    return LICENSE_DB.get(key)


@app.route("/v1/validate", methods=["POST"])
def validate():
    data = request.get_json(silent=True) or {}
    key = data.get("key")
    meta = _lookup(key)
    if meta is None:
        return jsonify({"valid": False, "reason": "chave_invalida_ou_desconhecida"}), 200
    return jsonify({"valid": True, **meta}), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "service": "blueshift-license-mock"}), 200


def run(host: str = "0.0.0.0", port: int = 9000, debug: bool = False):
    """Sobe o mock. Porta 9000 casa com LICENSE_SERVER_URL do client."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    port = int(os.getenv("BLUESHIFT_LICENSE_PORT", "9000"))
    run(port=port, debug=os.getenv("BLUESHIFT_DEV") == "1")
