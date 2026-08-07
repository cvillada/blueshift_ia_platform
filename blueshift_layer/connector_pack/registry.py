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
                             parametros: dict | None = None,
                             somente_ids: list[int] | None = None,
                             modelo: dict | None = None) -> list[dict]:
    """Executa conectores ATIVOS de uma area, passando parametros.

    Args:
        cliente_id: id do cliente.
        area: nome da area (vendas/suporte/...).
        pergunta: texto original para extrair parametros adicionais.
        parametros: dict opcional com parametros pre-extraidos (ex: id_cliente).
        somente_ids: roteamento por relevancia — executa apenas os ativos
            com id na lista. [] = nenhum (so RAG). None = todos (antigo).
        modelo: modelo usado pela CONSULTA INTELIGENTE (text-to-SQL). Quando
            informado e a query fixa do conector SQL volta vazia, uma
            pergunta de analise ("quem alugou mais e menos") dispara a
            geracao de SELECT sobre o schema real da fonte.

    Returns:
        Lista de dicts {conector, tipo, tool, args, resultado, erro}.
    """
    conectores = db.listar_conectores(cliente_id=cliente_id, area=area)
    resultados: list[dict] = []
    params = dict(parametros or {})

    for c in conectores:
        if not c.get("ativo"):
            continue
        if somente_ids is not None and c["id"] not in somente_ids:
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
                # Consulta inteligente DIRETA para perguntas de analise:
                # a query fixa nao faz sentido (placeholders virariam lixo
                # — ex: title='grafico de barras' quebra o SQL). O SELECT e
                # montado sobre o schema real. Fallback: query fixa.
                if (modelo and config.get("sql_analise", "1") != "0"
                        and _pergunta_analise(pergunta)):
                    res = _executar_sql_dinamico(nome, config, pergunta, modelo)
                    if not res.get("resultado"):
                        res = _executar_sql(nome, config, params, pergunta)
                else:
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
    """Chama uma ferramenta MCP via stdio ou SSE."""
    transport = config.get("transport", "stdio")
    tool = config.get("tool", "")
    if not tool:
        return {"erro": "Conector MCP sem tool configurada"}
    if transport == "sse":
        return _executar_mcp_sse(nome, config, params, pergunta)
    # stdio (padrao)
    command = config.get("command", "")
    if not command:
        return {"erro": "Conector MCP stdio sem command configurado"}

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
# Executor: MCP (SSE remoto)                                                  #
# --------------------------------------------------------------------------- #

def _executar_mcp_sse(nome: str, config: dict, params: dict, pergunta: str) -> dict:
    """Chama uma ferramenta MCP via SSE (servidor remoto HTTP)."""
    url = config.get("url", "")
    tool = config.get("tool", "")
    args_tool = dict(config.get("args", {}))
    if not url:
        return {"erro": "Conector MCP SSE sem URL configurada"}
    # Substitui placeholders nos args
    for k, v in args_tool.items():
        if isinstance(v, str):
            args_tool[k] = _aplicar_params(v, params)
    try:
        import asyncio
        from mcp.client.sse import sse_client
        from mcp import ClientSession
        async def _call():
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, args_tool)
                    return result
        r = asyncio.run(_call())
        if hasattr(r, "content"):
            return {"tool": f"mcp:{tool}", "args": args_tool, "resultado": r.content}
        return {"tool": f"mcp:{tool}", "args": args_tool, "resultado": str(r)}
    except Exception as e:
        return {"erro": f"Erro MCP SSE: {e}"}


# --------------------------------------------------------------------------- #
def _resolver_host_sql(host: str) -> str:
    """Se rodando em container e host for localhost, aponta pro host do Docker."""
    if os.path.exists("/.dockerenv") and host in ("127.0.0.1", "localhost", "0.0.0.0"):
        return "host.docker.internal"
    return host


# Executor: SQL View (PostgreSQL, MySQL, SQL Server)                            #
# --------------------------------------------------------------------------- #

