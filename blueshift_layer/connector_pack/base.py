#!/usr/bin/env python3
"""Classe base para servidores MCP do Connector Pack.

Cada conector (ERP/CRM/RH) herda de BaseConnector e implementa as tools.
Em producao, conecta ao banco/sistema real do cliente.
"""
from abc import ABC, abstractmethod


class BaseConnector(ABC):
    name: str = "base"

    @abstractmethod
    def tools(self) -> list:
        """Retorna a lista de ferramentas (tools) expostas via MCP."""
        ...

    def run(self):
        """Inicia o servidor MCP (stdio)."""
        print(f"[mcp:{self.name}] servidor iniciado (stdio)")
        # Em producao: usar mcp.server.stdio para expor as tools
