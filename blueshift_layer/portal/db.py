"""Banco SQLite local do Portal (fake, 100% offline) da BlueShift.

Centraliza TODO acesso a dados do portal em um unico ponto (padrao DRY
da plataforma). Nenhuma outra parte do portal abre conexao direta com o
SQLite — tudo passa por aqui.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import string
from contextlib import contextmanager
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────
# Hash de senha (scrypt — nativo, sem deps)
# ──────────────────────────────────────────
_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1


def _hash_senha(senha: str) -> str:
    """Retorna 'salt_hex$hash_hex' usando scrypt."""
    salt = os.urandom(16)
    h = hashlib.scrypt(senha.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return salt.hex() + "$" + h.hex()


def _verificar_senha(senha: str, armazenado: str) -> bool:
    """Verifica senha contra hash scrypt ou plaintext legado."""
    if "$" not in armazenado:
        # ── legado: plaintext (migra na proxima autenticacao bem-sucedida) ──
        return hmac.compare_digest(senha, armazenado)
    salt_hex, hash_hex = armazenado.split("$", 1)
    salt = bytes.fromhex(salt_hex)
    h = hashlib.scrypt(senha.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return hmac.compare_digest(h.hex(), hash_hex)

from datetime import datetime, timedelta, timezone

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
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
                modelo      TEXT NOT NULL DEFAULT 'bonsai-8b',  -- nome do modelo (ref. modelo_id)
                modelo_id   INTEGER,                              -- FK opcional -> modelos(id)
                modelo_secundario_id INTEGER,                    -- FK opcional -> modelos(id) usado em fallback
                skills      TEXT,                              -- CSV de skills
                conectores  TEXT,                              -- CSV de conectores MCP
                status      TEXT NOT NULL DEFAULT 'ativo',    -- ativo|pausado
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conectores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                area        TEXT NOT NULL DEFAULT '',              -- vendas|suporte|financeiro|rh|operacoes
                nome        TEXT NOT NULL,                         -- nome do conector
                tipo        TEXT NOT NULL DEFAULT 'api',           -- api|mcp|sql
                config      TEXT NOT NULL DEFAULT '{}',            -- JSON: url, headers, query, dsn, etc
                status      TEXT NOT NULL DEFAULT 'online',       -- online|offline|degradado
                ativo       INTEGER NOT NULL DEFAULT 1,
                ultimo_heartbeat TEXT,
                criado_em   TEXT NOT NULL
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

            CREATE TABLE IF NOT EXISTS uso_tokens (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                agente_id   INTEGER,                          -- agente usado (se houver)
                modelo      TEXT NOT NULL,                    -- nome do modelo efetivamente usado
                modelo_fallback INTEGER NOT NULL DEFAULT 0,   -- 1 se usou modelo secundario
                quem        TEXT NOT NULL DEFAULT 'usuario',  -- login OU 'sistema:<canal>' (API/canal)
                origem      TEXT NOT NULL DEFAULT 'chat',     -- chat | api | teste
                prompt_tokens   INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens     INTEGER NOT NULL DEFAULT 0,
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contratos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                valor_anual REAL NOT NULL DEFAULT 0,           -- valor do contrato anual (info, fora da plataforma)
                moeda       TEXT NOT NULL DEFAULT 'BRL',
                inicio      TEXT,                              -- YYYY-MM-DD
                fim         TEXT,                              -- YYYY-MM-DD
                status      TEXT NOT NULL DEFAULT 'ativo',    -- ativo|suspenso|expirado (do contrato, nao pagamento)
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skills (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nome        TEXT NOT NULL UNIQUE,
                descricao   TEXT NOT NULL DEFAULT '',
                body        TEXT NOT NULL DEFAULT '',
                version     TEXT NOT NULL DEFAULT '1.0.0',
                criado_em   TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tracing (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pergunta    TEXT NOT NULL,
                params      TEXT NOT NULL DEFAULT '{}',
                conectores  TEXT NOT NULL DEFAULT '[]',
                rag         TEXT NOT NULL DEFAULT '[]',
                modelo      TEXT NOT NULL DEFAULT '',
                modelo_fallback INTEGER NOT NULL DEFAULT 0,
                tokens      TEXT NOT NULL DEFAULT '{}',
                resposta    TEXT NOT NULL DEFAULT '',
                tempo_ms    INTEGER NOT NULL DEFAULT 0,
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auditoria (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario     TEXT NOT NULL,                     -- login
                papel       TEXT,                              -- admin|gestor|usuario|sistema
                acao        TEXT NOT NULL,                     -- ex: criar_cliente, login, marcar_paga
                alvo        TEXT,                              -- id/descricao do objeto afetado
                cliente_id  INTEGER,                           -- contexto de cliente (se houver)
                ip          TEXT,
                detalhe     TEXT,
                criado_em   TEXT NOT NULL
            );

            -- Indices para performance
            CREATE INDEX IF NOT EXISTS idx_auditoria_cliente ON auditoria(cliente_id);
            CREATE INDEX IF NOT EXISTS idx_auditoria_criado ON auditoria(criado_em);

            CREATE TABLE IF NOT EXISTS feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id    INTEGER,
                agente_id   INTEGER,
                pergunta    TEXT NOT NULL,
                resposta    TEXT NOT NULL DEFAULT '',
                feedback    TEXT NOT NULL,           -- 'util', 'nao_util'
                tipo        TEXT NOT NULL DEFAULT 'manual',  -- 'manual', 'implicito', 'api'
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS metricas_diarias (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                data        TEXT NOT NULL,           -- '2026-07-24'
                agente_id   INTEGER,
                modelo      TEXT NOT NULL DEFAULT '',
                chamadas    INTEGER NOT NULL DEFAULT 0,
                tokens_total INTEGER NOT NULL DEFAULT 0,
                latencia_p50 INTEGER NOT NULL DEFAULT 0,
                latencia_p95 INTEGER NOT NULL DEFAULT 0,
                erros       INTEGER NOT NULL DEFAULT 0,
                feedback_util   INTEGER NOT NULL DEFAULT 0,
                feedback_total  INTEGER NOT NULL DEFAULT 0,
                criado_em   TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_metrica_dia
                ON metricas_diarias(data, agente_id, modelo);

            CREATE TABLE IF NOT EXISTS alertas_config (
                chave       TEXT PRIMARY KEY,
                valor       REAL NOT NULL,
                descricao   TEXT NOT NULL DEFAULT ''
            );
            INSERT OR IGNORE INTO alertas_config (chave, valor, descricao) VALUES
                ('taxa_acerto_min', 70.0, 'Taxa de acerto minima (%)'),
                ('latencia_max', 1000, 'Latencia maxima (ms)'),
                ('erros_max', 5, 'Erros maximos por dia');

            CREATE TABLE IF NOT EXISTS custos_modelo (
                modelo      TEXT PRIMARY KEY,
                preco_input REAL NOT NULL DEFAULT 0.15,
                preco_output REAL NOT NULL DEFAULT 0.60,
                atualizado_em TEXT NOT NULL
            );

            INSERT OR IGNORE INTO custos_modelo (modelo, preco_input, preco_output, atualizado_em)
            VALUES
              ("hermes-3-llama-3.1-8b", 0.15, 0.60, ""),
              ("bonsai-8b", 0.10, 0.40, ""),
              ("qwen2.5-7b", 0.12, 0.50, "");

            CREATE TABLE IF NOT EXISTS memories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                usuario     TEXT NOT NULL,                     -- login do dono da memoria
                tipo        TEXT NOT NULL DEFAULT 'conversa',  -- conversa|preferencia|contexto
                conteudo    TEXT NOT NULL,
                vetor       TEXT,                              -- JSON do embedding (TF-IDF local)
                criado_em   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memories_cliente ON memories(cliente_id);
            CREATE INDEX IF NOT EXISTS idx_memories_criado ON memories(criado_em);

            CREATE TABLE IF NOT EXISTS knowledge (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                area        TEXT NOT NULL DEFAULT '',              -- vendas|suporte|financeiro|rh|operacoes
                titulo      TEXT NOT NULL,
                categoria   TEXT NOT NULL DEFAULT 'manual',    -- manual|politica|base_conhecimento|contrato
                fonte       TEXT NOT NULL DEFAULT 'manual',    -- manual|csv|push|conector:<nome>
                conteudo    TEXT NOT NULL,
                vetor       TEXT,                              -- JSON do embedding (TF-IDF local)
                acessos     INTEGER NOT NULL DEFAULT 0,
                ultimo_acesso TEXT,
                criado_em   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_knowledge_cliente ON knowledge(cliente_id);
            CREATE INDEX IF NOT EXISTS idx_knowledge_area ON knowledge(area);
            CREATE INDEX IF NOT EXISTS idx_knowledge_criado ON knowledge(criado_em);

            CREATE TABLE IF NOT EXISTS modelos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                nome        TEXT NOT NULL,                     -- ex: bonsai-8b
                base_url    TEXT NOT NULL,                     -- ex: http://127.0.0.1:1234
                modelo      TEXT NOT NULL,                     -- ex: bonsai-8b
                tipo        TEXT NOT NULL DEFAULT 'local',     -- local (LM Studio) | hibrido
                api_key     TEXT,                              -- opcional
                ativo       INTEGER NOT NULL DEFAULT 1,
                preco_input REAL NOT NULL DEFAULT 0.0,
                preco_output REAL NOT NULL DEFAULT 0.0,
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                chave       TEXT NOT NULL UNIQUE,              -- ex: bs_live_xxxx
                descricao   TEXT,
                ativo       INTEGER NOT NULL DEFAULT 1,
                criado_em   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS canais (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
                nome        TEXT NOT NULL,                     -- ex: Webhook Vendas
                tipo        TEXT NOT NULL DEFAULT 'api',       -- api | webhook
                agente_id   INTEGER,                           -- FK agentes(id); canal aponta p/ 1 agente
                token       TEXT NOT NULL UNIQUE,              -- bs_chan_xxxx (auth do canal)
                webhook_url TEXT,                              -- URL de saida (POST da resposta)
                webhook_headers TEXT DEFAULT '{}',             -- headers extras (JSON) p/ o webhook de saida
                ativo       INTEGER NOT NULL DEFAULT 1,
                criado_em   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sso_config (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ativo       INTEGER NOT NULL DEFAULT 0,
                dev_mode    INTEGER NOT NULL DEFAULT 0,
                issuer      TEXT,
                client_id   TEXT,
                client_secret TEXT,
                redirect_uri TEXT,
                dominio_admin TEXT,
                auto_criar  INTEGER NOT NULL DEFAULT 0,
                atualizado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lgpd_config (
                chave       TEXT PRIMARY KEY,
                valor       TEXT NOT NULL DEFAULT ''
            );
            INSERT OR IGNORE INTO lgpd_config (chave, valor) VALUES
                ('anonimizar_llm', '0'),
                ('anonimizar_rag', '0'),
                ('mask_cpf', '1'),
                ('mask_email', '1'),
                ('mask_telefone', '1'),
                ('mask_nome', '0'),
                ('mask_endereco', '0'),
                ('mask_cnpj', '0'),
                ('aviso_privacidade', '0'),
                ('aviso_texto', 'Esta plataforma processa dados corporativos para fins de inteligencia artificial. Consulte sua politica de privacidade interna para detalhes.'),
                ('finalidade_conector', '0'),
                ('retencao_auto', '0'),
                ('retencao_auditoria', '90'),
                ('retencao_tracing', '180'),
                ('retencao_memorias', '365');
            CREATE TABLE IF NOT EXISTS teste_ab (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                pergunta        TEXT NOT NULL,
                resposta_a      TEXT NOT NULL DEFAULT '',
                resposta_b      TEXT NOT NULL DEFAULT '',
                modelo_a        TEXT NOT NULL DEFAULT '',
                modelo_b        TEXT NOT NULL DEFAULT '',
                voto            TEXT NOT NULL DEFAULT 'EMPATE',  -- A | B | EMPATE
                justificativa   TEXT NOT NULL DEFAULT '',
                modelo_juiz     TEXT NOT NULL DEFAULT '',
                criado_por      TEXT NOT NULL DEFAULT '',
                criado_em       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_teste_ab_criado ON teste_ab(criado_em);
            """
        )
    # Migração idempotente: garante colunas novas em DBs já existentes
    # (CREATE TABLE IF NOT EXISTS não altera tabelas já criadas).
    _migrar_colunas()