def _conectar_sql(config: dict):
    """Abre conexao com o banco do conector (PostgreSQL, MySQL, SQL Server, Oracle).

    Levanta ImportError (driver ausente) ou Exception (falha de conexao).
    """
    driver = config.get("sql_driver", "postgresql")
    dsn = config.get("dsn", "") or os.environ.get(config.get("dsn_env", ""), "")
    host = _resolver_host_sql(config.get("sql_host", "127.0.0.1"))
    if driver == "postgresql":
        import psycopg
        if dsn:
            return psycopg.connect(dsn)
        return psycopg.connect(
            host=host, port=config.get("sql_port", "5432"),
            dbname=config.get("sql_db", ""),
            user=config.get("sql_user", ""),
            password=config.get("sql_pass", ""),
        )
    if driver == "mysql":
        import pymysql
        return pymysql.connect(
            host=host, port=int(config.get("sql_port", "3306")),
            database=config.get("sql_db", ""),
            user=config.get("sql_user", ""),
            password=config.get("sql_pass", ""),
            charset="utf8mb4",
        )
    if driver == "sqlserver":
        import pymssql
        return pymssql.connect(
            server=host, port=config.get("sql_port", "1433"),
            database=config.get("sql_db", ""),
            user=config.get("sql_user", ""),
            password=config.get("sql_pass", ""),
        )
    if driver == "oracle":
        import oracledb
        oracledb.defaults.fetchmany = 50
        return oracledb.connect(
            host=host, port=config.get("sql_port", "1521"),
            service_name=config.get("sql_db", ""),
            user=config.get("sql_user", ""),
            password=config.get("sql_pass", ""),
        )
    raise ValueError(f"Driver SQL desconhecido: {driver}")


def _rodar_select(conn, sql: str, driver: str, limite: int = 50) -> list[dict]:
    """Executa um SELECT e devolve as linhas (dicts), limitadas a `limite`."""
    kwargs = {"as_dict": True} if driver == "sqlserver" else {}
    with conn.cursor(**kwargs) as cur:
        cur.execute(sql)
        if driver == "sqlserver":
            return cur.fetchmany(limite)
        cols = [desc[0] for desc in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in cur.fetchmany(limite)]


def _executar_sql(nome: str, config: dict, params: dict, pergunta: str) -> dict:
    """Executa consulta SQL contra um banco configurado (PostgreSQL, MySQL ou SQL Server)."""
    driver = config.get("sql_driver", "postgresql")
    query = config.get("query", "")
    if not query:
        return {"erro": "SQL query nao configurada"}

    # Substitui placeholders na query
    query = _aplicar_params(query, params)

    try:
        conn = _conectar_sql(config)
        try:
            rows = _rodar_select(conn, query, driver)
            conn.commit()
            return {"tool": "sql:query", "args": query, "resultado": rows}
        finally:
            conn.close()
    except ImportError as e:
        nome_driver = {"postgresql": "psycopg[binary]", "mysql": "pymysql", "sqlserver": "pymssql", "oracle": "oracledb"}
        return {"erro": f"Driver {driver} nao instalado. Instale: pip install {nome_driver.get(driver, driver)}"}
    except Exception as e:
        return {"erro": f"Erro SQL ({driver}): {e}"}


# --------------------------------------------------------------------------- #
# Consulta inteligente (text-to-SQL) — analises sobre o schema real da fonte  #
# --------------------------------------------------------------------------- #

def _descobrir_schema(config: dict, max_tabelas: int = 15,
                      max_colunas: int = 20) -> str:
    """Descreve o schema da fonte (tabelas/views + colunas) para o LLM.

    Generico por driver: information_schema (MySQL/PostgreSQL/SQL Server)
    ou user_tab_columns (Oracle). Prioriza a tabela/view usada na query do
    conector. Nunca expoe dados — so estrutura.
    """
    driver = config.get("sql_driver", "postgresql")
    try:
        conn = _conectar_sql(config)
        try:
            if driver == "oracle":
                q = ("SELECT table_name, column_name, data_type FROM user_tab_columns "
                     "WHERE table_name NOT LIKE 'BIN$%' ORDER BY table_name, column_id")
            else:
                filtro = ("table_schema = 'public'" if driver == "postgresql"
                          else "table_schema = 'dbo'" if driver == "sqlserver"
                          else "table_schema = DATABASE()")
                q = (f"SELECT table_name, column_name, data_type FROM information_schema.columns "
                     f"WHERE {filtro} ORDER BY table_name, ordinal_position")
            kwargs = {"as_dict": True} if driver == "sqlserver" else {}
            with conn.cursor(**kwargs) as cur:
                cur.execute(q)
                rows = cur.fetchmany(800)
        finally:
            conn.close()
    except Exception as e:
        return f"(schema indisponivel: {e})"

    por_tabela: dict[str, list[str]] = {}
    for r in rows:
        t = str((r.get("table_name") or "") if isinstance(r, dict) else r[0])
        c = str((r.get("column_name") or "") if isinstance(r, dict) else r[1])
        ty = str((r.get("data_type") or "") if isinstance(r, dict) else r[2])
        if t:
            por_tabela.setdefault(t, []).append(f"{c} {ty}")

    # Prioriza a tabela/view da query do conector
    query = config.get("query", "")
    from_ = re.findall(r"from\s+([\w.\"`\[\]]+)", query.lower()) if query else []
    prioridade = [f.split(".")[-1].strip('"`[]') for f in from_] if from_ else []
    nomes = sorted(por_tabela.keys(), key=lambda t: (t not in prioridade, t))[:max_tabelas]
    blocos = []
    for t in nomes:
        colunas = por_tabela[t][:max_colunas]
        blocos.append(f"{t}({', '.join(colunas)})")
    return "\n".join(blocos) or "(schema vazio)"


