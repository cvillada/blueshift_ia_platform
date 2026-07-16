"""Banco SQLite local do Portal (fake, 100% offline) da BlueShift.

Centraliza TODO acesso a dados do portal em um unico ponto (padrao DRY
da plataforma). Nenhuma outra parte do portal abre conexao direta com o
SQLite — tudo passa por aqui.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from datetime import datetime, timezone

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "portal.db"


def db_path() -> Path:
    """Caminho do banco (configuravel via env BLUESHIFT_PORTAL_DB)."""
    import os

    env = os.getenv("BLUESHIFT_PORTAL_DB")
    return Path(env) if env else DEFAULT_DB_PATH


@contextmanager
def get_conn():
    """Context manager que entrega uma conexao SQLite (row_factory=dict-like)."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    """Cria as tabelas se nao existirem."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clientes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo      TEXT UNIQUE NOT NULL,
                nome        TEXT NOT NULL,
                empresa     TEXT,
                email       TEXT,
                licenca     TEXT NOT NULL DEFAULT 'anual_por_empresa',
                status      TEXT NOT NULL DEFAULT 'ativo',   -- ativo|suspenso|expirado
                criado_em   TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                nome        TEXT NOT NULL,
                login       TEXT NOT NULL,
                senha       TEXT NOT NULL,
                papel       TEXT NOT NULL DEFAULT 'usuario',  -- admin|gestor|usuario|sistema
                area        TEXT,                             -- vendas|suporte|financeiro|rh|operacoes
                ativo       INTEGER NOT NULL DEFAULT 1,
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agentes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                nome        TEXT NOT NULL,
                area        TEXT,
                modelo      TEXT NOT NULL DEFAULT 'finetuned-v1',
                skills      TEXT,                              -- CSV de skills
                conectores  TEXT,                              -- CSV de conectores MCP
                status      TEXT NOT NULL DEFAULT 'ativo',    -- ativo|pausado
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conectores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                nome        TEXT NOT NULL,                     -- erp|crm|rh
                tipo        TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'online',   -- online|offline|degradado
                ultimo_heartbeat TEXT
            );

            CREATE TABLE IF NOT EXISTS health (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                container   TEXT NOT NULL DEFAULT 'saudavel',  -- saudavel|degradado|parado
                modelo_local TEXT NOT NULL DEFAULT 'ok',       -- ok|sobrecarregado|indisponivel
                latencia_ms INTEGER NOT NULL DEFAULT 0,
                tokens_hoje INTEGER NOT NULL DEFAULT 0,
                erros_24h   INTEGER NOT NULL DEFAULT 0,
                atualizado_em TEXT NOT NULL
            );
            """
        )


# ---------------------------------------------------------------------------
# Helpers de leitura/escrita (pontos unicos de controle)
# ---------------------------------------------------------------------------

def _row(conn, sql, params=()):
    cur = conn.execute(sql, params)
    return cur.fetchone()


def _rows(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


# --- Clientes ---------------------------------------------------------------

def listar_clientes() -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in _rows(conn, "SELECT * FROM clientes ORDER BY id")]


def buscar_cliente(cliente_id: int) -> dict | None:
    with get_conn() as conn:
        r = _row(conn, "SELECT * FROM clientes WHERE id=?", (cliente_id,))
        return dict(r) if r else None


def criar_cliente(codigo, nome, empresa="", email="", licenca="anual_por_empresa") -> int:
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO clientes (codigo, nome, empresa, email, licenca, status, criado_em, atualizado_em)
               VALUES (?,?,?,?,?, 'ativo', ?, ?)""",
            (codigo, nome, empresa, email, licenca, ts, ts),
        )
        cid = cur.lastrowid
        # seed de registros filhos para o monitoramento funcionar de imediato
        conn.execute(
            "INSERT INTO conectores (cliente_id, nome, tipo, status, ultimo_heartbeat) VALUES (?, 'erp', 'mcp', 'online', ?)",
            (cid, ts),
        )
        conn.execute(
            "INSERT INTO conectores (cliente_id, nome, tipo, status, ultimo_heartbeat) VALUES (?, 'crm', 'mcp', 'online', ?)",
            (cid, ts),
        )
        conn.execute(
            "INSERT INTO conectores (cliente_id, nome, tipo, status, ultimo_heartbeat) VALUES (?, 'rh', 'mcp', 'online', ?)",
            (cid, ts),
        )
        conn.execute(
            """INSERT INTO health (cliente_id, container, modelo_local, latencia_ms, tokens_hoje, erros_24h, atualizado_em)
               VALUES (?, 'saudavel', 'ok', 0, 0, 0, ?)""",
            (cid, ts),
        )
        return cid