def _migrar_colunas() -> None:
    """Adiciona colunas novas a tabelas existentes sem destruir dados.

    Idempotente: checa PRAGMA table_info antes de cada ALTER TABLE. Cobre
    tanto a coluna recém-adicionada (modelo_secundario_id) quanto colunas
    que o schema do código já declara há tempo mas que podem faltar em DBs
    seedados por versões anteriores (ex.: modelo_id).

    Também limpa tabelas obsoletas (faturas foi substituída por uso_tokens
    + contratos, que são criadas via CREATE TABLE IF NOT EXISTS).
    """
    # Limpeza de tabelas obsoletas
    with get_conn() as conn:
        conn.execute("DROP TABLE IF EXISTS faturas")
        conn.execute("DROP TABLE IF EXISTS chamados")
    # Migração de colunas
    _ESPERADO = {
        "agentes": [
            ("modelo_id", "INTEGER"),
            ("modelo_secundario_id", "INTEGER"),
            ("lgpd_ativado", "INTEGER DEFAULT 1"),
        ],
        "modelos": [
            ("max_tokens", "INTEGER"),
        ],
        "conectores": [
            ("area", "TEXT DEFAULT ''"),
            ("config", "TEXT DEFAULT '{}'"),
            ("ativo", "INTEGER DEFAULT 1"),
            ("criado_em", "TEXT"),
            ("finalidade", "TEXT DEFAULT ''"),
        ],
        "memories": [
            ("area", "TEXT DEFAULT ''"),
        ],
        "knowledge": [
            ("area", "TEXT DEFAULT ''"),
            ("fonte", "TEXT DEFAULT 'manual'"),
            ("acessos", "INTEGER DEFAULT 0"),
            ("ultimo_acesso", "TEXT"),
        ],
        "tracing": [
            ("agente_id", "INTEGER"),
        ],
        "canais": [
            ("webhook_headers", "TEXT DEFAULT '{}'"),
        ],
    }
    with get_conn() as conn:
        for tabela, cols in _ESPERADO.items():
            existentes = {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}
            for coluna, tipo in cols:
                if coluna not in existentes:
                    conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")


# ---------------------------------------------------------------------------
# Helpers de leitura/escrita (pontos unicos de controle)

def _row(conn, sql, params=()):
    cur = conn.execute(sql, params)
    return cur.fetchone()