def _validar_sql_gerado(sql: str) -> list[str] | None:
    """Valida SQL gerado por IA: uma ou mais consultas SELECT de leitura.

    Divide por ';' e valida CADA statement (somente SELECT, sem DDL/DML,
    comentarios, UNION, INTO...). Cada um ganha LIMIT 50 quando o dialeto
    nao trouxe. Retorna a lista de SQLs validados, ou None se qualquer
    statement falhar (ex: "mais e menos" gera 2 SELECTs legitimos).
    """
    if not sql:
        return None
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    if not statements:
        return None
    validados: list[str] = []
    for st in statements:
        limpo = st.rstrip().strip()
        low = limpo.lower()
        if not low.startswith("select"):
            return None
        proibido = ("--", "/*", "drop ", "insert ", "update ", "delete ",
                    "alter ", "create ", "truncate ", "grant ", "revoke ",
                    "exec ", "execute ", "union ", "into ", "call ", "replace ")
        for p in proibido:
            if p in low:
                return None
        if not any(k in low for k in ("limit", "fetch first", "rownum")):
            # SQL Server usa TOP logo apos o SELECT (nao adiciona LIMIT)
            if " top " not in (" " + limpo[:24].lower()):
                limpo += " LIMIT 50"
        validados.append(limpo)
    return validados


def _gerar_sql_ia(pergunta: str, schema: str, modelo: dict,
                  dialeto: str = "MySQL") -> str | None:
    """Pede ao LLM para montar o SELECT sobre o schema real (so estrutura)."""
    from ..portal import llm_client
    mensagens = [
        {"role": "system", "content": (
            "Voce monta consultas SQL de LEITURA (SELECT) sobre o schema abaixo. "
            f"O banco e {dialeto}. Responda APENAS com o SQL: sem markdown, sem "
            "explicacoes, sem ponto e virgula no final. Use apenas tabelas e "
            "colunas existentes no schema. Se a pergunta pedir ranking/limite, "
            "use LIMIT (ou TOP no SQL Server).")},
        {"role": "user", "content": f"SCHEMA:\n{schema}\n\nPERGUNTA: {pergunta}\n\nSQL:"},
    ]
    out = llm_client.chat(modelo, mensagens, max_tokens=300, temperatura=0.0)
    if not out.get("ok"):
        return None
    texto = (out.get("content") or "").strip()
    m = re.search(r"```(?:sql)?\s*(.*?)```", texto, re.DOTALL)
    if m:
        texto = m.group(1).strip()
    return texto or None


_MARCADORES_ANALISE = (
    " mais", " menos", " quantos", " quantas", " top ", " ranking", " maior",
    " menor", " media", " média", " total", " soma", " count(", " sum(",
    " por categoria", " agrupad", " grupo", " group by", " resumo", " cada",
    " lista de", " listar", " ordenad", " classifica", " estatistica",
    " estatística", " compar", " distribui", " percentual",
)


def _pergunta_analise(pergunta: str) -> bool:
    """True se a pergunta pede analise/agregacao (gatilho da consulta inteligente)."""
    p = " " + pergunta.lower().strip()
    return any(m in p for m in _MARCADORES_ANALISE)


def _executar_sql_dinamico(nome: str, config: dict, pergunta: str,
                           modelo: dict) -> dict:
    """Consulta inteligente: schema real -> SQL por IA -> validacao -> execucao."""
    driver = config.get("sql_driver", "postgresql")
    schema = _descobrir_schema(config)
    if not schema or schema.startswith("(schema indisponivel"):
        return {"erro": "Schema da fonte indisponivel para consulta inteligente"}
    dialeto = {"postgresql": "PostgreSQL", "mysql": "MySQL",
               "sqlserver": "SQL Server", "oracle": "Oracle"}.get(driver, driver)
    sql = _gerar_sql_ia(pergunta, schema, modelo, dialeto)
    if not sql:
        return {"erro": "Nao foi possivel montar a consulta"}
    sqls = _validar_sql_gerado(sql)
    if not sqls:
        return {"erro": "Consulta gerada rejeitada pela validacao de seguranca"}
    try:
        conn = _conectar_sql(config)
        try:
            blocos = []
            for s in sqls:
                rows = _rodar_select(conn, s, driver)
                blocos.append({"sql": s, "linhas": rows})
            conn.commit()
            return {"tool": "sql:analise", "args": sqls, "resultado": blocos}
        finally:
            conn.close()
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