def atualizar_cliente(cliente_id, **campos) -> None:
    campos["atualizado_em"] = now_iso()
    cols = ", ".join(f"{k}=?" for k in campos)
    with get_conn() as conn:
        conn.execute(f"UPDATE clientes SET {cols} WHERE id=?", list(campos.values()) + [cliente_id])


# --- Usuarios ---------------------------------------------------------------

def listar_usuarios(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM usuarios WHERE cliente_id=? ORDER BY id", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM usuarios ORDER BY id")]


def criar_usuario(cliente_id, nome, login, senha, papel="usuario", area="") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO usuarios (cliente_id, nome, login, senha, papel, area, ativo, criado_em)
               VALUES (?,?,?,?,?,?,1,?)""",
            (cliente_id, nome, login, senha, papel, area, now_iso()),
        )
        return cur.lastrowid


def autenticar(login: str, senha: str) -> dict | None:
    with get_conn() as conn:
        r = _row(conn, "SELECT * FROM usuarios WHERE login=? AND ativo=1", (login,))
        if r and r["senha"] == senha:
            return dict(r)
        return None


# --- Agentes ----------------------------------------------------------------

def listar_agentes(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM agentes WHERE cliente_id=? ORDER BY id", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM agentes ORDER BY id")]


def criar_agente(cliente_id, nome, area="", modelo="finetuned-v1", skills="", conectores="") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO agentes (cliente_id, nome, area, modelo, skills, conectores, status, criado_em)
               VALUES (?,?,?,?,?,?, 'ativo', ?)""",
            (cliente_id, nome, area, modelo, skills, conectores, now_iso()),
        )
        return cur.lastrowid


# --- Conectores / Health ----------------------------------------------------

def listar_conectores(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM conectores WHERE cliente_id=? ORDER BY id", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM conectores ORDER BY id")]


def buscar_health(cliente_id: int) -> dict | None:
    with get_conn() as conn:
        r = _row(conn, "SELECT * FROM health WHERE cliente_id=? ORDER BY atualizado_em DESC LIMIT 1",
                 (cliente_id,))
        return dict(r) if r else None


def atualizar_health(cliente_id, **campos) -> None:
    campos["atualizado_em"] = now_iso()
    with get_conn() as conn:
        if buscar_health(cliente_id):
            cols = ", ".join(f"{k}=?" for k in campos)
            conn.execute(f"UPDATE health SET {cols} WHERE cliente_id=?", list(campos.values()) + [cliente_id])
        else:
            colsn = ", ".join(campos.keys())
            ph = ", ".join("?" for _ in campos)
            conn.execute(f"INSERT INTO health (cliente_id, {colsn}) VALUES (?, {ph})",
                         [cliente_id] + list(campos.values()))


# --- Seed demo --------------------------------------------------------------

def seed_demo() -> None:
    """Popula dados de demonstracao (idempotente)."""
    with get_conn() as conn:
        ja_tem = _row(conn, "SELECT COUNT(*) AS n FROM clientes")
        if ja_tem["n"] > 0:
            return
    cid = criar_cliente("porto", "Porto Seguros (Piloto)", "Porto Seguro S/A", "ti@porto.com.br")
    criar_usuario(cid, "Administrador BlueShift", "admin", "admin123", "admin", "operacoes")
    criar_usuario(cid, "Gestor Vendas", "gestor", "gestor123", "gestor", "vendas")
    criar_agente(cid, "Agente Vendas", "vendas", "finetuned-v1", "vendas,suporte", "erp,crm")
    criar_agente(cid, "Agente Suporte", "suporte", "finetuned-v1", "suporte", "crm")
    atualizar_health(cid, container="saudavel", modelo_local="ok", latencia_ms=42, tokens_hoje=18320, erros_24h=0)