def _rows(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def _one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


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
        _seed_conectores_demo(conn, cid, ts)
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
    senha_hash = _hash_senha(senha)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO usuarios (cliente_id, nome, login, senha, papel, area, ativo, criado_em)
               VALUES (?,?,?,?,?,?,1,?)""",
            (cliente_id, nome, login, senha_hash, papel, area, now_iso()),
        )
        return cur.lastrowid


def buscar_usuario(uid: int) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        return dict(r) if r else None


def atualizar_usuario(uid: int, **campos) -> None:
    cols = ", ".join(f"{k}=?" for k in campos)
    with get_conn() as conn:
        conn.execute(f"UPDATE usuarios SET {cols} WHERE id=?", (*campos.values(), uid))


def existe_admin() -> bool:
    """True se existe pelo menos um usuario com papel admin no sistema."""
    with get_conn() as conn:
        r = _row(conn, "SELECT COUNT(*) AS n FROM usuarios WHERE papel='admin'")
        return (r["n"] or 0) > 0


def autenticar(login: str, senha: str) -> dict | None:
    with get_conn() as conn:
        r = _row(conn, "SELECT * FROM usuarios WHERE login=? AND ativo=1", (login,))
        if r and _verificar_senha(senha, r["senha"]):
            u = dict(r)
            # ── migracao: se era plaintext, atualiza para hash ──
            if "$" not in r["senha"]:
                conn.execute("UPDATE usuarios SET senha=? WHERE id=?",
                             (_hash_senha(senha), r["id"]))
            return u
        return None


# --- Agentes ----------------------------------------------------------------

def listar_agentes(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM agentes WHERE cliente_id=? ORDER BY id", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM agentes ORDER BY id")]


def buscar_agente(aid: int) -> dict | None:
    with get_conn() as conn:
        row = _one(conn, "SELECT * FROM agentes WHERE id=?", (aid,))
        return dict(row) if row else None


def criar_agente(cliente_id, nome, area="", modelo="bonsai-8b", skills="", conectores="",
                 modelo_id=None, modelo_secundario_id=None,
                 lgpd_ativado: int = 1) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO agentes (cliente_id, nome, area, modelo, modelo_id, modelo_secundario_id, skills, conectores, lgpd_ativado, status, criado_em)
               VALUES (?,?,?,?,?,?,?,?,?, 'ativo', ?)""",
            (cliente_id, nome, area, modelo, modelo_id, modelo_secundario_id, skills, conectores, lgpd_ativado, now_iso()),
        )
        return cur.lastrowid


def atualizar_agente(aid: int, **campos) -> None:
    """Atualiza campos do agente (nome, area, modelo_id, modelo_secundario_id, skills, conectores, status)."""
    cols = ", ".join(f"{k}=?" for k in campos)
    with get_conn() as conn:
        conn.execute(f"UPDATE agentes SET {cols} WHERE id=?", list(campos.values()) + [aid])


def deletar_agente(aid: int) -> None:
    """Remove um agente pelo ID."""
    with get_conn() as conn:
        conn.execute("DELETE FROM agentes WHERE id=?", (aid,))


# --- Conectores (fontes externas configuráveis: API/MCP/SQL) ----------------

_AREAS = ["vendas", "suporte", "financeiro", "rh", "operacoes"]


def listar_areas() -> list[str]:
    """Retorna lista de areas configuradas via env BLUESHIFT_AREAS ou padrao."""
    raw = os.environ.get("BLUESHIFT_AREAS", "").strip()
    if raw:
        return [a.strip() for a in raw.split(",") if a.strip()]
    return list(_AREAS)


def criar_conector(cliente_id, nome, tipo="api", area="", config=None, status="online", finalidade="") -> int:
    """Cadastra uma nova fonte externa de dados por cliente + área."""
    ts = now_iso()
    cfg_json = json.dumps(config or {})
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO conectores (cliente_id, area, nome, tipo, config, finalidade, status, ativo, ultimo_heartbeat, criado_em)
               VALUES (?,?,?,?,?,?,?,1,?,?)""",
            (cliente_id, area, nome, tipo, cfg_json, finalidade, status, ts, ts),
        )
        return cur.lastrowid


def listar_conectores(cliente_id: int | None = None, area: str | None = None) -> list[dict]:
    """Lista conectores, opcionalmente filtrados por cliente e/ou área."""
    sql = "SELECT * FROM conectores WHERE 1=1"
    params = []
    if cliente_id is not None:
        sql += " AND cliente_id=?"
        params.append(cliente_id)
    if area:
        sql += " AND area=?"
        params.append(area)
    sql += " ORDER BY area, nome"
    with get_conn() as conn:
        return [dict(r) for r in _rows(conn, sql, params)]


def buscar_conector(cid: int) -> dict | None:
    """Retorna um conector pelo ID."""
    with get_conn() as conn:
        row = _one(conn, "SELECT * FROM conectores WHERE id=?", (cid,))
        return dict(row) if row else None


def atualizar_conector(cid: int, **campos) -> None:
    """Atualiza campos do conector (nome, tipo, config, area, status, ativo)."""
    if "config" in campos and isinstance(campos["config"], dict):
        campos["config"] = json.dumps(campos["config"])
    cols = ", ".join(f"{k}=?" for k in campos)
    with get_conn() as conn:
        conn.execute(f"UPDATE conectores SET {cols} WHERE id=?", list(campos.values()) + [cid])


def deletar_conector(cid: int) -> None:
    """Remove um conector pelo ID."""
    with get_conn() as conn:
        conn.execute("DELETE FROM conectores WHERE id=?", (cid,))


def listar_areas_com_conectores(cliente_id: int) -> list[str]:
    """Retorna as áreas que têm pelo menos um conector cadastrado."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT area FROM conectores WHERE cliente_id=? AND ativo=1 AND area!='' ORDER BY area",
            (cliente_id,),
        ).fetchall()
    return [r[0] for r in rows]


# --- Skills (armazenadas no banco para persistencia via volume) ---------------


def salvar_skill_db(nome: str, descricao: str, body: str, version: str = "1.0.0") -> None:
    """Salva ou atualiza uma skill no banco de dados (volume persistente)."""
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id FROM skills WHERE nome=?",
            (nome,),
        )
        row = cur.fetchone()
        if row:
            conn.execute(
                "UPDATE skills SET descricao=?, body=?, version=?, atualizado_em=? WHERE nome=?",
                (descricao, body, version, ts, nome),
            )
        else:
            conn.execute(
                "INSERT INTO skills (nome, descricao, body, version, criado_em, atualizado_em) VALUES (?,?,?,?,?,?)",
                (nome, descricao, body, version, ts, ts),
            )


def carregar_skill_db(nome: str) -> dict | None:
    """Carrega uma skill do banco. Retorna None se nao existir."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT nome, descricao, body, version FROM skills WHERE nome=?",
            (nome,),
        ).fetchone()
    if row:
        return {"name": row[0], "description": row[1], "body": row[2], "version": row[3],
                "fonte": "banco"}
    return None


def deletar_skill_db(nome: str) -> None:
    """Remove uma skill do banco de dados."""
    with get_conn() as conn:
        conn.execute("DELETE FROM skills WHERE nome=?", (nome,))


def listar_skills_db() -> list[dict]:
    """Lista todas as skills salvas no banco."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT nome, descricao, body, version FROM skills ORDER BY nome",
        ).fetchall()
    return [{"name": r[0], "description": r[1], "body": r[2], "version": r[3],
             "fonte": "banco"} for r in rows]


