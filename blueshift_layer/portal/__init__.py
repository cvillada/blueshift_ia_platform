"""Portal do Cliente BlueShift (Camada 4 — Experiência).

Gerencia, cadastra e monitora os clientes, usuarios, agentes e conectores
da BlueShift IA Platform. Roda 100% on-premise (SQLite local fake, sem rede
externa), seguindo o padrao da plataforma.

Uso:
    from blueshift_layer.portal import create_app
    app = create_app()
    app.run(port=5000)
"""
from __future__ import annotations

import os
import secrets

from . import db
from .views import bp


# ──────────────────────────────────────────
# Assinatura de autoria (HMAC-SHA256)
# Apenas o hash e a mensagem ficam no codigo.
# A chave secreta e mantida fora do repositorio.
# ──────────────────────────────────────────
_MENSAGEM_AUTORIA = "Autor: Claudnei Villada - 072026"
_HASH_AUTORIA = "88a20f0a44a81c0ac38f0490804f45f8ad07abf705dbd40123e2ef5b490e4cb8"


def verificar_autoria(chave: str) -> bool:
    """Verifica se a chave informada produz o mesmo hash da mensagem de autoria.

    Uso:
        from blueshift_layer.portal import verificar_autoria
        verificar_autoria("sua_chave_aqui")  # retorna True se a chave for correta
    """
    import hashlib
    import hmac
    esperado = hmac.new(chave.encode(), _MENSAGEM_AUTORIA.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, _HASH_AUTORIA)


def obter_hash_autoria() -> str:
    """Retorna o hash HMAC-SHA256 da autoria (64 chars hex)."""
    return _HASH_AUTORIA


# Segredo de sessao de exemplo do .env.example (publico no repositorio).
# Continua aceito — decisao do dono: num UPDATE avisar e seguir, nunca derrubar
# instalacao que ja esta no ar (recusar so numa versao futura, anunciada).
_SEGREDO_EXEMPLO = "bs-portal-secret-troque-em-producao"


