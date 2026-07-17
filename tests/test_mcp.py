#!/usr/bin/env python3
"""Teste do servidor MCP stdio (Python puro) do Connector Pack BlueShift.

Valida o protocolo JSON-RPC 2.0 (initialize/tools/list/tools/call) e a
execucao das ferramentas reais (CRM/RH) e o fallback do ERP sem Postgres.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _mcp() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "blueshift_layer.connector_pack.mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
    )


def _send(p: subprocess.Popen, obj: dict) -> dict:
    p.stdin.write(json.dumps(obj) + "\n")
    p.stdin.flush()
    return json.loads(p.stdout.readline())


def test_mcp_protocolo_e_ferramentas():
    p = _mcp()
    try:
        # initialize
        r = _send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert r["result"]["protocolVersion"] == "2024-11-05"
        assert r["result"]["serverInfo"]["name"] == "blueshift-connector-pack"

        # tools/list
        r = _send(p, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        nomes = [t["name"] for t in r["result"]["tools"]]
        for esperado in ["crm_historico_contato", "crm_proximos_passos",
                         "rh_consultar_colaborador", "rh_consultar_folha",
                         "erp_buscar_cliente", "erp_listar_pedidos"]:
            assert esperado in nomes, f"falta tool {esperado}"

        # tools/call CRM (real)
        r = _send(p, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": "crm_historico_contato", "arguments": {"id_cliente": "C001"}}})
        assert r["result"]["isError"] is False
        dados = json.loads(r["result"]["content"][0]["text"])
        assert any("proposta" in d["resumo"].lower() for d in dados)

        # tools/call RH (real)
        r = _send(p, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                      "params": {"name": "rh_consultar_colaborador", "arguments": {"id_colab": "E001"}}})
        assert r["result"]["isError"] is False
        colab = json.loads(r["result"]["content"][0]["text"])
        assert colab["nome"] == "Carlos Andrade"

        # tools/call ERP sem Postgres -> fallback gracioso (nao quebra)
        r = _send(p, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                      "params": {"name": "erp_buscar_cliente", "arguments": {"id_cliente": "C001"}}})
        assert r["result"]["isError"] is False  # fallback nao vira erro de protocolo

        # método desconhecido -> erro JSON-RPC
        r = _send(p, {"jsonrpc": "2.0", "id": 6, "method": "bogus", "params": {}})
        assert r["error"]["code"] == -32601
    finally:
        p.stdin.close()
        p.wait()


if __name__ == "__main__":
    test_mcp_protocolo_e_ferramentas()
    print("MCP TESTS PASSOU")