# --- Tracing (rastreio detalhado de execucao do agente) ----------------------


def salvar_trace(pergunta: str, params: dict, conectores: list,
                 rag: list, modelo: str, modelo_fallback: bool,
                 tokens: dict, resposta: str, tempo_ms: int,
                 agente_id: int | None = None) -> int:
    """Salva o trace de uma execucao do agente. Retorna o id do trace."""
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO tracing (pergunta, params, conectores, rag, modelo,
               modelo_fallback, tokens, resposta, tempo_ms, agente_id, criado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (pergunta, json.dumps(params), json.dumps(conectores, default=str),
             json.dumps(rag, default=str), modelo, 1 if modelo_fallback else 0,
             json.dumps(tokens), resposta, tempo_ms, agente_id, ts),
        )
        return cur.lastrowid


def buscar_trace(tid: int) -> dict | None:
    """Retorna um trace pelo ID."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tracing WHERE id=?", (tid,)).fetchone()
    if row:
        d = dict(row)
        d["params"] = json.loads(d.get("params", "{}"))
        d["conectores"] = json.loads(d.get("conectores", "[]"))
        d["rag"] = json.loads(d.get("rag", "[]"))
        d["tokens"] = json.loads(d.get("tokens", "{}"))
        return d
    return None


def limpar_auditoria_antiga(dias: int = 90) -> int:
    """Remove registros de auditoria com mais de `dias` dias.

    Retorna o numero de registros removidos.
    """
    ts = (datetime.now() - timedelta(days=dias)).isoformat()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM auditoria WHERE criado_em < ?", (ts,))
        return cur.rowcount


def limpar_dados_antigos() -> dict[str, int]:
    """Limpa auditoria, tracing e memorias conforme configuracao LGPD.

    Le a configuracao de retencao do banco e deleta registros
    mais antigos que o periodo definido. So executa se
    retencao_auto estiver ativo ('1').

    Retorna dict com quantos registros removeu de cada tabela.
    """
    cfg = carregar_lgpd_config()
    if cfg.get("retencao_auto") != "1":
        return {"auditoria": 0, "tracing": 0, "memories": 0}

    resultado = {}
    ts_auditoria = (datetime.now() - timedelta(days=int(cfg.get("retencao_auditoria", "90")))).isoformat()
    ts_tracing = (datetime.now() - timedelta(days=int(cfg.get("retencao_tracing", "180")))).isoformat()
    ts_memorias = (datetime.now() - timedelta(days=int(cfg.get("retencao_memorias", "365")))).isoformat()

    with get_conn() as conn:
        cur = conn.execute("DELETE FROM auditoria WHERE criado_em < ?", (ts_auditoria,))
        resultado["auditoria"] = cur.rowcount

        cur = conn.execute("DELETE FROM tracing WHERE criado_em < ?", (ts_tracing,))
        resultado["tracing"] = cur.rowcount

        cur = conn.execute("DELETE FROM memories WHERE criado_em < ?", (ts_memorias,))
        resultado["memories"] = cur.rowcount

    return resultado


# --- Feedback (avaliacao de respostas do agente) -------------------------------


def salvar_feedback(trace_id: int | None, agente_id: int | None,
                    pergunta: str, resposta: str,
                    feedback: str, tipo: str = "manual") -> int:
    """Registra feedback (util/nao_util) para uma resposta do agente.

    Retorna o id do feedback.
    """
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO feedback (trace_id, agente_id, pergunta, resposta,
               feedback, tipo, criado_em) VALUES (?,?,?,?,?,?,?)""",
            (trace_id, agente_id, pergunta[:200], resposta[:500],
             feedback, tipo, ts),
        )
        return cur.lastrowid


def buscar_feedback(fid: int) -> dict | None:
    """Retorna um feedback pelo ID."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM feedback WHERE id=?", (fid,)).fetchone()
    return dict(row) if row else None


# --- Teste A/B — julgamentos salvos (fonte p/ fine-tuning / benchmark) -------

def salvar_julgamento(pergunta, resposta_a, resposta_b, modelo_a, modelo_b,
                      voto, justificativa, modelo_juiz, criado_por) -> int:
    """Salva um veredito do Teste A/B (A/B/EMPATE) com as duas respostas."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO teste_ab
               (pergunta, resposta_a, resposta_b, modelo_a, modelo_b, voto,
                justificativa, modelo_juiz, criado_por, criado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (pergunta, resposta_a, resposta_b, modelo_a, modelo_b,
             voto, justificativa, modelo_juiz, criado_por, now_iso()))
        return cur.lastrowid


def listar_julgamentos(limite: int = 1000) -> list[dict]:
    """Lista julgamentos salvos (mais recentes primeiro)."""
    with get_conn() as conn:
        rows = _rows(conn, "SELECT * FROM teste_ab ORDER BY id DESC LIMIT ?", (limite,))
    return [dict(r) for r in rows]


def contar_julgamentos() -> int:
    """Total de julgamentos salvos (para exibir o botao de export)."""
    with get_conn() as conn:
        r = _row(conn, "SELECT COUNT(*) AS n FROM teste_ab")
        return r["n"] or 0


