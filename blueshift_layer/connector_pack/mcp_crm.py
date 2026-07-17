#!/usr/bin/env python3
"""Conector CRM real (BlueShift) — dados de exemplo locais, sem rede externa.

Substitui o stub. Mantem a mesma interface da BaseConnector usada pelos
Template Skills e smoke tests: `name`, `tools()` e os metodos de negocio.
Em producao, o metodo `_dados()` seria trocado por uma consulta a um
CRM real (SFDC, HubSpot, RD Station) — a superficie da tool nao muda.

Tools expostas:
    - historico_contato(id_cliente)  -> ultimas interacoes com o cliente
    - proximos_passos(id_cliente)    -> pipeline/follow-ups abertos
"""
from __future__ import annotations

from .base import BaseConnector

try:
    from mcp.server.fastmcp import FastMCP
    _HAS_FASTMCP = True
except Exception:  # pragma: no cover
    FastMCP = None
    _HAS_FASTMCP = False

import json
from typing import Any, Dict, List, Optional


class CrmConnector(BaseConnector):
    """Conector CRM real (dados de exemplo embarcados)."""

    name = "crm"
    _mcp = None

    # ------------------------------------------------------------------ #
    def tools(self) -> List[str]:
        return ["historico_contato", "proximos_passos"]

    # ------------------------------------------------------------------ #
    # Dados de exemplo (em producao: consulta ao CRM real do cliente)    #
    # ------------------------------------------------------------------ #
    def _dados(self) -> Dict[str, Any]:
        return {
            "C001": {
                "historico": [
                    {"data": "2026-06-20", "canal": "email", "resumo": "Envio de proposta de seguro auto"},
                    {"data": "2026-07-01", "canal": "telefone", "resumo": "Reunião de renovação — cliente satisfeito"},
                    {"data": "2026-07-10", "canal": "whatsapp", "resumo": "Dúvida sobre cobertura de terceiros"},
                ],
                "proximos": [
                    {"acao": "Enviar contrato assinado", "responsavel": "Ana", "quando": "2026-07-18", "status": "aberto"},
                    {"acao": "Follow-up pós-venda", "responsavel": "Suporte", "quando": "2026-07-25", "status": "agendado"},
                ],
            },
            "C002": {
                "historico": [
                    {"data": "2026-05-15", "canal": "email", "resumo": "Primeira abordagem — interesse em seguro vida"},
                ],
                "proximos": [
                    {"acao": "Apresentar cotação", "responsavel": "Bia", "quando": "2026-07-20", "status": "aberto"},
                ],
            },
        }

    # ------------------------------------------------------------------ #
    # Tools de negocio                                                  #
    # ------------------------------------------------------------------ #
    def historico_contato(self, id_cliente: str) -> List[Dict[str, Any]]:
        """Retorna o histórico de interações do cliente no CRM."""
        return self._dados().get(id_cliente, {}).get("historico", [])

    def proximos_passos(self, id_cliente: str) -> List[Dict[str, Any]]:
        """Retorna os próximos passos / pipeline aberto do cliente."""
        return self._dados().get(id_cliente, {}).get("proximos", [])

    # ------------------------------------------------------------------ #
    # Servidor MCP real (stdio) — opcional                              #
    # ------------------------------------------------------------------ #
    def build_mcp(self) -> "FastMCP":
        if self._mcp is not None:
            return self._mcp
        if not _HAS_FASTMCP:
            raise RuntimeError("FastMCP indisponível: instale 'mcp>=1.0' com extras.")
        mcp = FastMCP("blueshift-crm")

        @mcp.tool()
        def historico_contato(id_cliente: str) -> str:
            """Histórico de interações de um cliente no CRM.

            Args:
                id_cliente: id do cliente (ex: 'C001').
            """
            return json.dumps(self.historico_contato(id_cliente), ensure_ascii=False, default=str)

        @mcp.tool()
        def proximos_passos(id_cliente: str) -> str:
            """Próximos passos / pipeline aberto de um cliente no CRM.

            Args:
                id_cliente: id do cliente (ex: 'C001').
            """
            return json.dumps(self.proximos_passos(id_cliente), ensure_ascii=False, default=str)

        self._mcp = mcp
        return mcp

    def run(self):
        self.build_mcp().run()


if __name__ == "__main__":
    CrmConnector().run()
