#!/usr/bin/env python3
"""Conector CRM (stub)."""
from .base import BaseConnector


class CrmConnector(BaseConnector):
    name = "crm"

    def tools(self) -> list:
        return ["historico_contato", "proximos_passos"]

    def historico_contato(self, id_cliente: str) -> list:
        return []

    def proximos_passos(self, id_cliente: str) -> list:
        return []


if __name__ == "__main__":
    CrmConnector().run()