def verificar_pergunta_repetida(agente_id: int, pergunta: str,
                                limite_minutos: int = 5) -> dict | None:
    """Detecta se a mesma pergunta foi feita recentemente (feedback implicito).

    Se encontrar, marca a resposta anterior como 'nao_util' e retorna os dados.
    Retorna None se nao houver repeticao.
    """
    ts_limite = (datetime.now() - timedelta(minutes=limite_minutos)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id, trace_id, pergunta, resposta FROM feedback
               WHERE agente_id=? AND pergunta=?
               AND criado_em >= ? AND feedback='util'
               ORDER BY id DESC LIMIT 1""",
            (agente_id, pergunta[:200], ts_limite),
        ).fetchone()
    if row:
        # Marca a anterior como nao_util (nao resolveu)
        with get_conn() as conn:
            conn.execute(
                "UPDATE feedback SET feedback='nao_util' WHERE id=?",
                (row["id"],),
            )
        return dict(row)
    return None


def listar_feedback(agente_id: int | None = None,
                    limite: int = 100, offset: int = 0) -> list[dict]:
    """Lista feedbacks recentes, opcionalmente filtrados por agente."""
    sql = "SELECT * FROM feedback"
    params: list = []
    if agente_id:
        sql += " WHERE agente_id=?"
        params.append(agente_id)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limite, offset])
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def contar_feedback() -> int:
    """Total de feedbacks registrados (para paginacao do Teste A/B)."""
    with get_conn() as conn:
        r = _row(conn, "SELECT COUNT(*) AS n FROM feedback")
        return r["n"] or 0


# --- Metricas diarias (KPIs de observabilidade) ---------------------------------


def agregar_metricas_diarias(data: str | None = None) -> int:
    """Consolida metricas do dia a partir das tabelas tracing e feedback.

    data: string 'YYYY-MM-DD' ou None (hoje). Retorna quantas linhas inseriu.
    """
    if data is None:
        data = now_iso()[:10]
    ts_inicio = data + " 00:00:00"
    ts_fim = data + " 23:59:59"

    with get_conn() as conn:
        # Busca tracing do dia
        rows = conn.execute(
            """SELECT modelo, modelo_fallback,
               COUNT(*) as chamadas,
               SUM(json_extract(tokens, '$.total_tokens')) as tokens_total,
               AVG(tempo_ms) as avg_lat,
               SUM(CASE WHEN resposta='' THEN 1 ELSE 0 END) as erros
               FROM tracing
               WHERE criado_em BETWEEN ? AND ?
               GROUP BY modelo""",
            (ts_inicio, ts_fim),
        ).fetchall()

        # Busca feedback do dia agrupado por agente
        from datetime import datetime as _dt
        fb_rows = conn.execute(
            """SELECT f.agente_id, t.modelo,
               COUNT(*) as total,
               SUM(CASE WHEN feedback='util' THEN 1 ELSE 0 END) as util
               FROM feedback f
               LEFT JOIN tracing t ON f.trace_id = t.id
               WHERE f.criado_em BETWEEN ? AND ?
               GROUP BY f.agente_id, t.modelo""",
            (ts_inicio, ts_fim),
        ).fetchall()

        # Mapeia feedback por agente
        fb_map: dict[tuple, dict] = {}
        for r in fb_rows:
            fb_map[(r["agente_id"], r["modelo"])] = {"total": r["total"], "util": r["util"]}

        # Insere/atualiza metricas (deleta antes para evitar duplicatas com NULL)
        inseridas = 0
        for r in rows:
            modelo = r["modelo"]
            conn.execute(
                "DELETE FROM metricas_diarias WHERE data=? AND modelo=?",
                (data, modelo),
            )
            fb = fb_map.get((None, modelo), {"total": 0, "util": 0})
            ts = now_iso()
            conn.execute(
                """INSERT INTO metricas_diarias
                   (data, agente_id, modelo, chamadas, tokens_total,
                    latencia_p50, latencia_p95, erros,
                    feedback_util, feedback_total, criado_em)
                   VALUES (?,NULL,?,?,?,?,?,?,?,?,?)""",
                (data, modelo, r["chamadas"], r["tokens_total"] or 0,
                 int(r["avg_lat"] or 0), int(r["avg_lat"] or 0), r["erros"] or 0,
                 fb["util"], fb["total"], ts),
            )
            inseridas += 1
        return inseridas


def listar_metricas(dias: int = 30) -> list[dict]:
    """Retorna metricas dos ultimos N dias."""
    data_corte = (datetime.now() - timedelta(days=dias)).isoformat()[:10]
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM metricas_diarias
               WHERE data >= ? ORDER BY data DESC""",
            (data_corte,),
        ).fetchall()
    return [dict(r) for r in rows]


def comparar_periodos(dias: int = 7) -> list[dict]:
    """Compara metricas entre periodo atual e anterior.

    Retorna lista com modelo, chamadas, latencia_media, taxa_acerto, delta.
    delta > 0 = melhorou, delta < 0 = piorou.
    """
    hoje = datetime.now()
    ini_atual = (hoje - timedelta(days=dias)).isoformat()[:10]
    ini_anterior = (hoje - timedelta(days=dias * 2)).isoformat()[:10]
    fim_anterior = (hoje - timedelta(days=dias)).isoformat()[:10]

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT modelo,
               SUM(CASE WHEN data >= ? THEN chamadas ELSE 0 END) as chamadas_atual,
               SUM(CASE WHEN data < ? THEN chamadas ELSE 0 END) as chamadas_anterior,
               AVG(CASE WHEN data >= ? THEN latencia_p50 ELSE NULL END) as lat_atual,
               AVG(CASE WHEN data < ? THEN latencia_p50 ELSE NULL END) as lat_anterior,
               SUM(CASE WHEN data >= ? THEN feedback_util ELSE 0 END) as util_atual,
               SUM(CASE WHEN data >= ? THEN feedback_total ELSE 0 END) as fb_atual,
               SUM(CASE WHEN data < ? THEN feedback_util ELSE 0 END) as util_anterior,
               SUM(CASE WHEN data < ? THEN feedback_total ELSE 0 END) as fb_anterior
               FROM metricas_diarias
               WHERE data >= ?
               GROUP BY modelo""",
            (ini_atual, ini_atual,
             ini_atual, ini_atual,
             ini_atual, ini_atual,
             ini_atual, ini_atual,
             ini_anterior),
        ).fetchall()

    resultado = []
    for r in rows:
        lat_media = int(r["lat_atual"] or 0)
        lat_ant = int(r["lat_anterior"] or 0)
        tx_atual = (r["util_atual"] / r["fb_atual"] * 100) if r["fb_atual"] else None
        tx_anterior = (r["util_anterior"] / r["fb_anterior"] * 100) if r["fb_anterior"] else None
        delta_tx = round(tx_atual - tx_anterior, 1) if tx_atual is not None and tx_anterior is not None else None
        delta_lat = round((lat_media - lat_ant) / lat_ant * 100, 1) if lat_media and lat_ant else None
        resultado.append({
            "modelo": r["modelo"],
            "chamadas": r["chamadas_atual"] or 0,
            "chamadas_anterior": r["chamadas_anterior"] or 0,
            "latencia_media": lat_media,
            "latencia_anterior": lat_ant,
            "taxa_acerto": f"{tx_atual:.0f}%" if tx_atual else "--",
            "taxa_anterior": f"{tx_anterior:.0f}%" if tx_anterior else "--",
            "delta_taxa": delta_tx,
            "delta_latencia": delta_lat,
        })
    return resultado


def calcular_custos(dias: int = 30) -> list[dict]:
    """Calcula custo estimado por modelo baseado nos tokens consumidos."""
    data_corte = (datetime.now() - timedelta(days=dias)).isoformat()[:10]
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.modelo,
               SUM(m.tokens_total) as tokens,
               c.preco_input, c.preco_output
               FROM metricas_diarias m
               LEFT JOIN custos_modelo c ON m.modelo = c.modelo
               WHERE m.data >= ?
               GROUP BY m.modelo""",
            (data_corte,),
        ).fetchall()
    resultado = []
    for r in rows:
        tokens = r["tokens"] or 0
        preco = r["preco_input"] or 0.15
        custo = tokens / 1_000_000 * preco
        resultado.append({
            "modelo": r["modelo"],
            "tokens": tokens,
            "custo": round(custo, 4),
            "preco_milhao": preco,
        })
    return resultado




def verificar_alertas() -> list[dict]:
    """Verifica thresholds (lidos do banco) e retorna alertas ativos."""
    config = obter_alertas_config()
    taxa_min = config.get("taxa_acerto_min", {}).get("valor", 70.0)
    lat_max = config.get("latencia_max", {}).get("valor", 1000)
    err_max = config.get("erros_max", {}).get("valor", 5)
    hoje = datetime.now().isoformat()[:10]
    alertas = []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT modelo, SUM(feedback_util)*100.0/NULLIF(SUM(feedback_total),0) as taxa FROM metricas_diarias WHERE data >= ? GROUP BY modelo",
            ((datetime.now() - timedelta(days=7)).isoformat()[:10],),
        ).fetchall()
        for r in rows:
            if r["taxa"] is not None and r["taxa"] < taxa_min:
                alertas.append({"tipo": "taxa_acerto_baixa", "modelo": r["modelo"], "valor": round(r["taxa"], 1), "threshold": taxa_min, "desc": f"Taxa de acerto < {taxa_min:.0f}% (7d)"})
        rows = conn.execute("SELECT modelo, latencia_p50 FROM metricas_diarias WHERE data=? AND chamadas>0", (hoje,)).fetchall()
        for r in rows:
            if r["latencia_p50"] > lat_max:
                alertas.append({"tipo": "latencia_alta", "modelo": r["modelo"], "valor": r["latencia_p50"], "threshold": lat_max, "desc": f"Latencia > {lat_max:.0f}ms hoje"})
        rows = conn.execute("SELECT modelo, SUM(erros) as total_erros FROM metricas_diarias WHERE data=? GROUP BY modelo", (hoje,)).fetchall()
        for r in rows:
            if r["total_erros"] > err_max:
                alertas.append({"tipo": "erros_altos", "modelo": r["modelo"], "valor": r["total_erros"], "threshold": err_max, "desc": f"Mais de {err_max:.0f} erros hoje"})
    return alertas


