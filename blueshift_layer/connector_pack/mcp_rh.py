#!/usr/bin/env python3
"""Conector RH (stub)."""
from .base import BaseConnector


class RhConnector(BaseConnector):
    name = "rh"

    def tools(self) -> list:
        return ["consultar_folha", "consultar_colaborador"]

    def consultar_folha(self, mes: str) -> dict:
        return {"mes": mes, "total": 0.0}

    def consultar_colaborador(self, id_colab: str) -> dict:
        return {"id": id_colab, "nome": "MOCK"}


if __name__ == "__main__":
    RhConnector().run()
