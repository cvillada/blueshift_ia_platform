#!/usr/bin/env python3
"""Conector ERP real (BlueShift) — servidor MCP sobre um Postgres de exemplo.

Substitui o stub anterior. Conecta-se a um banco Postgres (demo: erp_demo em
localhost:5433 via docker-compose LOCAL, fora do repo — nao versionado). Em producao, aponte as variaveis
de ambiente para o Postgres real do cliente.

Tools expostas via MCP (FastMCP / stdio):
    - buscar_cliente(id_cliente)      -> dados cadastrais + health do relacionamento
    - listar_pedidos(id_cliente)      -> pedidos (ordens/apolices) do cliente
    - criar_oportunidade(...)         -> insere oportunidade na tabela oportunidades

A mesma classe Eh usada pelos Template Skills (vendas/financeiro/suporte) e pelo
smoke test, mantendo a interface: `name`, `tools()`, e os metodos de negocio.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import BaseConnector

try:
    from mcp.server.fastmcp import FastMCP
    _HAS_FASTMCP = True
except Exception:  # pragma: no cover - FastMCP ausente
    FastMCP = None
    _HAS_FASTMCP = False


# Configuracao de conexao (override via env para o Postgres real do cliente)
def _dsn() -> str:
    return os.environ.get(
        "ERP_DSN",
        "host=localhost port=5433 dbname=erp_demo user=blueshift password=blueshift",
    )


@dataclass
class ErpConnectionError(RuntimeError):
    """Erro de conexao com o ERP/Postgres."""


class ErpConnector(BaseConnector):
    """Conector ERP real: leitura/escrita no Postgres do cliente/demo."""

    name = "erp"

    def __init__(self, dsn: Optional[str] = None):
        self._dsn = dsn or _dsn()
        self._mcp: Optional["FastMCP"] = None

    # ------------------------------------------------------------------ #
    # Interface exigida pela BaseConnector / smoke test / template skills #
    # ------------------------------------------------------------------ #
    def tools(self) -> List[str]:
        return [
            "buscar_cliente",
            "listar_pedidos",
            "criar_oportunidade",
        ]

    # ------------------------------------------------------------------ #
    # Pool de conexoes (leve; um conn por operacao, thread-safe o bastante) #
    # ------------------------------------------------------------------ #
    @contextmanager
    def _conn(self):
        import psycopg  # import local: nao quebra import do modulo sem o driver

        conn = psycopg.connect(self._dsn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Tools de negocio (tb expostas via MCP)                             #
    # ------------------------------------------------------------------ #
    def buscar_cliente(self, id_cliente: str) -> Dict[str, Any]:
        """Retorna dados cadastrais do cliente + resumo de relacionamento.

        Inclui totais de pedidos (count, valor total, status) para o
        Template Skill de vendas/suporte responder 'status do cliente X'.
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id_cliente, razao_social, nome_fantasia, cnpj,
                       segmento, uf, score, limite_credito, desde, ativo
                FROM clientes WHERE id_cliente = %s
                """,
                (id_cliente,),
            )
            row = cur.fetchone()
            if not row:
                return {"encontrado": False, "id": id_cliente}

            cols = [
                "id_cliente", "razao_social", "nome_fantasia", "cnpj",
                "segmento", "uf", "score", "limite_credito", "desde", "ativo",
            ]
            cliente = dict(zip(cols, [self._py(v) for v in row]))

            cur.execute(
                """
                SELECT count(*),
                       coalesce(sum(valor), 0),
                       coalesce(sum(CASE WHEN status = 'pendente' THEN valor ELSE 0 END), 0),
                       max(data_emissao)
                FROM pedidos WHERE id_cliente = %s
                """,
                (id_cliente,),
            )
            tot, vt, pend, last = cur.fetchone()
            cliente["pedidos_count"] = int(tot)
            cliente["pedidos_valor_total"] = float(vt)
            cliente["pedidos_valor_pendente"] = float(pend)
            cliente["ultima_compra"] = self._py(last)
            cliente["encontrado"] = True
            return cliente

    def listar_pedidos(self, id_cliente: str) -> List[Dict[str, Any]]:
        """Lista os pedidos (ordens/apolices) de um cliente, mais recentes primeiro."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id_pedido, data_emissao, valor, status, canal, produto
                FROM pedidos WHERE id_cliente = %s
                ORDER BY data_emissao DESC
                """,
                (id_cliente,),
            )
            cols = ["id_pedido", "data_emissao", "valor", "status", "canal", "produto"]
            return [dict(zip(cols, [self._py(v) for v in r])) for r in cur.fetchall()]

    def criar_oportunidade(
        self,
        cliente: str,
        titulo: str,
        valor_estimado: float,
        itens: Optional[List[Dict[str, Any]]] = None,
        probabilidade: int = 10,
        etapa: str = "prospecção",
    ) -> str:
        """Cria uma oportunidade de venda para o cliente. Retorna o id gerado."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM clientes WHERE id_cliente = %s", (cliente,))
            if not cur.fetchone():
                raise ValueError(f"Cliente {cliente} nao existe no ERP")
            cur.execute(
                """
                INSERT INTO oportunidades
                    (id_cliente, titulo, valor_estimado, probabilidade, etapa, itens)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id_oportunidade
                """,
                (cliente, titulo, valor_estimado, probabilidade, etapa,
                 json.dumps(itens or [], ensure_ascii=False)),
            )
            new_id = cur.fetchone()[0]
            return f"OP-{new_id:06d}"

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _py(v: Any) -> Any:
        """Converte tipos do psycopg para tipos JSON-seriaveis."""
        if v is None:
            return None
        if isinstance(v, (list, dict, str, int, float, bool)):
            return v
        return str(v)

    # ------------------------------------------------------------------ #
    # Servidor MCP real (stdio) via FastMCP                              #
    # ------------------------------------------------------------------ #
    def build_mcp(self) -> "FastMCP":
        """Constroi (e memoiza) o servidor MCP expondo as tools via stdio."""
        if self._mcp is not None:
            return self._mcp
        if not _HAS_FASTMCP:
            raise RuntimeError("FastMCP indisponivel: instale 'mcp>=1.0' com extras.")
        mcp = FastMCP("blueshift-erp")

        @mcp.tool()
        def buscar_cliente(id_cliente: str) -> str:
            """Dados cadastrais + resumo de relacionamento de um cliente ERP.

            Args:
                id_cliente: id do cliente (ex: 'C001').
            """
            return json.dumps(self.buscar_cliente(id_cliente), ensure_ascii=False, default=str)

        @mcp.tool()
        def listar_pedidos(id_cliente: str) -> str:
            """Lista os pedidos/apolices de um cliente, do mais recente ao mais antigo.

            Args:
                id_cliente: id do cliente (ex: 'C001').
            """
            return json.dumps(self.listar_pedidos(id_cliente), ensure_ascii=False, default=str)

        @mcp.tool()
        def criar_oportunidade(
            cliente: str,
            titulo: str,
            valor_estimado: float,
            itens: Optional[List[Dict[str, Any]]] = None,
            probabilidade: int = 10,
            etapa: str = "prospecção",
        ) -> str:
            """Cria uma oportunidade de venda no ERP. Retorna o id (ex: OP-000007).

            Args:
                cliente: id do cliente (ex: 'C001').
                titulo: titulo da oportunidade.
                valor_estimado: valor estimado em R$.
                itens: lista opcional de itens (JSON).
                probabilidade: % de probabilidade (default 10).
                etapa: etapa do funil (default 'prospecção').
            """
            return self.criar_oportunidade(
                cliente, titulo, valor_estimado, itens, probabilidade, etapa
            )

        self._mcp = mcp
        return mcp

    def run(self):
        """Inicia o servidor MCP real (stdio). Substitui o print do stub."""
        mcp = self.build_mcp()
        mcp.run()


if __name__ == "__main__":
    ErpConnector().run()