def obter_alertas_config() -> dict[str, dict]:
    """Retorna todas as configuracoes de alerta."""
    with get_conn() as conn:
        rows = conn.execute("SELECT chave, valor, descricao FROM alertas_config").fetchall()
    return {r["chave"]: {"valor": r["valor"], "descricao": r["descricao"]} for r in rows}


def salvar_alerta_config(chave: str, valor: float) -> None:
    """Atualiza o valor de um alerta config."""
    with get_conn() as conn:
        conn.execute("UPDATE alertas_config SET valor=? WHERE chave=?", (valor, chave))


# --- LGPD Config ---------------------------------------------------------------


def carregar_lgpd_config() -> dict[str, str]:
    """Retorna todas as configuracoes LGPD como dict chave->valor."""
    with get_conn() as conn:
        rows = conn.execute("SELECT chave, valor FROM lgpd_config").fetchall()
    return {r["chave"]: r["valor"] for r in rows}


def salvar_lgpd_config(chave: str, valor: str) -> None:
    """Atualiza uma configuracao LGPD."""
    with get_conn() as conn:
        conn.execute("UPDATE lgpd_config SET valor=? WHERE chave=?", (valor, chave))


# --- Seed / Demo ----------------------------------------------------------------


def _seed_conectores_demo(conn, cliente_id: int, ts: str) -> None:
    """Cria conectores de demonstração para o cliente (ERP/CRM/RH) nas áreas relevantes."""
    demo_conectores = [
        ("vendas", "ERP", "mcp", '{"dsn_env": "ERP_DSN", "descricao": "Postgres real do cliente"}'),
        ("vendas", "CRM", "mcp", '{"descricao": "Dados de exemplo CRM"}'),
        ("suporte", "CRM", "mcp", '{"descricao": "Dados de exemplo CRM"}'),
        ("financeiro", "ERP Financeiro", "mcp", '{"dsn_env": "ERP_DSN", "descricao": "Postgres real do cliente"}'),
        ("rh", "RH", "mcp", '{"descricao": "Dados de exemplo RH"}'),
        ("operacoes", "ERP Operações", "mcp", '{"dsn_env": "ERP_DSN", "descricao": "Postgres real do cliente"}'),
    ]
    for area, nome, tipo, config in demo_conectores:
        conn.execute(
            """INSERT INTO conectores (cliente_id, area, nome, tipo, config, status, ativo, ultimo_heartbeat, criado_em)
               VALUES (?,?,?,?,?, 'online', 1, ?, ?)""",
            (cliente_id, area, nome, tipo, config, ts, ts),
        )


def atualizar_heartbeat_conector(cid: int, status: str = "online") -> None:
    """Atualiza heartbeat e status de um conector."""
    ts = now_iso()
    with get_conn() as conn:
        conn.execute("UPDATE conectores SET status=?, ultimo_heartbeat=? WHERE id=?",
                     (status, ts, cid))


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


# --- Billing (faturas) ------------------------------------------------------

# --- Uso de Tokens (analise de consumo, nao pagamento) ----------------------

def registrar_uso_token(cliente_id, modelo, total_tokens, prompt_tokens=0, completion_tokens=0,
                        agente_id=None, modelo_fallback=0, quem="usuario", origem="chat") -> int:
    """Registra consumo de tokens de uma chamada ao LLM."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO uso_tokens (cliente_id, agente_id, modelo, modelo_fallback,
               quem, origem, prompt_tokens, completion_tokens, total_tokens, criado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (cliente_id, agente_id, modelo, modelo_fallback, quem, origem,
             prompt_tokens, completion_tokens, total_tokens, now_iso()),
        )
        return cur.lastrowid


def listar_uso_tokens(cliente_id: int | None = None, limite: int = 200) -> list[dict]:
    """Lista registros de uso de tokens, do mais recente primeiro."""
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM uso_tokens WHERE cliente_id=? ORDER BY id DESC LIMIT ?",
                (cliente_id, limite))]
        return [dict(r) for r in _rows(
            conn, "SELECT * FROM uso_tokens ORDER BY id DESC LIMIT ?", (limite,))]


def agregar_uso_por_cliente(cliente_id: int | None = None) -> list[dict]:
    """Agrega tokens totais por cliente + modelo + origem."""
    sql = """SELECT cliente_id, modelo, origem,
                    SUM(prompt_tokens) AS total_prompt,
                    SUM(completion_tokens) AS total_completion,
                    SUM(total_tokens) AS total_tokens,
                    COUNT(*) AS chamadas
             FROM uso_tokens
             """ + ("WHERE cliente_id=? " if cliente_id else "") + """
             GROUP BY cliente_id, modelo, origem
             ORDER BY total_tokens DESC"""
    params = (cliente_id,) if cliente_id else ()
    with get_conn() as conn:
        return [dict(r) for r in _rows(conn, sql, params)]


# --- Contratos (info estatica de contrato anual, fora da plataforma) --------

def criar_contrato(cliente_id, valor_anual: float = 0.0, moeda="BRL", inicio="", fim="",
                   status="ativo") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO contratos (cliente_id, valor_anual, moeda, inicio, fim, status, criado_em)
               VALUES (?,?,?,?,?,?,?)""",
            (cliente_id, valor_anual, moeda, inicio, fim, status, now_iso()),
        )
        return cur.lastrowid


def listar_contratos(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM contratos WHERE cliente_id=? ORDER BY id DESC", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM contratos ORDER BY id DESC")]


def buscar_contrato(cliente_id: int) -> dict | None:
    """Retorna o contrato ativo mais recente do cliente."""
    with get_conn() as conn:
        r = _row(conn, "SELECT * FROM contratos WHERE cliente_id=? AND status='ativo' ORDER BY id DESC LIMIT 1",
                 (cliente_id,))
        return dict(r) if r else None



# --- Memoria por usuario + RAG (banco vetorial local) ----------------------

def criar_memoria(cliente_id, usuario, conteudo, tipo="conversa", area="") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO memories (cliente_id, usuario, tipo, conteudo, vetor, area, criado_em)
               VALUES (?,?,?,?, '[]', ?, ?)""",
            (cliente_id, usuario, tipo, conteudo, area, now_iso()),
        )
        return cur.lastrowid


def listar_memorias(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM memories WHERE cliente_id=? ORDER BY id DESC", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM memories ORDER BY id DESC")]


def criar_documento(cliente_id, titulo, categoria, conteudo, area="", fonte="manual") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO knowledge (cliente_id, area, titulo, categoria, fonte, conteudo, vetor, acessos, criado_em)
               VALUES (?,?,?,?,?,?, '[]', 0, ?)""",
            (cliente_id, area, titulo, categoria, fonte, conteudo, now_iso()),
        )
        return cur.lastrowid


