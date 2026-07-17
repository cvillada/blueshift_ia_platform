#!/usr/bin/env python3
"""Conector RH real (BlueShift) — dados de exemplo locais, sem rede externa.

Substitui o stub. Mantém a interface da BaseConnector usada pelos Template
Skills e smoke tests. Em produção, o método `_dados()` seria trocado por uma
consulta ao ERP de RH / folha real do cliente (eSocial, SAP, Senior, etc).

Tools expostas:
    - consultar_colaborador(id_colab) -> dados do colaborador
    - consultar_folha(mes)            -> resumo da folha do mês
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


class RhConnector(BaseConnector):
    """Conector RH real (dados de exemplo embarcados)."""

    name = "rh"
    _mcp = None

    def tools(self) -> List[str]:
        return ["consultar_colaborador", "consultar_folha"]

    # ------------------------------------------------------------------ #
    def _dados(self) -> Dict[str, Any]:
        return {
            "E001": {
                "nome": "Carlos Andrade", "cargo": "Analista de Seguros",
                "setor": "Vendas", "admissao": "2021-03-10", "gestor": "Ana Lima",
                "status": "ativo",
            },
            "E002": {
                "nome": "Marina Souza", "cargo": "Especialista RH",
                "setor": "People", "admissao": "2022-08-01", "gestor": "Bia Rocha",
                "status": "ativo",
            },
        }

    def consultar_colaborador(self, id_colab: str) -> Dict[str, Any]:
        d = self._dados().get(id_colab)
        if not d:
            return {"id": id_colab, "encontrado": False}
        return {"encontrado": True, "id": id_colab, **d}

    def consultar_folha(self, mes: str) -> Dict[str, Any]:
        # dados de exemplo determinísticos por mês
        return {
            "mes": mes,
            "total_funcionarios": 2,
            "massa_salarial": 38000.0,
            "verbas": {"salarios": 34000.0, "beneficios": 4000.0},
            "status": "fechada" if mes < "2026-07" else "em_aberto",
        }

    # ------------------------------------------------------------------ #
    def build_mcp(self) -> "FastMCP":
        if self._mcp is not None:
            return self._mcp
        if not _HAS_FASTMCP:
            raise RuntimeError("FastMCP indisponível: instale 'mcp>=1.0' com extras.")
        mcp = FastMCP("blueshift-rh")

        @mcp.tool()
        def consultar_colaborador(id_colab: str) -> str:
            """Dados de um colaborador (nome, cargo, setor, gestor, status).

            Args:
                id_colab: matrícula (ex: 'E001').
            """
            return json.dumps(self.consultar_colaborador(id_colab), ensure_ascii=False, default=str)

        @mcp.tool()
        def consultar_folha(mes: str) -> str:
            """Resumo da folha de pagamento de um mês (massa salarial, verbas).

            Args:
                mes: AAA-MM (ex: '2026-06').
            """
            return json.dumps(self.consultar_folha(mes), ensure_ascii=False, default=str)

        self._mcp = mcp
        return mcp

    def run(self):
        self.build_mcp().run()


if __name__ == "__main__":
    RhConnector().run()