def _segredo_sessao() -> str:
    """Segredo que assina o cookie de sessao (C3, v0.11.9).

    Ordem: variavel de ambiente -> arquivo `.portal_secret` ao lado do
    `portal.db` (0600) -> gera um aleatorio e persiste.

    Antes: `os.environ.get(...) or secrets.token_hex(32)` — sem a variavel, o
    segredo era aleatorio POR PROCESSO, entao toda reinicializacao derrubava
    as sessoes (e com mais de um worker a sessao oscilava entre eles). E o
    compose trazia um default publico, que permitia forjar o cookie de admin
    (achado da varredura de 2026-09-30, corrigido na prod por rotacao manual).
    """
    do_ambiente = (os.environ.get("BLUESHIFT_PORTAL_SECRET") or "").strip()
    if do_ambiente:
        return do_ambiente
    caminho = os.path.join(
        os.path.dirname(os.environ.get("BLUESHIFT_PORTAL_DB", "data/portal.db")),
        ".portal_secret")
    try:
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as fh:
                salvo = fh.read().strip()
            if salvo:
                return salvo
        novo = secrets.token_hex(32)
        pasta = os.path.dirname(caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as fh:
            fh.write(novo)
        os.chmod(caminho, 0o600)
        return novo
    except OSError:
        # Sem permissao de escrita: mantem o comportamento antigo (sessao vale
        # so neste processo) em vez de derrubar o portal no boot.
        return secrets.token_hex(32)


def create_app() -> "Flask":
    """Factory do Portal. Inicializa o SQLite e registra o blueprint."""
    from flask import Flask, Response, jsonify, request

    app = Flask(__name__)
    app.secret_key = _segredo_sessao()
    if app.secret_key == _SEGREDO_EXEMPLO:
        # C4 — avisa no log e SEGUE (nao derruba instalacao no ar).
        app.logger.warning(
            "[seguranca] BLUESHIFT_PORTAL_SECRET esta no valor de exemplo do "
            ".env.example (publico no repositorio): o cookie de sessao pode ser "
            "forjado. Rode `openssl rand -hex 32` e atualize o .env, ou deixe a "
            "variavel vazia que o portal gera um segredo proprio.")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 min
    # Secure: so em producao (HTTPS). Local HTTP sem Secure para nao quebrar testes.
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("BLUESHIFT_PORTAL_SECURE", "").lower() in ("1", "true")
    app.debug = False  # nunca rodar em debug em producao

    # ── Erro interno apresentavel (v0.11.9) ──
    # Antes nao existia errorhandler: qualquer excecao nao tratada devolvia a
    # pagina crua do Flask ("Internal Server Error") e o traceback so existia
    # no log do container — quem opera via um erro mudo e um numero de versao
    # nenhum. Agora: mensagem em pt-BR no visual do portal nas telas e JSON nas
    # rotas de API (`/portal/api/...`), com o traceback no log para suporte.
    @app.errorhandler(500)
    def _erro_interno(e):  # noqa: ANN001 - assinatura do Flask
        import traceback
        app.logger.error("erro interno em %s: %s", request.path,
                         traceback.format_exc())
        if request.path.startswith(("/portal/api", "/v1")):
            return jsonify({"ok": False,
                            "erro": "erro interno no servidor (detalhe no log do portal)"}), 500
        return Response(
            "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
            "<title>Erro interno</title></head>"
            "<body style=\"font-family:system-ui,sans-serif;background:#0f1115;"
            "color:#e6e8eb;padding:48px;line-height:1.6\">"
            "<h2 style=\"margin:0 0 8px\">Erro interno</h2>"
            "<p style=\"color:#9aa4b2;max-width:560px\">A operacao nao foi concluida. "
            "O erro foi registrado no log do servidor (docker logs blueshift-platform) "
            "para o suporte identificar a causa.</p>"
            "<p><a href=\"/portal/monitorar\" style=\"color:#69b1ff\">Voltar ao portal</a></p>"
            "</body></html>",
            status=500, mimetype="text/html")

    db.init_db()
    # Purge retroativo de contagio RAG: remove chunks com tag de tool_call
    # cru gravados antes do filtro de gravacao (best-effort, idempotente).
    try:
        _purge = db.purgar_conteudo_tool_call()
        if sum(_purge.values()):
            app.logger.info(
                f"[rag] purge tool_call: {_purge.get('knowledge', 0)} knowledge "
                f"+ {_purge.get('memories', 0)} memories removidos")
    except Exception:
        pass  # nunca derruba o boot
    # Seed demo: so quando BLUESHIFT_SEED_DEMO != "0". Em instalacao de cliente
    # final (sem BLUESHIFT_DEV), desligar nao cria dados demo de empresa —
    # o cliente cadastra a propria empresa na tela Clientes.
    if os.environ.get("BLUESHIFT_SEED_DEMO", "1") != "0":
        db.seed_demo()
    app.register_blueprint(bp)

    # ── Retencao automatica de logs (LGPD Art. 15) ──
    import threading as _threading

    def _limpeza_periodica():
        import time as _time
        while True:
            try:
                result = db.limpar_dados_antigos()
                total = sum(result.values())
                if total:
                    app.logger.info(
                        f"[lgpd] retencao: {result['auditoria']} auditoria + "
                        f"{result['tracing']} tracing + {result['uso_tokens']} uso_tokens + "
                        f"{result['memories']} memorias removidos"
                    )
            except Exception:
                pass  # falha silenciosa — best-effort
            _time.sleep(3600)  # 1 hora

    _t = _threading.Thread(target=_limpeza_periodica, daemon=True)
    _t.start()

    # ── CSRF protection for portal POST routes ──
    from flask import request, session, flash, redirect, url_for

    @app.before_request
    def _csrf_check():
        if request.method not in ("POST", "PUT", "DELETE"):
            return
        # Skip API routes (autenticadas por token, nao sessao)
        if request.path.startswith("/portal/api/"):
            return
        # Skip login POST (o rate limit ja protege)
        if request.path == "/portal/login":
            return
        # Skills gerar-ia e chamado via fetch (JSON), sem formulario padrao
        if request.path == "/portal/skills/gerar-ia":
            return
        if request.path == "/portal/conectores/testar-conexao":
            return
        if request.path == "/portal/conectores/gerar-query-ia":
            return
        token = (request.form or {}).get("_csrf_token", "")
        if not token or token != session.get("csrf_token", ""):
            flash("Sessão expirada ou requisição inválida. Tente novamente.", "bad")
            return redirect(url_for("portal.monitorar"))

    @app.before_request
    def _rbac_por_tela():
        """RBAC na LEITURA das telas (v0.11.9).

        Fonte unica em auth.TELAS_ADMIN (mesma usada pelo menu). Escrever ja era
        protegido; o que faltava era a leitura — usuario comum abria a tela de
        Usuarios e via logins/papeis. Isentas: login/logout, healthz, fluxo SSO,
        API por token e a raiz. As telas de uso normal (Monitorar, Chat, Memoria,
        Conhecimento, Docs, Workspace, Rastreio) seguem liberadas para quem
        esta logado.
        """
        caminho = request.path or ""
        if not caminho.startswith("/portal"):
            return None
        if caminho in ("/portal", "/portal/"):
            return None
        isentas = ("/portal/login", "/portal/logout", "/portal/healthz",
                   "/portal/api/", "/portal/sso/login", "/portal/sso/callback",
                   "/portal/sso/mock_authorize")
        for i in isentas:
            if caminho == i or caminho.startswith(i):
                return None
        if not session.get("user_id"):
            flash("Faça login para acessar o portal.", "warn")
            return redirect(url_for("portal.login"))
        from . import auth as _auth
        if not _auth.pode_ver(session.get("user_papel", ""), caminho):
            flash("Acesso restrito ao administrador.", "bad")
            return redirect(url_for("portal.monitorar"))
        return None

    @app.after_request
    def _add_headers(response):
        # CORS aberto SOMENTE para a API de canal (integracao externa);
        # o portal web nao precisa de CORS "*" (paginas servidas na mesma origem)
        if request.path.startswith("/portal/api/"):
            response.headers.setdefault("Access-Control-Allow-Origin", "*")
            response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization")
            response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        # Headers de seguranca HTTP (M1 da auditoria 02/08)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # 'unsafe-inline' e necessario: o portal usa style/script inline nas
        # f-strings; data: e para os graficos embutidos nas respostas
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'",
        )
        return response

    @app.route("/")
    def _root():
        from flask import redirect, url_for

        return redirect(url_for("portal.monitorar"))

    return app


__all__ = ["create_app", "db", "bp", "verificar_autoria", "obter_hash_autoria"]