def listar_documentos(cliente_id: int | None = None, area: str | None = None) -> list[dict]:
    sql = "SELECT * FROM knowledge WHERE 1=1"
    params = []
    if cliente_id is not None:
        sql += " AND cliente_id=?"
        params.append(cliente_id)
    if area:
        sql += " AND area=?"
        params.append(area)
    sql += " ORDER BY id DESC"
    with get_conn() as conn:
        return [dict(r) for r in _rows(conn, sql, params)]


def buscar_documento(did: int) -> dict | None:
    with get_conn() as conn:
        row = _one(conn, "SELECT * FROM knowledge WHERE id=?", (did,))
        return dict(row) if row else None


def atualizar_documento(did: int, **campos) -> None:
    if "conteudo" in campos or "titulo" in campos:
        campos["vetor"] = "[]"  # marca para re-embedding
    # Whitelist de colunas validas da tabela knowledge
    _COLUNAS_VALIDAS = {"cliente_id", "area", "titulo", "categoria", "fonte",
                        "conteudo", "vetor", "acessos", "ultimo_acesso"}
    cols_validas = {k: v for k, v in campos.items() if k in _COLUNAS_VALIDAS}
    if not cols_validas:
        return
    cols = ", ".join(f"{k}=?" for k in cols_validas)
    with get_conn() as conn:
        conn.execute(f"UPDATE knowledge SET {cols} WHERE id=?", list(cols_validas.values()) + [did])


def deletar_documento(did: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM knowledge WHERE id=?", (did,))


def registrar_acesso_documento(did: int) -> None:
    ts = now_iso()
    with get_conn() as conn:
        conn.execute("UPDATE knowledge SET acessos=acessos+1, ultimo_acesso=? WHERE id=?", (ts, did))


def contar_documentos(cliente_id: int | None = None) -> list[dict]:
    """Agrega estatisticas dos documentos: total, por area, por categoria, por fonte."""
    sql = """SELECT
               COUNT(*) AS total,
               COUNT(DISTINCT area) AS areas,
               SUM(acessos) AS total_acessos,
               ROUND(AVG(LENGTH(conteudo))) AS tamanho_medio
             FROM knowledge"""
    params = []
    if cliente_id is not None:
        sql += " WHERE cliente_id=?"
        params.append(cliente_id)
    with get_conn() as conn:
        stats = [dict(r) for r in _rows(conn, sql, params)]
    # por area
    sql_area = "SELECT area, COUNT(*) AS qtd, SUM(acessos) AS acessos FROM knowledge"
    if cliente_id is not None:
        sql_area += " WHERE cliente_id=?"
    sql_area += " GROUP BY area ORDER BY qtd DESC"
    with get_conn() as conn:
        params_a = [cliente_id] if cliente_id is not None else []
        por_area = [dict(r) for r in _rows(conn, sql_area, params_a)]
    # por fonte
    sql_fonte = "SELECT fonte, COUNT(*) AS qtd FROM knowledge"
    if cliente_id is not None:
        sql_fonte += " WHERE cliente_id=?"
    sql_fonte += " GROUP BY fonte ORDER BY qtd DESC"
    with get_conn() as conn:
        params_f = [cliente_id] if cliente_id is not None else []
        por_fonte = [dict(r) for r in _rows(conn, sql_fonte, params_f)]
    return {
        "geral": stats[0] if stats else {"total": 0, "areas": 0, "total_acessos": 0, "tamanho_medio": 0},
        "por_area": por_area,
        "por_fonte": por_fonte,
    }


# --- Modelos de IA (cadastro de LLMs por cliente) --------------------------

def criar_modelo(cliente_id, nome, base_url, modelo, tipo="local", api_key=None, ativo=1, max_tokens=None,
                 preco_input=0.0, preco_output=0.0) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO modelos (cliente_id, nome, base_url, modelo, tipo, api_key, max_tokens, ativo,
               preco_input, preco_output, criado_em)
               VALUES (?,?,?,?,?,?,?,1,?,?,?)""",
            (cliente_id, nome, base_url, modelo, tipo, api_key, max_tokens, preco_input, preco_output, now_iso()),
        )
        return cur.lastrowid


def listar_modelos(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM modelos WHERE cliente_id=? ORDER BY id DESC", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM modelos ORDER BY id DESC")]


def buscar_modelo(mid: int) -> dict | None:
    with get_conn() as conn:
        row = _one(conn, "SELECT * FROM modelos WHERE id=?", (mid,))
        return dict(row) if row else None


def atualizar_modelo(mid: int, **campos) -> None:
    """Atualiza campos do modelo (nome, base_url, modelo, tipo, api_key, max_tokens, ativo)."""
    cols = ", ".join(f"{k}=?" for k in campos)
    with get_conn() as conn:
        conn.execute(f"UPDATE modelos SET {cols} WHERE id=?", list(campos.values()) + [mid])


def deletar_modelo(mid: int) -> None:
    """Remove um modelo pelo ID."""
    with get_conn() as conn:
        conn.execute("DELETE FROM modelos WHERE id=?", (mid,))


# --- API Keys (canal de integracao / sistema) -----------------------------

def criar_api_key(cliente_id, chave, descricao="") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO api_keys (cliente_id, chave, descricao, ativo, criado_em) VALUES (?,?,?,1,?)",
            (cliente_id, chave, descricao, now_iso()),
        )
        return cur.lastrowid


def buscar_api_key(chave: str) -> dict | None:
    with get_conn() as conn:
        row = _one(conn, "SELECT * FROM api_keys WHERE chave=? AND ativo=1", (chave,))
        return dict(row) if row else None


def listar_api_keys(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM api_keys WHERE cliente_id=? ORDER BY id DESC", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM api_keys ORDER BY id DESC")]


# --- Canais (API/webhook que expoe um agente p/ integracao real) -----------

import secrets

def gerar_token(prefix: str = "bs_chan") -> str:
    return f"{prefix}_{secrets.token_urlsafe(24)}"


def validar_webhook_url(url: str) -> str | None:
    """Valida URL de webhook. Retorna None se ok, ou mensagem de erro."""
    import urllib.parse
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "Esquema deve ser http ou https"
    host = parsed.hostname or ""
    # Bloqueia enderecos internos
    internos = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "::ffff:127.0.0.1"}
    if host in internos or host.startswith("127.") or host.startswith("10.") \
       or host.startswith("172.16.") or host.startswith("192.168."):
        return "URL nao pode apontar para servicos internos (localhost, 10.x, 172.16.x, 192.168.x)"
    return None


def criar_canal(cliente_id, nome, agente_id, tipo="api", token=None, webhook_url=None,
                webhook_headers=None) -> int:
    if webhook_url:
        erro = validar_webhook_url(webhook_url)
        if erro:
            raise ValueError(erro)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO canais (cliente_id, nome, tipo, agente_id, token, webhook_url,
                                   webhook_headers, ativo, criado_em)
               VALUES (?,?,?,?,?,?,?,1,?)""",
            (cliente_id, nome, tipo, agente_id, token or gerar_token(), webhook_url,
             webhook_headers or '{}', now_iso()),
        )
        return cur.lastrowid


def buscar_canal_por_token(token: str) -> dict | None:
    with get_conn() as conn:
        row = _one(conn, "SELECT * FROM canais WHERE token=? AND ativo=1", (token,))
        return dict(row) if row else None


