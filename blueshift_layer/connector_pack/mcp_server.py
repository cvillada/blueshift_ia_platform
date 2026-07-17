#!/usr/bin/env python3
"""Servidor MCP (Model Context Protocol) stdio em Python PURO — BlueShift.

Expoe os conectores reais (CRM/RH/ERP) como ferramentas MCP para clientes
externos (Claude Desktop, Cursor, outro Hermes, etc.), SEM dependencias
externas (nao usa a lib `mcp` — implementa o JSON-RPC 2.0 sobre stdio).

Reaproveita as mesmas funcoes de negocio dos conectores (connector_pack/),
entao o mesmo dado que o Agente usa fica disponivel para um cliente MCP
externo. O ERP tenta o Postgres real; se indisponivel, usa dados de exemplo
(em ambiente on-premise sem o ERP de demonstracao, nao quebra).

Uso:
    python -m blueshift_layer.connector_pack.mcp_server
    # ou: blueshift mcp

Protocolo: ler linhas JSON (requests) do stdin, escrever linhas JSON
(responses/notifications) no stdout. Cada mensagem é um objeto JSON-RPC 2.0.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from . import registry
from .mcp_crm import CrmConnector
from .mcp_rh import RhConnector


# --------------------------------------------------------------------------- #
# Schemas das ferramentas (reaproveitam os conectores reais)                 #
# --------------------------------------------------------------------------- #

def _tools_catalog() -> List[Dict[str, Any]]:
    """Catalogo de ferramentas MCP com schema de entrada (JSON Schema mínimo)."""
    return [
        {
            "name": "crm_historico_contato",
            "description": "Histórico de interações de um cliente no CRM (BlueShift).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id_cliente": {"type": "string", "description": "id do cliente, ex: 'C001'"}
                },
                "required": ["id_cliente"],
            },
        },
        {
            "name": "crm_proximos_passos",
            "description": "Próximos passos / pipeline aberto de um cliente no CRM (BlueShift).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id_cliente": {"type": "string", "description": "id do cliente, ex: 'C001'"}
                },
                "required": ["id_cliente"],
            },
        },
        {
            "name": "rh_consultar_colaborador",
            "description": "Dados de um colaborador (nome, cargo, setor, gestor, status) no RH (BlueShift).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id_colab": {"type": "string", "description": "matrícula, ex: 'E001'"}
                },
                "required": ["id_colab"],
            },
        },
        {
            "name": "rh_consultar_folha",
            "description": "Resumo da folha de pagamento de um mês (massa salarial, verbas) no RH (BlueShift).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mes": {"type": "string", "description": "AAA-MM, ex: '2026-06'"}
                },
                "required": ["mes"],
            },
        },
        {
            "name": "erp_buscar_cliente",
            "description": "Dados cadastrais + resumo de relacionamento de um cliente no ERP (BlueShift).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id_cliente": {"type": "string", "description": "id do cliente, ex: 'C001'"}
                },
                "required": ["id_cliente"],
            },
        },
        {
            "name": "erp_listar_pedidos",
            "description": "Lista os pedidos/apólices de um cliente no ERP (BlueShift).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id_cliente": {"type": "string", "description": "id do cliente, ex: 'C001'"}
                },
                "required": ["id_cliente"],
            },
        },
    ]


def _call_tool(name: str, args: Dict[str, Any]) -> str:
    """Executa a ferramenta MCP chamando o conector real (reaproveitado)."""
    crm = CrmConnector()
    rh = RhConnector()
    if name == "crm_historico_contato":
        return json.dumps(crm.historico_contato(args.get("id_cliente", "")),
                           ensure_ascii=False, default=str)
    if name == "crm_proximos_passos":
        return json.dumps(crm.proximos_passos(args.get("id_cliente", "")),
                           ensure_ascii=False, default=str)
    if name == "rh_consultar_colaborador":
        return json.dumps(rh.consultar_colaborador(args.get("id_colab", "")),
                           ensure_ascii=False, default=str)
    if name == "rh_consultar_folha":
        return json.dumps(rh.consultar_folha(args.get("mes", "")),
                           ensure_ascii=False, default=str)
    if name in ("erp_buscar_cliente", "erp_listar_pedidos"):
        # ERP: tenta Postgres; se indisponivel, usa dados de exemplo (offline ok)
        try:
            from .mcp_erp import ErpConnector
            erp = ErpConnector()
            if name == "erp_buscar_cliente":
                return json.dumps(erp.buscar_cliente(args.get("id_cliente", "")),
                                   ensure_ascii=False, default=str)
            return json.dumps(erp.listar_pedidos(args.get("id_cliente", "")),
                               ensure_ascii=False, default=str)
        except Exception as e:  # Postgres ausente -> fallback exemplo
            if name == "erp_buscar_cliente":
                res = {"encontrado": False, "id": args.get("id_cliente", ""),
                       "erro": f"ERP indisponível (modo exemplo): {e}"}
            else:
                res = []
            return json.dumps(res, ensure_ascii=False, default=str)
    raise ValueError(f"Ferramenta '{name}' desconhecida.")


# --------------------------------------------------------------------------- #
# Loop JSON-RPC 2.0 sobre stdio (Python puro)                                #
# --------------------------------------------------------------------------- #

def _handle(req: Dict[str, Any]) -> Dict[str, Any] | None:
    method = req.get("method")
    msg_id = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "blueshift-connector-pack", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {"tools": _tools_catalog()},
        }
    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result_text = _call_tool(name, arguments)
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                    "isError": False,
                },
            }
        except Exception as e:  # noqa: BLE001
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Erro: {e}"}],
                    "isError": True,
                },
            }
    if method == "notifications/initialized":
        return None  # notificação: sem resposta
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    # método desconhecido
    return {
        "jsonrpc": "2.0", "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def run() -> None:
    """Loop principal: lê linhas JSON do stdin, escreve respostas no stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run()
