"""Registry do Connector Pack (BlueShift).

Executa conectores cadastrados no banco (tabela conectores) por tipo:
  - api: chamada HTTP via urllib
  - mcp: executa servidor MCP stdio e chama tool
  - sql: consulta SQL via psycopg

Nao depende de classes fixas (ERP/CRM/RH) — cada conector e configurado
dinamicamente pelo admin no Portal e executado por tipo.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse

from ..portal import db


# --------------------------------------------------------------------------- #
# Engine principal: executa conectores de uma area                           #
# --------------------------------------------------------------------------- #

def executar_conectores_area(cliente_id: int, area: str, pergunta: str,
                             parametros: dict | None = None) -> list[dict]:
    """Executa todos os conectores ATIVOS de uma area, passando parametros.

    Args:
        cliente_id: id do cliente.
        area: nome da area (vendas/suporte/...).
        pergunta: texto original para extrair parametros adicionais.
        parametros: dict opcional com parametros pre-extraidos (ex: id_cliente).

    Returns:
        Lista de dicts {conector, tipo, tool, args, resultado, erro}.
    """
    conectores = db.listar_conectores(cliente_id=cliente_id, area=area)
    resultados: list[dict] = []
    params = dict(parametros or {})

    for c in conectores:
        if not c.get("ativo"):
            continue
        config = _parse_config(c.get("config", "{}"))
        nome = c["nome"]
        tipo = c["tipo"]

        try:
            if tipo == "api":
                res = _executar_api(nome, config, params, pergunta)
            elif tipo == "mcp":
                res = _executar_mcp(nome, config, params, pergunta)
            elif tipo == "sql":
                res = _executar_sql(nome, config, params, pergunta)
            else:
                res = {"erro": f"Tipo de conector desconhecido: {tipo}"}

            resultados.append({
                "conector": nome,
                "tipo": tipo,
                **res,
            })
            # Atualiza heartbeat
            db.atualizar_heartbeat_conector(c["id"], status="online")
        except Exception as e:  # noqa: BLE001
            resultados.append({
                "conector": nome,
                "tipo": tipo,
                "erro": str(e),
            })
            db.atualizar_heartbeat_conector(c["id"], status="offline")

    return resultados


# --------------------------------------------------------------------------- #
# Executor: API REST                                                         #
# --------------------------------------------------------------------------- #

def _executar_api(nome: str, config: dict, params: dict, pergunta: str) -> dict:
    """Chama uma API REST externa."""
    url = config.get("url", "")
    if not url:
        return {"erro": "URL nao configurada"}

    method = config.get("method", "GET").upper()
    headers_str = config.get("headers", "{}")
    if isinstance(headers_str, str):
        headers = json.loads(headers_str) if headers_str.strip() else {}
    else:
        headers = dict(headers_str)

    # Substitui placeholders {param} nos valores
    url = _aplicar_params(url, params)
    headers = {k: _aplicar_params(v, params) for k, v in headers.items()}

    body = None
    if method in ("POST", "PUT", "PATCH"):
        body_template = config.get("body", "")
        if body_template:
            body = _aplicar_params(body_template, params).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=body, headers=headers, method=method,
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            try:
                data = json.loads(data)  # tenta parsear JSON
            except (json.JSONDecodeError, ValueError):
                pass  # mantem string
            return {"tool": f"api:{method}", "args": url, "resultado": data}
    except urllib.error.HTTPError as e:
        return {"erro": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"erro": f"Falha de conexao: {e.reason}"}


# --------------------------------------------------------------------------- #
# Executor: MCP (stdio)                                                      #
# --------------------------------------------------------------------------- #

def _executar_mcp(nome: str, config: dict, params: dict, pergunta: str) -> dict:
    """Chama uma ferramenta MCP via stdio (subprocesso)."""
    command = config.get("command", "")
    tool = config.get("tool", "")
    if not command or not tool:
        return {"erro": "Conector MCP sem command e/ou tool configurados"}

    args_tool = config.get("args", {})
    # Substitui placeholders nos args
    for k, v in args_tool.items():
        if isinstance(v, str):
            args_tool[k] = _aplicar_params(v, params)

    # Prepara request JSON-RPC 2.0
    request_id = 1
    req_json = json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": tool,
            "arguments": args_tool,
        },
    })

    try:
        proc = subprocess.run(
            command.split(),
            input=req_json + "\n",
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return {"erro": f"MCP stderr: {proc.stderr[:200]}"}
        resp = json.loads(proc.stdout.strip())
        if "error" in resp:
            return {"erro": resp["error"].get("message", str(resp["error"]))}
        content = resp.get("result", {}).get("content", [])
        texto = " ".join(
            c.get("text", "") for c in content if c.get("type") == "text"
        )
        return {"tool": f"mcp:{tool}", "args": args_tool, "resultado": texto}
    except subprocess.TimeoutExpired:
        return {"erro": "MCP timeout (30s)"}
    except FileNotFoundError:
        return {"erro": f"Comando MCP nao encontrado: {command}"}
    except json.JSONDecodeError as e:
        return {"erro": f"Resposta MCP invalida: {e}"}


# --------------------------------------------------------------------------- #
def _resolver_host_sql(host: str) -> str:
    """Se rodando em container e host for localhost, aponta pro host do Docker."""
    if os.path.exists("/.dockerenv") and host in ("127.0.0.1", "localhost", "0.0.0.0"):
        return "host.docker.internal"
    return host


# Executor: SQL View (PostgreSQL, MySQL, SQL Server)                            #
# --------------------------------------------------------------------------- #

def _executar_sql(nome: str, config: dict, params: dict, pergunta: str) -> dict:
    """Executa consulta SQL contra um banco configurado (PostgreSQL, MySQL ou SQL Server)."""
    driver = config.get("sql_driver", "postgresql")
    query = config.get("query", "")
    if not query:
        return {"erro": "SQL query nao configurada"}

    # Substitui placeholders na query
    query = _aplicar_params(query, params)

    # Tenta DSN direto primeiro
    dsn = config.get("dsn", "") or os.environ.get(config.get("dsn_env", ""), "")

    try:
        if driver == "postgresql":
            import psycopg
            if dsn:
                conn = psycopg.connect(dsn)
            else:
                host = _resolver_host_sql(config.get("sql_host", "127.0.0.1"))
                port = config.get("sql_port", "5432")
                conn = psycopg.connect(
                    host=host, port=port,
                    dbname=config.get("sql_db", ""),
                    user=config.get("sql_user", ""),
                    password=config.get("sql_pass", ""),
                )
            try:
                with conn.cursor() as cur:
                    cur.execute(query)
                    cols = [desc[0] for desc in cur.description] if cur.description else []
                    rows = [dict(zip(cols, r)) for r in cur.fetchmany(50)]
                conn.commit()
                return {"tool": "sql:query", "args": query, "resultado": rows}
            finally:
                conn.close()

        elif driver == "mysql":
            import pymysql
            host = _resolver_host_sql(config.get("sql_host", "127.0.0.1"))
            port = int(config.get("sql_port", "3306"))
            conn = pymysql.connect(
                host=host, port=port,
                database=config.get("sql_db", ""),
                user=config.get("sql_user", ""),
                password=config.get("sql_pass", ""),
                charset="utf8mb4",
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(query)
                    cols = [desc[0] for desc in cur.description] if cur.description else []
                    rows = [dict(zip(cols, r)) for r in cur.fetchmany(50)]
                conn.commit()
                return {"tool": "sql:query", "args": query, "resultado": rows}
            finally:
                conn.close()

        elif driver == "sqlserver":
            import pymssql
            host = _resolver_host_sql(config.get("sql_host", "127.0.0.1"))
            port = config.get("sql_port", "1433")
            conn = pymssql.connect(
                server=host, port=port,
                database=config.get("sql_db", ""),
                user=config.get("sql_user", ""),
                password=config.get("sql_pass", ""),
            )
            try:
                with conn.cursor(as_dict=True) as cur:
                    cur.execute(query)
                    rows = cur.fetchmany(50)
                conn.commit()
                return {"tool": "sql:query", "args": query, "resultado": rows}
            finally:
                conn.close()

        elif driver == "oracle":
            import oracledb
            oracledb.defaults.fetchmany = 50
            host = _resolver_host_sql(config.get("sql_host", "127.0.0.1"))
            port = config.get("sql_port", "1521")
            conn = oracledb.connect(
                host=host, port=port,
                service_name=config.get("sql_db", ""),
                user=config.get("sql_user", ""),
                password=config.get("sql_pass", ""),
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(query)
                    cols = [desc[0] for desc in cur.description] if cur.description else []
                    rows = [dict(zip(cols, r)) for r in cur.fetchmany(50)]
                conn.commit()
                return {"tool": "sql:query", "args": query, "resultado": rows}
            finally:
                conn.close()

        else:
            return {"erro": f"Driver SQL desconhecido: {driver}"}

    except ImportError as e:
        nome_driver = {"postgresql": "psycopg[binary]", "mysql": "pymysql", "sqlserver": "pymssql", "oracle": "oracledb"}
        return {"erro": f"Driver {driver} nao instalado. Instale: pip install {nome_driver.get(driver, driver)}"}
    except Exception as e:
        return {"erro": f"Erro SQL ({driver}): {e}"}


# --------------------------------------------------------------------------- #
# Helpers                                                                    #
# --------------------------------------------------------------------------- #

def _parse_config(raw: str | dict) -> dict:
    """Parseia config JSON para dict."""
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _aplicar_params(texto: str, params: dict) -> str:
    """Substitui {param} pelos valores do dict."""
    if not params:
        return texto

    def _repl(m):
        key = m.group(1)
        val = params.get(key)
        if val is None:
            return m.group(0)
        # URL-encode se parece URL
        if texto.startswith("http"):
            return urllib.parse.quote(str(val), safe="")
        return str(val)

    return re.sub(r"\{(\w+)\}", _repl, texto)