def listar_canais(cliente_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if cliente_id:
            return [dict(r) for r in _rows(
                conn, "SELECT * FROM canais WHERE cliente_id=? ORDER BY id DESC", (cliente_id,))]
        return [dict(r) for r in _rows(conn, "SELECT * FROM canais ORDER BY id DESC")]


def regenerar_token_canal(canal_id: int) -> str:
    """Gera um novo token para o canal e retorna o token."""
    novo = gerar_token()
    with get_conn() as conn:
        conn.execute("UPDATE canais SET token=? WHERE id=?", (novo, canal_id))
    return novo


def alternar_canal(canal_id: int) -> dict | None:
    """Alterna ativo/inativo. Retorna o canal atualizado ou None se não existir."""
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM canais WHERE id=?", (canal_id,))
        row = cur.fetchone()
        if not row:
            return None
        novo_status = 0 if row["ativo"] else 1
        conn.execute("UPDATE canais SET ativo=? WHERE id=?", (novo_status, canal_id))
        return dict({**row, "ativo": novo_status})


def buscar_canal(canal_id: int) -> dict | None:
    """Retorna um canal pelo ID."""
    with get_conn() as conn:
        row = _one(conn, "SELECT * FROM canais WHERE id=?", (canal_id,))
        return dict(row) if row else None


def atualizar_canal(canal_id: int, **campos) -> None:
    """Atualiza campos do canal (nome, tipo, agente_id, webhook_url)."""
    cols = ", ".join(f"{k}=?" for k in campos)
    with get_conn() as conn:
        conn.execute(f"UPDATE canais SET {cols} WHERE id=?", list(campos.values()) + [canal_id])


# --- Auditoria (rastreabilidade / LGPD) ------------------------------------

def registrar_auditoria(usuario, papel, acao, alvo="", cliente_id=None, ip="", detalhe="") -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO auditoria (usuario, papel, acao, alvo, cliente_id, ip, detalhe, criado_em)
               VALUES (?,?,?,?,?,?,?,?)""",
            (usuario, papel, acao, alvo, cliente_id, ip, detalhe, now_iso()),
        )


def listar_auditoria(limite: int = 100, usuario: str | None = None) -> list[dict]:
    with get_conn() as conn:
        sql = "SELECT * FROM auditoria"
        params = []
        if usuario:
            sql += " WHERE usuario=?"
            params.append(usuario)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        return [dict(r) for r in _rows(conn, sql, params)]

def buscar_sso_config() -> dict | None:
    """Retorna a configuracao de SSO (unica linha). None se nao houver."""
    with get_conn() as conn:
        r = _one(conn, "SELECT * FROM sso_config ORDER BY id DESC LIMIT 1")
        return dict(r) if r else None


def sso_ativo() -> bool:
    cfg = buscar_sso_config()
    return bool(cfg and cfg.get("ativo"))


def salvar_sso_config(ativo=0, dev_mode=0, issuer="", client_id="", client_secret="",
                      redirect_uri="", dominio_admin="", auto_criar=0) -> None:
    """Insere ou atualiza a unica linha de config de SSO."""
    ts = now_iso()
    with get_conn() as conn:
        if buscar_sso_config():
            conn.execute(
                "UPDATE sso_config SET ativo=?, dev_mode=?, issuer=?, client_id=?, client_secret=?, redirect_uri=?, dominio_admin=?, auto_criar=?, atualizado_em=?",
                (ativo, dev_mode, issuer, client_id, client_secret, redirect_uri, dominio_admin, auto_criar, ts))
        else:
            conn.execute(
                "INSERT INTO sso_config (ativo, dev_mode, issuer, client_id, client_secret, redirect_uri, dominio_admin, auto_criar, atualizado_em) VALUES (?,?,?,?,?,?,?,?,?)",
                (ativo, dev_mode, issuer, client_id, client_secret, redirect_uri, dominio_admin, auto_criar, ts))


# --- Seed demo --------------------------------------------------------------

def seed_demo() -> None:
    """Popula dados de demonstracao (idempotente)."""
    with get_conn() as conn:
        ja_tem = _row(conn, "SELECT COUNT(*) AS n FROM clientes")
        if ja_tem["n"] > 0:
            # DB existente: garante contrato demo se nao tiver (migracao conceitual)
            primeiro = _row(conn, "SELECT id FROM clientes ORDER BY id LIMIT 1")
            if primeiro:
                cid = primeiro["id"]
                ct = _row(conn, "SELECT id FROM contratos WHERE cliente_id=? LIMIT 1", (cid,))
                if not ct:
                    criar_contrato(cid, valor_anual=120000.00, moeda="BRL",
                                   inicio="2026-07-01", fim="2027-06-30", status="ativo")
            return
    cid = criar_cliente("xpto", "XPTO Seguros (Piloto)", "XPTO Seguro S/A", "ti@xpto.com.br")
    criar_usuario(cid, "Administrador BlueShift", "admin", "admin123", "admin", "operacoes")
    criar_usuario(cid, "Gestor Vendas", "gestor", "gestor123", "gestor", "vendas")
    criar_usuario(cid, "Ana Suporte", "ana", "ana123", "usuario", "suporte")
    criar_usuario(cid, "Carlos Financeiro", "carlos", "carlos123", "usuario", "financeiro")
    criar_usuario(cid, "Beatriz RH", "bia", "bia123", "usuario", "rh")
    # modelo de IA demo (LM Studio local do cliente) — criado ANTES dos agentes
    mid = criar_modelo(cid, "bonsai-8b", "http://127.0.0.1:1234", "bonsai-8b", tipo="local")
    aid_vendas = criar_agente(cid, "Agente Vendas", "vendas", "bonsai-8b", "vendas,suporte", "erp,crm", modelo_id=mid)
    criar_agente(cid, "Agente Suporte", "suporte", "bonsai-8b", "suporte", "crm", modelo_id=mid)
    criar_agente(cid, "Agente Financeiro", "financeiro", "bonsai-8b", "financeiro", "erp", modelo_id=mid)
    criar_agente(cid, "Agente RH", "rh", "bonsai-8b", "rh", "", modelo_id=mid)
    criar_agente(cid, "Agente Operações", "operacoes", "bonsai-8b", "operacoes", "erp", modelo_id=mid)
    # canal de integracao real (API) apontando para o Agente Vendas
    criar_canal(cid, "API Vendas (Webhook)", aid_vendas,
                tipo="api", token="bs_chan_demo_vendas_123")
    atualizar_health(cid, container="saudavel", modelo_local="ok", latencia_ms=42, tokens_hoje=18320, erros_24h=0)
    # contrato anual (info estatica, cobranca e fora da plataforma)
    criar_contrato(cid, valor_anual=120000.00, moeda="BRL", inicio="2026-07-01", fim="2027-06-30", status="ativo")

    # base de conhecimento (RAG) demo
    criar_documento(cid, "Política de Privacidade LGPD", "politica",
                    "A BlueShift mantém todos os dados do cliente dentro do ambiente dele. "
                    "A memória de cada usuário é isolada por ID e nunca é compartilhada entre usuários. "
                    "Dados sensíveis não saem do servidor do cliente.",
                    area="operacoes")
    criar_documento(cid, "Manual do Agente de Vendas", "manual",
                    "O agente de vendas qualifica leads, faz follow-up e estima receita. "
                    "Ele acessa apenas dados da área de vendas via conector ERP e CRM.",
                    area="vendas")
    criar_documento(cid, "Base de Conhecimento de Suporte", "base_conhecimento",
                    "O conector CRM em ambiente de demonstração pode retornar lista vazia. "
                    "Verifique se o banco está populado com dados de exemplo.",
                    area="suporte")
