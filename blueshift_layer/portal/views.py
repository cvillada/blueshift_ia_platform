"""Views do Portal BlueShift (Camada 4).

Telas:
  - login/logout        -> autenticacao do admin
  - monitorar           -> dashboard de saude (container/modelo/conectores/agentes)
  - clientes            -> gerenciar + cadastrar clientes (admin)
  - usuarios            -> gerenciar + cadastrar usuarios (admin)
  - agentes             -> Agent Factory (admin)
  - conectores          -> status dos conectores MCP
  - billing             -> faturas / licenca anual (admin)
  - suporte             -> chamados tecnicos
  - auditoria           -> rastreabilidade LGPD (admin)
"""
from __future__ import annotations

from flask import (
    Blueprint, request, redirect, url_for, session, flash, current_app, jsonify, make_response,
)
import json
import os
import urllib.parse
from . import db, auth, templates, sso
from .db import listar_areas
from . import memory
from . import agente as agente_mod

bp = Blueprint("portal", __name__, url_prefix="/portal")


def _user() -> dict | None:
    if not session.get("user_id"):
        return None
    return {
        "id": session["user_id"],
        "nome": session.get("user_nome", ""),
        "papel": session.get("user_papel", ""),
        "login": session.get("user_login", ""),
    }


def _opts_cliente(sel: int | None = None) -> str:
    """Options de cliente para selects; default = PRIMEIRA empresa cadastrada.

    Modelo on-premise (1 empresa por instalacao): nunca deixar o form sem
    selecao — a primeira empresa ja vem marcada. Se sel for passado (ex:
    filtro ou edicao), marca o valor informado.
    """
    clientes = db.listar_clientes()
    if not clientes:
        return ""
    alvo = sel if sel else clientes[0]["id"]
    return "".join(
        f'<option value="{c["id"]}" {"selected" if c["id"] == alvo else ""}>{c["nome"]}</option>'
        for c in clientes
    )


# ---------------------------------------------------------------------------
# Autenticacao
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
@auth.rate_limit_login
def login():
    # ── Primeiro acesso: sem nenhum admin, o portal vira setup inicial ──
    # O cliente cadastra a propria empresa + administrador (nada de demo fixo).
    setup = not db.existe_admin()
    if setup and request.method == "POST" and request.form.get("_acao") == "setup":
        emp_nome = request.form.get("empresa_nome", "").strip()
        emp_codigo = request.form.get("empresa_codigo", "").strip().lower()
        emp_razao = request.form.get("empresa_razao", "").strip()
        emp_email = request.form.get("empresa_email", "").strip()
        adm_nome = request.form.get("admin_nome", "").strip()
        adm_login = request.form.get("admin_login", "").strip()
        adm_senha = request.form.get("admin_senha", "")
        if not (emp_nome and emp_codigo and adm_nome and adm_login and adm_senha):
            flash("Preencha todos os campos obrigatórios (*).", "warn")
        elif len(adm_senha) < 6:
            flash("Senha do administrador deve ter ao menos 6 caracteres.", "warn")
        else:
            try:
                cid = db.criar_cliente(emp_codigo, emp_nome, emp_razao or emp_nome, emp_email)
                db.criar_usuario(cid, adm_nome, adm_login, adm_senha, "admin", "operacoes")
                user = db.autenticar(adm_login, adm_senha)
                if not user:
                    flash("Erro ao autenticar o admin recém-criado.", "bad")
                    return redirect(url_for("portal.login"))
                auth.fazer_login(user)
                db.registrar_auditoria(
                    user["login"], "admin", "setup_inicial",
                    alvo=emp_nome, cliente_id=cid, ip=request.remote_addr,
                    detalhe="primeiro acesso: empresa + admin inicial",
                )
                flash("Empresa e administrador inicial criados. Bem-vindo!", "ok")
                return redirect(url_for("portal.monitorar"))
            except Exception as e:  # noqa: BLE001
                flash(f"Erro ao criar: {e}", "bad")
    if request.method == "POST":
        login_ = request.form.get("login", "").strip()
        senha = request.form.get("senha", "")
        user = db.autenticar(login_, senha)
        if user:
            auth.fazer_login(user)
            db.registrar_auditoria(
                user["login"], user["papel"], "login",
                ip=request.remote_addr, detalhe="acesso ao portal",
            )
            flash("Bem-vindo ao Portal BlueShift.", "ok")
            return redirect(url_for("portal.monitorar"))
        flash("Login ou senha inválidos.", "bad")
    if _user():
        return redirect(url_for("portal.monitorar"))
    # Aviso de privacidade (LGPD)
    lgpd_cfg = db.carregar_lgpd_config()
    aviso_html = ""
    if lgpd_cfg.get("aviso_privacidade") == "1":
        aviso_texto = lgpd_cfg.get("aviso_texto", "").strip()
        if aviso_texto:
            aviso_html = f'<div class="card" style="max-width:380px;margin-bottom:12px;font-size:12px;background:var(--code-bg);border-color:var(--line-soft)"><span class="muted">{templates.h(aviso_texto)}</span></div>'
    if setup:
        content = f"""
    {aviso_html}<div class="card" style="max-width:420px">
      <h3 style="margin-top:0">Configuração inicial</h3>
      <p class="muted" style="font-size:12px">Bem-vindo ao BlueShift! Cadastre a <b>empresa</b> e o <b>administrador inicial</b> — os demais usuários podem ser criados depois na tela Usuários.</p>
      <form method="post">
        {templates.csrf_field()}<input type="hidden" name="_acao" value="setup">
        <label>Nome da empresa *</label><input name="empresa_nome" placeholder="ex: XPTO Seguros" autofocus>
        <label>Código *</label><input name="empresa_codigo" placeholder="ex: xpto" style="text-transform:lowercase">
        <div class="form-row">
          <div><label>Razão social</label><input name="empresa_razao" placeholder="XPTO Seguro S/A"></div>
          <div><label>E-mail de contato</label><input name="empresa_email" placeholder="ti@empresa.com.br"></div>
        </div>
        <div class="form-row">
          <div><label>Nome do admin *</label><input name="admin_nome" placeholder="Nome completo"></div>
          <div><label>Login do admin *</label><input name="admin_login" placeholder="admin"></div>
        </div>
        <label>Senha do admin *</label><input name="admin_senha" type="password" placeholder="mínimo 6 caracteres">
        <div style="margin-top:16px">
          <button class="btn" type="submit">Criar empresa e acessar</button>
        </div>
      </form>
    </div>"""
    else:
        content = f"""
    {aviso_html}<div class="card" style="max-width:380px">
      <h3 style="margin-top:0">Acesso ao Portal</h3>
      <form method="post">
        {templates.csrf_field()}<label>Login</label>
        <input name="login" placeholder="admin" autofocus>
        <label>Senha</label>
        <input name="senha" type="password" placeholder="••••••">
        <div style="margin-top:16px">
          <button class="btn" type="submit">Entrar</button>
        </div>
      </form>
      <p class="muted" style="margin-top:14px;font-size:12px">
        &nbsp;</p>
      <hr style="margin:18px 0;border-color:var(--line-soft)">
      <a class="btn btn-sso" href="/portal/sso/login">Entrar com SSO (OIDC)</a>
      <p class="muted" style="margin-top:10px;font-size:11px">Login federado via provedor OIDC (Azure AD, Okta, Keycloak, Google).</p>
    </div>"""
    return templates.page("Login", content, active="", show_nav=False)


@bp.route("/logout")
def logout():
    auth.fazer_logout()
    return redirect(url_for("portal.login"))


# ---------------------------------------------------------------------------
# SSO (OIDC) — Login federado. Mantem o login LOCAL intacto.
# ---------------------------------------------------------------------------

@bp.route("/sso/login")
def sso_login():
    """Inicia o fluxo OIDC: redireciona para o authorize (ou mock dev)."""
    if not sso.esta_ativo():
        flash("SSO nao esta configurado/ativo neste portal.", "bad")
        return redirect(url_for("portal.login"))
    redirect_uri = url_for("portal.sso_callback", _external=True)
    return redirect(sso.build_auth_url(redirect_uri))


@bp.route("/sso/callback")
def sso_callback():
    """Recebe o code do IdP, troca por identidade, mapeia usuario e loga."""
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        flash("Fluxo SSO interrompido (sem code).", "bad")
        return redirect(url_for("portal.login"))
    try:
        redirect_uri = url_for("portal.sso_callback", _external=True)
        claims = sso.verificar_e_extrair(code, redirect_uri)
        user = sso.mapear_usuario(claims)
        if not user.get("ativo"):
            flash("Usuario SSO desativado.", "bad")
            return redirect(url_for("portal.login"))
        auth.fazer_login(user)
        db.registrar_auditoria(
            user["login"], user["papel"], "login_sso",
            ip=request.remote_addr, detalhe="acesso via SSO (OIDC)",
        )
        flash("Bem-vindo via SSO.", "ok")
        return redirect(url_for("portal.monitorar"))
    except ValueError as e:
        flash(f"SSO: {e}", "bad")
        return redirect(url_for("portal.login"))
    except Exception as e:  # noqa: BLE001
        flash(f"Erro no SSO: {e}", "bad")
        return redirect(url_for("portal.login"))


@bp.route("/sso/mock_authorize")
def sso_mock_authorize():
    """Mock do IdP (dev mode): tela que 'autentica' e volta com code."""
    if not sso.esta_ativo() or not sso.carregar_config().get("dev_mode"):
        return "SSO mock indisponivel (dev_mode off).", 404
    code = "dev:devuser:dev@blueshift.local:Usuario Dev SSO:usuario"
    params = {k: request.args.get(k, "") for k in ("state", "redirect_uri", "nonce")}
    redirect_uri = params["redirect_uri"] or url_for("portal.sso_callback", _external=True)
    sep = "&" if "?" in redirect_uri else "?"
    return redirect(f"{redirect_uri}{sep}code={urllib.parse.quote(code)}&state={params['state']}")


@bp.route("/sso/config", methods=["GET", "POST"])
@auth.admin_required
def sso_config():
    """Admin configura o provedor SSO (ligar/desligar, issuer, client, dev_mode)."""
    if request.method == "POST":
        ativo = 1 if request.form.get("ativo") else 0
        dev_mode = 1 if request.form.get("dev_mode") else 0
        db.salvar_sso_config(
            ativo=ativo,
            dev_mode=dev_mode,
            issuer=request.form.get("issuer", "").strip(),
            client_id=request.form.get("client_id", "").strip(),
            client_secret=request.form.get("client_secret", "").strip(),
            redirect_uri=request.form.get("redirect_uri", "").strip(),
            dominio_admin=request.form.get("dominio_admin", "").strip(),
            auto_criar=1 if request.form.get("auto_criar") else 0,
        )
        flash("Configuracao de SSO salva.", "ok")
        return redirect(url_for("portal.sso_config"))
    cfg = db.buscar_sso_config() or {}
    content = templates.form_sso_config(cfg)
    return templates.page("Configurar SSO", content, active="sso", user=_user())


# ---------------------------------------------------------------------------
# MONITORAR (dashboard de saude)
# ---------------------------------------------------------------------------

@bp.route("/")
@bp.route("/monitorar")
@auth.login_required
def monitorar():
    clientes = db.listar_clientes()
    total_clientes = len(clientes)
    total_usuarios = len(db.listar_usuarios())
    agentes = db.listar_agentes()
    total_agentes = len(agentes)
    total_conectores = len(db.listar_conectores())
    total_modelos = len(db.listar_modelos())
    total_canais = len(db.listar_canais())
    total_docs = len(db.listar_documentos())
    total_memorias = len(db.listar_memorias())
    uso = db.agregar_uso_por_cliente()
    total_tokens = sum(r["total_tokens"] for r in uso) if uso else 0
    total_chamadas_llm = sum(r["chamadas"] for r in uso) if uso else 0

    # cards de saude por cliente
    cards = ""
    for c in clientes:
        h = db.buscar_health(c["id"]) or {}
        conns = db.listar_conectores(c["id"])
        online = sum(1 for k in conns if k["status"] == "online")
        off = len(conns) - online
        n_ag = sum(1 for a in agentes if a["cliente_id"] == c["id"])
        # tokens reais do cliente (uso_tokens)
        uso_c = db.agregar_uso_por_cliente(c["id"])
        tokens_reais = sum(r["total_tokens"] for r in uso_c) if uso_c else 0
        chamadas_reais = sum(r["chamadas"] for r in uso_c) if uso_c else 0
        cards += f"""
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong>{c['nome']}</strong>
            {templates.badge(c['status'])}
          </div>
          <div class="muted" style="font-size:12px;margin:4px 0 10px">código: {c['codigo']} · {n_ag} agente(s) · {chamadas_reais} chamada(s) LLM</div>
          <div class="grid grid-2" style="gap:10px">
            <div><div class="muted" style="font-size:11px">Container</div>{templates.badge(h.get('container','-'))}</div>
            <div><div class="muted" style="font-size:11px">Modelo local</div>{templates.badge(h.get('modelo_local','-'))}</div>
            <div><div class="muted" style="font-size:11px">Latência</div><b>{h.get('latencia_ms',0)} ms</b></div>
            <div><div class="muted" style="font-size:11px">Tokens</div><b>{tokens_reais:,}</b></div>
          </div>
          <div style="margin-top:10px;font-size:12px" class="muted">
            Conectores: {online} online / {off} offline ·
            Erros 24h: <b style="color:var(--{'bad' if h.get('erros_24h',0) else 'txt'})">{h.get('erros_24h',0)}</b>
          </div>
        </div>"""

    kpis = f"""
    <div class="grid grid-4" style="margin-bottom:18px">
      <div class="kpi"><div class="label">Clientes</div><div class="value">{total_clientes}</div><div class="sub">na plataforma</div></div>
      <div class="kpi"><div class="label">Usuários</div><div class="value">{total_usuarios}</div><div class="sub">cadastrados</div></div>
      <div class="kpi"><div class="label">Agentes</div><div class="value">{total_agentes}</div><div class="sub">operando</div></div>
      <div class="kpi"><div class="label">Modelos IA</div><div class="value">{total_modelos}</div><div class="sub">cadastrados</div></div>
      <div class="kpi"><div class="label">Conectores</div><div class="value">{total_conectores}</div><div class="sub">MCP expostos</div></div>
      <div class="kpi"><div class="label">Canais</div><div class="value">{total_canais}</div><div class="sub">API/webhook</div></div>
      <div class="kpi"><div class="label">Tokens</div><div class="value">{total_tokens:,}</div><div class="sub">processados</div></div>
      <div class="kpi"><div class="label">Documentos</div><div class="value">{total_docs + total_memorias}</div><div class="sub">RAG + memórias</div></div>
    </div>"""

    content = kpis + '<div class="grid grid-2" style="margin-top:6px">' + cards + "</div>"
    if not clientes:
        content += '<div class="empty">Nenhum cliente cadastrado ainda. <a class="btn" href="/portal/clientes">Cadastrar cliente</a></div>'
    return templates.page("Monitorar", content, active="monitorar", user=_user())


# --------------------------------------------------------------------------- #
# WORKSPACE POR DEPARTAMENTO (PRD §8-D: segmentação por área da empresa)
# AREAS — via db.listar_areas() (env BLUESHIFT_AREAS)


def _fmt_tokens(n: int) -> str:
    """Formato compacto de tokens: 682k / 1.2M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


@bp.route("/workspace")
@auth.login_required
def workspace():
    u = _user()
    papel = u["papel"]
    area_usuario = auth.area_atual()

    # Admin vê todas as áreas por padrão; gestor/usuario fica preso na própria área.
    if papel == "admin":
        area_sel = request.args.get("area", "")
    else:
        area_sel = area_usuario  # não-admin não pode trocar de área

    if area_sel:
        agentes = [a for a in db.listar_agentes() if (a["area"] or "") == area_sel]
    else:
        agentes = db.listar_agentes()

    # conhecimento do cliente (RAG já é por cliente); sem área no doc, mostra tudo
    docs = db.listar_documentos()

    # tokens por agente (periodo igual da Observabilidade: 1d/7d/30d/90d)
    dias = request.args.get("dias", 7, type=int)
    if dias not in (1, 7, 30, 90):
        dias = 7
    tokens_por_agente = db.somar_tokens_por_agente(dias)

    # métricas da área
    n_agentes = len(agentes)
    n_docs = len(docs)
    n_usuarios_area = len([x for x in db.listar_usuarios() if (x["area"] or "") == area_sel]) if area_sel else len(db.listar_usuarios())

    sel = ""
    if papel == "admin":
        opts = "".join(
            f'<option value="{a}"{" selected" if a == area_sel else ""}>{a}</option>'
            for a in listar_areas()
        )
        sel = f'<form method="get" style="margin-bottom:14px"><label>Área</label><select name="area" onchange="this.form.submit()"><option value="">todas</option>{opts}</select></form>'

    cards_agentes = ""
    for a in agentes:
        _conns = [{"nome": c["nome"], "tipo": c["tipo"]}
                  for c in db.listar_conectores(cliente_id=a.get("cliente_id"), area=a.get("area") or "")]
        _fluxo = json.dumps({
            "id": a["id"], "nome": a["nome"],
            "modelo": a.get("modelo") or "-",
            "fallback": a.get("modelo_secundario") or "",
            "skills": [s.strip() for s in (a.get("skills") or "").split(",") if s.strip()],
            "conectores": _conns,
        }, ensure_ascii=False)
        cards_agentes += f"""
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong>{a['nome']}</strong>{templates.badge(a['status'])}</div>
          <div class="muted" style="font-size:12px;margin:6px 0">modelo {a['modelo']} · skills [{a['skills'] or '-'}] · ⚡ {_fmt_tokens(tokens_por_agente.get(a['id'], 0))} tokens ({dias}d)</div>
          <div style="display:flex;gap:8px">
            <a class="btn ghost" href="/portal/agentes/{a['id']}/testar">testar agente</a>
            <button class="btn ghost" type="button" onclick='abrirFluxo({_fluxo})' title="Ver o fluxo de execução do agente">fluxo</button>
          </div>
        </div>"""

    kpis = f"""
    <div class="grid grid-4">
      <div class="kpi"><div class="label">Área</div><div class="value" style="font-size:18px;text-transform:capitalize">{area_sel or 'todas'}</div></div>
      <div class="kpi"><div class="label">Agentes</div><div class="value">{n_agentes}</div><div class="sub">da área</div></div>
      <div class="kpi"><div class="label">Usuários</div><div class="value">{n_usuarios_area}</div><div class="sub">na área</div></div>
      <div class="kpi"><div class="label">Base de conhecimento</div><div class="value">{n_docs}</div><div class="sub">documentos</div></div>
    </div>"""

    content = kpis + sel + (
        f'<div class="muted" style="margin:4px 0 10px;font-size:12px">Tokens por agente — últimos {dias} dias. '
        f'[<a href="?area={area_sel}&dias=1">1d</a> | <a href="?area={area_sel}&dias=7">7d</a> | '
        f'<a href="?area={area_sel}&dias=30">30d</a> | <a href="?area={area_sel}&dias=90">90d</a>]</div>'
    ) + ('<div class="grid grid-2" style="margin-top:16px">' + cards_agentes + "</div>"
              if cards_agentes else
              '<div class="empty">Nenhum agente nesta área ainda.</div>')
    if not area_sel and papel != "admin":
        content += '<div class="muted" style="margin-top:10px">Você não está vinculado a nenhuma área — peça ao admin para definir sua área no cadastro de usuário.</div>'
    return templates.page("Workspace", content, active="workspace", user=_user())


# --------------------------------------------------------------------------- #


# ---------------------------------------------------------------------------
# CLIENTES (gerenciar + cadastrar)
# ---------------------------------------------------------------------------

@bp.route("/clientes")
@auth.login_required
def clientes():
    # On-premise: teoricamente 1 cliente por instalacao — sem paginacao,
    # lista completa na tela (nao faz sentido paginar/limitar).
    rows = db.listar_clientes()

    body = ""
    for c in rows:
        n_user = len(db.listar_usuarios(c["id"]))
        n_age = len(db.listar_agentes(c["id"]))
        body += f"""<tr>
          <td><b>{c['nome']}</b><div class="muted" style="font-size:12px">{c['empresa'] or ''}</div></td>
          <td>{c['codigo']}</td>
          <td>{c['email'] or '-'}</td>
          <td>{templates.badge(c['status'])}</td>
          <td>{n_user} usu · {n_age} agentes</td>
          <td class="row-actions">
            <a href="{url_for('portal.cliente_editar', cid=c['id'])}">editar</a>
            <a href="{url_for('portal.cliente_alternar', cid=c['id'], acao='suspenso' if c['status']=='ativo' else 'ativo')}">
              {'suspender' if c['status']=='ativo' else 'ativar'}</a>
          </td></tr>"""

    tabela = f"""<table><thead><tr><th>Cliente</th><th>Código</th><th>Email</th><th>Status</th><th>Composição</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=6 class="empty">Nenhum cliente.</td></tr>'}</tbody></table>"""
    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Gerencie e cadastre os clientes da plataforma.</div>
      <a class="btn" href="{url_for('portal.cliente_novo')}">+ Cadastrar cliente</a>
    </div>
    <div class="muted" style="font-size:13px;margin-bottom:8px">{len(rows)} cliente(s) cadastrado(s)</div>
    {tabela}"""
    return templates.page("Clientes", content, active="clientes", user=_user())


@bp.route("/clientes/novo", methods=["GET", "POST"])
@auth.admin_required
def cliente_novo():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        nome = request.form.get("nome", "").strip()
        if not codigo or not nome:
            flash("Código e nome são obrigatórios.", "warn")
        else:
            db.criar_cliente(
                codigo, nome,
                request.form.get("empresa", ""),
                request.form.get("email", ""),
                request.form.get("licenca", "anual_por_empresa"),
            )
            u = _user()
            db.registrar_auditoria(u["login"], u["papel"], "criar_cliente", alvo=nome,
                                   ip=request.remote_addr)
            flash(f"Cliente '{nome}' cadastrado.", "ok")
            return redirect(url_for("portal.clientes"))
    content = """
    <div class="card" style="max-width:640px">
      <h3 style="margin-top:0">Cadastrar cliente</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Código *</label><input name="codigo" placeholder="ex: xpto"></div>
          <div><label>Nome *</label><input name="nome" placeholder="ex: XPTO Seguros"></div>
        </div>
        <div class="form-row">
          <div><label>Empresa</label><input name="empresa"></div>
          <div><label>Email de contato</label><input name="email" type="email"></div>
        </div>
        <div class="form-row">
          <div><label>Plano de licença</label>
            <select name="licenca">
              <option value="anual_por_empresa">Anual por empresa</option>
              <option value="anual_por_empresa_plus">Anual + modelo externo</option>
            </select></div>
          <div></div>
        </div>
        <p class="muted" style="font-size:11px;margin-top:6px">O plano é o tipo contratado (registro). A <b>chave de ativação</b> da plataforma é definida na instalação, na variável <code>BLUESHIFT_LICENSE</code> — consulte a tela Atualizações para ver o status.</p>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar cliente</button>
          <a class="btn ghost" href="/portal/clientes">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Cadastrar cliente", content, active="clientes", user=_user())


@bp.route("/clientes/<int:cid>/editar", methods=["GET", "POST"])
@auth.admin_required
def cliente_editar(cid: int):
    c = db.buscar_cliente(cid)
    if not c:
        flash("Cliente não encontrado.", "bad")
        return redirect(url_for("portal.clientes"))
    if request.method == "POST":
        db.atualizar_cliente(
            cid,
            codigo=request.form.get("codigo", c["codigo"]),
            nome=request.form.get("nome", c["nome"]),
            empresa=request.form.get("empresa", c["empresa"]),
            email=request.form.get("email", c["email"]),
            licenca=request.form.get("licenca", c["licenca"]),
            status=request.form.get("status", c["status"]),
        )
        u = _user()
        db.registrar_auditoria(u["login"], u["papel"], "editar_cliente", alvo=c["nome"],
                               cliente_id=cid, ip=request.remote_addr)
        flash("Cliente atualizado.", "ok")
        return redirect(url_for("portal.clientes"))
    content = f"""
    <div class="card" style="max-width:640px">
      <h3 style="margin-top:0">Editar cliente #{cid}</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Código</label><input name="codigo" value="{c['codigo']}"></div>
          <div><label>Nome</label><input name="nome" value="{c['nome']}"></div>
        </div>
        <div class="form-row">
          <div><label>Empresa</label><input name="empresa" value="{c['empresa'] or ''}"></div>
          <div><label>Email</label><input name="email" value="{c['email'] or ''}"></div>
        </div>
        <div class="form-row">
          <div><label>Plano de licença</label>
            <select name="licenca">
              <option value="anual_por_empresa" {'selected' if c['licenca']=='anual_por_empresa' else ''}>Anual por empresa</option>
              <option value="anual_por_empresa_plus" {'selected' if c['licenca']=='anual_por_empresa_plus' else ''}>Anual + modelo externo</option>
            </select></div>
          <div><label>Status</label>
            <select name="status">
              <option value="ativo" {'selected' if c['status']=='ativo' else ''}>Ativo</option>
              <option value="suspenso" {'selected' if c['status']=='suspenso' else ''}>Suspenso</option>
              <option value="expirado" {'selected' if c['status']=='expirado' else ''}>Expirado</option>
            </select></div>
        </div>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/clientes">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Editar cliente", content, active="clientes", user=_user())


@bp.route("/clientes/<int:cid>/<acao>")
@auth.admin_required
def cliente_alternar(cid: int, acao: str):
    if acao in ("ativo", "suspenso", "expirado"):
        db.atualizar_cliente(cid, status=acao)
        u = _user()
        db.registrar_auditoria(u["login"], u["papel"], "alterar_status_cliente",
                               alvo=acao, cliente_id=cid, ip=request.remote_addr)
        flash(f"Cliente {acao}.", "ok")
    return redirect(url_for("portal.clientes"))


# ---------------------------------------------------------------------------
# USUÁRIOS (gerenciar + cadastrar)
# ---------------------------------------------------------------------------

@bp.route("/usuarios")
@auth.login_required
def usuarios():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    rows = db.listar_usuarios()
    body = ""
    for u in rows:
        body += f"""<tr>
          <td><b>{u['nome']}</b></td>
          <td>{u['login']}</td>
          <td>{templates.badge(u['papel'])}</td>
          <td>{u['area'] or '-'}</td>
          <td>{clientes.get(u['cliente_id'], '?')}</td>
          <td>{templates.badge('ativo' if u['ativo'] else 'suspenso')}</td>
          <td class="row-actions">
            <a href="/portal/usuarios/{u['id']}/editar">editar</a>
            <a href="/portal/usuarios/{u['id']}/suspender" onclick="return confirm('Confirmar?')">{'suspender' if u['ativo'] else 'reativar'}</a>
          </td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Nome</th><th>Login</th><th>Papel</th><th>Área</th><th>Cliente</th><th>Status</th><th>Ações</th></tr></thead>
      <tbody>{body or '<tr><td colspan=7 class="empty">Nenhum usuário.</td></tr>'}</tbody></table>"""
    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Usuários com acesso à plataforma (papéis: admin, gestor, usuário, sistema).</div>
      <a class="btn" href="/portal/usuarios/novo">+ Cadastrar usuário</a>
    </div>{tabela}"""
    return templates.page("Usuários", content, active="usuarios", user=_user())


@bp.route("/usuarios/novo", methods=["GET", "POST"])
@auth.admin_required
def usuario_novo():
    clientes = db.listar_clientes()
    if request.method == "POST":
        cid = int(request.form.get("cliente_id", 0))
        nome = request.form.get("nome", "").strip()
        login = request.form.get("login", "").strip()
        senha = request.form.get("senha", "").strip()
        if not (cid and nome and login and senha):
            flash("Cliente, nome, login e senha são obrigatórios.", "warn")
        else:
            db.criar_usuario(cid, nome, login, senha,
                             request.form.get("papel", "usuario"),
                             request.form.get("area", ""))
            u = _user()
            db.registrar_auditoria(u["login"], u["papel"], "criar_usuario", alvo=login,
                                   cliente_id=cid, ip=request.remote_addr)
            flash(f"Usuário '{login}' criado.", "ok")
            return redirect(url_for("portal.usuarios"))
    opts = _opts_cliente()
    content = f"""
    <div class="card" style="max-width:640px">
      <h3 style="margin-top:0">Cadastrar usuário</h3>
      <form method="post">
        {templates.csrf_field()}<label>Cliente</label><select name="cliente_id">{opts}</select>
        <div class="form-row">
          <div><label>Nome</label><input name="nome"></div>
          <div><label>Login</label><input name="login"></div>
        </div>
        <div class="form-row">
          <div><label>Senha</label><input name="senha" type="password"></div>
          <div><label>Área</label>
            <select name="area"><option value="">--</option><option>vendas</option><option>suporte</option><option>financeiro</option><option>rh</option><option>operacoes</option></select></div>
        </div>
        <label>Papel</label>
        <select name="papel">
          <option value="usuario">Usuário</option>
          <option value="gestor">Gestor</option>
          <option value="admin">Administrador</option>
          <option value="sistema">Sistema (API/MCP)</option>
        </select>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/usuarios">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Cadastrar usuário", content, active="usuarios", user=_user())


@bp.route("/usuarios/<int:uid>/editar", methods=["GET", "POST"])
@auth.admin_required
def usuario_editar(uid: int):
    u = db.buscar_usuario(uid)
    if not u:
        flash("Usuário não encontrado.", "bad")
        return redirect(url_for("portal.usuarios"))
    if request.method == "POST":
        campos = {}
        for k in ("nome", "login", "papel"):
            v = request.form.get(k, "").strip()
            if v: campos[k] = v
        area = request.form.get("area", "").strip()
        if area is not None: campos["area"] = area
        senha = request.form.get("senha", "").strip()
        if senha: campos["senha"] = db._hash_senha(senha)
        if campos: db.atualizar_usuario(uid, **campos)
        db.registrar_auditoria(_user()["login"], "admin", "editar_usuario", alvo=u["nome"], ip=request.remote_addr)
        flash("Usuário atualizado.", "ok")
        return redirect(url_for("portal.usuarios"))
    areas_opts = "".join(f'<option value="{a}" {"selected" if a==u.get("area","") else ""}>{a}</option>' for a in listar_areas())
    papel_opts = "".join(f'<option value="{p}" {"selected" if p==u["papel"] else ""}>{p.title()}</option>' for p in ["admin","gestor","usuario","sistema"])
    content = f"""
    <div class="card" style="max-width:600px">
      <h3 style="margin-top:0">Editar usuário: {u['nome']}</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Nome</label><input name="nome" value="{u['nome']}"></div>
          <div><label>Login</label><input name="login" value="{u['login']}"></div>
        </div>
        <div class="form-row">
          <div><label>Nova senha</label><input name="senha" type="password" placeholder="Deixar em branco p/ manter"></div>
          <div><label>Área</label><select name="area"><option value="">--</option>{areas_opts}</select></div>
        </div>
        <label>Papel</label>
        <select name="papel">{papel_opts}</select>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/usuarios">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page(f"Editar {u['nome']}", content, active="usuarios", user=_user())


@bp.route("/usuarios/<int:uid>/suspender")
@auth.admin_required
def usuario_suspender(uid: int):
    u = db.buscar_usuario(uid)
    if not u:
        flash("Usuário não encontrado.", "bad")
        return redirect(url_for("portal.usuarios"))
    novo_status = 0 if u["ativo"] else 1
    db.atualizar_usuario(uid, ativo=novo_status)
    db.registrar_auditoria(_user()["login"], "admin",
                           "ativar_usuario" if novo_status else "suspender_usuario",
                           alvo=u["nome"], ip=request.remote_addr)
    flash(f"Usuário {'ativado' if novo_status else 'suspenso'}.", "ok")
    return redirect(url_for("portal.usuarios"))



# ---------------------------------------------------------------------------
# AGENTES (Agent Factory: gerenciar + cadastrar)
# ---------------------------------------------------------------------------

@bp.route("/agentes")
@auth.login_required
def agentes():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    rows = db.listar_agentes()
    body = ""
    for a in rows:
        sec = a.get("modelo_secundario_id")
        modelo_sec_txt = ""
        if sec:
            m2 = db.buscar_modelo(sec)
            modelo_sec_txt = f" → fallback: {m2['nome']}" if m2 else ""
        body += f"""<tr>
          <td><b>{a['nome']}</b></td>
          <td>{a['area'] or '-'}</td>
          <td>{a['modelo']}{modelo_sec_txt}</td>
          <td>{a['skills'] or '-'}</td>
          <td><a href="/portal/conectores?area={a['area'] or ''}" class="muted" style="font-size:12px;text-decoration:none">{a['area'] and '🔌 ver' or '-'}</a></td>
          <td>{templates.badge(a['status'])}</td>
          <td>{clientes.get(a['cliente_id'], '?')}</td>
          <td class="row-actions">
            <a href="/portal/agentes/{a['id']}/testar">testar</a>
            <a href="/portal/agentes/{a['id']}/editar">editar</a>
            <a href="/portal/agentes/{a['id']}/excluir" onclick="return confirm('Excluir agente {a['nome']}?')" style="color:var(--bad)">excluir</a>
          </td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Agente</th><th>Área</th><th>Modelo</th><th>Skills</th><th>Conectores (área)</th><th>Status</th><th>Cliente</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=8 class="empty">Nenhum agente.</td></tr>'}</tbody></table>"""

    # ── Checklist contextual: o que o agente precisa (em ordem de config) ──
    from . import agente as agente_mod
    n_modelos = len(db.listar_modelos())
    try:
        n_skills = len(agente_mod.listar_skills())
    except Exception:  # noqa: BLE001
        n_skills = 0
    n_conn = len(db.listar_conectores())
    chk_modelo = (f'<span class="badge ok">✓ Modelo IA ({n_modelos})</span>' if n_modelos
                  else '<a class="badge warn" href="/portal/modelos" style="text-decoration:none">✗ Modelo IA — cadastre aqui</a>')
    chk_skills = (f'<span class="badge neutral">Skills: {n_skills}</span>' if n_skills
                  else '<span class="muted" style="font-size:12px">Skills: opcional</span>')
    chk_conn = (f'<span class="badge neutral">Conectores: {n_conn}</span>' if n_conn
                else '<span class="muted" style="font-size:12px">Conectores: opcional</span>')
    aviso = ""
    if n_modelos == 0:
        aviso = ('<div class="flash warn" style="margin-bottom:12px">⚠️ Nenhum modelo de IA cadastrado. '
                 '<b>Comece por aqui:</b> cadastre um modelo em <a href="/portal/modelos">Modelos IA</a> '
                 '— sem ele os agentes não têm de onde responder.</div>')
    checklist = (f'<div style="font-size:12px;margin-bottom:12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">'
                 f'{chk_modelo} {chk_skills} {chk_conn} '
                 '<span class="muted" style="font-size:11px">— o que o agente precisa, na ordem de configuração</span></div>')

    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Agent Factory: monte agentes a partir do catálogo de skills + conectores MCP + modelo de IA.</div>
      <a class="btn" href="/portal/agentes/novo">+ Montar agente</a>
    </div>
    {aviso}
    {checklist}
    {tabela}"""
    return templates.page("Agentes", content, active="agentes", user=_user())


def _resposta_html(texto: str) -> str:
    """Converte a resposta em HTML: escapa tudo e transforma a imagem
    data-URI (grafico gerado) em <img> renderizavel."""
    import re as _re
    def _img(m):
        return (f'<img src="data:image/png;base64,{m.group(1)}" '
                'style="max-width:100%;border-radius:8px;margin:6px 0">')
    return _re.sub(
        r"!\[[^\]]*\]\(data:image/png;base64,([A-Za-z0-9+/=]+)\)",
        _img, templates.h(texto or ""))


@bp.route("/agentes/<int:aid>/testar", methods=["GET", "POST"])
@auth.login_required
def agente_testar(aid: int):
    from . import agente as agente_mod
    a = db.buscar_agente(aid)
    if not a:
        flash("Agente não encontrado.", "warn")
        return redirect(url_for("portal.agentes"))
    u = _user()
    resposta = None
    contexto = []
    ferramentas = []
    erro = None
    fallback_usado = False
    trace_id = None
    if request.method == "POST":
        pergunta = request.form.get("pergunta", "").strip()
        if pergunta:
            out = agente_mod.responder(a, pergunta, u["login"])
            fallback_usado = out.get("model_fallback", False)
            trace_id = out.get("trace_id")
            if out["ok"]:
                resposta = out["content"]
                contexto = out["contexto"]
                ferramentas = out.get("ferramentas", [])
                db.registrar_auditoria(u["login"], u["papel"], "testar_agente", alvo=a["nome"],
                                       cliente_id=a["cliente_id"], ip=request.remote_addr,
                                       detalhe=pergunta[:80] + (" [fallback]" if fallback_usado else ""))
            else:
                erro = out["error"]
    ctx_html = ""
    if contexto:
        ctx_html = "<div class=\"muted\" style=\"margin:10px 0;font-size:13px\"><b>Contexto RAG recuperado:</b><ul style=\"margin:6px 0 0 18px\">" + \
            "".join(f"<li>{c['texto'][:140]}</li>" for c in contexto) + "</ul></div>"
    fer_html = ""
    if ferramentas:
        itens = []
        for f in ferramentas:
            if "erro" in f:
                itens.append(f"<li><b>{f.get('conector','?')}</b>: erro {f['erro']}</li>")
            else:
                itens.append(f"<li><b>{f.get('conector')}.{f.get('tool')}</b> {f.get('args')} → "
                             f"<code>{f.get('resultado')}</code></li>")
        fer_html = "<div class=\"muted\" style=\"margin:10px 0;font-size:13px\"><b>Dados de sistema (conectores externos executados):</b><ul style=\"margin:6px 0 0 18px\">" + \
            "".join(itens) + "</ul></div>"
    area = a["area"] or ""
    conn_count = len(db.listar_conectores(cliente_id=a["cliente_id"], area=area)) if area else 0
    conn_info = f"{conn_count} conector(es) da área" if conn_count else "sem conectores configurados para esta área"
    badge_fallback = ' <span class=\"badge warn\">⚡ fallback de modelo</span>' if fallback_usado else ""
    badge_lgpd = ' <span class=\"badge info\">🔒 Anonimizado</span>' if a.get("lgpd_ativado", 1) else ' <span class=\"badge neutral\">🔓 Sem anonimizacao</span>'
    badge_rastreio = f' <a href=\"#\" onclick=\"abrirRastreio({trace_id});return false\" style=\"font-size:12px;margin-left:8px\">🔍 Rastreio</a>' if trace_id else ''
    # Feedback script (evita f-string dentro de f-string)
    fb_script = ""
    if trace_id:
        fb_script = '''<script>
      var _tid = ''' + str(trace_id) + ''';
      function enviarFeedback(util){
        var b1=document.getElementById("btn-util");
        var b2=document.getElementById("btn-nao-util");
        var m=document.getElementById("feedback-msg");
        if(b1)b1.disabled=true; if(b2)b2.disabled=true;
        if(m)m.textContent="Enviando...";
        fetch("/portal/api/v1/feedback/"+_tid,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({util:util,tipo:"manual"})})
          .then(function(r){return r.json()})
          .then(function(d){if(m)m.textContent=d.ok?"OK":"Erro";})
          .catch(function(e){if(m)m.textContent="Erro";if(b1)b1.disabled=false;if(b2)b2.disabled=false;});
      }
      </script>'''
    content = f"""
    <div class="muted" style="margin-bottom:10px">
      Teste do agente <b>{a['nome']}</b> (área {area or 'geral'}) — modelo <b>{a['modelo']}</b>,
      skills [{a['skills'] or '-'}], {conn_info}.
    </div>
    <div class="card" style="max-width:760px">
      <form method="post" id="form-agente-test">
        {templates.csrf_field()}<label>Pergunta para o agente</label>
        <textarea name="pergunta" rows="3" placeholder="Ex: qual o status do cliente 123?">{request.form.get("pergunta","")}</textarea>
        <div style="margin-top:12px"><button class="btn btn-spin" id="btn-enviar-agente" type="submit">Enviar ao agente</button></div>
      </form>
      <script>
      document.getElementById('form-agente-test').addEventListener('submit',function(){{
        var b=document.getElementById('btn-enviar-agente');
        b.classList.add('loading');b.disabled=true;b.innerHTML='\u23f3 Processando...';
      }});
      </script>
      {fb_script}
      {ctx_html}
      {fer_html}
      {f'<div class="card" style="margin-top:14px;background:var(--deep)"><b>🤖 {a["nome"]}:</b><div style="margin:8px 0 0">{_resposta_html(resposta)}</div>{badge_lgpd}{badge_fallback}<div style="margin-top:10px;display:flex;gap:8px"><button class="btn ghost" id="btn-util" style="font-size:12px;padding:4px 10px" onclick="enviarFeedback(true)">👍 Util</button><button class="btn ghost" id="btn-nao-util" style="font-size:12px;padding:4px 10px" onclick="enviarFeedback(false)">👎 Nao util</button><span id="feedback-msg" style="font-size:11px;margin-left:8px"></span>{badge_rastreio}</div></div>' if resposta else ''}
      {f'<div class="badge warn" style="margin-top:12px">⚠️ {erro}</div>' if erro else ''}
    </div>
    <div style="margin-top:14px"><a class="btn ghost" href="/portal/agentes">← Voltar</a></div>
    <div class="modal-overlay" id="modal-rastreio" onclick="if(event.target===this)fecharRastreio()">
      <div class="modal-box" style="max-width:960px;width:94%;max-height:85vh;overflow-y:auto">
        <div id="rastreio-conteudo"><p class="muted">Carregando...</p></div>
        <div style="text-align:center;margin-top:14px">
          <button class="btn ghost" onclick="fecharRastreio()">Fechar</button>
        </div>
      </div>
    </div>
    <script>
    function abrirRastreio(tid){{
      document.getElementById('modal-rastreio').classList.add('show');
      document.getElementById('rastreio-conteudo').innerHTML = '<p class="muted">Carregando...</p>';
      fetch('/portal/rastreio/'+tid).then(r=>r.json()).then(d=>{{
        if(!d.ok){{document.getElementById('rastreio-conteudo').innerHTML='<p class="badge bad">Erro: '+d.erro+'</p>';return}}
        var t=d.trace;
        var h='<h3>Rastreio #'+t.id+'</h3><p class="muted">Pergunta: <b>'+t.pergunta+'</b></p><hr>';
        h+='<div style="display:flex;gap:4px;margin-bottom:14px;flex-wrap:wrap">';
        var p=t.params||{{}}; var pk=Object.keys(p);
        var c=t.conectores||[]; var rg=t.rag||[];
        var passos=[
          {{n:1, cor:"#2563eb", rotulo:"Params", detalhe:pk.length?pk.join(", "):"(nenhum)"}},
          {{n:2, cor:"#7c3aed", rotulo:"Conectores", detalhe:c.length?c.length+" exec(s)":"(nenhum)"}},
          {{n:3, cor:"#059669", rotulo:"RAG", detalhe:rg.length?rg.length+" doc(s)":"(vazio)"}},
          {{n:4, cor:"#d97706", rotulo:"Modelo", detalhe:t.modelo+" ("+t.tempo_ms+"ms)"+(t.modelo_fallback?" fallback":"")}},
        ];
        for(var i=0;i<passos.length;i++){{var s=passos[i];
          h+='<div style="flex:1;min-width:120px;background:var(--panel-soft);border-radius:8px;padding:10px;border-left:3px solid '+s.cor+'">';
          h+='<div style="font-size:11px;color:'+s.cor+';font-weight:700">PASSO '+s.n+'</div>';
          h+='<div style="font-size:14px;font-weight:600;margin:2px 0">'+s.rotulo+'</div>';
          h+='<div style="font-size:11px;color:var(--muted-soft)">'+s.detalhe+'</div></div>';
        }}
        h+='</div><hr>';
        h+='<div style="margin-bottom:12px"><b>Detalhamento:</b></div>';
        h+='<div style="margin-bottom:8px;background:var(--code-bg);border-radius:6px;padding:8px"><div style="font-weight:600;color:#2563eb">1. Parametros extraidos</div>';
        h+=pk.length?pk.map(function(k){{return '<code style="background:var(--panel-soft);padding:2px 6px;border-radius:4px">'+k+' = '+p[k]+'</code>'}}).join(' '):'<span class="muted">Nenhum parametro extraido</span>';
        h+='</div>';
        h+='<div style="margin-bottom:8px;background:var(--code-bg);border-radius:6px;padding:8px"><div style="font-weight:600;color:#7c3aed">2. Conectores executados</div>';
        if(c.length){{for(var i=0;i<c.length;i++){{var f=c[i];
          if(f.erro){{h+='<div style="color:var(--bad)"> ERRO '+f.conector+': '+f.erro+'</div>';}}
          else{{h+='<div> OK <b>'+f.conector+'</b>.'+f.tool+'<br><span class="muted" style="font-size:11px">args: '+JSON.stringify(f.args)+' | retorno: '+(f.resultado?f.resultado.length+' registros':'vazio')+'</span></div>';}}
        }}}}else{{h+='<span class="muted">Nenhum conector executado</span>';}}
        h+='</div>';
        h+='<div style="margin-bottom:8px;background:var(--code-bg);border-radius:6px;padding:8px"><div style="font-weight:600;color:#059669">3. RAG (base de conhecimento)</div>';
        h+=rg.length?'<span class="muted">'+rg.map(function(x){{return (x.texto||'').substring(0,80)}}).join(' | ')+'</span>':'<span class="muted">Vazio</span>';
        h+='</div>';
        h+='<div style="margin-bottom:12px;background:var(--code-bg);border-radius:6px;padding:8px"><div style="font-weight:600;color:#d97706">4. Modelo de IA</div>';
        h+='Modelo: <code>'+t.modelo+'</code>'+(t.modelo_fallback?' <span class="badge warn">fallback</span>':'')+' | Tokens: '+(t.tokens?t.tokens.total_tokens||0:0)+' | Tempo: '+t.tempo_ms+'ms';
        h+='</div>';
        h+='<hr><div><b>Resposta:</b></div><pre style="background:var(--code-bg);padding:10px;border-radius:6px;font-size:12px;white-space:pre-wrap;margin:6px 0 0">'+t.resposta+'</pre>';
        document.getElementById('rastreio-conteudo').innerHTML=h;
      }}).catch(e=>{{document.getElementById('rastreio-conteudo').innerHTML='<p class="badge bad">Erro: '+e.message+'</p>'}});
    }}
    function fecharRastreio(){{document.getElementById('modal-rastreio').classList.remove('show');}}
    </script>"""
    return templates.page(f"Testar {a['nome']}", content, active="agentes", user=u)


@bp.route("/agentes/novo", methods=["GET", "POST"])
@auth.admin_required
def agente_novo():
    from . import agente as agente_mod
    clientes = db.listar_clientes()
    modelos = db.listar_modelos()
    skills_disp = agente_mod.listar_skills()
    if request.method == "POST":
        cid = int(request.form.get("cliente_id", 0))
        nome = request.form.get("nome", "").strip()
        modelo_id = request.form.get("modelo_id") or None
        if modelo_id:
            modelo_id = int(modelo_id)
        if not (cid and nome):
            flash("Cliente e nome são obrigatórios.", "warn")
        else:
            skills = ",".join(request.form.getlist("skills"))
            modelo_nome = ""
            if modelo_id:
                m = db.buscar_modelo(modelo_id)
                modelo_nome = m["nome"] if m else ""
            modelo_sec_id = request.form.get("modelo_secundario_id") or None
            if modelo_sec_id:
                modelo_sec_id = int(modelo_sec_id)
            # se secundario igual ao principal, ignora (nao faz sentido)
            if modelo_sec_id == modelo_id:
                modelo_sec_id = None
            db.criar_agente(cid, nome, request.form.get("area", ""), modelo_nome,
                            skills, modelo_id=modelo_id,
                            modelo_secundario_id=modelo_sec_id,
                            lgpd_ativado=1 if request.form.get("lgpd_ativado") else 0)
            u = _user()
            db.registrar_auditoria(u["login"], u["papel"], "criar_agente", alvo=nome,
                                   cliente_id=cid, ip=request.remote_addr)
            flash(f"Agente '{nome}' criado.", "ok")
            return redirect(url_for("portal.agentes"))
    opts = _opts_cliente()
    mopts = "".join(f'<option value="{m["id"]}">{m["nome"]} ({m["modelo"]})</option>' for m in modelos) \
        or '<option value="">-- cadastre um modelo em Modelos IA --</option>'
    skopts = "".join(
        f'<tr><td style="white-space:nowrap;padding:4px 0"><label style="display:inline;margin:0;font-weight:400;font-size:13px">'
        f'<input type="checkbox" name="skills" value="{s["name"]}" style="width:auto;margin:0;vertical-align:middle"> '
        f'<b>{s["name"]}</b>'
        f'<br><span style="color:var(--muted);font-size:11px;margin-left:20px">{s.get("description","")}</span>'
        f'</label></td></tr>'
        for s in skills_disp
    ) or '<tr><td class="muted">nenhuma skill no catálogo</td></tr>'
    copts = ""
    content = f"""
    <div class="card" style="max-width:700px">
      <h3 style="margin-top:0">Montar agente (Agent Factory)</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Cliente</label><select name="cliente_id">{opts}</select></div>
          <div><label>Nome do agente</label><input name="nome" placeholder="ex: Agente Vendas"></div>
        </div>
        <div class="form-row">
          <div><label>Área</label>
            <select name="area"><option value="">--</option><option>vendas</option><option>suporte</option><option>financeiro</option><option>rh</option><option>operacoes</option></select></div>
          <div><label>Modelo de IA (principal)</label><select name="modelo_id">{mopts}</select></div>
        </div>
        <div class="form-row" style="grid-template-columns:1fr"><div><label>Modelo de IA (fallback)</label><select name="modelo_secundario_id"><option value="">-- nenhum (sem failover) --</option>{mopts}</select>
          <span class="muted" style="font-size:11px">Usado automaticamente se o principal falhar (endpoint indisponível). Garante resposta mesmo em falha.</span></div>
        <label>Skills do catálogo</label>
        <table style="width:100%;border:none;background:transparent"><tbody>{skopts}</tbody></table>
        <div class="card muted" style="font-size:13px;margin-top:12px;padding:12px">
          <b>🔌 Conectores externos</b><br>
          Este agente usará automaticamente os conectores configurados para a <b>área</b> selecionada.
          Vá em <a href="/portal/conectores">Conectores</a> para cadastrar APIs, servidores MCP ou consultas SQL
          como fonte de dados para os agentes da área.
        </div>
        <label style="margin-top:12px;display:block;font-size:13px;padding-left:2px">
          <input type="checkbox" name="lgpd_ativado" value="1" checked style="width:auto;margin:0;vertical-align:middle">
          🔒 Aplicar LGPD (anonimizar resposta do agente)
        </label>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Montar agente</button>
          <a class="btn ghost" href="/portal/agentes">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Cadastrar agente", content, active="agentes", user=_user())


@bp.route("/agentes/<int:aid>/editar", methods=["GET", "POST"])
@auth.admin_required
def agente_editar(aid: int):
    a = db.buscar_agente(aid)
    if not a:
        flash("Agente não encontrado.", "warn")
        return redirect(url_for("portal.agentes"))
    modelos = db.listar_modelos()
    skills_disp = agente_mod.listar_skills()
    skills_sel = (a["skills"] or "").split(",")
    if request.method == "POST":
        campos = {}
        if request.form.get("nome", "").strip():
            campos["nome"] = request.form["nome"].strip()
        if request.form.get("area", ""):
            campos["area"] = request.form["area"]
        mid = request.form.get("modelo_id") or None
        if mid:
            campos["modelo_id"] = int(mid)
            # atualiza tambem o texto legado 'modelo' com o nome do modelo
            m = db.buscar_modelo(int(mid))
            if m:
                campos["modelo"] = m["nome"]
        mid2 = request.form.get("modelo_secundario_id") or None
        if mid2:
            mid2 = int(mid2)
        if mid2 == campos.get("modelo_id"):
            mid2 = None
        campos["modelo_secundario_id"] = mid2
        campos["skills"] = ",".join(request.form.getlist("skills"))
        campos["lgpd_ativado"] = 1 if request.form.get("lgpd_ativado") else 0
        if request.form.get("status") in ("ativo", "pausado"):
            campos["status"] = request.form["status"]
        db.atualizar_agente(aid, **campos)
        db.registrar_auditoria(_user()["login"], "admin", "editar_agente", alvo=request.form.get("nome", a["nome"]),
                               cliente_id=a["cliente_id"], ip=request.remote_addr)
        flash("Agente atualizado.", "ok")
        return redirect(url_for("portal.agentes"))
    mopts = "".join(f'<option value="{m["id"]}" {"selected" if m["id"]==a.get("modelo_id") else ""}>{m["nome"]} ({m["modelo"]})</option>' for m in modelos)
    mopts2 = "".join(f'<option value="{m["id"]}" {"selected" if m["id"]==a.get("modelo_secundario_id") else ""}>{m["nome"]} ({m["modelo"]})</option>' for m in modelos)
    skopts = "".join(
        f'<tr><td style="padding:4px 0"><label style="display:inline;margin:0;font-weight:400;font-size:13px">'
        f'<input type="checkbox" name="skills" value="{s["name"]}" style="width:auto;margin:0;vertical-align:middle" {"checked" if s["name"] in skills_sel else ""}> '
        f'<b>{s["name"]}</b>'
        f'<br><span style="color:var(--muted);font-size:11px;margin-left:20px">{s.get("description","")}</span>'
        f'</label></td></tr>'
        for s in skills_disp
    )
    copts = ""
    areas_opts = "".join(f'<option value="{ar}" {"selected" if ar==a.get("area") else ""}>{ar}</option>' for ar in ["vendas","suporte","financeiro","rh","operacoes"])
    content = f"""
    <div class="card" style="max-width:700px">
      <h3 style="margin-top:0">Editar agente #{aid}: {a['nome']}</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Nome do agente</label><input name="nome" value="{a['nome']}"></div>
          <div><label>Área</label><select name="area"><option value="">--</option>{areas_opts}</select></div>
        </div>
        <div class="form-row">
          <div><label>Modelo de IA (principal)</label><select name="modelo_id"><option value="">--</option>{mopts}</select></div>
          <div><label>Status</label><select name="status"><option value="ativo" {"selected" if a.get("status")=="ativo" else ""}>Ativo</option><option value="pausado" {"selected" if a.get("status")=="pausado" else ""}>Pausado</option></select></div>
        </div>
        <div class="form-row" style="grid-template-columns:1fr"><div><label>Modelo de IA (fallback)</label><select name="modelo_secundario_id"><option value="">-- nenhum --</option>{mopts2}</select>
          <span class="muted" style="font-size:11px">Usado automaticamente se o principal falhar.</span></div></div>
        <label>Skills do catálogo</label>
        <table style="width:100%;border:none;background:transparent"><tbody>{skopts}</tbody></table>
        <div class="card muted" style="font-size:13px;margin-top:12px;padding:12px">
          <b>🔌 Conectores externos</b><br>
          Este agente usará automaticamente os conectores configurados para a <b>área</b> selecionada.
          Vá em <a href="/portal/conectores">Conectores</a> para cadastrar APIs, servidores MCP ou consultas SQL
          como fonte de dados para os agentes da área.
        </div>
        <label style="margin-top:12px;display:block;font-size:13px;padding-left:2px">
          <input type="checkbox" name="lgpd_ativado" value="1" style="width:auto;margin:0;vertical-align:middle" {"checked" if a.get("lgpd_ativado", 1) else ""}>
          🔒 Aplicar LGPD (anonimizar resposta do agente)
        </label>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/agentes">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page(f"Editar {a['nome']}", content, active="agentes", user=_user())


@bp.route("/agentes/<int:aid>/excluir")
@auth.admin_required
def agente_excluir(aid: int):
    a = db.buscar_agente(aid)
    if a:
        db.deletar_agente(aid)
        db.registrar_auditoria(_user()["login"], "admin", "excluir_agente", alvo=a["nome"],
                               cliente_id=a["cliente_id"], ip=request.remote_addr)
        flash(f"Agente '{a['nome']}' excluído.", "ok")
    return redirect(url_for("portal.agentes"))


# ---------------------------------------------------------------------------
# SKILLS (Catalogo de skills — SKILL.md em template_skills/)
# ---------------------------------------------------------------------------

@bp.route("/skills")
@auth.login_required
def skills():
    from . import agente as agente_mod
    cat = agente_mod.listar_skills()
    body = ""
    for s in cat:
        body += f"""<tr>
          <td><b>{s['name']}</b></td>
          <td>{s.get('description','')}</td>
          <td><code>v{s.get('version','1.0.0')}</code></td>
          <td class="row-actions">
            <a href="/portal/skills/{s['name']}/editar">editar</a>
            <a href="/portal/skills/{s['name']}/excluir" onclick="return confirm('Excluir skill {s['name']}?')" style="color:var(--bad)">excluir</a>
          </td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Nome</th><th>Descrição</th><th>Versão</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=4 class="empty">Nenhuma skill no catálogo.</td></tr>'}</tbody></table>"""
    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Skills disponíveis no catálogo (template_skills/). Cada skill é um SKILL.md com frontmatter + instruções.</div>
      <div style="display:flex;gap:8px">
        <a class="btn ghost" href="/portal/skills/indexar-rag">\U0001f4e4 Indexar no RAG</a>
        <a class="btn" href="/portal/skills/novo">+ Nova skill</a>
      </div>
    </div>{tabela}"""
    return templates.page("Skills", content, active="skills", user=_user())


@bp.route("/skills/indexar-rag")
@auth.admin_required
def skills_indexar_rag():
    """Importa todas as skills do catalogo para a base de conhecimento (RAG)."""
    from . import agente as agente_mod
    clientes = db.listar_clientes()
    if not clientes:
        flash("Nenhum cliente cadastrado.", "warn")
        return redirect(url_for("portal.skills"))
    cid = clientes[0]["id"]
    count = 0
    skills = agente_mod.listar_skills_catalogo()
    for nome, meta, body in skills:
        desc = meta.get("description", nome)
        texto = f"Skill: {nome}\nDescricao: {desc}\n\n{body}"
        # Verifica se ja existe
        docs = db.listar_documentos(cliente_id=cid)
        if any(d["titulo"] == f"Skill: {nome}" for d in docs):
            continue
        db.criar_documento(cid, f"Skill: {nome}", "manual", texto,
                           area=meta.get("category") or meta.get("name", ""), fonte="skill")
        count += 1
    db.registrar_auditoria(_user()["login"], "admin", "indexar_skills_rag",
                           alvo=f"{count} skills importadas", cliente_id=cid, ip=request.remote_addr)
    flash(f"{count} skill(s) importadas para o RAG (as ja existentes foram ignoradas).", "ok")
    return redirect(url_for("portal.skills"))


_MODAL_HTML = """<div class="modal-overlay" id="modal-ia" onclick="if(event.target===this)fecharModalIA()">
  <div class="modal-box">
    <h3>✨ Gerar skill com IA</h3>
    <label style="font-size:13px;color:var(--muted)">Modelo de IA:</label>
    {modelos_opts}
    <textarea id="ia-prompt" rows="4" placeholder="Ex: Agente de suporte que consulta a base de conhecimento..." style="margin-top:8px"></textarea>
    <div class="modal-actions">
      <button class="btn btn-spin" id="btn-gerar" onclick="gerarSkillIA()">\U0001f680 Gerar</button>
      <button class="btn ghost" onclick="copiarSkillIA()" id="btn-copiar" style="display:none">\U0001f4cb Copiar para o campo</button>
      <button class="btn ghost" onclick="fecharModalIA()">Fechar</button>
    </div>
    <div id="ia-resultado" style="display:none;margin-top:12px">
      <label>Previa do conteudo gerado:</label>
      <textarea id="ia-conteudo" rows="10" readonly></textarea>
    </div>
    <div id="ia-erro" class="badge bad" style="display:none;margin-top:8px"></div>
  </div>
</div>
<script>
function abrirModalIA(){document.getElementById("modal-ia").classList.add("show")}
function fecharModalIA(){document.getElementById("modal-ia").classList.remove("show")}
function gerarSkillIA(){
  var p=document.getElementById("ia-prompt").value.trim();
  if(!p){alert("Descreva a skill primeiro.");return}
  var m=document.getElementById("ia-modelo").value;
  var b=document.getElementById("btn-gerar");b.classList.add("loading");b.disabled=true;b.innerHTML="\u23f3 Gerando...";
  document.getElementById("ia-erro").style.display="none";
  fetch("/portal/skills/gerar-ia",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt:p,modelo_id:m})})
    .then(function(r){return r.json()})
    .then(function(d){
      b.classList.remove("loading");b.disabled=false;b.innerHTML="\u2728 Gerar de novo";
      if(d.ok){
        document.getElementById("ia-resultado").style.display="block";
        document.getElementById("ia-conteudo").value=d.conteudo;
        document.getElementById("btn-copiar").style.display="inline-block"
      }else{
        var e=document.getElementById("ia-erro");e.textContent=d.erro;e.style.display="block"
      }
    })
    .catch(function(e){b.classList.remove("loading");b.disabled=false;b.innerHTML="\u2728 Gerar";var er=document.getElementById("ia-erro");er.textContent="Erro: "+e.message;er.style.display="block"})
}
function copiarSkillIA(){
  document.getElementById("skill-body").value=document.getElementById("ia-conteudo").value;
  fecharModalIA()
}
</script>"""


@bp.route("/skills/novo", methods=["GET", "POST"])
@auth.admin_required
def skill_novo():
    from . import agente as agente_mod
    if request.method == "POST":
        nome = request.form.get("nome", "").strip().lower().replace(" ", "_")
        desc = request.form.get("descricao", "").strip()
        body = request.form.get("body", "").strip()
        if not nome or not desc:
            flash("Nome e descrição são obrigatórios.", "warn")
        else:
            agente_mod.salvar_skill(nome, desc, body, request.form.get("version", "1.0.0"))
            db.registrar_auditoria(_user()["login"], "admin", "criar_skill", alvo=nome)
            flash(f"Skill '{nome}' criada.", "ok")
            return redirect(url_for("portal.skills"))
    content = f"""
    <div class="card" style="max-width:700px">
      <h3 style="margin-top:0">Nova skill</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Nome (identificador)</label><input name="nome" placeholder="ex: vendas"></div>
          <div><label>Versão</label><input name="version" value="1.0.0"></div>
        </div>
        <label>Descrição</label><input name="descricao" id="skill-desc" placeholder="Agente de vendas - consulta ERP, propoe produtos">
        <label>
          Conteúdo (SKILL.md body — instruções do agente)
          <button type="button" class="btn-ia" onclick="abrirModalIA()" style="margin-left:8px">✨ Gerar com IA</button>
        </label>
        <textarea name="body" id="skill-body" rows="10" placeholder="# Comportamento&#10;1. Ao perguntarem status, consulte o ERP&#10;2. Nunca invente dados&#10;3. Coloque aqui os Guardrails"></textarea>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Criar skill</button>
          <a class="btn ghost" href="/portal/skills">Cancelar</a>
        </div>
      </form>
    </div>"""
    _mdls = db.listar_modelos()
    _mopts = '<select id="ia-modelo">' + "".join(f'<option value="{m["id"]}">{m["nome"]} ({m["modelo"]})</option>' for m in _mdls) + '</select>' if _mdls else '<select id="ia-modelo"><option value="">-- nenhum --</option></select>'
    content += _MODAL_HTML.replace("{modelos_opts}", _mopts)
    return templates.page("Nova skill", content, active="skills", user=_user())


@bp.route("/skills/<nome>/editar", methods=["GET", "POST"])
@auth.admin_required
def skill_editar(nome: str):
    from . import agente as agente_mod
    skill = agente_mod.ler_skill(nome)
    if not skill:
        flash("Skill não encontrada.", "warn")
        return redirect(url_for("portal.skills"))
    if request.method == "POST":
        desc = request.form.get("descricao", "").strip()
        body = request.form.get("body", "").strip()
        if desc:
            agente_mod.salvar_skill(nome, desc, body, request.form.get("version", skill.get("version", "1.0.0")))
            db.registrar_auditoria(_user()["login"], "admin", "editar_skill", alvo=nome)
            flash(f"Skill '{nome}' atualizada.", "ok")
            return redirect(url_for("portal.skills"))
    content = f"""
    <div class="card" style="max-width:700px">
      <h3 style="margin-top:0">Editar skill: {skill['name']}</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Nome</label><input name="nome" value="{skill['name']}" readonly style="color:var(--muted)"></div>
          <div><label>Versão</label><input name="version" value="{skill.get('version','1.0.0')}"></div>
        </div>
        <label>Descrição</label><input name="descricao" id="skill-desc" value="{skill.get('description','')}">
        <label>
          Conteúdo (SKILL.md body)
          <button type="button" class="btn-ia" onclick="abrirModalIA()" style="margin-left:8px">✨ Gerar com IA</button>
        </label>
        <textarea name="body" id="skill-body" rows="10">{skill.get('body','')}</textarea>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/skills">Cancelar</a>
        </div>
      </form>
    </div>"""
    _mdls_e = db.listar_modelos()
    _mopts_e = '<select id="ia-modelo">' + "".join(f'<option value="{m["id"]}">{m["nome"]} ({m["modelo"]})</option>' for m in _mdls_e) + '</select>' if _mdls_e else '<select id="ia-modelo"><option value="">-- nenhum --</option></select>'
    content += _MODAL_HTML.replace("{modelos_opts}", _mopts_e)
    return templates.page(f"Editar {skill['name']}", content, active="skills", user=_user())


@bp.route("/skills/<nome>/excluir")
@auth.admin_required
def skill_excluir(nome: str):
    from . import agente as agente_mod
    if agente_mod.deletar_skill(nome):
        db.registrar_auditoria(_user()["login"], "admin", "excluir_skill", alvo=nome)
        flash(f"Skill '{nome}' excluída.", "ok")
    return redirect(url_for("portal.skills"))


@bp.route("/skills/gerar-ia", methods=["POST"])
@auth.admin_required
def skill_gerar_ia():
    """Usa o primeiro modelo de IA ativo para gerar conteúdo de skill."""
    from . import llm_client
    prompt = (request.form.get("prompt", "") or request.json.get("prompt", "") if request.is_json else "").strip()
    if not prompt:
        return jsonify({"ok": False, "erro": "Prompt obrigatório"}), 400

    # Pega o primeiro modelo ativo do primeiro cliente
    clientes = db.listar_clientes()
    if not clientes:
        return jsonify({"ok": False, "erro": "Nenhum cliente cadastrado"}), 400
    modelos = db.listar_modelos(clientes[0]["id"])
    if not modelos:
        return jsonify({"ok": False, "erro": "Nenhum modelo de IA cadastrado. Cadastre um em Modelos IA primeiro."}), 400

    mid = request.json.get("modelo_id", "") if request.is_json else ""
    if mid and str(mid).isdigit():
        mid = int(mid)
        modelo = next((m for m in modelos if m["id"] == mid), modelos[0])
    else:
        modelo = modelos[0]
    system = (
        "Você é um especialista em criar skills para agentes de IA corporativos. "
        "Gere o conteúdo de um arquivo SKILL.md baseado na descrição fornecida pelo usuário.\n\n"
        "Formato esperado:\n"
        "- Título da skill\n"
        "- Objetivo: descrição do que o agente faz\n"
        "- Comportamento: lista numerada de instruções\n"
        "- Regras: restrições e boas práticas\n"
        "- Exemplos: exemplos de perguntas e respostas esperadas\n\n"
        "Seja objetivo e prático. Use português brasileiro."
    )
    mensagens = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Crie uma skill de IA para: {prompt}"},
    ]
    out = llm_client.chat(modelo, mensagens)
    if out["ok"]:
        return jsonify({"ok": True, "conteudo": out["content"]})
    return jsonify({"ok": False, "erro": out.get("error", "Falha ao gerar skill")}), 500


# ---------------------------------------------------------------------------
# CONECTORES (status)
# ---------------------------------------------------------------------------

@bp.route("/conectores", methods=["GET", "POST"])
@auth.admin_required
def conectores():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}

    if request.method == "POST":
        cid = int(request.form.get("cliente_id") or 1)
        area = request.form.get("area", "").strip()
        nome = request.form.get("nome", "").strip()
        tipo = request.form.get("tipo", "api")
        config = {}

        if not nome:
            flash("Nome do conector é obrigatório.", "warn")
            return redirect(url_for("portal.conectores"))
        if not area:
            flash("Selecione uma área.", "warn")
            return redirect(url_for("portal.conectores"))

        if tipo == "api":
            config["url"] = request.form.get("api_url", "").strip()
            config["method"] = request.form.get("api_method", "GET")
            config["headers"] = request.form.get("api_headers", "{}").strip()
            config["body"] = request.form.get("api_body", "").strip()
        elif tipo == "mcp":
            config["transport"] = request.form.get("mcp_transport", "stdio").strip()
            config["url"] = request.form.get("mcp_url", "").strip()
            config["command"] = request.form.get("mcp_command", "").strip()
            config["tool"] = request.form.get("mcp_tool", "").strip()
            args_raw = request.form.get("mcp_args", "{}").strip()
            try:
                config["args"] = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                config["args"] = {}
        elif tipo == "sql":
            config["sql_driver"] = request.form.get("sql_driver", "postgresql")
            config["sql_host"] = request.form.get("sql_host", "").strip()
            config["sql_port"] = request.form.get("sql_port", "").strip()
            config["sql_db"] = request.form.get("sql_db", "").strip()
            config["sql_user"] = request.form.get("sql_user", "").strip()
            config["sql_pass"] = request.form.get("sql_pass", "").strip()
            config["dsn_env"] = request.form.get("sql_dsn_env", "").strip()
            config["dsn"] = request.form.get("sql_dsn", "").strip()
            config["query"] = request.form.get("sql_query", "").strip()
            config["sql_analise"] = "1" if request.form.get("sql_analise") else "0"

        config["descricao"] = request.form.get("descricao", "").strip()
        finalidade = request.form.get("finalidade", "").strip()
        # Se finalidade_conector estiver ativo e finalidade vazia, bloqueia
        lgpd_cfg = db.carregar_lgpd_config()
        if lgpd_cfg.get("finalidade_conector") == "1" and not finalidade:
            flash("Finalidade do tratamento é obrigatória quando LGPD está ativo.", "warn")
            return redirect(url_for("portal.conectores"))

        db.criar_conector(cid, nome, tipo=tipo, area=area, config=config, finalidade=finalidade)
        db.registrar_auditoria(_user()["login"], "admin", "criar_conector",
                               alvo=nome, cliente_id=cid, ip=request.remote_addr)
        flash(f"Conector '{nome}' criado na area {area}.", "ok")
        return redirect(url_for("portal.conectores"))

    # GET: listar com filtro de área
    area_sel = request.args.get("area", "")
    cid_sel = request.args.get("cliente_id", type=int)
    rows = db.listar_conectores(cliente_id=cid_sel, area=area_sel or None)
    body = ""
    for k in rows:
        cfg = _parse_config(k.get("config", "{}"))
        tipo_icon = {"api": "🌐", "mcp": "🔌", "sql": "🗄️"}.get(k["tipo"], "❓")
        cfg_resumo = cfg.get("descricao") or cfg.get("url") or cfg.get("tool") or cfg.get("query", "")[:60]
        finalidade = k.get("finalidade") or cfg.get("finalidade", "")
        body += f"""<tr>
          <td><b>{k['nome']}</b></td>
          <td>{tipo_icon} {k['tipo']}</td>
          <td>{k['area'] or '-'}</td>
          <td class="muted" style="max-width:300px;overflow:hidden;text-overflow:ellipsis">{cfg_resumo}</td>
          <td style="font-size:11px;color:var(--muted-soft)">{finalidade[:40] or '-'}</td>
          <td>{templates.badge(k['status'])}</td>
          <td class="muted">{k['ultimo_heartbeat'] or '-'}</td>
          <td class="row-actions">
            <a href="{url_for('portal.conector_editar', cid=k['id'])}">editar</a>
            <a href="{url_for('portal.conector_excluir', cid=k['id'])}" onclick="return confirm('Excluir conector \'{k['nome']}\'?')" style="color:var(--bad)">excluir</a>
          </td></tr>"""

    opts_area = "".join(f'<option value="{a}" {"selected" if a == area_sel else ""}>{a}</option>' for a in listar_areas())
    opts_cliente = _opts_cliente(cid_sel)
    content = f"""
    <div class="card" style="max-width:720px">
      <h3 style="margin-top:0">Cadastrar fonte externa</h3>
      <p class="muted">Conecte APIs, servidores MCP ou consultas SQL como fonte de dados para os agentes da área.</p>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Cliente</label><select name="cliente_id">{opts_cliente}</select></div>
          <div><label>Área</label><select name="area"><option value="">selecione</option>{opts_area}</select></div>
        </div>
        <div class="form-row">
          <div><label>Nome</label><input name="nome" placeholder="Ex: API Câmbio"></div>
          <div><label>Tipo</label>
            <select name="tipo" id="conn-tipo" onchange="toggleConnFields()">
              <option value="api">🌐 API REST</option>
              <option value="mcp">🔌 MCP (stdio)</option>
              <option value="sql">🗄️ SQL View</option>
            </select></div>
        </div>
        <div id="conn-fields-api">
          <label>URL</label><input name="api_url" placeholder="https://api.exemplo.com/v1/dados">
          <div class="form-row">
            <div><label>Método</label><select name="api_method"><option value="GET">GET</option><option value="POST">POST</option></select></div>
            <div><label>Headers (JSON) <span class="info-tip" title='{{"User-Agent": "Mozilla/5.0", "Authorization": "Bearer token"}}' style="cursor:help;color:var(--muted);font-size:13px">ⓘ</span></label><input name="api_headers" placeholder='{{"User-Agent": "Mozilla/5.0"}}'></div>
          </div>
          <label>Body (JSON, só POST)</label><input name="api_body" placeholder='{{"id": "{{id_cliente}}"}}'>
        </div>
        <div id="conn-fields-mcp" style="display:none">
          <label>Transporte</label>
          <select name="mcp_transport" onchange="toggleMCPTransport()">
            <option value="stdio">stdio (local)</option>
            <option value="sse">SSE (remoto)</option>
          </select>
          <div id="mcp-stdio-fields">
            <label>Comando</label><input name="mcp_command" placeholder="python /opt/blueshift/mcp_server.py">
          </div>
          <div id="mcp-sse-fields" style="display:none">
            <label>URL</label><input name="mcp_url" placeholder="http://servidor:8000/mcp">
          </div>
          <label>Ferramenta (tool)</label><input name="mcp_tool" placeholder="erp_buscar_cliente">
          <label>Argumentos (JSON)</label><input name="mcp_args" placeholder='{{"id_cliente": "{{id_cliente}}"}}'>
        </div>
        <div id="conn-fields-sql" style="display:none">
          <label>Driver</label>
          <select name="sql_driver" id="sql-driver">
            <option value="postgresql">PostgreSQL</option>
            <option value="mysql">MySQL</option>
            <option value="sqlserver">SQL Server</option>
            <option value="oracle">Oracle</option>
          </select>
          <div class="form-row">
            <div><label>Host</label><input name="sql_host" placeholder="host.docker.internal"></div>
            <div><label>Porta</label><input name="sql_port" placeholder="5432 (PG) / 3306 (MySQL) / 1433 (SQL Server) / 1521 (Oracle)"></div>
          </div>
          <div class="form-row">
            <div><label>Banco</label><input name="sql_db" placeholder="nome_do_banco"></div>
            <div><label>Usuário</label><input name="sql_user" placeholder="usuario"></div>
          </div>
          <label>Senha</label><input name="sql_pass" type="password" placeholder="senha">
          <details style="margin-top:10px;font-size:12px"><summary>DSN alternativo (avançado)</summary>
            <label>DSN (variável de ambiente)</label><input name="sql_dsn_env" placeholder="ERP_DSN">
            <label>DSN direto (opcional)</label><input name="sql_dsn" placeholder="host=... dbname=...">
          </details>
          <div style="text-align:center;margin:10px 0">
            <button type="button" class="btn ghost" onclick="testarConexaoSQL()" style="font-size:12px" id="btn-testar-conexao">🔌 Testar Conexão</button>
          </div>
          <div id="sql-test-resultado" style="margin-bottom:6px;font-size:12px;text-align:center"></div>
          <label>Query SQL
            <button type="button" class="btn-ia" onclick="abrirModalQueryIA()" style="margin-left:8px;font-size:12px;padding:4px 10px">🤖 Gerar Query com IA</button>
          </label>
          <textarea name="sql_query" id="sql-query" rows="3" placeholder="Ex: SELECT * FROM clientes WHERE id = &#123;id_cliente&#125;  (use &#123;id_cliente&#125;, &#123;email&#125;, &#123;data&#125;)"></textarea>
          <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;margin:12px 0 0;font-weight:400;font-size:13px"><input type="checkbox" name="sql_analise" value="1" checked style="width:auto;margin:0;vertical-align:middle"> Consulta inteligente (análise automática)</label>
          <div class="muted" style="font-size:11px;margin-top:4px">Quando a query fixa voltar vazia e a pergunta pedir análise ("quem alugou mais e menos", "quantos por categoria"), o agente monta o SELECT sozinho olhando o schema real da fonte (somente leitura, com LIMIT).</div>
        </div>
        <label>Descrição</label><input name="descricao" placeholder="O que este conector faz">
        <div id="conn-finalidade" style="margin-top:8px">
          <label>Finalidade do tratamento <span class="muted" style="font-weight:400;font-size:11px">(Art. 26 LGPD)</span></label>
          <input name="finalidade" placeholder="Ex: Consultar dados cadastrais do cliente para agente de vendas">
        </div>
        <div style="margin-top:14px"><button class="btn" type="submit">Cadastrar conector</button></div>
      </form>
    </div>
    <select id="modelos-store" style="display:none">{"".join(f'<option value="{m["id"]}">{m["nome"]} ({m["modelo"]})</option>' for m in db.listar_modelos())}</select>
    <div class="modal-overlay" id="modal-query-ia" onclick="if(event.target===this)fecharModalQueryIA()">
      <div class="modal-box">
        <h3>🤖 Gerar Query SQL com IA</h3>
        <label style="font-size:13px;color:var(--muted)">Modelo de IA:</label>
        <select id="ia-query-modelo"></select>
        <textarea id="ia-query-desc" rows="4" placeholder="Ex: Listar todos os clientes ativos com saldo acima de 1000" style="margin-top:8px"></textarea>
        <div class="modal-actions">
          <button class="btn btn-spin" id="btn-gerar-query" onclick="gerarQueryIA()">🚀 Gerar</button>
          <button class="btn ghost" onclick="copiarQueryIA()" id="btn-copiar-query" style="display:none">📋 Copiar para o campo</button>
          <button class="btn ghost" onclick="fecharModalQueryIA()">Fechar</button>
        </div>
        <div id="ia-query-resultado" style="display:none;margin-top:12px">
          <label>Query gerada:</label>
          <textarea id="ia-query-conteudo" rows="6" readonly></textarea>
        </div>
        <div id="ia-query-erro" class="badge bad" style="display:none;margin-top:8px"></div>
      </div>
    </div>
    <script>
    function toggleConnFields() {{
      var t = document.getElementById('conn-tipo').value;
      document.getElementById('conn-fields-api').style.display = t === 'api' ? '' : 'none';
      document.getElementById('conn-fields-mcp').style.display = t === 'mcp' ? '' : 'none';
      document.getElementById('conn-fields-sql').style.display = t === 'sql' ? '' : 'none';
    }}
    function toggleMCPTransport() {{
      var t = document.querySelector('[name=mcp_transport]').value;
      document.getElementById('mcp-stdio-fields').style.display = t === 'stdio' ? '' : 'none';
      document.getElementById('mcp-sse-fields').style.display = t === 'sse' ? '' : 'none';
    }}
    function testarConexaoSQL() {{
      var b = document.getElementById('btn-testar-conexao');
      b.textContent = '⏳ Testando...';
      b.disabled = true;
      var r = document.getElementById('sql-test-resultado');
      r.innerHTML = '';
      var fd = new FormData();
      fd.append('driver', document.getElementById('sql-driver').value);
      fd.append('host', document.querySelector('[name=sql_host]').value);
      fd.append('port', document.querySelector('[name=sql_port]').value);
      fd.append('db', document.querySelector('[name=sql_db]').value);
      fd.append('user', document.querySelector('[name=sql_user]').value);
      fd.append('password', document.querySelector('[name=sql_pass]').value);
      fd.append('dsn', document.querySelector('[name=sql_dsn]').value);
      fd.append('query', document.querySelector('[name=sql_query]').value);
      fetch('/portal/conectores/testar-conexao', {{method:'POST',body:fd}})
        .then(function(r){{return r.json()}})
        .then(function(d){{
          b.textContent = '🔌 Testar Conexão';
          b.disabled = false;
          r.innerHTML = d.ok
            ? '<span style="color:var(--ok)">✅ Conexão OK</span>'
            : '<span style="color:var(--bad)">❌ ' + d.erro + '</span>';
        }})
        .catch(function(e){{
          b.textContent = '🔌 Testar Conexão';
          b.disabled = false;
          r.innerHTML = '<span style="color:var(--bad)">❌ Erro: ' + e.message + '</span>';
        }});
    }}
    function abrirModalQueryIA(){{var s=document.getElementById('ia-query-modelo'),st=document.getElementById('modelos-store');if(st&&s){{s.innerHTML=st.innerHTML}}document.getElementById('modal-query-ia').classList.add('show')}}
    function fecharModalQueryIA(){{document.getElementById('modal-query-ia').classList.remove('show')}}
    function gerarQueryIA(){{
      var desc=document.getElementById('ia-query-desc').value.trim();
      if(!desc){{alert('Descreva a query primeiro.');return}}
      var driver=document.getElementById('sql-driver').value;
      var b=document.getElementById('btn-gerar-query');b.classList.add('loading');b.disabled=true;
      document.getElementById('ia-query-erro').style.display='none';
      fetch('/portal/conectores/gerar-query-ia',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{descricao:desc,driver:driver}})}})
        .then(function(r){{return r.json()}})
        .then(function(d){{
          b.classList.remove('loading');b.disabled=false;
          if(d.ok){{
            document.getElementById('ia-query-resultado').style.display='block';
            document.getElementById('ia-query-conteudo').value=d.query;
            document.getElementById('btn-copiar-query').style.display='inline-block';
          }}else{{
            var e=document.getElementById('ia-query-erro');e.textContent=d.erro;e.style.display='block';
          }}
        }})
        .catch(function(e){{b.classList.remove('loading');b.disabled=false;var er=document.getElementById('ia-query-erro');er.textContent='Erro: '+e.message;er.style.display='block'}})
    }}
    function copiarQueryIA(){{
      document.getElementById('sql-query').value=document.getElementById('ia-query-conteudo').value;
      fecharModalQueryIA();
    }}
    </script>
    <div class="card">
      <h3 style="margin-top:0">Fontes externas cadastradas</h3>
      <form method="get" style="margin-bottom:12px;display:flex;gap:8px;align-items:end">
        <div><label>Cliente</label><select name="cliente_id">{opts_cliente}</select></div>
        <div><label>Área</label><select name="area"><option value="">todas</option>{opts_area}</select></div>
        <div><button class="btn ghost" type="submit">Filtrar</button></div>
      </form>
      <table><thead><tr><th>Nome</th><th>Tipo</th><th>Área</th><th>Config</th><th>Finalidade</th><th>Status</th><th>Heartbeat</th><th></th></tr></thead>
        <tbody>{body or '<tr><td colspan="8" class="muted">Nenhum conector cadastrado. Crie um acima.</td></tr>'}</tbody></table>
    </div>"""
    return templates.page("Conectores", content, active="conectores", user=_user())


@bp.route("/conectores/testar-conexao", methods=["POST"])
@auth.admin_required
def conector_testar_conexao():
    """Testa a conexao com um banco SQL usando os parametros fornecidos."""
    driver = request.form.get("driver", "postgresql")
    host = request.form.get("host", "").strip()
    port = request.form.get("port", "").strip()
    db_name = request.form.get("db", "").strip()
    user = request.form.get("user", "").strip()
    password = request.form.get("password", "").strip()
    dsn = request.form.get("dsn", "").strip()
    query = request.form.get("query", "SELECT 1").strip()
    if not query:
        query = "SELECT 1"

    try:
        if driver == "postgresql":
            import psycopg
            if dsn:
                conn = psycopg.connect(dsn)
            else:
                conn = psycopg.connect(host=host or "127.0.0.1", port=port or "5432",
                                       dbname=db_name, user=user, password=password)
        elif driver == "mysql":
            import pymysql
            conn = pymysql.connect(host=host or "127.0.0.1", port=int(port or "3306"),
                                   database=db_name, user=user, password=password, charset="utf8mb4")
        elif driver == "sqlserver":
            import pymssql
            conn = pymssql.connect(server=host or "127.0.0.1", port=port or "1433",
                                   database=db_name, user=user, password=password)
        else:
            return jsonify({"ok": False, "erro": f"Driver desconhecido: {driver}"})
        try:
            with conn.cursor() as cur:
                cur.execute(query)
            conn.commit()
            return jsonify({"ok": True})
        finally:
            conn.close()
    except ImportError:
        return jsonify({"ok": False, "erro": f"Driver {driver} nao instalado. Execute: pip install {driver}"})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)})


@bp.route("/conectores/gerar-query-ia", methods=["POST"])
@auth.admin_required
def conector_gerar_query_ia():
    """Usa o primeiro modelo de IA ativo para gerar uma query SQL."""
    from . import llm_client
    descricao = (request.form.get("descricao", "") or request.json.get("descricao", "") if request.is_json else "").strip()
    driver = (request.form.get("driver", "") or request.json.get("driver", "postgresql") if request.is_json else "postgresql").strip()
    if not descricao:
        return jsonify({"ok": False, "erro": "Descricao obrigatoria"}), 400

    clientes = db.listar_clientes()
    if not clientes:
        return jsonify({"ok": False, "erro": "Nenhum cliente cadastrado"}), 400
    modelos = db.listar_modelos(clientes[0]["id"])
    if not modelos:
        return jsonify({"ok": False, "erro": "Nenhum modelo de IA cadastrado."}), 400
    dialetos = {"postgresql": "PostgreSQL", "mysql": "MySQL", "sqlserver": "SQL Server", "oracle": "Oracle"}
    mid_q = request.json.get("modelo_id", "") if request.is_json else ""
    if mid_q and str(mid_q).isdigit():
        mid_q = int(mid_q)
        modelo = next((m for m in modelos if m["id"] == mid_q), modelos[0])
    else:
        modelo = modelos[0]
    dialeto = dialetos.get(driver, "SQL")
    system = (
        f"Voce e um especialista em SQL para {dialeto}."
        f"Gere apenas a query SQL, sem explicacoes, comentarios ou marcacao. "
        f"Use a sintaxe correta para {dialeto}. "
        f"Retorne somente o SQL puro."
    )
    mensagens = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Crie uma query {dialeto} para: {descricao}"},
    ]
    out = llm_client.chat(modelo, mensagens)
    if out["ok"]:
        return jsonify({"ok": True, "query": out["content"].strip()})
    return jsonify({"ok": False, "erro": out.get("error", "Falha ao gerar query")}), 500


@bp.route("/conectores/<int:cid>/editar", methods=["GET", "POST"])
@auth.admin_required
def conector_editar(cid: int):
    con = db.buscar_conector(cid)
    if not con:
        flash("Conector não encontrado.", "bad")
        return redirect(url_for("portal.conectores"))
    cfg = _parse_config(con.get("config", "{}"))

    if request.method == "POST":
        nome = (request.form.get("nome") or con["nome"]).strip()
        area = request.form.get("area") or con["area"]
        tipo = request.form.get("tipo") or con["tipo"]
        config = {}

        if tipo == "api":
            config["url"] = request.form.get("api_url", "").strip()
            config["method"] = request.form.get("api_method", "GET")
            config["headers"] = request.form.get("api_headers", "{}").strip()
            config["body"] = request.form.get("api_body", "").strip()
        elif tipo == "mcp":
            config["transport"] = request.form.get("mcp_transport", "stdio").strip()
            config["url"] = request.form.get("mcp_url", "").strip()
            config["command"] = request.form.get("mcp_command", "").strip()
            config["tool"] = request.form.get("mcp_tool", "").strip()
            args_raw = request.form.get("mcp_args", "{}").strip()
            try:
                config["args"] = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                config["args"] = {}
        elif tipo == "sql":
            config["sql_driver"] = request.form.get("sql_driver", "postgresql")
            config["sql_host"] = request.form.get("sql_host", "").strip()
            config["sql_port"] = request.form.get("sql_port", "").strip()
            config["sql_db"] = request.form.get("sql_db", "").strip()
            config["sql_user"] = request.form.get("sql_user", "").strip()
            config["sql_pass"] = request.form.get("sql_pass", "").strip()
            config["dsn_env"] = request.form.get("sql_dsn_env", "").strip()
            config["dsn"] = request.form.get("sql_dsn", "").strip()
            config["query"] = request.form.get("sql_query", "").strip()
            config["sql_analise"] = "1" if request.form.get("sql_analise") else "0"

        config["descricao"] = request.form.get("descricao", "").strip()
        finalidade = request.form.get("finalidade", "").strip()

        if not nome:
            flash("Nome é obrigatório.", "warn")
            return redirect(url_for("portal.conector_editar", cid=cid))

        db.atualizar_conector(cid, nome=nome, area=area, tipo=tipo, config=config, finalidade=finalidade)
        db.registrar_auditoria(_user()["login"], "admin", "editar_conector",
                               alvo=nome, ip=request.remote_addr)
        flash(f"Conector '{nome}' atualizado.", "ok")
        return redirect(url_for("portal.conectores"))

    opts_area = "".join(f'<option value="{a}" {"selected" if a == con["area"] else ""}>{a}</option>' for a in listar_areas())
    opts_cliente = "".join(f'<option value="{c["id"]}" {"selected" if c["id"]==con["cliente_id"] else ""}>{c["nome"]}</option>' for c in db.listar_clientes())
    cfg = _parse_config(con.get("config", "{}"))
    tipo = con["tipo"]

    # Campos preenchidos
    api_url = cfg.get("url", "")
    api_method = cfg.get("method", "GET")
    api_headers = cfg.get("headers", "{}")
    api_body = cfg.get("body", "")
    mcp_cmd = cfg.get("command", "")
    mcp_tool = cfg.get("tool", "")
    mcp_transport = cfg.get("transport", "stdio")
    mcp_url = cfg.get("url", "")
    mcp_args = json.dumps(cfg.get("args", {}), ensure_ascii=False)
    sql_driver = cfg.get("sql_driver", "postgresql")
    sql_host = cfg.get("sql_host", "")
    sql_port = cfg.get("sql_port", "")
    sql_db = cfg.get("sql_db", "")
    sql_user = cfg.get("sql_user", "")
    sql_pass = cfg.get("sql_pass", "")
    sql_dsn_env = cfg.get("dsn_env", "")
    sql_dsn = cfg.get("dsn", "")
    sql_query = cfg.get("query", "")
    sql_analise = cfg.get("sql_analise", "1") != "0"
    descricao = cfg.get("descricao", "")

    api_sel = {"api": "", "mcp": "", "sql": ""}
    api_sel[tipo] = 'selected'
    sql_drv_opts = "".join(f'<option value="{d}" {"selected" if sql_driver==d else ""}>{d.upper()}</option>'
                           for d in ["postgresql", "mysql", "sqlserver", "oracle"])

    content = f"""
    <div class="card" style="max-width:720px">
      <h3 style="margin-top:0">Editar conector #{cid}</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Cliente</label><select name="cliente_id">{opts_cliente}</select></div>
          <div><label>Nome</label><input name="nome" value="{con['nome']}"></div>
        </div>
        <div class="form-row">
          <div><label>Área</label><select name="area">{opts_area}</select></div>
          <div><label>Tipo</label>
            <select name="tipo" id="edit-conn-tipo" onchange="toggleEditConnFields()">
              <option value="api" {api_sel["api"]}>API</option>
              <option value="mcp" {api_sel["mcp"]}>MCP</option>
              <option value="sql" {api_sel["sql"]}>SQL</option>
            </select></div>
        </div>

        <div id="edit-fields-api" style="display:{'block' if tipo=='api' else 'none'}">
          <div class="form-row">
            <div><label>URL</label><input name="api_url" value="{api_url}" placeholder="https://api.externa.com/dados"></div>
            <div><label>Método</label><select name="api_method"><option value="GET" {"selected" if api_method=='GET' else ''}>GET</option><option value="POST" {"selected" if api_method=='POST' else ''}>POST</option></select></div>
          </div>
          <label>Headers (JSON) <span class="info-tip" title='{{"User-Agent": "Mozilla/5.0", "Authorization": "Bearer token"}}' style="cursor:help;color:var(--muted);font-size:13px">ⓘ</span></label><input name="api_headers" value='{templates.h(api_headers)}' placeholder='{{"User-Agent": "Mozilla/5.0"}}'>
          <label>Body (JSON, só POST)</label><input name="api_body" value='{templates.h(api_body)}' placeholder='{{"id": "{{id_cliente}}"}}'>
        </div>

        <div id="edit-fields-mcp" style="display:{'block' if tipo=='mcp' else 'none'}">
          <label>Transporte</label>
          <select name="mcp_transport" onchange="toggleEditMCPTransport()">
            <option value="stdio" {"selected" if mcp_transport=='stdio' else ""}>stdio (local)</option>
            <option value="sse" {"selected" if mcp_transport=='sse' else ""}>SSE (remoto)</option>
          </select>
          <div id="edit-mcp-stdio-fields" style="display:{'block' if mcp_transport!='sse' else 'none'}">
            <label>Comando</label><input name="mcp_command" value="{mcp_cmd}" placeholder="python /opt/blueshift/mcp_server.py">
          </div>
          <div id="edit-mcp-sse-fields" style="display:{'block' if mcp_transport=='sse' else 'none'}">
            <label>URL</label><input name="mcp_url" value="{mcp_url}" placeholder="http://servidor:8000/mcp">
          </div>
          <label>Ferramenta (tool)</label><input name="mcp_tool" value="{mcp_tool}" placeholder="erp_buscar_cliente">
          <label>Argumentos (JSON)</label><input name="mcp_args" value='{mcp_args}' placeholder='{{"id_cliente": "{{id_cliente}}"}}'>
        </div>

        <div id="edit-fields-sql" style="display:{'block' if tipo=='sql' else 'none'}">
          <label>Driver</label><select name="sql_driver">{sql_drv_opts}</select>
          <div class="form-row">
            <div><label>Host</label><input name="sql_host" value="{sql_host}" placeholder="host.docker.internal"></div>
            <div><label>Porta</label><input name="sql_port" value="{sql_port}" placeholder="5432 / 3306 / 1433"></div>
          </div>
          <div class="form-row">
            <div><label>Banco</label><input name="sql_db" value="{sql_db}"></div>
            <div><label>Usuário</label><input name="sql_user" value="{sql_user}"></div>
          </div>
          <label>Senha</label><input name="sql_pass" type="password" value="{sql_pass}" placeholder="deixar em branco para manter">
          <details style="margin-top:10px;font-size:12px"><summary>DSN alternativo (avançado)</summary>
            <label>DSN (variável de ambiente)</label><input name="sql_dsn_env" value="{sql_dsn_env}">
            <label>DSN direto (opcional)</label><input name="sql_dsn" value="{sql_dsn}">
          </details>
          <div style="text-align:center;margin:10px 0">
            <button type="button" class="btn ghost" onclick="testarConexaoEdit()" style="font-size:12px" id="btn-testar-conexao">🔌 Testar Conexão</button>
          </div>
          <div id="sql-test-resultado" style="margin-bottom:6px;font-size:12px;text-align:center"></div>
          <div class="form-row">
            <div style="flex:1;width:100%">
              <label>Query SQL
                <button type="button" class="btn-ia" onclick="abrirModalQueryIAEdit()" style="margin-left:8px;font-size:12px;padding:4px 10px">🤖 Gerar Query com IA</button>
              </label>
              <textarea name="sql_query" id="sql-query" rows="3" placeholder="Ex: SELECT * FROM clientes WHERE id = &#123;id_cliente&#125;" style="width:100%;box-sizing:border-box">{sql_query}</textarea>
              <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;margin:12px 0 0;font-weight:400;font-size:13px"><input type="checkbox" name="sql_analise" value="1" {"checked" if sql_analise else ''} style="width:auto;margin:0;vertical-align:middle"> Consulta inteligente (análise automática)</label>
              <div class="muted" style="font-size:11px;margin-top:4px">Quando a query fixa voltar vazia e a pergunta pedir análise ("quem alugou mais e menos", "quantos por categoria"), o agente monta o SELECT sozinho olhando o schema real da fonte (somente leitura, com LIMIT).</div>
            </div>
          </div>
        </div>

        <label>Descrição</label><input name="descricao" value="{descricao}">
        <label style="margin-top:10px">Finalidade do tratamento <span class="muted" style="font-weight:400;font-size:11px">(Art. 26 LGPD)</span></label>
        <input name="finalidade" value="{con.get('finalidade','')}" placeholder="Ex: Consultar dados cadastrais do cliente para agente de vendas">
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/conectores">Cancelar</a>
        </div>
      </form>
    </div>
    <select id="modelos-store-edit" style="display:none">{"".join(f'<option value="{m["id"]}">{m["nome"]} ({m["modelo"]})</option>' for m in db.listar_modelos())}</select>
    <div class="modal-overlay" id="modal-query-ia-edit" onclick="if(event.target===this)fecharModalQueryIAEdit()">
      <div class="modal-box">
        <h3>🤖 Gerar Query SQL com IA</h3>
        <label style="font-size:13px;color:var(--muted)">Modelo de IA:</label>
        <select id="ia-query-modelo-edit"></select>
        <textarea id="ia-query-desc-edit" rows="4" placeholder="Ex: Listar todos os clientes ativos com saldo acima de 1000" style="margin-top:8px"></textarea>
        <div class="modal-actions">
          <button class="btn btn-spin" id="btn-gerar-query-edit" onclick="gerarQueryIAEdit()">🚀 Gerar</button>
          <button class="btn ghost" onclick="copiarQueryIAEdit()" id="btn-copiar-query-edit" style="display:none">📋 Copiar para o campo</button>
          <button class="btn ghost" onclick="fecharModalQueryIAEdit()">Fechar</button>
        </div>
        <div id="ia-query-resultado-edit" style="display:none;margin-top:12px">
          <label>Query gerada:</label>
          <textarea id="ia-query-conteudo-edit" rows="6" readonly></textarea>
        </div>
        <div id="ia-query-erro-edit" class="badge bad" style="display:none;margin-top:8px"></div>
      </div>
    </div>
    <script>
    function toggleEditConnFields() {{
      var t = document.getElementById('edit-conn-tipo').value;
      document.getElementById('edit-fields-api').style.display = t === 'api' ? '' : 'none';
      document.getElementById('edit-fields-mcp').style.display = t === 'mcp' ? '' : 'none';
      document.getElementById('edit-fields-sql').style.display = t === 'sql' ? '' : 'none';
    }}
    function toggleEditMCPTransport() {{
      var t = document.querySelector('[name=mcp_transport]').value;
      document.getElementById('edit-mcp-stdio-fields').style.display = t === 'stdio' ? '' : 'none';
      document.getElementById('edit-mcp-sse-fields').style.display = t === 'sse' ? '' : 'none';
    }}
    function testarConexaoEdit() {{
      var b = document.getElementById('btn-testar-conexao');
      if(!b) return;
      b.textContent = '⏳ Testando...';
      b.disabled = true;
      var r = document.getElementById('sql-test-resultado');
      r.innerHTML = '';
      var fd = new FormData();
      fd.append('driver', (document.querySelector('[name=sql_driver]')||{{}}).value||'postgresql');
      fd.append('host', (document.querySelector('[name=sql_host]')||{{}}).value||'');
      fd.append('port', (document.querySelector('[name=sql_port]')||{{}}).value||'');
      fd.append('db', (document.querySelector('[name=sql_db]')||{{}}).value||'');
      fd.append('user', (document.querySelector('[name=sql_user]')||{{}}).value||'');
      fd.append('password', (document.querySelector('[name=sql_pass]')||{{}}).value||'');
      fd.append('dsn', (document.querySelector('[name=sql_dsn]')||{{}}).value||'');
      fd.append('query', (document.querySelector('[name=sql_query]')||{{}}).value||'');
      fetch('/portal/conectores/testar-conexao', {{method:'POST',body:fd}})
        .then(function(r){{return r.json()}})
        .then(function(d){{
          b.textContent = '🔌 Testar Conexão';
          b.disabled = false;
          r.innerHTML = d.ok ? '<span style="color:var(--ok)">✅ Conexão OK</span>' : '<span style="color:var(--bad)">❌ ' + d.erro + '</span>';
        }})
        .catch(function(e){{
          b.textContent = '🔌 Testar Conexão';
          b.disabled = false;
          r.innerHTML = '<span style="color:var(--bad)">❌ Erro: ' + e.message + '</span>';
        }});
    }}
    function abrirModalQueryIAEdit(){{var s=document.getElementById('ia-query-modelo-edit'),st=document.getElementById('modelos-store-edit');if(st&&s){{s.innerHTML=st.innerHTML}}document.getElementById('modal-query-ia-edit').classList.add('show')}}
    function fecharModalQueryIAEdit(){{document.getElementById('modal-query-ia-edit').classList.remove('show')}}
    function gerarQueryIAEdit(){{
      var desc=document.getElementById('ia-query-desc-edit').value.trim();
      if(!desc){{alert('Descreva a query primeiro.');return}}
      var driver=(document.querySelector('[name=sql_driver]')||{{}}).value||'postgresql';
      var b=document.getElementById('btn-gerar-query-edit');b.classList.add('loading');b.disabled=true;
      document.getElementById('ia-query-erro-edit').style.display='none';
      fetch('/portal/conectores/gerar-query-ia',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{descricao:desc,driver:driver}})}})
        .then(function(r){{return r.json()}})
        .then(function(d){{
          b.classList.remove('loading');b.disabled=false;
          if(d.ok){{
            document.getElementById('ia-query-resultado-edit').style.display='block';
            document.getElementById('ia-query-conteudo-edit').value=d.query;
            document.getElementById('btn-copiar-query-edit').style.display='inline-block';
          }}else{{var e=document.getElementById('ia-query-erro-edit');e.textContent=d.erro;e.style.display='block'}}
        }})
        .catch(function(e){{b.classList.remove('loading');b.disabled=false;var er=document.getElementById('ia-query-erro-edit');er.textContent='Erro: '+e.message;er.style.display='block'}})
    }}
    function copiarQueryIAEdit(){{
      document.getElementById('sql-query').value=document.getElementById('ia-query-conteudo-edit').value;
      fecharModalQueryIAEdit();
    }}
    </script>"""
    return templates.page("Editar conector", content, active="conectores", user=_user())


@bp.route("/conectores/<int:cid>/excluir")
@auth.admin_required
def conector_excluir(cid: int):
    con = db.buscar_conector(cid)
    if not con:
        flash("Conector não encontrado.", "bad")
    else:
        db.deletar_conector(cid)
        db.registrar_auditoria(_user()["login"], "admin", "excluir_conector",
                               alvo=con["nome"], ip=request.remote_addr)
        flash(f"Conector '{con['nome']}' excluído.", "ok")
    return redirect(url_for("portal.conectores"))


def _parse_config(raw: str | dict) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# USO DE TOKENS (analise de consumo, nao pagamento — cobranca e contrato anual externo)
# ---------------------------------------------------------------------------

@bp.route("/uso-tokens")
@auth.login_required
def uso_tokens():
    u = _user()
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    # agregacao por cliente
    agregado = db.agregar_uso_por_cliente()
    total_geral = sum(r["total_tokens"] for r in agregado)
    total_chamadas = sum(r["chamadas"] for r in agregado)
    body = ""
    for r in agregado:
        body += f"""<tr>
          <td>{clientes.get(r['cliente_id'], '?')}</td>
          <td><code>{r['modelo']}</code></td>
          <td>{templates.badge(r['origem'])}</td>
          <td style="text-align:right">{r['total_tokens']}</td>
          <td style="text-align:right">{r['total_prompt']}</td>
          <td style="text-align:right">{r['total_completion']}</td>
          <td style="text-align:right">{r['chamadas']}</td>
        </tr>"""
    clientes_opts = "".join(
        f'<option value="{c["id"]}">{c["nome"]}</option>' for c in db.listar_clientes())
    tabela = f"""<table><thead><tr><th>Cliente</th><th>Modelo</th><th>Origem</th><th>Total tokens</th><th>Prompt</th><th>Completion</th><th>Chamadas</th></tr></thead>
      <tbody>{body or '<tr><td colspan=8 class="empty">Nenhum consumo registrado ainda.</td></tr>'}</tbody></table>"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Consumo de tokens por chamada ao LLM (modelo cadastrado). Cobrança via contrato anual externo.
    </div>
    <div class="grid grid-3" style="margin-bottom:16px">
      <div class="kpi"><div class="label">Total tokens</div><div class="value">{total_geral:,}</div><div class="sub">processados</div></div>
      <div class="kpi"><div class="label">Chamadas</div><div class="value">{total_chamadas:,}</div><div class="sub">ao LLM</div></div>
    </div>
    {tabela}"""
    return templates.page("Uso de Tokens", content, active="uso_tokens", user=u)



# ---------------------------------------------------------------------------
# AUDITORIA (rastreabilidade / LGPD)


# ---------------------------------------------------------------------------
# AUDITORIA (rastreabilidade / LGPD)
# ---------------------------------------------------------------------------

def _rastreio_link(a: dict) -> str:
    """Retorna link Rastreio se a auditoria tiver trace_id no detalhe E o
    trace ainda existir (traces removidos por limpeza/retencao nao mostram
    o link — evita 'Trace nao encontrado' no popup)."""
    d = a.get("detalhe", "")
    if d.startswith("trace:"):
        tid = d.split("|")[0].replace("trace:", "").strip()
        if tid.isdigit() and db.buscar_trace(int(tid)):
            return f'<a href="#" onclick="abrirRastreio({tid});return false" style="font-size:12px">🔍 Rastreio</a>'
    return ""


@bp.route("/auditoria")
@auth.admin_required
def auditoria():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    filtro_usuario = request.args.get("usuario", "").strip()
    limite = request.args.get("limite", 50, type=int)
    if limite not in (10, 20, 50, 100, 200):
        limite = 50
    pagina = request.args.get("pagina", 1, type=int)

    # Carrega registros com filtro (limite generoso para paginar)
    rows = db.listar_auditoria(5000, usuario=filtro_usuario or None)
    total = len(rows)
    total_paginas = max(1, (total + limite - 1) // limite)
    pagina = max(1, min(pagina, total_paginas))
    inicio = (pagina - 1) * limite
    fim = inicio + limite
    pagina_atual = rows[inicio:fim]

    def _url(**kw):
        args = dict(request.args)
        args.update(kw)
        return url_for("portal.auditoria", **args)

    body = ""
    for a in pagina_atual:
        cliente = clientes.get(a["cliente_id"], "-") if a["cliente_id"] else "-"
        body += f"""<tr>
          <td class="muted">{a['criado_em']}</td>
          <td><b>{a['usuario']}</b></td>
          <td>{templates.badge(a['papel'])}</td>
          <td>{a['acao']}</td>
          <td>{a['alvo'] or '-'}</td>
          <td>{cliente}</td>
          <td class="muted">{a['ip'] or '-'}</td>
          <td style="font-size:12px">{_rastreio_link(a)}</td>
        </tr>"""

    # Paginacao
    pag_btns = ""
    if total_paginas > 1:
        pag_btns = '<div class="paginacao" style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:13px">'
        pag_btns += f'<span class="muted">{inicio+1}–{min(fim, total)} de {total}</span>'
        pag_btns += '<div style="display:flex;gap:4px">'
        if pagina > 1:
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=1)}" style="padding:4px 10px;font-size:12px">«</a>'
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=pagina-1)}" style="padding:4px 10px;font-size:12px">‹</a>'
        for p in range(max(1, pagina-2), min(total_paginas, pagina+2)+1):
            if p == pagina:
                pag_btns += f'<button class="btn" style="padding:4px 10px;font-size:12px">{p}</button>'
            else:
                pag_btns += f'<a class="btn ghost" href="{_url(pagina=p)}" style="padding:4px 10px;font-size:12px">{p}</a>'
        if pagina < total_paginas:
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=pagina+1)}" style="padding:4px 10px;font-size:12px">›</a>'
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=total_paginas)}" style="padding:4px 10px;font-size:12px">»</a>'
        pag_btns += '</div></div>'

    # Opcoes do seletor de limite
    limite_opts = " ".join(f'<option value="{n}" {"selected" if limite==n else ""}>{n}</option>' for n in [10,20,50,100,200])

    # Lista de usuarios para o filtro
    usuarios = sorted(set(r["usuario"] for r in rows))

    tabela = f"""<table><thead><tr><th>Data/Hora</th><th>Usuário</th><th>Papel</th><th>Ação</th><th>Alvo</th><th>Cliente</th><th>IP</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=7 class="empty">Nenhum evento registrado.</td></tr>'}</tbody></table>{pag_btns}"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Rastreabilidade completa (LGPD): todo login e toda ação sensível é registrada com usuário, papel, alvo, cliente e IP.
    </div>
    <div class="card">
      <h3 style="margin-top:0">Filtros</h3>
      <form method="get" style="display:flex;gap:8px;align-items:end;flex-wrap:wrap">
        <div><label>Usuário</label>
          <select name="usuario">
            <option value="">todos</option>
            {''.join(f'<option value="{u}" {"selected" if filtro_usuario==u else ""}>{u}</option>' for u in usuarios)}
          </select></div>
        <div><label>Por página</label>
          <select name="limite" onchange="this.form.submit()">
            {limite_opts}
          </select></div>
        <div><button class="btn ghost" type="submit">Filtrar</button>
          <a class="btn ghost" href="/portal/auditoria" style="margin-left:4px">Limpar</a></div>
      </form>
    </div>
    {tabela}
    <div class="modal-overlay" id="modal-rastreio" onclick="if(event.target===this)fecharRastreio()">
      <div class="modal-box" style="max-width:960px;width:94%;max-height:85vh;overflow-y:auto">
        <div id="rastreio-conteudo"><p class="muted">Carregando...</p></div>
        <div style="text-align:center;margin-top:14px">
          <button class="btn ghost" onclick="fecharRastreio()">Fechar</button>
        </div>
      </div>
    </div>
    <script>
    function abrirRastreio(tid){{
      document.getElementById('modal-rastreio').classList.add('show');
      document.getElementById('rastreio-conteudo').innerHTML = '<p class="muted">Carregando...</p>';
      fetch('/portal/rastreio/'+tid).then(r=>r.json()).then(d=>{{
        if(!d.ok){{document.getElementById('rastreio-conteudo').innerHTML='<p class="badge bad">Erro: '+d.erro+'</p>';return}}
        var t=d.trace;
        var h='<h3>Rastreio #'+t.id+'</h3><p class="muted">Pergunta: <b>'+t.pergunta+'</b></p><hr>';
        h+='<div style="display:flex;gap:4px;margin-bottom:14px;flex-wrap:wrap">';
        var p=t.params||{{}}; var pk=Object.keys(p);
        var c=t.conectores||[]; var rg=t.rag||[];
        var passos=[
          {{n:1, cor:"#2563eb", rotulo:"Params", detalhe:pk.length?pk.join(", "):"(nenhum)"}},
          {{n:2, cor:"#7c3aed", rotulo:"Conectores", detalhe:c.length?c.length+" exec(s)":"(nenhum)"}},
          {{n:3, cor:"#059669", rotulo:"RAG", detalhe:rg.length?rg.length+" doc(s)":"(vazio)"}},
          {{n:4, cor:"#d97706", rotulo:"Modelo", detalhe:t.modelo+" ("+t.tempo_ms+"ms)"+(t.modelo_fallback?" fallback":"")}},
        ];
        for(var i=0;i<passos.length;i++){{var s=passos[i];
          h+='<div style="flex:1;min-width:120px;background:var(--panel-soft);border-radius:8px;padding:10px;border-left:3px solid '+s.cor+'">';
          h+='<div style="font-size:11px;color:'+s.cor+';font-weight:700">PASSO '+s.n+'</div>';
          h+='<div style="font-size:14px;font-weight:600;margin:2px 0">'+s.rotulo+'</div>';
          h+='<div style="font-size:11px;color:var(--muted-soft)">'+s.detalhe+'</div></div>';
        }}
        h+='</div>';
        h+='<hr>';
        h+='<div style="margin-bottom:12px"><b>Detalhamento:</b></div>';
        h+='<div style="margin-bottom:8px;background:var(--code-bg);border-radius:6px;padding:8px">';
        h+='<div style="font-weight:600;color:#2563eb">1. Parametros extraidos</div>';
        h+=pk.length?pk.map(function(k){{return '<code style="background:var(--panel-soft);padding:2px 6px;border-radius:4px">'+k+' = '+p[k]+'</code>'}}).join(' '):'<span class="muted">Nenhum parametro extraido</span>';
        h+='</div>';
        h+='<div style="margin-bottom:8px;background:var(--code-bg);border-radius:6px;padding:8px">';
        h+='<div style="font-weight:600;color:#7c3aed">2. Conectores executados</div>';
        if(c.length){{for(var i=0;i<c.length;i++){{var f=c[i];
          if(f.erro){{h+='<div style="color:var(--bad)"> ERRO '+f.conector+': '+f.erro+'</div>';}}
          else{{h+='<div> OK <b>'+f.conector+'</b>.'+f.tool+'<br><span class="muted" style="font-size:11px">args: '+JSON.stringify(f.args)+' | retorno: '+(f.resultado?f.resultado.length+' registros':'vazio')+'</span></div>';}}
        }}}}else{{h+='<span class="muted">Nenhum conector executado</span>';}}
        h+='</div>';
        h+='<div style="margin-bottom:8px;background:var(--code-bg);border-radius:6px;padding:8px">';
        h+='<div style="font-weight:600;color:#059669">3. RAG (base de conhecimento)</div>';
        h+=rg.length?'<span class="muted">'+rg.map(function(x){{return (x.texto||'').substring(0,80)}}).join(' | ')+'</span>':'<span class="muted">Vazio</span>';
        h+='</div>';
        h+='<div style="margin-bottom:12px;background:var(--code-bg);border-radius:6px;padding:8px">';
        h+='<div style="font-weight:600;color:#d97706">4. Modelo de IA</div>';
        h+='Modelo: <code>'+t.modelo+'</code>'+(t.modelo_fallback?' <span class="badge warn">fallback</span>':'')+' | Tokens: '+(t.tokens?t.tokens.total_tokens||0:0)+' | Tempo: '+t.tempo_ms+'ms';
        h+='</div>';
        h+='<hr><div><b>Resposta:</b></div><pre style="background:var(--code-bg);padding:10px;border-radius:6px;font-size:12px;white-space:pre-wrap;margin:6px 0 0">'+t.resposta+'</pre>';
        document.getElementById('rastreio-conteudo').innerHTML=h;
      }}).catch(e=>{{document.getElementById('rastreio-conteudo').innerHTML='<p class="badge bad">Erro: '+e.message+'</p>'}});
    }}
    function fecharRastreio(){{document.getElementById('modal-rastreio').classList.remove('show');}}
    </script>
"""
    return templates.page("Auditoria", content, active="auditoria", user=_user())


def _url_dias(d):
    args = dict(request.args)
    args["dias"] = str(d)
    return url_for("portal.observabilidade", **args)


@bp.route("/observabilidade")
@auth.admin_required
def observabilidade():
    """Dashboard de observabilidade: KPIs, graficos e tabela de feedback."""
    u = _user()
    dias = request.args.get("dias", 7, type=int)
    if dias not in (1, 7, 30, 90):
        dias = 7

    metricas = db.listar_metricas(dias)
    feedbacks = db.listar_feedback(limite=50)

    total_chamadas = sum(m["chamadas"] for m in metricas)
    total_tokens = sum(m["tokens_total"] for m in metricas)
    total_erros = sum(m["erros"] for m in metricas)
    total_util = sum(m["feedback_util"] for m in metricas)
    total_fb = sum(m["feedback_total"] for m in metricas)
    taxa_acerto = f"{(total_util / total_fb * 100):.0f}%" if total_fb else "--"
    lat_media = int(sum(m["latencia_p50"] * m["chamadas"] for m in metricas) / total_chamadas) if total_chamadas else 0

    # Drift detection
    comparacao = db.comparar_periodos(dias)
    drift_rows = ""
    for c in comparacao:
        d_tx = c.get("delta_taxa")
        d_lat = c.get("delta_latencia")
        tx_delta_class = "delta-ok" if (d_tx or 0) >= 0 else "delta-bad"
        lat_delta_class = "delta-bad" if (d_lat or 0) > 10 else "delta-ok"
        tx_delta_str = f"{d_tx:+.1f}%" if d_tx is not None else "--"
        lat_delta_str = f"{d_lat:+.1f}%" if d_lat is not None else "--"
        drift_rows += f'<tr><td><b>{c["modelo"]}</b></td><td>{c["chamadas"]}</td><td>{c["taxa_acerto"]}</td><td>{c["taxa_anterior"]}</td><td class="{tx_delta_class}">{tx_delta_str}</td><td>{c["latencia_media"]}ms</td><td>{c["latencia_anterior"]}ms</td><td class="{lat_delta_class}">{lat_delta_str}</td></tr>'
    if not drift_rows:
        drift_rows = '<tr><td colspan=8 class="empty">Sem dados suficientes para comparacao.</td></tr>'

    # Alertas
    alertas = db.verificar_alertas()
    alerta_html = ''
    for a in alertas:
        alerta_html += f'<div class="badge warn" style="margin:4px;display:inline-block">⚠️ {a["desc"]} ({a["modelo"]}: {a["valor"]}ms) <span style="cursor:pointer;font-size:11px;color:var(--muted-soft)" onclick="infoAlerta()">ⓘ</span></div>'
    if not alertas:
        alerta_html = '<span class="muted">Nenhum alerta ativo — tudo ok</span>'

    # Cost intelligence
    custos = db.calcular_custos(dias)
    custo_rows = ""
    custo_total = 0.0
    for c in custos:
        custo_total += c["custo"]
        custo_rows += f'<tr><td><b>{c["modelo"]}</b></td><td>{c["tokens"]:,}</td><td>R$ {c["custo"]:.4f}</td><td>R$ {c["preco_milhao"]}/M</td></tr>'
    if not custo_rows:
        custo_rows = '<tr><td colspan=4 class="empty">Sem dados de custo.</td></tr>'

    fb_rows = ""
    for f in feedbacks[:20]:
        fb_icon = f'<span style="color:var(--ok)">👍</span>' if f["feedback"] == "util" else f'<span style="color:var(--bad)">👎</span>'
        fb_rows += f'<tr><td>{fb_icon}</td><td>{f["tipo"]}</td><td class="muted">{f["pergunta"][:80]}</td><td>{f["resposta"][:60]}</td><td>{f["criado_em"][:16]}</td></tr>'

    spark_html = ""
    if metricas:
        # Agrega por data: soma chamadas do mesmo dia
        from collections import defaultdict as _dd
        dia = _dd(int)
        for m in metricas:
            dia[m["data"]] += m["chamadas"]
        items = sorted(dia.items())  # (data, chamadas)
        max_c = max(c for _, c in items) or 1
        for data, chamadas in items[-30:]:
            h = int(chamadas / max_c * 40)
            spark_html += f'<div class="bar" style="height:{h}px" title="{data}: {chamadas} chamadas"></div>'

    content = f"""
    <style>
    .kpis{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;max-width:100%}}
    .kpi-card{{flex:1 1 130px;min-width:120px;max-width:220px;background:var(--panel-soft);border-radius:10px;padding:14px}}
    .kpi-card .label{{font-size:11px;color:var(--muted-soft);text-transform:uppercase;letter-spacing:.5px}}
    .kpi-card .value{{font-size:28px;font-weight:700;margin:4px 0}}
    .kpi-card .sub{{font-size:11px;color:var(--muted-soft)}}
    .sparkline{{display:flex;align-items:flex-end;gap:1px;height:40px;margin:8px 0}}
    .sparkline .bar{{flex:1;min-width:2px;background:linear-gradient(to top,#2563eb,#60a5fa);border-radius:1px 1px 0 0}}
    .delta-ok{{color:var(--ok);font-weight:700}}
    .delta-bad{{color:var(--bad);font-weight:700}}
    </style>
    <div class="muted" style="margin-bottom:14px;display:flex;justify-content:space-between;align-items:end">
      <span>Dashboard de observabilidade — metricas consolidadas dos ultimos {dias} dias.
      [<a href="{_url_dias(1)}">1d</a> | <a href="{_url_dias(7)}">7d</a> | <a href="{_url_dias(30)}">30d</a> | <a href="{_url_dias(90)}">90d</a>]</span>
      <button class="btn" id="btn-processar" onclick="processarMetricas()" style="font-size:12px;padding:4px 10px">Processar metricas</button>
    </div>
    <script>
    function infoAlerta(){{alert("Os alertas sao disparados quando as metricas ultrapassam thresholds definidos. Ajuste os valores em Cadastros > Alertas.");}}
    function processarMetricas(){{
      var b=document.getElementById("btn-processar");
      b.innerHTML="Processando...";b.disabled=true;
      fetch("/portal/processar-metricas").then(function(r){{
        if(!r.ok){{ throw new Error("HTTP "+r.status); }}
        return r.json();
      }}).then(function(d){{
        b.innerHTML="OK ("+d.inseridas+" linhas)";
        setTimeout(function(){{window.location.reload();}},1000);
      }}).catch(function(e){{
        // 302 -> login (sessao expirada) retorna HTML: o json() falharia
        // com "Erro" mudo. Mensagem clara + leva para o login.
        b.innerHTML="Sessao expirada — relogando...";
        b.disabled=false;
        window.location.href="/portal/login";
      }});
    }}
    </script>
    <div class="kpis">
      <div class="kpi-card"><div class="label">Chamadas</div><div class="value">{total_chamadas:,}</div><div class="sub">ultimos {dias}d</div></div>
      <div class="kpi-card"><div class="label">Taxa de Acerto</div><div class="value" style="color:{'var(--ok)' if taxa_acerto!='--' else 'var(--muted-soft)'}">{taxa_acerto}</div><div class="sub">{total_util}/{total_fb} uteis</div></div>
      <div class="kpi-card"><div class="label">Latencia Media</div><div class="value">{lat_media}ms</div><div class="sub">ultimos {dias}d</div></div>
      <div class="kpi-card"><div class="label">Tokens</div><div class="value">{total_tokens:,}</div><div class="sub">{total_chamadas} chamadas</div></div>
      <div class="kpi-card"><div class="label">Erros</div><div class="value" style="color:{'var(--bad)' if total_erros else 'var(--ok)'}">{total_erros}</div><div class="sub">{'sem erros' if not total_erros else f'{total_erros} falhas'}</div></div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <b>Alertas ativos</b>
      {alerta_html}
    </div>
    <div class="card" style="margin-bottom:16px">
      <b>Chamadas por dia</b>
      <div class="sparkline">{spark_html}</div>
    </div>
    <h3>Drift Detection — comparacao com periodo anterior</h3>
    <table>
      <thead><tr><th>Modelo</th><th>Chamadas</th><th>Taxa Acerto</th><th>Anterior</th><th>Delta</th><th>Latencia</th><th>Anterior</th><th>Delta</th></tr></thead>
      <tbody>{drift_rows}</tbody>
    </table>
    <h3>Cost Intelligence — custo estimado</h3>
    <table>
      <thead><tr><th>Modelo</th><th>Tokens<span style=\"cursor:help;margin-left:4px;color:#4a9eff;font-size:13px\" onclick=\"alert('Os tokens no dashboard de observabilidade consideram apenas as respostas do agente (tabela tracing). Chamadas de teste no chat livre ou skills que n\\u00e3o passam pelo agente n\\u00e3o s\\u00e3o contabilizadas aqui. Para o total geral de tokens, consulte a p\\u00e1gina Uso de Tokens.')\">ⓘ</span></th><th>Custo ({dias}d)</th><th>Preco/M</th></tr></thead>
      <tbody>{custo_rows}</tbody>
      <tfoot><tr><td><b>Total</b></td><td></td><td><b>R$ {custo_total:.4f}</b></td><td></td></tr></tfoot>
    </table>
    <h3>Feedback recente</h3>
    <table>
      <thead><tr><th></th><th>Tipo</th><th>Pergunta</th><th>Resposta</th><th>Quando</th></tr></thead>
      <tbody>{fb_rows or '<tr><td colspan=5 class="empty">Nenhum feedback registrado.</td></tr>'}</tbody>
    </table>
"""
    return templates.page("Observabilidade", content, active="observabilidade", user=u)


@bp.route("/alertas-config", methods=["GET", "POST"])
@auth.admin_required
def alertas_config():
    """Pagina de configuracao de alertas da observabilidade."""
    u = _user()
    if request.method == "POST":
        for chave in ("taxa_acerto_min", "latencia_max", "erros_max"):
            val = request.form.get(chave)
            if val:
                db.salvar_alerta_config(chave, float(val))
        flash("Configuracoes salvas.", "ok")
        return redirect(url_for("portal.alertas_config"))
    config = db.obter_alertas_config()
    rows = ""
    for chave in ("taxa_acerto_min", "latencia_max", "erros_max"):
        cfg = config.get(chave, {"valor": 0, "descricao": chave})
        rows += f'<tr><td><b>{cfg["descricao"]}</b></td><td><input name="{chave}" type="number" step="any" value="{cfg["valor"]}" style="width:120px"></td></tr>'
    content = f"""<div class="card" style="max-width:600px">
      <h3 style="margin-top:0">Alertas da Observabilidade</h3>
      <form method="post">
        {templates.csrf_field()}<table>
          <thead><tr><th>Alerta</th><th>Valor</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        <div style="margin-top:12px"><button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/observabilidade">Voltar</a></div>
      </form>
    </div>"""
    return templates.page("Alertas", content, active="alertas_config", user=u)


@bp.route("/teste-ab", methods=["GET", "POST"])
@auth.login_required
def teste_ab():
    """Teste A/B entre modelos: reexecuta perguntas do feedback com outro modelo."""
    u = _user()
    papel = (u or {}).get("papel", "")
    if papel not in ("admin", "gestor"):
        flash("Acesso restrito a administradores e gestores.", "bad")
        return redirect(url_for("portal.monitorar"))

    from . import llm_client
    import json as _json

    # Carrega modelos
    clientes = db.listar_clientes()
    modelos = []
    if clientes:
        modelos = db.listar_modelos(clientes[0]["id"])

    if request.method == "POST":
        acao = request.form.get("acao", "executar")

        # ── PASSO 2: Analisar respostas ──
        if acao == "analisar":
            raw = request.form.get("resultados_json", "[]")
            try:
                resultados = _json.loads(raw)
            except Exception:
                resultados = []
            juiz_id = request.form.get("modelo_juiz", "").strip()
            modelo_juiz = next((m for m in modelos if str(m["id"]) == juiz_id), None)
            if not modelo_juiz or not resultados:
                flash("Dados invalidos para analise.", "bad")
                return redirect(url_for("portal.teste_ab"))

            # Auditoria do julgamento
            db.registrar_auditoria(
                u["login"], u["papel"], "teste_ab_julgamento",
                alvo=f"{len(resultados)} respostas, juiz: {modelo_juiz['modelo']}",
                ip=request.remote_addr or "",
            )

            vereditos = []
            vereditos = []
            justificativas = []
            for r in resultados:
                r_orig = r.get("original_resp", "")
                r_novo = r.get("novo_resp", "")
                pergunta = r.get("pergunta", "")
                prompt_juiz = (
                    "Voce e um analista de qualidade de respostas de IA. "
                    "Compare as duas respostas abaixo e diga qual e a melhor.\n\n"
                    f"Pergunta: {pergunta}\n\n"
                    f"Resposta A (modelo atual): {r_orig}\n\n"
                    f"Resposta B (novo modelo): {r_novo}\n\n"
                    "Responda no formato:\n"
                    "VOTO: A, B ou EMPATE\n"
                    "JUSTIFICATIVA: motivo em ate 2 linhas"
                )
                out = llm_client.chat(modelo_juiz, [
                    {"role": "system", "content": "Voce e um juiz imparcial de respostas de IA."},
                    {"role": "user", "content": prompt_juiz},
                ])
                voto = "EMPATE"
                justificativa = ""
                if out.get("ok"):
                    texto = (out.get("content", "") or "").strip()
                    linhas = texto.split("\n")
                    achou_voto = False
                    for linha in linhas:
                        ls = linha.strip().upper()
                        if ls.startswith("VOTO:"):
                            v = ls.replace("VOTO:", "").strip()
                            if "EMPATE" in v or v == "":
                                voto = "EMPATE"
                            elif v.startswith("A"):
                                voto = "A"
                            elif v.startswith("B"):
                                voto = "B"
                            achou_voto = True
                        elif ls.startswith("JUSTIFICATIVA:"):
                            justificativa = linha.split(":", 1)[1].strip() if ":" in linha else ""
                    # Se nao achou JUSTIFICATIVA mas achou VOTO, pega o resto do texto como justificativa
                    if not justificativa and achou_voto:
                        for linha in linhas:
                            ls = linha.strip().upper()
                            if ls.startswith("VOTO:"):
                                continue
                            if ls.startswith("JUSTIFICATIVA:"):
                                continue
                            if ls.strip():
                                justificativa = (justificativa + " " + linha.strip()).strip()
                vereditos.append(voto)
                justificativas.append(justificativa)
                # ── salva julgamento (fonte p/ fine-tuning / benchmark) ──
                try:
                    db.salvar_julgamento(
                        pergunta=pergunta,
                        resposta_a=r_orig,
                        resposta_b=r_novo,
                        modelo_a=r.get("modelo_orig", ""),
                        modelo_b=r.get("modelo_novo", ""),
                        voto=voto,
                        justificativa=justificativa,
                        modelo_juiz=modelo_juiz["modelo"],
                        criado_por=u["login"],
                    )
                except Exception:  # noqa: BLE001 — nunca quebra a analise
                    pass

            # Renderiza com cores
            rows = ""
            for i, r in enumerate(resultados):
                v = vereditos[i] if i < len(vereditos) else "EMPATE"
                just = justificativas[i] if i < len(justificativas) else ""
                just_attr = just.replace("'", "\\'").replace('"', '&quot;') if just else ""
                cor_a = "rgba(34,197,94,.1)" if v == "A" else ("rgba(239,68,68,.08)" if v == "B" else "")
                cor_b = "rgba(34,197,94,.1)" if v == "B" else ("rgba(239,68,68,.08)" if v == "A" else "")
                info_icon = f' <span class="info-icon" onclick="alert(\'{just_attr}\')" title="Clique para detalhes" style="cursor:pointer;font-size:12px;color:var(--muted)">ⓘ</span>' if just else ""
                badge_v = {"A": f'<span class="badge ok">Venceu{info_icon}</span>',
                           "B": f'<span class="badge ok">Venceu{info_icon}</span>',
                           "EMPATE": f'<span class="badge neutral">Empate{info_icon}</span>'}.get(v, "")
                vencedor = "Original" if v == "A" else ("Novo" if v == "B" else "Empate")
                rows += f"""<tr>
                  <td style="vertical-align:top;font-size:12px">{i+1}</td>
                  <td style="vertical-align:top;font-size:12px;max-width:200px">{templates.h(r.get('pergunta','')[:200])}</td>
                  <td style="vertical-align:top;font-size:12px;max-width:220px;background:{cor_a}">
                    <span class="muted" style="font-size:11px">({r.get('modelo_orig','?')})</span><br>{templates.h(r.get('original_resp','')[:350])}
                  </td>
                  <td style="vertical-align:top;font-size:12px;max-width:220px;background:{cor_b}">
                    <span class="muted" style="font-size:11px">({r.get('modelo_novo','?')})</span><br>{templates.h(r.get('novo_resp','')[:350])}
                  </td>
                  <td style="vertical-align:top;font-size:12px;text-align:center">{badge_v}<br><span class="muted" style="font-size:10px">{vencedor}</span></td>
                </tr>"""
            content = f"""<div class="card" style="max-width:100%">
  <h3 style="margin-top:0">Resultado da Analise</h3>
  <p class="muted">Julgamento por <b>{modelo_juiz['modelo']}</b> — {len(resultados)} resposta(s).</p>
  <table style="font-size:12px">
  <thead><tr><th>#</th><th>Pergunta</th><th>Resposta Original</th><th>Resposta Novo Modelo</th><th>Veredito</th></tr></thead>
  <tbody>{rows}</tbody>
  </table>
  <div style="margin-top:14px"><a class="btn ghost" href="/portal/teste-ab">Novo teste</a></div>
</div>"""
            return templates.page("Teste A/B", content, active="teste_ab", user=u)

        # ── PASSO 1: Executar teste ──
        selecionados = request.form.getlist("selecionados")
        alvo = request.form.get("modelo_alvo", "").strip()
        if not selecionados:
            flash("Selecione ao menos um feedback para testar.", "warn")
            return redirect(url_for("portal.teste_ab"))
        if len(selecionados) > 10:
            flash("Selecione no máximo 10 perguntas por execução — cada uma roda o agente completo (conectores + RAG + LLM) e o julgamento.", "warn")
            return redirect(url_for("portal.teste_ab"))
        if not alvo or not alvo.isdigit():
            flash("Selecione um modelo alvo para o teste.", "warn")
            return redirect(url_for("portal.teste_ab"))
        modelo_alvo = next((m for m in modelos if str(m["id"]) == alvo), None)
        if not modelo_alvo:
            flash("Modelo alvo nao encontrado.", "bad")
            return redirect(url_for("portal.teste_ab"))
        if not modelo_alvo.get("base_url", "").strip() or modelo_alvo["base_url"].strip() == "-":
            flash(f"O modelo '{modelo_alvo['nome']}' nao tem endpoint configurado. Va em Modelos IA e configure a URL base.", "bad")
            return redirect(url_for("portal.teste_ab"))

        fb_list = []
        for fid in selecionados:
            fb = db.buscar_feedback(int(fid))
            if fb:
                fb_list.append(fb)

        resultados = []
        for fb in fb_list:
            pergunta = fb["pergunta"]
            original = fb["resposta"]
            modelo_orig = "desconhecido"
            if fb.get("trace_id"):
                trace = db.buscar_trace(fb["trace_id"])
                if trace and trace.get("modelo"):
                    modelo_orig = trace["modelo"]
            # Executa via pipeline completo do agente (conectores + RAG + LLM)
            from . import agente as _agente
            agente_orig = db.buscar_agente(fb.get("agente_id") or 0) if fb.get("agente_id") else None
            if agente_orig:
                agente_test = dict(agente_orig)
                agente_test["modelo_id"] = modelo_alvo["id"]
                agente_test["modelo_secundario_id"] = None
                out = _agente.responder(agente_test, pergunta, "teste_ab", "",
                                        anonimizar=False)
                nova_resp = out.get("content", "") if out.get("ok") else f"(erro pipeline: {out.get('error', 'falha')})"
            elif fb.get("trace_id"):
                # Reusa dados do trace original (conectores + RAG) com novo modelo
                trace = db.buscar_trace(fb["trace_id"])
                if trace:
                    conectores_trace = trace.get("conectores", []) or []
                    rag_trace = trace.get("rag", []) or []
                    # Monta prompt igual ao agente original (sem skills - nao temos)
                    system = "Voce e um assistente corporativo da BlueShift.\n\n"
                    blocos = []
                    for f in conectores_trace:
                        if "erro" in f:
                            continue
                        blocos.append(f"[{f.get('conector')}.{f.get('tool')}] "
                                      f"args={f.get('args')} -> {f.get('resultado')}")
                    if blocos:
                        system += "DADOS DE SISTEMA (conectores executados — FONTE PRIMARIA):\n" + "\n".join(blocos) + "\n\n"
                    system += "CONTEXTO (base de conhecimento — FONTE SECUNDARIA):\n"
                    system += "\n".join(f"- {c.get('texto','')}" for c in rag_trace) or "(vazio)"
                    out = llm_client.chat(modelo_alvo, [
                        {"role": "system", "content": system},
                        {"role": "user", "content": pergunta},
                    ])
                    nova_resp = out.get("content", "") if out.get("ok") else f"(erro: {out.get('error', 'falha na requisicao')})"
                else:
                    nova_resp = "(erro: trace nao encontrado)"
            else:
                out = llm_client.chat(modelo_alvo, [
                    {"role": "system", "content": "Voce e um assistente corporativo. Responda de forma objetiva e direta com base nos dados disponiveis."},
                    {"role": "user", "content": pergunta},
                ])
                nova_resp = out.get("content", "") if out.get("ok") else f"(erro: {out.get('error', 'falha na requisicao')})"
            resultados.append({
                "pergunta": pergunta,
                "original_resp": agente_mod._limpar_imagens(original),
                "novo_resp": agente_mod._limpar_imagens(nova_resp),
                "modelo_orig": modelo_orig,
                "modelo_novo": modelo_alvo["modelo"],
            })

        db.registrar_auditoria(
            u["login"], u["papel"], "teste_ab",
            alvo=f"{len(resultados)} perguntas, modelo alvo: {modelo_alvo['modelo']}",
            ip=request.remote_addr or "",
        )

        # Renderiza resultados + formulario de julgamento
        rows = ""
        for i, r in enumerate(resultados, 1):
            rows += f"""<tr>
              <td style="vertical-align:top;font-size:12px">{i}</td>
              <td style="vertical-align:top;font-size:12px;max-width:250px">{templates.h(r['pergunta'][:200])}</td>
              <td style="vertical-align:top;font-size:12px;max-width:250px;background:rgba(34,197,94,.05)">
                <span class="muted" style="font-size:11px">({r['modelo_orig']})</span><br>{templates.h(r['original_resp'][:400])}
              </td>
              <td style="vertical-align:top;font-size:12px;max-width:250px;background:rgba(59,130,246,.05)">
                <span class="muted" style="font-size:11px">({r['modelo_novo']})</span><br>{templates.h(r['novo_resp'][:400])}
              </td>
            </tr>"""
        resultados_json = templates.h(_json.dumps(resultados, ensure_ascii=False))
        juiz_opts = "".join(f'<option value="{m["id"]}">{m["nome"]} ({m["modelo"]})</option>' for m in modelos)
        content = f"""<div class="card" style="max-width:100%">
  <h3 style="margin-top:0">Resultado do Teste A/B</h3>
  <p class="muted">Comparacao entre o modelo original e <b>{modelo_alvo['modelo']}</b> para {len(resultados)} pergunta(s).</p>
  <table style="font-size:12px">
  <thead><tr><th>#</th><th>Pergunta</th><th>Resposta Original</th><th>Resposta Novo Modelo</th></tr></thead>
  <tbody>{rows}</tbody>
  </table>
  <form method="post" style="margin-top:16px;padding:14px;background:var(--panel2);border-radius:8px">
    {templates.csrf_field()}
    <input type="hidden" name="acao" value="analisar">
    <input type="hidden" name="resultados_json" value='{resultados_json}'>
    <h4 style="margin:0 0 8px">📊 Analisar respostas</h4>
    <p class="muted" style="font-size:12px">Escolha um modelo para julgar qual resposta foi melhor (Original vs Novo).</p>
    <select name="modelo_juiz" style="max-width:400px">
      <option value="">-- selecione o modelo juiz --</option>
      {juiz_opts}
    </select>
    <div style="margin-top:10px"><button class="btn btn-spin" type="submit" onclick="this.classList.add('loading');this.innerHTML='⏳ Analisando...'">📊 Analisar respostas</button>
    <a class="btn ghost" href="/portal/teste-ab">Novo teste</a></div>
  </form>
</div>"""
        return templates.page("Teste A/B", content, active="teste_ab", user=u)

    # GET: feedbacks recentes + modelos (paginacao em memoria, padrao auditoria)
    # Fixo em 10 por pagina: o limite de selecao e 10 por execucao — paginar
    # com 20/50 nao faria sentido (mostra mais, mas so pode marcar 10).
    filtro = request.args.get("filtro", "todos")
    limite_fb = 10
    try:
        todos_fb = db.listar_feedback(limite=5000)
    except Exception:
        todos_fb = []
    if filtro == "util":
        todos_fb = [f for f in todos_fb if f.get("feedback") == "util"]
    elif filtro == "nao_util":
        todos_fb = [f for f in todos_fb if f.get("feedback") == "nao_util"]
    total_fb = len(todos_fb)
    total_paginas = max(1, (total_fb + limite_fb - 1) // limite_fb)
    try:
        pagina_fb = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina_fb = 1
    pagina_fb = min(pagina_fb, total_paginas)
    inicio = (pagina_fb - 1) * limite_fb
    feedbacks = todos_fb[inicio:inicio + limite_fb]

    def _url_fb(**kw):
        args = {"filtro": filtro, "pagina": pagina_fb}
        args.update(kw)
        return "?" + "&".join(f"{k}={v}" for k, v in args.items())

    pag_btns = ""
    if total_paginas > 1:
        pag_btns = ('<div class="paginacao" style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:13px">'
                    f'<span class="muted">{inicio+1}–{min(inicio+limite_fb, total_fb)} de {total_fb}</span>'
                    '<div style="display:flex;gap:4px">')
        if pagina_fb > 1:
            pag_btns += f'<a class="btn ghost" href="{_url_fb(pagina=1)}" style="padding:4px 10px;font-size:12px">«</a>'
            pag_btns += f'<a class="btn ghost" href="{_url_fb(pagina=pagina_fb-1)}" style="padding:4px 10px;font-size:12px">‹</a>'
        for p in range(max(1, pagina_fb-2), min(total_paginas, pagina_fb+2)+1):
            if p == pagina_fb:
                pag_btns += f'<button class="btn" style="padding:4px 10px;font-size:12px">{p}</button>'
            else:
                pag_btns += f'<a class="btn ghost" href="{_url_fb(pagina=p)}" style="padding:4px 10px;font-size:12px">{p}</a>'
        if pagina_fb < total_paginas:
            pag_btns += f'<a class="btn ghost" href="{_url_fb(pagina=pagina_fb+1)}" style="padding:4px 10px;font-size:12px">›</a>'
            pag_btns += f'<a class="btn ghost" href="{_url_fb(pagina=total_paginas)}" style="padding:4px 10px;font-size:12px">»</a>'
        pag_btns += '</div></div>'

    filtro_links = "".join(
        f'<a class="btn ghost {"active" if filtro == v else ""}" '
        f'href="?filtro={v}" style="font-size:12px;padding:4px 10px">{l}</a>'
        for v, l in [("todos", "Todos"), ("util", "👍 Uteis"), ("nao_util", "👎 Nao uteis")]
    )

    fb_opts = ""
    for fb in feedbacks:
        tid = fb.get("trace_id", "")
        pergunta_curta = (fb.get("pergunta", "") or "")[:80]
        fb_opts += f"""<tr>
          <td><input type="checkbox" name="selecionados" value="{fb['id']}" style="width:auto;margin:0"></td>
          <td style="font-size:12px">{templates.h(pergunta_curta)}</td>
          <td style="font-size:11px;color:var(--muted)">{fb.get('tipo','')}</td>
          <td style="font-size:11px">{templates.h((fb.get('resposta','') or '')[:80])}...</td>
        </tr>"""

    modelos_opts = "".join(f'<option value="{m["id"]}">{m["nome"]} ({m["modelo"]})</option>' for m in modelos)

    if len(modelos) < 2:
        aviso = """<div class="flash warn">Teste A/B requer ao menos <b>2 modelos</b> cadastrados.
        Cadastre um segundo modelo em <a href="/portal/modelos">Modelos IA</a> antes de realizar o teste.</div>"""
    else:
        aviso = ""

    n_julg = db.contar_julgamentos()
    export_btn = (f'<a class="btn ghost" href="/portal/teste-ab/exportar-jsonl" style="font-size:12px" title="Baixar julgamentos salvos do Teste A/B (mascara LGPD aplicada)">📥 Exportar JSONL ({n_julg})</a>'
                  if n_julg else "")
    content = f"""
    <div class="card" style="max-width:100%">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <h3 style="margin-top:0">Teste A/B entre Modelos</h3>
        {export_btn}
      </div>
      <p class="muted">Compare a qualidade de dois modelos nas MESMAS perguntas. Selecione até <b>10 por execução</b> — cada uma roda o agente completo (conectores + RAG + LLM) e depois o juiz avalia. Navegue pela paginação para ver mais perguntas.</p>
      {aviso}
      <form method="post">
        {templates.csrf_field()}
        <h4>1. Selecione os feedbacks para testar</h4>
        <div style="margin-bottom:8px">{filtro_links}</div>
        <table>
        <thead><tr><th style="width:30px"><input type="checkbox" id="sel-todos" onchange="selTodos(this)" style="width:auto;margin:0"></th><th>Pergunta</th><th>Tipo</th><th>Resposta original</th></tr></thead>
        <tbody>{fb_opts or '<tr><td colspan="4" class="muted" style="text-align:center;padding:20px">Nenhum feedback encontrado. Faca perguntas no Chat primeiro.</td></tr>'}</tbody>
        </table>
        {pag_btns}
        <h4 style="margin-top:18px">2. Modelo alvo para o teste</h4>
        <select name="modelo_alvo" style="max-width:400px">
          <option value="">-- selecione --</option>
          {modelos_opts}
        </select>
        <div style="margin-top:18px"><button class="btn btn-spin" type="submit" {"disabled" if len(modelos) < 2 else ""} onclick="this.classList.add('loading');this.innerHTML='⏳ Executando...'">Executar Teste A/B</button></div>
      </form>
    </div>
    <script>
    function limiteSel(el){{
      var c=document.querySelectorAll('[name=selecionados]:checked').length;
      if(c>10){{el.checked=false;alert('Máximo de 10 selecionados por execução.');return}}
    }}
    function selTodos(el){{
      var cbs=document.querySelectorAll('[name=selecionados]');
      if(el.checked){{
        var n=0;
        for(var i=0;i<cbs.length&&n<10;i++){{cbs[i].checked=true;n++}}
      }}else{{for(var i=0;i<cbs.length;i++){{cbs[i].checked=false}}}}
    }}
    var cbs=document.querySelectorAll('[name=selecionados]');
    for(var i=0;i<cbs.length;i++){{cbs[i].setAttribute('onchange','limiteSel(this)')}}
    </script>"""
    return templates.page("Teste A/B", content, active="teste_ab", user=u)


@bp.route("/teste-ab/exportar-jsonl")
@auth.login_required
def teste_ab_exportar_jsonl():
    """Exporta julgamentos salvos do Teste A/B como JSONL (mascara LGPD aplicada).

    Formato rico (benchmark): pergunta, respostas A/B, voto, justificativa,
    modelos. Se quiser treinar (SFT/DPO), converte chosen/rejected do voto.
    """
    u = _user()
    papel = (u or {}).get("papel", "")
    if papel not in ("admin", "gestor"):
        flash("Acesso restrito a administradores e gestores.", "bad")
        return redirect(url_for("portal.monitorar"))
    julgamentos = db.listar_julgamentos()
    if not julgamentos:
        flash("Nenhum julgamento salvo para exportar.", "warn")
        return redirect(url_for("portal.teste_ab"))
    from . import mask as _mask
    lgpd_cfg = db.carregar_lgpd_config()
    linhas = []
    for j in julgamentos:
        linhas.append({
            "pergunta": _mask.aplicar_mascaras(j.get("pergunta", ""), lgpd_cfg),
            "resposta_original": _mask.aplicar_mascaras(j.get("resposta_a", ""), lgpd_cfg),
            "resposta_novo_modelo": _mask.aplicar_mascaras(j.get("resposta_b", ""), lgpd_cfg),
            "voto": j.get("voto", "EMPATE"),
            "justificativa": _mask.aplicar_mascaras(j.get("justificativa", ""), lgpd_cfg),
            "modelo_original": j.get("modelo_a", ""),
            "modelo_novo": j.get("modelo_b", ""),
            "modelo_juiz": j.get("modelo_juiz", ""),
            "criado_por": j.get("criado_por", ""),
            "criado_em": j.get("criado_em", ""),
        })
    from datetime import datetime as _dt
    nome = f"teste_ab_julgamentos_{_dt.now().strftime('%Y%m%d')}.jsonl"
    corpo = "\n".join(json.dumps(l, ensure_ascii=False) for l in linhas) + "\n"
    resp = make_response(corpo)
    resp.mimetype = "application/jsonl"
    resp.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
    db.registrar_auditoria(
        u["login"], u["papel"], "teste_ab_exportar",
        alvo=f"{len(linhas)} julgamentos", ip=request.remote_addr or "",
    )
    return resp


@bp.route("/lgpd", methods=["GET", "POST"])
@auth.admin_required
def lgpd():
    """Pagina de configuracao LGPD — anonimizacao, transparencia e governanca."""
    u = _user()
    if request.method == "POST":
        for chave in (
            "anonimizar_llm", "anonimizar_rag",
            "mask_cpf", "mask_email", "mask_telefone", "mask_nome",
            "mask_endereco", "mask_cnpj",
            "aviso_privacidade",
            "finalidade_conector", "retencao_auto",
        ):
            db.salvar_lgpd_config(chave, "1" if request.form.get(chave) else "0")
        for chave in ("aviso_texto",):
            val = request.form.get(chave, "").strip()
            db.salvar_lgpd_config(chave, val)
        for chave in ("retencao_auditoria", "retencao_tracing", "retencao_memorias"):
            val = request.form.get(chave, "").strip()
            if val.isdigit():
                db.salvar_lgpd_config(chave, val)
        flash("Configuracoes LGPD salvas.", "ok")
        return redirect(url_for("portal.lgpd"))

    cfg = db.carregar_lgpd_config()
    ck = lambda k: 'checked' if cfg.get(k, '0') == '1' else ''
    val = lambda k: cfg.get(k, '')

    content = f"""<div class="card" style="max-width:780px">
      <h3 style="margin-top:0">Conformidade LGPD — Saida de Dados</h3>
      <div class="muted" style="font-size:12px;margin-bottom:16px;padding:10px;background:var(--code-bg);border-radius:6px">
        A BlueShift e uma plataforma de inteligencia sobre dados existentes.
        O tratamento na origem (coleta, consentimento, DPO) e responsabilidade
        do sistema conectado (ERP/CRM/Portal do cliente). A BlueShift atua na
        <b>SAIDA</b>: controle do que vaza nas respostas e exports.
      </div>

      <form method="post">
        {templates.csrf_field()}

        <h4>1. Anonimizacao na Saida <span class="muted" style="font-weight:400;font-size:12px">Arts. 12, 13</span></h4>
        <table style="width:100%;border:none;background:transparent">
        <tr>
          <td style="padding:6px 0"><label class="inline">
            <input type="checkbox" name="anonimizar_llm" value="1" {ck('anonimizar_llm')} style="width:auto;margin:0;vertical-align:middle">
            <b>Anonimizar resposta do LLM</b></label>
            <br><span class="muted" style="font-size:11px;margin-left:20px">Mascara CPF, email, telefone, etc. na resposta do agente (chat, API, webhook).</span>
            <div style="margin:6px 0 4px 20px;padding:8px;background:var(--code-bg);border-radius:6px">
              <div style="font-weight:600;font-size:12px;margin-bottom:4px">Campos a mascarar <span class="muted" style="font-weight:400;font-size:11px">(aplica-se tambem a exportacao RAG quando ativa)</span>:</div>
              <div style="display:flex;flex-wrap:wrap;gap:4px 14px">
                <label class="inline" style="font-size:12px"><input type="checkbox" name="mask_cpf" value="1" {ck('mask_cpf')} style="width:auto;margin:0;vertical-align:middle"> CPF</label>
                <label class="inline" style="font-size:12px"><input type="checkbox" name="mask_email" value="1" {ck('mask_email')} style="width:auto;margin:0;vertical-align:middle"> E-mail</label>
                <label class="inline" style="font-size:12px"><input type="checkbox" name="mask_telefone" value="1" {ck('mask_telefone')} style="width:auto;margin:0;vertical-align:middle"> Telefone</label>
                <label class="inline" style="font-size:12px"><input type="checkbox" name="mask_nome" value="1" {ck('mask_nome')} style="width:auto;margin:0;vertical-align:middle"> Nome completo</label>
                <label class="inline" style="font-size:12px"><input type="checkbox" name="mask_endereco" value="1" {ck('mask_endereco')} style="width:auto;margin:0;vertical-align:middle"> Endereco</label>
                <label class="inline" style="font-size:12px"><input type="checkbox" name="mask_cnpj" value="1" {ck('mask_cnpj')} style="width:auto;margin:0;vertical-align:middle"> CNPJ</label>
              </div>
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:6px 0"><label class="inline">
            <input type="checkbox" name="anonimizar_rag" value="1" {ck('anonimizar_rag')} style="width:auto;margin:0;vertical-align:middle">
            <b>Anonimizar exportacao RAG</b></label>
            <br><span class="muted" style="font-size:11px;margin-left:20px">Aplica mascaras antes de gerar o arquivo JSONL em Conhecimento > Exportar. Usa os mesmos campos configurados acima.</span>
          </td>
        </tr>
        </table>

        <h4>2. Transparencia <span class="muted" style="font-weight:400;font-size:12px">Arts. 9, 10</span></h4>
        <table style="width:100%;border:none;background:transparent">
        <tr>
          <td style="padding:6px 0"><label class="inline">
            <input type="checkbox" name="aviso_privacidade" value="1" {ck('aviso_privacidade')} style="width:auto;margin:0;vertical-align:middle">
            <b>Exibir aviso de privacidade no login</b></label>
            <br><span class="muted" style="font-size:11px;margin-left:20px">Exibe texto configurado no rodape da tela de login.</span>
          </td>
        </tr>
        <tr>
          <td style="padding:6px 0"><label class="muted" style="font-size:12px;margin-left:24px">Texto do aviso:</label>
            <textarea name="aviso_texto" rows="2" style="margin-left:24px;width:90%;font-size:12px">{val('aviso_texto')}</textarea>
          </td>
        </tr>
        </table>

        <h4>3. Governanca de Dados <span class="muted" style="font-weight:400;font-size:12px">Arts. 26, 15</span></h4>
        <table style="width:100%;border:none;background:transparent">
        <tr>
          <td style="padding:6px 0"><label class="inline">
            <input type="checkbox" name="finalidade_conector" value="1" {ck('finalidade_conector')} style="width:auto;margin:0;vertical-align:middle">
            <b>Exigir finalidade por conector</b></label>
            <br><span class="muted" style="font-size:11px;margin-left:20px">Art. 26 — Todo conector MCP/API/SQL exige campo "Finalidade do tratamento".</span>
          </td>
        </tr>
        <tr>
          <td style="padding:6px 0"><label class="inline">
            <input type="checkbox" name="retencao_auto" value="1" {ck('retencao_auto')} style="width:auto;margin:0;vertical-align:middle">
            <b>Retencao automatica de logs</b></label>
            <br><span class="muted" style="font-size:11px;margin-left:20px">Art. 15 — Limpa auditoria, tracing e memorias apos periodo configurado.</span>
          </td>
        </tr>
        </table>
        <div style="display:flex;gap:12px;margin:6px 0 12px 24px">
          <div><label class="muted" style="font-size:12px">Auditoria (dias)</label><br><input name="retencao_auditoria" type="number" value="{val('retencao_auditoria')}" style="width:90px"></div>
          <div><label class="muted" style="font-size:12px">Tracing (dias)</label><br><input name="retencao_tracing" type="number" value="{val('retencao_tracing')}" style="width:90px"></div>
          <div><label class="muted" style="font-size:12px">Memorias (dias)</label><br><input name="retencao_memorias" type="number" value="{val('retencao_memorias')}" style="width:90px"></div>
        </div>

        <div style="margin-top:18px"><button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/monitorar">Voltar</a></div>
      </form>
    </div>"""
    return templates.page("LGPD", content, active="lgpd", user=u)


@bp.route("/fine-tuning")
@auth.login_required
def fine_tuning():
    """Pagina de documentacao sobre Fine-Tuning de modelos de IA."""
    u = _user()
    content = """<div class="card" style="max-width:860px">
  <h3 style="margin-top:0">Fine-Tuning de Modelos de IA</h3>

  <p class="muted">O <b>fine-tuning</b> (ou ajuste fino) e o processo de
  treinar um modelo de linguagem pre-existente com dados especificos do seu
  negocio para melhorar a precisao nas respostas. Em vez de usar um modelo
  generico, o fine-tuning ensina ao modelo a linguagem, os termos tecnicos e
  os padroes de resposta da sua empresa.</p>

  <h4>Quando fazer fine-tuning?</h4>
  <table>
  <tr><th>Cenario</th><th>Recomendacao</th></tr>
  <tr><td>Modelo erra termos tecnicos do seu setor</td><td> Fazer FT</td></tr>
  <tr><td>Respostas genericas demais para o seu contexto</td><td> Fazer FT</td></tr>
  <tr><td>Precisa de um tom/padrao de resposta especifico</td><td> Fazer FT</td></tr>
  <tr><td>Modelo ja responde bem com RAG + prompt</td><td> RAG pode ser suficiente</td></tr>
  <tr><td>Poucos dados de treino (< 50 exemplos)</td><td> RAG e melhor caminho</td></tr>
  </table>

  <h4>Formatos de modelo</h4>
  <table>
  <tr><th>Formato</th><th>Framework</th><th>Uso</th></tr>
  <tr><td><b>GGUF</b></td><td>llama.cpp, LM Studio, Ollama</td><td>Inferencia em CPU — mais popular para deploy local</td></tr>
  <tr><td><b>MLX</b></td><td>mlx-lm (Apple)</td><td>Fine-tuning e inferencia em Macs Apple Silicon (M1/M2/M3/M4)</td></tr>
  <tr><td><b>SafeTensors</b></td><td>HuggingFace Transformers, TRL</td><td>Treino em GPU (NVIDIA) — padrao da industria</td></tr>
  <tr><td><b>AWQ/GPTQ</b></td><td>AutoAWQ, GPTQ-for-LLaMa</td><td>Modelos quantizados para GPU com pouco VRAM</td></tr>
  </table>

  <h4>Tipos de fine-tuning</h4>
  <table>
  <tr><th>Tipo</th><th>O que faz</th><th>Custo</th></tr>
  <tr><td><b>Full fine-tuning</b></td><td>Atualiza todos os pesos do modelo</td><td>Alto (GPU necessaria)</td></tr>
  <tr><td><b>LoRA</b></td><td>Adiciona pesos adaptadores pequenos (1-2% do original)</td><td>Baixo (CPU ou GPU modesta)</td></tr>
  <tr><td><b>QLoRA</b></td><td>LoRA + modelo quantizado (4-bit)</td><td>Muito baixo (ate 8GB RAM)</td></tr>
  </table>

  <h4>Requisitos de hardware</h4>
  <table>
  <tr><th>Metodo</th><th>Modelo ate</th><th>RAM minima</th><th>GPU</th><th>Exemplo</th></tr>
  <tr><td>QLoRA (MLX)</td><td>8B params</td><td>16 GB</td><td>Nao precisa</td><td>Mac M2/M3 com 16GB unified</td></tr>
  <tr><td>QLoRA (GPU)</td><td>8B params</td><td>16 GB</td><td>RTX 3060 12GB+</td><td>Servidor Linux + RTX 4060</td></tr>
  <tr><td>LoRA (GPU)</td><td>8B params</td><td>24 GB</td><td>RTX 4090 24GB</td><td>Workstation dedicada</td></tr>
  <tr><td>Full FT (GPU)</td><td>3B params</td><td>32 GB</td><td>A4000 16GB+</td><td>Servidor enterprise</td></tr>
  </table>

  <h4>Dados para fine-tuning</h4>
  <p>A BlueShift ja exporta a Base de Conhecimento no formato JSONL compativel
  com MLX, HuggingFace TRL, Unsloth e OpenAI. Acesse <b>Conhecimento > Exportar
  JSONL</b> para gerar o arquivo.</p>

  <p><b>Formato esperado (messages):</b></p>
  <pre style="font-size:12px;background:var(--code-bg);padding:12px;border-radius:6px;overflow-x:auto">
{"messages":[{"role":"user","content":"Qual o saldo do cliente C001?"},{"role":"assistant","content":"O saldo do cliente C001 e R$ 15.230,00."}]}
{"messages":[{"role":"user","content":"Listar pedidos pendentes"},{"role":"assistant","content":"Ha 3 pedidos pendentes: PED-01, PED-02 e PED-03."}]}</pre>

  <h5>Recomendacoes para os dados</h5>
  <table>
  <tr><th>Criterio</th><th>Recomendacao</th></tr>
  <tr><td>Quantidade minima</td><td>50 exemplos (ideal: 200-1000)</td></tr>
  <tr><td>Qualidade</td><td>Revisar cada exemplo — dados ruins geram modelo pior</td></tr>
  <tr><td>Cobertura</td><td>Variar perguntas, nao repetir o mesmo padrao</td></tr>
  <tr><td>Limpeza</td><td>Remover dados pessoais (anonimizacao LGPD ja aplicada na exportacao)</td></tr>
  <tr><td>Teste</td><td>Separar 10-20% dos dados para validacao</td></tr>
  </table>

  <h4>Passo a passo (MLX — Mac Silicon)</h4>
  <ol style="font-size:13px">
    <li><b>Exportar dados:</b> No portal BlueShift, va em Conhecimento > Exportar JSONL</li>
    <li><b>Preparar ambiente:</b> No Mac, instale mlx-lm: <code>pip install mlx-lm</code></li>
    <li><b>Treinar:</b> <code>mlx_lm.lora --model meta-llama/Llama-3.2-3B --data ./dados.jsonl --lora-layers 16 --iters 200</code></li>
    <li><b>Testar:</b> <code>mlx_lm.generate --model meta-llama/Llama-3.2-3B --adapter-path ./adapters</code></li>
    <li><b>Exportar GGUF (opcional):</b> Converta o adaptador + modelo base para GGUF usando <code>llama.cpp/convert.py</code> para usar em LM Studio ou Ollama</li>
  </ol>

  <h4>Vantagens do modelo fine-tuned</h4>
  <table>
  <tr><th>Vantagem</th><th>Com RAG + prompt</th><th>Com fine-tuning</th></tr>
  <tr><td><b>Precisao em termos tecnicos</b></td><td>Depende do contexto injetado</td><td>Modelo internaliza o vocabulario</td></tr>
  <tr><td><b>Velocidade</b></td><td>Maior latencia (injecao de contexto)</td><td>Responde direto, sem contexto extra</td></tr>
  <tr><td><b>Consistencia</b></td><td>Varia conforme o prompt</td><td>Padrao unificado de resposta</td></tr>
  <tr><td><b>Regras de negocios</b></td><td>Precisa estar no prompt sempre</td><td>Modelo segue naturalmente</td></tr>
  <tr><td><b>Processos internos</b></td><td>Pode ser ignorado se o prompt for longo</td><td>Modelo aprende o fluxo</td></tr>
  <tr><td><b>Offline total</b></td><td>Sim</td><td>Sim — modelo funciona sem internet</td></tr>
  <tr><td><b>Dados sensiveis</b></td><td>Contexto pode vazar no historico</td><td>Dados ficam no modelo, sem exposição</td></tr>
  </table>

  <h4>Quem pode fazer</h4>
  <p>O fine-tuning é um servico <b>realizado pela BlueShift</b> para clientes
  corporativos. A plataforma fornece os dados de saida (JSONL), e a BlueShift
  executa o treino nos hardwares adequados, entregando o modelo ajustado
  pronto para uso no ambiente do cliente.</p>

  <p>Para contratar o servico de fine-tuning, entre em contato com seu
  representante BlueShift.</p>

  <hr style="border-color:var(--line-soft);margin:20px 0">
</div>"""
    return templates.page("Fine-Tuning", content, active="fine_tuning", user=u)


@bp.route("/rastreio/<int:tid>")
@auth.admin_required
def rastreio(tid: int):
    """Retorna os dados de trace como JSON para o modal."""
    trace = db.buscar_trace(tid)
    if not trace:
        return jsonify({"ok": False, "erro": "Trace nao encontrado (removido por limpeza ou retencao)"}), 404
    return jsonify({"ok": True, "trace": trace})


# ---------------------------------------------------------------------------
# MEMORIA POR USUARIO + RAG (Contexto Dinamico, PRD §8-C)
# ---------------------------------------------------------------------------

@bp.route("/memoria", methods=["GET", "POST"])
@auth.login_required
def memoria():
    u = _user()
    cliente_id = None
    # admin/gestor veem todos; usuario comum ve apenas a propria
    if u and u["papel"] in ("admin", "gestor"):
        cliente_id = request.args.get("cliente_id", type=int)
    if request.method == "POST":
        cid = int(request.form.get("cliente_id", 0)) or cliente_id
        texto = request.form.get("conteudo", "").strip()
        if cid and texto:
            db.criar_memoria(cid, u["login"], texto, request.form.get("tipo", "conversa"))
            db.registrar_auditoria(u["login"], u["papel"], "salvar_memoria", alvo=u["login"],
                                   cliente_id=cid, ip=request.remote_addr)
            flash("Memória salva.", "ok")
            return redirect(url_for("portal.memoria"))
    dono = u["login"] if u and u["papel"] not in ("admin", "gestor") else None
    rows = db.listar_memorias(cliente_id) if (u and u["papel"] in ("admin", "gestor")) else \
        [m for m in db.listar_memorias(cliente_id or None) if m["usuario"] == u["login"]]

    # Paginacao
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 20, type=int)
    if limite not in (10, 20, 50, 100, 200):
        limite = 20
    total = len(rows)
    total_paginas = max(1, (total + limite - 1) // limite)
    pagina = max(1, min(pagina, total_paginas))
    inicio = (pagina - 1) * limite
    fim = inicio + limite
    pagina_atual = rows[inicio:fim]

    def _url(**kw):
        args = dict(request.args)
        args.update(kw)
        return url_for("portal.memoria", **args)

    body = ""
    for m in pagina_atual:
        body += f"""<tr>
          <td>{templates.badge(m['tipo'])}</td>
          <td>{m['conteudo']}</td>
          <td>{m['usuario']}</td>
          <td class="muted">{m['criado_em']}</td>
        </tr>"""

    pag_btns = ""
    if total_paginas > 1:
        pag_btns = '<div class="paginacao" style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:13px">'
        pag_btns += f'<span class="muted">{inicio+1}–{min(fim, total)} de {total}</span>'
        pag_btns += '<div style="display:flex;gap:4px">'
        if pagina > 1:
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=1, limite=limite)}" style="padding:4px 10px;font-size:12px">«</a>'
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=pagina-1, limite=limite)}" style="padding:4px 10px;font-size:12px">‹</a>'
        for p in range(max(1, pagina-2), min(total_paginas, pagina+2)+1):
            if p == pagina:
                pag_btns += f'<button class="btn" style="padding:4px 10px;font-size:12px">{p}</button>'
            else:
                pag_btns += f'<a class="btn ghost" href="{_url(pagina=p, limite=limite)}" style="padding:4px 10px;font-size:12px">{p}</a>'
        if pagina < total_paginas:
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=pagina+1, limite=limite)}" style="padding:4px 10px;font-size:12px">›</a>'
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=total_paginas, limite=limite)}" style="padding:4px 10px;font-size:12px">»</a>'
        pag_btns += '</div></div>'

    # Opcoes do seletor de limite
    limite_opts = " ".join(f'<option value="{n}" {"selected" if limite==n else ""}>{n}</option>' for n in [10,20,50,100,200])

    tabela = f"""<table><thead><tr><th>Tipo</th><th>Conteúdo</th><th>Usuário</th><th>Quando</th></tr></thead>
      <tbody>{body or '<tr><td colspan=4 class="empty">Nenhuma memória.</td></tr>'}</tbody></table>{pag_btns}"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Memória persistente por usuário (banco vetorial local). Isolada por login — cada usuário vê só a própria.
    </div>
    <div class="card" style="max-width:680px;margin-bottom:16px">
      <h3 style="margin-top:0">Salvar memória</h3>
      <form method="post">
        {templates.csrf_field()}<label>Cliente</label>
          <select name="cliente_id">
            {''.join(f'<option value="{c["id"]}" {"selected" if c["id"]==cliente_id else ""}>{c["nome"]}</option>' for c in db.listar_clientes())}
          </select>
        <label>Tipo</label>
          <select name="tipo"><option value="conversa">Conversa</option><option value="preferencia">Preferência</option><option value="contexto">Contexto</option></select>
        <label>Conteúdo</label><textarea name="conteudo" rows="3" placeholder="Ex: cliente prefere contato por email"></textarea>
        <div style="margin-top:12px"><button class="btn" type="submit">Salvar memória</button></div>
      </form>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:end;margin-bottom:8px">
      <div class="muted" style="font-size:13px">{total} memória(s) registrada(s)</div>
      <div><label style="font-size:12px">Por página</label>
        <select onchange="var u=new URL(location.href);u.searchParams.set('limite',this.value);u.searchParams.set('pagina','1');location.href=u.toString()" style="font-size:12px;padding:3px 6px">
          {limite_opts}
        </select></div>
    </div>
    {tabela}"""
    return templates.page("Memória", content, active="memoria", user=u)


@bp.route("/conhecimento", methods=["GET", "POST"])
@auth.login_required
def conhecimento():
    u = _user()

    # --- CSV Import ---
    if request.method == "POST" and request.form.get("_action") == "csv_import":
        cid = int(request.form.get("cliente_id", 0))
        area = request.form.get("area", "").strip()
        file = request.files.get("csv_file")
        if not file or not cid:
            flash("Selecione um cliente e um arquivo CSV.", "warn")
            return redirect(url_for("portal.conhecimento"))
        try:
            import csv
            import io
            content = file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            count = 0
            for row in reader:
                titulo = row.get("titulo", row.get("Titulo", "")).strip()
                texto = row.get("conteudo", row.get("Conteudo", row.get("texto", ""))).strip()
                fonte = row.get("fonte", row.get("Fonte", "csv")).strip()
                # area da linha do CSV; se vazia, usa a do formulario
                row_area = row.get("area", row.get("Area", "")).strip() or area
                if titulo and texto:
                    db.criar_documento(cid, titulo, "base_conhecimento", texto,
                                       area=row_area, fonte=fonte)
                    count += 1
            db.registrar_auditoria(u["login"], u["papel"], "csv_import_conhecimento",
                                   alvo=f"{count} documentos", cliente_id=cid, ip=request.remote_addr)
            flash(f"{count} documento(s) importados via CSV.", "ok")
        except Exception as e:
            flash(f"Erro ao importar CSV: {e}", "bad")
        return redirect(url_for("portal.conhecimento"))

    # --- PDF Import ---
    if request.method == "POST" and request.form.get("_action") == "pdf_import":
        cid = int(request.form.get("cliente_id", 0))
        area = request.form.get("area", "").strip()
        cat = request.form.get("categoria", "manual")
        file = request.files.get("pdf_file")
        if not file or not cid:
            flash("Selecione um cliente e um arquivo PDF.", "warn")
            return redirect(url_for("portal.conhecimento"))
        try:
            import fitz  # PyMuPDF
            pdf = fitz.open(stream=file.read(), filetype="pdf")
            texto = ""
            for page in pdf:
                texto += page.get_text()
            pdf.close()
            texto = texto.strip()
            if not texto:
                flash("Nenhum texto extraído do PDF. O arquivo pode ser só de imagens.", "warn")
                return redirect(url_for("portal.conhecimento"))
            nome = file.filename or "documento.pdf"
            if nome.lower().endswith(".pdf"):
                nome = nome[:-4]
            # Chunking: se o texto for muito grande, quebra em partes
            chunk_size = 2000
            if len(texto) > chunk_size:
                count = 0
                for i in range(0, len(texto), chunk_size):
                    chunk = texto[i:i + chunk_size]
                    titulo = f"{nome} (parte {i//chunk_size + 1})" if i > 0 else nome
                    db.criar_documento(cid, titulo, cat, chunk, area=area, fonte="pdf")
                    count += 1
                flash(f"PDF importado: {count} documento(s) criados.", "ok")
            else:
                db.criar_documento(cid, nome, cat, texto, area=area, fonte="pdf")
                flash("PDF importado com sucesso.", "ok")
            db.registrar_auditoria(u["login"], u["papel"], "pdf_import_conhecimento",
                                   alvo=f"{nome}", cliente_id=cid, ip=request.remote_addr)
        except ImportError:
            flash("Para importar PDF, instale: pip install PyMuPDF", "bad")
        except Exception as e:
            flash(f"Erro ao importar PDF: {e}", "bad")
        return redirect(url_for("portal.conhecimento"))

    # --- Adicionar documento manual ---
    if request.method == "POST" and request.form.get("_action") == "add":
        cid = int(request.form.get("cliente_id", 0))
        titulo = request.form.get("titulo", "").strip()
        texto = request.form.get("conteudo", "").strip()
        area = request.form.get("area", "").strip()
        if cid and titulo and texto:
            db.criar_documento(cid, titulo, request.form.get("categoria", "manual"), texto,
                               area=area)
            db.registrar_auditoria(u["login"], u["papel"], "salvar_documento", alvo=titulo,
                                   cliente_id=cid, ip=request.remote_addr)
            flash("Documento adicionado à base de conhecimento.", "ok")
            return redirect(url_for("portal.conhecimento"))

    # --- Listar com filtro ---
    cid_sel = request.args.get("cliente_id", type=int)
    area_sel = request.args.get("area", "")
    docs = db.listar_documentos(cliente_id=cid_sel, area=area_sel or None)

    # Paginação
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 20, type=int)
    if limite not in (10, 20, 50, 100, 200):
        limite = 20
    total = len(docs)
    total_paginas = max(1, (total + limite - 1) // limite)
    pagina = max(1, min(pagina, total_paginas))
    inicio = (pagina - 1) * limite
    fim = inicio + limite
    pagina_atual = docs[inicio:fim]

    def _url(**kw):
        args = dict(request.args)
        args.update(kw)
        return url_for("portal.conhecimento", **args)

    body = ""
    for d in pagina_atual:
        preview = d['conteudo'][:120] + ("…" if len(d['conteudo']) > 120 else "")
        acessos_txt = f"{d.get('acessos',0)} acesso(s)" if d.get('acessos', 0) else "0 acesso"
        ultimo = f" · último: {d.get('ultimo_acesso','-')[:10]}" if d.get('ultimo_acesso') else ""
        body += f"""<tr>
          <td><b>{d['titulo']}</b><br><span class="muted" style="font-size:11px">{d.get('fonte','manual')}</span></td>
          <td>{templates.badge(d.get('area') or '-')}</td>
          <td>{templates.badge(d['categoria'])}</td>
          <td class="muted">{preview}</td>
          <td style="font-size:12px">{acessos_txt}{ultimo}</td>
          <td class="muted">{d['criado_em'][:16]}</td>
          <td class="row-actions">
            <a href="{url_for('portal.conhecimento_editar', did=d['id'])}">editar</a>
            <a href="{url_for('portal.conhecimento_excluir', did=d['id'])}" onclick="return confirm('Excluir documento?')" style="color:var(--bad)">excluir</a>
          </td></tr>"""

    # Botões de paginação
    pag_btns = ""
    if total_paginas > 1:
        pag_btns = '<div class="paginacao" style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:13px">'
        pag_btns += f'<span class="muted">{inicio+1}–{min(fim, total)} de {total}</span>'
        pag_btns += '<div style="display:flex;gap:4px">'
        if pagina > 1:
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=1, limite=limite)}" style="padding:4px 10px;font-size:12px">«</a>'
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=pagina-1, limite=limite)}" style="padding:4px 10px;font-size:12px">‹</a>'
        for p in range(max(1, pagina-2), min(total_paginas, pagina+2)+1):
            ativo = ' style="padding:4px 10px;font-size:12px"'
            if p == pagina:
                pag_btns += f'<button class="btn" style="padding:4px 10px;font-size:12px">{p}</button>'
            else:
                pag_btns += f'<a class="btn ghost" href="{_url(pagina=p, limite=limite)}" style="padding:4px 10px;font-size:12px">{p}</a>'
        if pagina < total_paginas:
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=pagina+1, limite=limite)}" style="padding:4px 10px;font-size:12px">›</a>'
            pag_btns += f'<a class="btn ghost" href="{_url(pagina=total_paginas, limite=limite)}" style="padding:4px 10px;font-size:12px">»</a>'
        pag_btns += '</div></div>'

    # --- Estatisticas ---
    stats = db.contar_documentos(cliente_id=cid_sel)

    opts_cliente = "".join(f'<option value="{c["id"]}" {"selected" if c["id"]==cid_sel else ""}>{c["nome"]}</option>' for c in db.listar_clientes())
    opts_area = "".join(f'<option value="{a}" {"selected" if a==area_sel else ""}>{a}</option>' for a in listar_areas())

    stats_html = f"""
    <div class="grid grid-4" style="margin-bottom:14px">
      <div class="kpi"><div class="label">Documentos</div><div class="value">{stats['geral']['total']}</div><div class="sub">no RAG</div></div>
      <div class="kpi"><div class="label">Áreas</div><div class="value">{stats['geral']['areas']}</div><div class="sub">com documentos</div></div>
      <div class="kpi"><div class="label">Acessos</div><div class="value">{stats['geral']['total_acessos']}</div><div class="sub">total no RAG</div></div>
      <div class="kpi"><div class="label">Tam. médio</div><div class="value">{stats['geral']['tamanho_medio']}</div><div class="sub">caracteres</div></div>
    </div>"""

    details_html = ""
    if stats["por_area"]:
        details_html += "<div style='margin-bottom:8px'><span class='muted' style='font-size:12px'><b>Por área:</b> "
        details_html += " · ".join(f"{a['area'] or 'sem área'}: {a['qtd']} docs ({a['acessos']} acessos)" for a in stats["por_area"])
        details_html += "</span></div>"
    if stats["por_fonte"]:
        details_html += "<div style='margin-bottom:8px'><span class='muted' style='font-size:12px'><b>Por fonte:</b> "
        details_html += " · ".join(f"{f['fonte']}: {f['qtd']}" for f in stats["por_fonte"])
        details_html += "</span></div>"

    content = f"""
    {stats_html}
    {details_html}
    <div class="card" style="max-width:720px;margin-bottom:16px">
      <h3 style="margin-top:0">Adicionar documento (RAG)</h3>
      <form method="post">
        {templates.csrf_field()}<input type="hidden" name="_action" value="add">
        <div class="form-row">
          <div><label>Cliente</label><select name="cliente_id">{opts_cliente}</select></div>
          <div><label>Área</label><select name="area"><option value="">geral</option>{opts_area}</select></div>
        </div>
        <div class="form-row">
          <div><label>Título</label><input name="titulo" placeholder="Ex: Política de Privacidade"></div>
          <div><label>Categoria</label><select name="categoria"><option value="manual">Manual</option><option value="politica">Política</option><option value="base_conhecimento">Base de Conhecimento</option><option value="contrato">Contrato</option></select></div>
        </div>
        <label>Conteúdo</label><textarea name="conteudo" rows="4" placeholder="Texto do documento"></textarea>
        <div style="margin-top:12px"><button class="btn" type="submit">Adicionar</button></div>
      </form>
    </div>
    <div class="card" style="max-width:720px;margin-bottom:16px">
      <h3 style="margin-top:0">Importar CSV</h3>
      <p class="muted" style="font-size:13px">Formato: <code>titulo,conteudo,fonte</code> (opcional: <code>area</code>). Se area vazia, usa a selecionada abaixo.</p>
      <form method="post" enctype="multipart/form-data">
        {templates.csrf_field()}<input type="hidden" name="_action" value="csv_import">
        <div class="form-row">
          <div><label>Cliente</label><select name="cliente_id">{opts_cliente}</select></div>
          <div><label>Área padrão</label><select name="area"><option value="">geral</option>{opts_area}</select></div>
        </div>
        <label>Arquivo CSV</label>
        <input type="file" name="csv_file" accept=".csv" style="padding:6px">
        <div style="margin-top:12px"><button class="btn" type="submit">Importar CSV</button></div>
      </form>
    </div>
    <div class="card" style="max-width:720px;margin-bottom:16px">
      <h3 style="margin-top:0">Importar PDF</h3>
      <p class="muted" style="font-size:13px">Envie um arquivo PDF. O texto sera extraido e dividido em partes (chunks) de ate 2000 caracteres.</p>
      <form method="post" enctype="multipart/form-data">
        {templates.csrf_field()}<input type="hidden" name="_action" value="pdf_import">
        <div class="form-row">
          <div><label>Cliente</label><select name="cliente_id">{opts_cliente}</select></div>
          <div><label>Área</label><select name="area"><option value="">geral</option>{opts_area}</select></div>
        </div>
        <div class="form-row">
          <div><label>Categoria</label>
            <select name="categoria"><option value="manual">Manual</option><option value="politica">Política</option><option value="base_conhecimento">Base de Conhecimento</option><option value="contrato">Contrato</option></select></div>
          <div><label>Arquivo PDF</label><input type="file" name="pdf_file" accept=".pdf" style="padding:6px"></div>
        </div>
        <div style="margin-top:12px"><button class="btn" type="submit">Importar PDF</button></div>
      </form>
    </div>
    <div class="card" style="max-width:720px;margin-bottom:16px">
      <h3 style="margin-top:0">Exportar para Fine-Tuning</h3>
      <p class="muted" style="font-size:13px">Exporta a base de conhecimento como JSONL no formato <code>messages</code> (chat-style), compativel com frameworks de fine-tuning como MLX, HuggingFace, Unsloth, LlamaFactory, Axolotl e OpenAI.</p>
      <form method="get" style="display:flex;gap:8px;align-items:end">
        <div><label>Cliente</label><select name="cliente_id">{''.join(f'<option value="{c["id"]}" {"selected" if c["id"]==cid_sel else ""}>{c["nome"]}</option>' for c in db.listar_clientes())}</select></div>
        <div><label>Área</label><select name="area"><option value="">todas</option>{opts_area}</select></div>
        <div><a class="btn" href="/portal/conhecimento/exportar-jsonl?cliente_id={cid_sel or ''}&area={area_sel or ''}">📥 Exportar JSONL</a></div>
      </form>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Documentos</h3>
      <form method="get" style="margin-bottom:10px;display:flex;gap:8px;align-items:end">
        <div><label>Cliente</label><select name="cliente_id" onchange="this.form.submit()"><option value="">todos</option>{''.join(f'<option value="{c["id"]}" {"selected" if c["id"]==cid_sel else ""}>{c["nome"]}</option>' for c in db.listar_clientes())}</select></div>
        <div><label>Área</label><select name="area" onchange="this.form.submit()"><option value="">todas</option>{opts_area}</select></div>
        <div><label>Por página</label><select name="limite" onchange="this.form.submit()">
          {' '.join(f'<option value="{n}" {"selected" if limite==n else ""}>{n}</option>' for n in [10,20,50,100,200])}
        </select></div>
      </form>
      <table><thead><tr><th>Título</th><th>Área</th><th>Categoria</th><th>Conteúdo</th><th>Acessos</th><th>Quando</th><th></th></tr></thead>
        <tbody>{body or '<tr><td colspan="7" class="muted">Nenhum documento.</td></tr>'}</tbody></table>
      {pag_btns}
    </div>"""
    return templates.page("Base de Conhecimento", content, active="conhecimento", user=u)


@bp.route("/conhecimento/<int:did>/editar", methods=["GET", "POST"])
@auth.admin_required
def conhecimento_editar(did: int):
    doc = db.buscar_documento(did)
    if not doc:
        flash("Documento não encontrado.", "bad")
        return redirect(url_for("portal.conhecimento"))
    if request.method == "POST":
        cid = int(request.form.get("cliente_id") or doc["cliente_id"])
        titulo = (request.form.get("titulo") or doc["titulo"]).strip()
        texto = (request.form.get("conteudo") or doc["conteudo"]).strip()
        area = request.form.get("area") or doc.get("area", "")
        categoria = request.form.get("categoria") or doc["categoria"]
        if not titulo:
            flash("Título é obrigatório.", "warn")
            return redirect(url_for("portal.conhecimento_editar", did=did))
        db.atualizar_documento(did, cliente_id=cid, titulo=titulo, conteudo=texto, area=area, categoria=categoria)
        db.registrar_auditoria(_user()["login"], "admin", "editar_documento", alvo=titulo,
                               cliente_id=doc["cliente_id"], ip=request.remote_addr)
        flash("Documento atualizado.", "ok")
        return redirect(url_for("portal.conhecimento"))
    opts_area = "".join(f'<option value="{a}" {"selected" if a==doc.get("area","") else ""}>{a}</option>' for a in listar_areas())
    opts_cliente = "".join(f'<option value="{c["id"]}" {"selected" if c["id"]==doc["cliente_id"] else ""}>{c["nome"]}</option>' for c in db.listar_clientes())
    content = f"""
    <div class="card" style="max-width:700px">
      <h3 style="margin-top:0">Editar documento #{did}</h3>
      <form method="post">
        {templates.csrf_field()}<div class="form-row">
          <div><label>Cliente</label><select name="cliente_id">{opts_cliente}</select></div>
          <div><label>Área</label><select name="area"><option value="">geral</option>{opts_area}</select></div>
        </div>
        <div class="form-row">
          <div><label>Título</label><input name="titulo" value="{doc['titulo']}"></div>
          <div><label>Categoria</label>
            <select name="categoria">
              <option value="manual" {"selected" if doc['categoria']=='manual' else ''}>Manual</option>
              <option value="politica" {"selected" if doc['categoria']=='politica' else ''}>Política</option>
              <option value="base_conhecimento" {"selected" if doc['categoria']=='base_conhecimento' else ''}>Base de Conhecimento</option>
              <option value="contrato" {"selected" if doc['categoria']=='contrato' else ''}>Contrato</option>
            </select></div>
        </div>
        <label>Conteúdo</label>
        <textarea name="conteudo" rows="10">{doc['conteudo']}</textarea>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/conhecimento">Cancelar</a>
        </div>
      </form>
      <div class="muted" style="font-size:12px;margin-top:12px">
        Fonte: {doc.get('fonte','manual')} · Acessos: {doc.get('acessos',0)} · Criado: {doc['criado_em']}
        {(' · Ultimo acesso: ' + doc["ultimo_acesso"]) if doc.get("ultimo_acesso") else ''}
      </div>
    </div>"""
    return templates.page("Editar documento", content, active="conhecimento", user=_user())


@bp.route("/conhecimento/<int:did>/excluir")
@auth.admin_required
def conhecimento_excluir(did: int):
    doc = db.buscar_documento(did)
    if doc:
        db.deletar_documento(did)
        db.registrar_auditoria(_user()["login"], "admin", "excluir_documento", alvo=doc["titulo"],
                               cliente_id=doc["cliente_id"], ip=request.remote_addr)
        flash(f"Documento '{doc['titulo']}' excluído.", "ok")
    return redirect(url_for("portal.conhecimento"))


@bp.route("/conhecimento/exportar-jsonl")
@auth.admin_required
def conhecimento_exportar_jsonl():
    """Exporta a base de conhecimento como JSONL no formato messages (chat-style).

    Formato compativel com TreinarModelo (mlx_lm lora):
      {"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}

    Documentos do tipo "RAG auto:" sao parseados para extrair pergunta e resposta.
    Demais documentos viram: user="Explique sobre {titulo}", assistant={conteudo}.
    """
    area = request.args.get("area", "")
    cid = request.args.get("cliente_id", type=int)
    docs = db.listar_documentos(cliente_id=cid, area=area or None)

    linhas: list[str] = []
    for d in docs:
        titulo = d["titulo"]
        conteudo = d["conteudo"]
        user_msg = ""
        assistant_msg = ""

        # Tenta parsear documentos do RAG auto-save: "Pergunta: ...\nResposta: ...\nDados: ..."
        if titulo.startswith("RAG auto:"):
            partes = conteudo.split("\n", 2)
            for p in partes:
                if p.startswith("Pergunta:"):
                    user_msg = p[len("Pergunta:"):].strip()
                elif p.startswith("Resposta:"):
                    assistant_msg = p[len("Resposta:"):].strip()
            if not assistant_msg:
                # Fallback: usa o conteudo inteiro como resposta
                user_msg = titulo
                assistant_msg = conteudo
        else:
            # Documento manual: pergunta generica sobre o titulo
            user_msg = f"Explique sobre: {titulo}"
            assistant_msg = conteudo

        if user_msg and assistant_msg:
            # Anonimizacao LGPD na exportacao (Arts. 12, 13)
            lgpd_cfg = db.carregar_lgpd_config()
            if lgpd_cfg.get("anonimizar_rag") == "1":
                from . import mask as _mask
                user_msg = _mask.aplicar_mascaras(user_msg, lgpd_cfg)
                assistant_msg = _mask.aplicar_mascaras(assistant_msg, lgpd_cfg)

            # Adiciona contexto da area e fonte como metadado no assistant
            meta = f" [area: {d.get('area','') or 'geral'} | fonte: {d.get('fonte','manual')}]"
            exemplo = {
                "messages": [
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant_msg + meta},
                ]
            }
            linhas.append(json.dumps(exemplo, ensure_ascii=False))

    if not linhas:
        flash("Nenhum documento para exportar.", "warn")
        return redirect(url_for("portal.conhecimento"))

    # Monta resposta como download
    conteudo_jsonl = "\n".join(linhas)
    nome_arquivo = f"blueshift_rag_{area or 'todas'}_{len(linhas)}exemplos.jsonl"
    response = make_response(conteudo_jsonl)
    response.headers["Content-Type"] = "application/jsonl"
    response.headers["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    db.registrar_auditoria(_user()["login"], "admin", "exportar_rag_jsonl",
                           alvo=f"{len(linhas)} exemplos, area={area or 'todas'}",
                           cliente_id=cid or 0, ip=request.remote_addr)
    return response


# ---------------------------------------------------------------------------
# MODELOS DE IA (cadastro de LLMs por cliente) + CHAT DE TESTE (RAG + memoria)
# ---------------------------------------------------------------------------

@bp.route("/modelos", methods=["GET", "POST"])
@auth.admin_required
def modelos():
    from . import llm_client
    if request.method == "POST":
        cid = int(request.form.get("cliente_id", 0))
        nome = request.form.get("nome", "").strip()
        base_url = request.form.get("base_url", "").strip()
        modelo = request.form.get("modelo", "").strip()
        if cid and nome and base_url and modelo:
            db.criar_modelo(cid, nome, base_url, modelo,
                            preco_input=float(request.form.get("preco_input", 0) or 0),
                            preco_output=float(request.form.get("preco_output", 0) or 0),
                            tipo=request.form.get("tipo", "local"),
                            api_key=request.form.get("api_key") or None,
                            max_tokens=request.form.get("max_tokens") or None)
            db.registrar_auditoria(_user()["login"], _user()["papel"], "cadastrar_modelo",
                                   alvo=nome, cliente_id=cid, ip=request.remote_addr)
            flash("Modelo de IA cadastrado.", "ok")
            return redirect(url_for("portal.modelos"))
    rows = db.listar_modelos()
    # checa saude de cada endpoint
    for r in rows:
        r["online"] = llm_client.health(r)
    body = ""
    for m in rows:
        badge = templates.badge("online" if m["online"] else "offline")
        body += f"""<tr>
          <td class="muted" style="font-size:12px">{m['id']}</td>
          <td><b>{m['nome']}</b></td>
          <td>{templates.badge(m['tipo'])}</td>
          <td class="muted">{m['base_url']}</td>
          <td class="muted">{m['modelo']}</td>
          <td>{badge}</td>
          <td class="row-actions">
            <a href="/portal/modelos/{m['id']}/editar">editar</a>
            <a href="/portal/modelos/{m['id']}/excluir" onclick="return confirm('Excluir modelo {m['nome']}?')" style="color:var(--bad)">excluir</a>
          </td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Endpoint</th><th>Modelo</th><th>Status</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=6 class="empty">Nenhum modelo cadastrado.</td></tr>'}</tbody></table>"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Cadastro de LLMs por cliente (OpenAI-compatible: LM Studio, vLLM, Ollama). O chat de teste usa estes modelos.
    </div>
    <div class="card" style="max-width:680px;margin-bottom:16px">
      <h3 style="margin-top:0">Cadastrar modelo de IA</h3>
      <form method="post">
        {templates.csrf_field()}<label>Cliente</label>
          <select name="cliente_id">
            {''.join(f'<option value="{c["id"]}">{c["nome"]}</option>' for c in db.listar_clientes())}
          </select>
        <label>Nome</label><input name="nome" placeholder="ex: bonsai-8b">
        <label>Endpoint (base_url)</label><input name="base_url" placeholder="http://127.0.0.1:1234">
        <label>Modelo</label><input name="modelo" placeholder="ex: bonsai-8b">
        <label>Tipo</label>
          <select name="tipo"><option value="local">Local (LM Studio)</option><option value="hibrido">Híbrido externo</option></select>
        <label>API Key (opcional)</label><input name="api_key" placeholder="deixe em branco se não usar">
        <label>Max tokens</label><input name="max_tokens" type="number" value="4096" placeholder="4096" style="width:200px">
        <div class="muted" style="font-size:11px;margin-top:4px">Aumente para modelos com thinking/reasoning (ex: 8192, 16384). Timeout: 180s.</div>
        <label>Preço input (R$ / 1M tokens)</label><input name="preco_input" type="number" step="0.01" value="0.15" placeholder="0.15" style="width:200px">
        <label>Preço output (R$ / 1M tokens)</label><input name="preco_output" type="number" step="0.01" value="0.60" placeholder="0.60" style="width:200px">
        <div class="muted" style="font-size:11px;margin-top:4px">Usado para calcular custos no dashboard de observabilidade.</div>
        <div style="margin-top:12px"><button class="btn" type="submit">Cadastrar</button></div>
      </form>
    </div>
    {tabela}"""
    return templates.page("Modelos de IA", content, active="modelos", user=_user())


@bp.route("/modelos/<int:mid>/editar", methods=["GET", "POST"])
@auth.admin_required
def modelo_editar(mid: int):
    m = db.buscar_modelo(mid)
    if not m:
        flash("Modelo não encontrado.", "warn")
        return redirect(url_for("portal.modelos"))
    if request.method == "POST":
        campos = {}
        for field in ("nome", "base_url", "modelo", "tipo"):
            v = request.form.get(field, "").strip()
            if v:
                campos[field] = v
        api_key = request.form.get("api_key") or None
        if api_key is not None:
            campos["api_key"] = api_key
        max_tok = request.form.get("max_tokens") or None
        if max_tok is not None:
            campos["max_tokens"] = int(max_tok)
        preco_i = request.form.get("preco_input") or None
        if preco_i is not None:
            campos["preco_input"] = float(preco_i)
        preco_o = request.form.get("preco_output") or None
        if preco_o is not None:
            campos["preco_output"] = float(preco_o)
        db.atualizar_modelo(mid, **campos)
        db.registrar_auditoria(_user()["login"], "admin", "editar_modelo", alvo=request.form.get("nome", m["nome"]),
                               cliente_id=m["cliente_id"], ip=request.remote_addr)
        flash("Modelo atualizado.", "ok")
        return redirect(url_for("portal.modelos"))
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Editar modelo #{mid}: {m['nome']}</h3>
      <form method="post">
        {templates.csrf_field()}<label>Nome</label><input name="nome" value="{m['nome']}">
        <label>Endpoint (base_url)</label><input name="base_url" value="{m['base_url']}">
        <label>Modelo</label><input name="modelo" value="{m['modelo']}">
        <label>Tipo</label>
          <select name="tipo"><option value="local" {"selected" if m['tipo']=='local' else ""}>Local</option><option value="hibrido" {"selected" if m['tipo']=='hibrido' else ""}>Híbrido</option></select>
        <label>API Key</label><input name="api_key" value="{m.get('api_key') or ''}">
        <label>Max tokens</label><input name="max_tokens" type="number" value="{m.get('max_tokens') or 4096}" style="width:200px">
        <div class="muted" style="font-size:11px;margin-top:4px">Aumente para modelos com thinking (8192, 16384). Timeout: 180s.</div>
        <label>Preço input (R$ / 1M tokens)</label><input name="preco_input" type="number" step="0.01" value="{m.get('preco_input') or 0.15}" style="width:200px">
        <label>Preço output (R$ / 1M tokens)</label><input name="preco_output" type="number" step="0.01" value="{m.get('preco_output') or 0.60}" style="width:200px">
        <div class="muted" style="font-size:11px;margin-top:4px">Usado para calcular custos no dashboard de observabilidade.</div>
        <div style="margin-top:12px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/modelos">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page(f"Editar {m['nome']}", content, active="modelos", user=_user())


@bp.route("/modelos/<int:mid>/excluir")
@auth.admin_required
def modelo_excluir(mid: int):
    m = db.buscar_modelo(mid)
    if m:
        db.deletar_modelo(mid)
        db.registrar_auditoria(_user()["login"], "admin", "excluir_modelo", alvo=m["nome"],
                               cliente_id=m["cliente_id"], ip=request.remote_addr)
        flash(f"Modelo '{m['nome']}' excluído.", "ok")
    return redirect(url_for("portal.modelos"))


@bp.route("/chat", methods=["GET", "POST"])
@auth.login_required
def chat():
    from . import llm_client
    u = _user()
    resposta = None
    contexto = []
    ferramentas = []
    modelo_usado = None
    erro = None
    if request.method == "POST":
        mid = int(request.form.get("modelo_id", 0))
        pergunta = request.form.get("pergunta", "").strip()
        modelo = db.buscar_modelo(mid) if mid else None
        if not modelo:
            erro = "Selecione um modelo de IA cadastrado."
        elif pergunta:
            # contexto dinamico: memoria do usuario + base de conhecimento do cliente
            cliente_id = modelo["cliente_id"]
            contexto = memory.buscar_contexto(pergunta, cliente_id, usuario=u["login"], top_k=4)
            system = (
                "Você é um assistente corporativo da BlueShift. "
                "Use SOMENTE o contexto abaixo para responder. "
                "Se o contexto não tiver a resposta, diga que não sabe.\n\n"
                "CONTEXTO:\n" + "\n".join(f"- {c['texto']}" for c in contexto)
            )
            mensagens = [
                {"role": "system", "content": system},
                {"role": "user", "content": pergunta},
            ]
            out = llm_client.chat(modelo, mensagens)
            if out["ok"]:
                resposta = out["content"]
                modelo_usado = out["model"]
                # salva a interacao na memoria do usuario (isolada)
                db.criar_memoria(cliente_id, u["login"], f"P: {pergunta} | R: {resposta}",
                                 tipo="conversa")
                db.registrar_auditoria(u["login"], u["papel"], "chat", alvo=modelo["nome"],
                                       cliente_id=cliente_id, ip=request.remote_addr,
                                       detalhe=pergunta[:80])
                # registra tokens consumidos
                tok = out.get("tokens") or {}
                db.registrar_uso_token(
                    cliente_id=cliente_id, modelo=modelo_usado,
                    total_tokens=tok.get("total_tokens", 0),
                    prompt_tokens=tok.get("prompt_tokens", 0),
                    completion_tokens=tok.get("completion_tokens", 0),
                    modelo_fallback=0, quem=u["login"], origem="chat",
                )
            else:
                erro = out["error"]
    modelos = db.listar_modelos()
    opts = "".join(
        f'<option value="{m["id"]}" {"selected" if m["id"]==int(request.form.get("modelo_id",0) or 0) else ""}>'
        f'{m["nome"]} ({m["modelo"]})</option>'
        for m in modelos
    ) or '<option value="">-- nenhum modelo cadastrado --</option>'
    ctx_html = ""
    if contexto:
        ctx_html = "<div class=\"muted\" style=\"margin:10px 0;font-size:13px\"><b>Contexto RAG recuperado:</b><ul style=\"margin:6px 0 0 18px\">" + \
            "".join(f"<li>{c['texto'][:140]}</li>" for c in contexto) + "</ul></div>"
    fer_html = ""
    if ferramentas:
        itens = []
        for f in ferramentas:
            if "erro" in f:
                itens.append(f"<li><b>{f.get('conector','?')}</b>: erro {f['erro']}</li>")
            else:
                itens.append(f"<li><b>{f.get('conector')}.{f.get('tool')}</b> {f.get('args')} → "
                             f"<code>{f.get('resultado')}</code></li>")
        fer_html = "<div class=\"muted\" style=\"margin:10px 0;font-size:13px\"><b>Dados de sistema (conectores MCP executados):</b><ul style=\"margin:6px 0 0 18px\">" + \
            "".join(itens) + "</ul></div>"
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Chat de teste do contexto dinâmico: recupera memória do usuário + base de conhecimento (RAG)
      e envia ao modelo de IA cadastrado. Roda 100% on-premise.
    </div>
    <div class="card" style="max-width:760px">
      <form method="post">
        {templates.csrf_field()}<label>Modelo de IA</label><select name="modelo_id">{opts}</select>
        <label>Pergunta</label><textarea name="pergunta" rows="3" placeholder="Ex: qual a política de privacidade da BlueShift?">{request.form.get("pergunta","")}</textarea>
        <div style="margin-top:12px"><button class="btn" type="submit">Enviar</button></div>
      </form>
      {ctx_html}
      {fer_html}
      {f'<div class="card" style="margin-top:14px;background:var(--deep)"><b>🤖 {modelo_usado or "IA"}:</b><p style="margin:8px 0 0">{resposta}</p></div>' if resposta else ''}
      {f'<div class="badge warn" style="margin-top:12px">⚠️ {erro}</div>' if erro else ''}
    </div>"""
    return templates.page("Chat de Teste", content, active="chat", user=u)


# --------------------------------------------------------------------------- #
# Processar metricas (agregacao manual)
# --------------------------------------------------------------------------- #

@bp.route("/processar-metricas")
@auth.admin_required
def processar_metricas():
    """Agrega metricas do banco: tenta hoje, se vazio tenta dias anteriores."""
    from datetime import datetime, timedelta
    from blueshift_layer.portal.db import now_iso
    hoje = now_iso()[:10]
    total = db.agregar_metricas_diarias(hoje)
    if total == 0:
        # Tenta dias anteriores com dados de tracing
        for i in range(1, 8):
                    d = (datetime.now() - timedelta(days=i)).isoformat()[:10]
                    total = db.agregar_metricas_diarias(d)
                    if total > 0:
                        break
    return jsonify({"ok": True, "inseridas": total})


# --------------------------------------------------------------------------- #
# Feedback API (avaliacao de respostas)
# --------------------------------------------------------------------------- #

@bp.route("/api/v1/feedback/<int:trace_id>", methods=["POST"])
@auth.rate_limit_api
def api_feedback(trace_id: int):
    """Registra feedback para uma resposta do agente."""
    data = request.get_json(silent=True) or {}
    util = data.get("util", True)
    tipo = data.get("tipo", "api")  # 'api' via curl, 'manual' via UI
    trace = db.buscar_trace(trace_id)
    if not trace:
        return jsonify({"ok": False, "erro": "trace nao encontrado"}), 404
    fid = db.salvar_feedback(
        trace_id, trace.get("agente_id"), trace.get("pergunta", ""),
        trace.get("resposta", ""),
        "util" if util else "nao_util",
        tipo=tipo,
    )
    return jsonify({"ok": True, "feedback_id": fid})


# --------------------------------------------------------------------------- #
# Canal real (API / webhook) — integracao maquina-a-maquina com o agente      #
# --------------------------------------------------------------------------- #

@bp.route("/api/v1/agente", methods=["POST"])
@auth.rate_limit_api
@auth.api_key_required
def api_agente(canal):
    """Endpoint real de canal: recebe uma mensagem e responde com o agente do canal.

    Autenticacao: Bearer token do canal (ou ?token=). Nao usa sessao de browser.
    Body (JSON ou form): {"pergunta": "...", "usuario": "opcional", "id_cliente": "C001"}

    Retorna JSON: {ok, resposta, agente, modelo, contexto, ferramentas, erro}
    """
    data = request.get_json(silent=True) or request.form
    pergunta = (data.get("pergunta") or "").strip()
    if not pergunta:
        return jsonify({"ok": False, "erro": "campo 'pergunta' obrigatorio"}), 400

    agente_id = canal.get("agente_id")
    if not agente_id:
        return jsonify({"ok": False, "erro": "canal nao aponta para nenhum agente"}), 400
    a = db.buscar_agente(agente_id)
    if not a:
        return jsonify({"ok": False, "erro": "agente nao encontrado"}), 404

    usuario = (data.get("usuario") or f"canal:{canal['id']}")[:40]
    id_cliente = data.get("id_cliente") or ""
    contexto = (data.get("contexto") or "").strip()
    origem = (data.get("origem") or "").strip()
    out = agente_mod.responder(a, pergunta, usuario, id_cliente=id_cliente,
                               contexto_extra=contexto)
    # Feedback DEFAULT para chats externos (gateway/Open WebUI e outras
    # plataformas): sem botao de avaliacao proprio, a interacao conta como
    # 'util' (tipo 'gateway' — distinguivel do feedback manual/implicito na
    # Observabilidade e no Teste A/B). A resposta gravada SEM a imagem.
    if origem == "gateway" and out.get("ok") and out.get("trace_id"):
        try:
            db.salvar_feedback(
                trace_id=out["trace_id"], agente_id=a.get("id"),
                pergunta=pergunta,
                resposta=agente_mod._limpar_imagens(out.get("content", "")),
                feedback="util", tipo="gateway",
            )
        except Exception:  # noqa: BLE001 — feedback e best-effort
            pass
    db.registrar_auditoria(
        f"canal:{canal['id']}", "sistema", "api_agente", alvo=a["nome"],
        cliente_id=canal["cliente_id"], ip=request.remote_addr, detalhe=pergunta[:80],
    )
    resposta = {
        "ok": out["ok"],
        "resposta": out["content"],
        "pergunta": pergunta,
        "agente": a["nome"],
        "modelo": out.get("model"),
        "feedback_url": out.get("feedback_url"),
        "erro": out.get("error"),
        "tokens": out.get("tokens", {}),
        "tempo_ms": out.get("tempo_ms", 0),
    }
    if canal.get("webhook_url"):
        import json as _json
        try:
            _wh_headers = _json.loads(canal.get("webhook_headers") or "{}")
        except Exception:  # noqa: BLE001
            _wh_headers = {}
        wh = agente_mod.enviar_webhook(canal["webhook_url"], {
            "canal": canal["nome"],
            "agente": a["nome"],
            "pergunta": pergunta,
            "resposta": out["content"],
            "modelo": out.get("model"),
        }, headers_extra=_wh_headers)
        resposta["webhook"] = wh
    return jsonify(resposta)


@bp.route("/canais", methods=["GET", "POST"])
@auth.admin_required
def canais():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    agentes = db.listar_agentes()
    if request.method == "POST":
        cid = int(request.form.get("cliente_id") or 1)
        nome = request.form.get("nome", "").strip()
        agente_id = request.form.get("agente_id") or None
        if agente_id:
            agente_id = int(agente_id)
        if not nome:
            flash("Nome do canal é obrigatório.", "warn")
            return redirect(url_for("portal.canais"))
        if not agente_id:
            flash("Selecione um agente para o canal.", "warn")
            return redirect(url_for("portal.canais"))
        tipo = request.form.get("tipo", "api")
        webhook_url = request.form.get("webhook_url", "").strip() or None
        # Headers extras do webhook de saida (JSON opcional — ex: X-Webhook-Secret)
        wh_headers_raw = (request.form.get("webhook_headers") or "").strip()
        wh_headers = None
        if wh_headers_raw:
            try:
                wh_headers = json.dumps(json.loads(wh_headers_raw), ensure_ascii=False)
            except Exception:  # noqa: BLE001
                flash("Headers do webhook inválidos — use JSON válido (ex: {\"X-Webhook-Secret\": \"abc\"}).", "warn")
                return redirect(url_for("portal.canais"))
        db.criar_canal(cid, nome, agente_id, tipo=tipo, webhook_url=webhook_url,
                       webhook_headers=wh_headers)
        db.registrar_auditoria(_user()["login"], "admin", "criar_canal", alvo=nome,
                               cliente_id=cid, ip=request.remote_addr)
        flash("Canal criado.", "ok")
        return redirect(url_for("portal.canais"))
    rows = db.listar_canais()
    body = ""
    for c in rows:
        ag = next((a["nome"] for a in agentes if a["id"] == c["agente_id"]), "(sem agente)")
        wh = c.get("webhook_url") or "-"
        st = "ativo" if c["ativo"] else "revogado"
        _nome_js = c["nome"].replace("\\", "\\\\").replace("'", "\\'")
        _testar_link = (f'<a href="#" onclick="abrirTestarCanal({c["id"]},\'{c["token"]}\',\'{_nome_js}\');return false" title="Testar API do canal">testar</a> '
                        if c["ativo"] else "")
        body += f"""<tr>
          <td><b>{c['id']}</b></td>
          <td><b>{c['nome']}</b></td>
          <td>{c['tipo']}</td>
          <td>{ag}</td>
          <td style="max-width:260px"><code style="font-size:11px">{c['token']}</code>
            <button class="btn-copy" onclick="navigator.clipboard.writeText('{c['token']}')" title="Copiar chave">📋</button>
          </td>
          <td>{templates.badge(st)}</td>
          <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis"><code>{wh}</code></td>
          <td class="row-actions">
            {_testar_link}<a href="{url_for('portal.canal_editar', canal_id=c['id'])}">editar</a>
            <a href="{url_for('portal.canal_regenerar_token', canal_id=c['id'])}">nova chave</a>
            <a href="{url_for('portal.canal_alternar', canal_id=c['id'])}">{'revogar' if c['ativo'] else 'reativar'}</a>
          </td></tr>"""
    token_tooltip = """<div class="card muted" style="font-size:12px">
      <b>⚠️ Importante sobre chaves de canal:</b><br>
      Cada canal tem sua <b>própria chave de API</b> (token). Nunca use a chave de licença da plataforma
      para autenticar chamadas de canal. Se a chave de um canal vazar, use <b>"nova chave"</b> para
      gerar outra (a anterior para de funcionar imediatamente). Para desabilitar um canal sem deletar,
      use <b>"revogar"</b>.
    </div>"""
    testar_modal = """
    <div class="modal-overlay" id="modal-testar" onclick="if(event.target===this)fecharTestar()">
      <div class="modal-box" style="max-width:640px">
        <h3 id="tester-titulo" style="margin-top:0">Testar canal</h3>
        <div style="display:flex;gap:6px;margin-bottom:12px">
          <button class="btn" id="tab1" onclick="testerAba(1)" style="font-size:12px;padding:5px 12px">1. Agente</button>
          <button class="btn ghost" id="tab2" onclick="testerAba(2)" style="font-size:12px;padding:5px 12px">2. Feedback</button>
        </div>
        <div id="tester-agente">
          <label>Pergunta</label>
          <textarea id="tester-pergunta" placeholder="Ex: Qual o historico do cliente C001?" style="min-height:60px"></textarea>
          <div style="margin-top:10px"><button class="btn" onclick="testarAgente()">Enviar</button></div>
          <div id="tester-msg-agente" style="margin-top:12px"></div>
        </div>
        <div id="tester-feedback" style="display:none">
          <label>Trace ID (preenchido automaticamente apos testar o agente)</label>
          <input id="tester-trace" placeholder="ex: 123">
          <div style="margin-top:10px;display:flex;gap:8px">
            <button class="btn" onclick="testarFeedback(true)" style="font-size:12px">👍 Util</button>
            <button class="btn ghost" onclick="testarFeedback(false)" style="font-size:12px;color:var(--bad);border-color:var(--bad)">👎 Nao util</button>
          </div>
          <div id="tester-msg-feedback" style="margin-top:12px"></div>
        </div>
        <div class="modal-actions">
          <button class="btn ghost" onclick="fecharTestar()">Fechar</button>
        </div>
      </div>
    </div>"""
    testar_script = """<script>
var TESTER={token:"",canal:"",traceId:""};
function abrirTestarCanal(id,token,nome){
  TESTER.token=token;TESTER.canal=nome;TESTER.traceId="";
  document.getElementById("tester-titulo").textContent="Testar canal: "+nome;
  document.getElementById("tester-pergunta").value="";
  document.getElementById("tester-msg-agente").innerHTML="";
  document.getElementById("tester-msg-feedback").innerHTML="";
  document.getElementById("tester-trace").value="";
  testerAba(1);
  document.getElementById("modal-testar").classList.add("show");
}
function fecharTestar(){document.getElementById("modal-testar").classList.remove("show")}
function testerAba(n){
  document.getElementById("tester-agente").style.display=n===1?"block":"none";
  document.getElementById("tester-feedback").style.display=n===2?"block":"none";
  var a1=document.getElementById("tab1"),a2=document.getElementById("tab2");
  a1.style.background=n===1?"var(--blue2)":"transparent";a1.style.color=n===1?"#fff":"var(--txt)";
  a2.style.background=n===2?"var(--blue2)":"transparent";a2.style.color=n===2?"#fff":"var(--txt)";
}
function escHTML(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function testarAgente(){
  var p=document.getElementById("tester-pergunta").value.trim();
  var box=document.getElementById("tester-msg-agente");
  if(!p){box.innerHTML='<div class="badge warn">Digite uma pergunta.</div>';return}
  box.innerHTML='<div class="badge neutral">⏳ Processando... (pode levar ate 3 min)</div>';
  fetch("/portal/api/v1/agente",{method:"POST",
    headers:{"Content-Type":"application/json","Authorization":"Bearer "+TESTER.token},
    body:JSON.stringify({pergunta:p})})
  .then(function(r){return r.json().catch(function(){return {ok:false,erro:"resposta nao-JSON (HTTP "+r.status+")"}})})
  .then(function(d){
    if(d.feedback_url){var m=d.feedback_url.match(/feedback\\/(\\d+)/);if(m)TESTER.traceId=m[1]}
    var h="";
    if(d.ok){
      var rp=escHTML(d.resposta).replace(/!\\[[^\\]]*\\]\\(data:image\\/png;base64,([A-Za-z0-9+/=]+)\\)/g,'<img src="data:image/png;base64,$1" style="max-width:100%;border-radius:8px;margin:6px 0">');
      h+='<div style="margin-bottom:6px"><b>Resposta:</b></div><pre style="background:var(--code-bg);padding:10px;border-radius:6px;font-size:12px;white-space:pre-wrap;margin:0 0 10px">'+rp+'</pre>';
      h+='<div style="font-size:12px">Modelo: <b>'+escHTML(d.modelo||"-")+'</b> | Tempo: <b>'+(d.tempo_ms||0)+'ms</b> | Tokens: <b>'+((d.tokens&&d.tokens.total_tokens)||0)+'</b></div>';
      if(d.webhook)h+='<div style="font-size:12px;margin-top:4px">Webhook: <b>'+escHTML(d.webhook.enviado===true?"enviado (HTTP "+d.webhook.status+")":(d.webhook.motivo||d.webhook.erro||"falhou"))+'</b></div>';
      if(d.feedback_url)h+='<div style="font-size:12px;margin-top:4px">Feedback URL: <code>'+escHTML(d.feedback_url)+'</code></div>';
    }else{
      h+='<div class="badge bad">Erro: '+escHTML(d.erro||"falha na chamada")+'</div>';
    }
    box.innerHTML=h;
    if(TESTER.traceId){document.getElementById("tester-trace").value=TESTER.traceId}
  });
}
function testarFeedback(util){
  var t=document.getElementById("tester-trace").value.trim();
  var box=document.getElementById("tester-msg-feedback");
  if(!t){box.innerHTML='<div class="badge warn">Sem trace_id — teste o agente primeiro.</div>';return}
  box.innerHTML='<div class="badge neutral">⏳ Enviando feedback...</div>';
  fetch("/portal/api/v1/feedback/"+t,{method:"POST",
    headers:{"Content-Type":"application/json","Authorization":"Bearer "+TESTER.token},
    body:JSON.stringify({util:util,tipo:"manual"})})
  .then(function(r){return r.json().catch(function(){return {ok:false,erro:"HTTP "+r.status}})})
  .then(function(d){
    box.innerHTML=d.ok
      ?'<div class="badge ok">✓ Feedback salvo (id '+(d.feedback_id||"?")+')</div>'
      :'<div class="badge bad">Erro: '+escHTML(d.erro||"falha")+'</div>';
  });
}
document.addEventListener("keydown",function(e){if(e.key==="Escape")fecharTestar()});
</script>"""
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Criar canal de integração</h3>
      <form method="post">
        {templates.csrf_field()}<label>Cliente</label><select name="cliente_id">{''.join(f'<option value="{i}">{n}</option>' for i,n in clientes.items())}</select>
        <label>Nome</label><input name="nome" placeholder="Ex: Webhook Vendas Site">
        <label>Tipo</label><select name="tipo"><option value="api">API</option><option value="webhook">Webhook</option></select>
        <label>Agente</label><select name="agente_id"><option value="">(nenhum)</option>{''.join(f'<option value="{a["id"]}">{a["nome"]}</option>' for a in agentes)}</select>
        <label>Webhook de saída (URL)</label><input name="webhook_url" placeholder="https://... (POST da resposta)">
        <label>Headers do webhook (JSON, opcional)</label>
        <textarea name="webhook_headers" rows="2" placeholder='{{"X-Webhook-Secret": "sua-chave"}}' style="font-family:var(--code-font,monospace);font-size:12px"></textarea>
        <div class="muted" style="font-size:11px">Para webhooks que exigem autenticação — ex: <code>{{"X-Webhook-Secret": "abc"}}</code> ou <code>{{"Authorization": "Bearer token"}}</code>.</div>
        <div style="margin-top:12px"><button class="btn" type="submit">Criar canal</button></div>
      </form>
    </div>
    {token_tooltip}
    <div class="card">
      <h3 style="margin-top:0">Canais cadastrados</h3>
      <table><thead><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Agente</th><th>Chave (token)</th><th>Status</th><th>Webhook saída</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan="8" class="muted">nenhum canal cadastrado</td></tr>'}</tbody></table>
    </div>
    <div class="card muted" style="font-size:13px">
      <b>Como usar (canal real):</b><br><br>
      Faça uma requisição <code>POST</code> para o endpoint do agente usando o token do canal:<br><br>
      <pre id="pre1" style="background:var(--code-bg);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.6">curl -X POST http://localhost:8080/portal/api/v1/agente \u005c<br>  -H "Authorization: Bearer &lt;TOKEN_DO_CANAL&gt;" \u005c<br>  -H "Content-Type: application/json" \u005c<br>  -d '{{"pergunta": "Qual o hist\u00f3rico do cliente C001?"}}'</pre> <button class="btn ghost" style="font-size:11px;padding:2px 8px" onclick="copyPre(1,this)">📋 Copiar</button>
      <br>
      Substitua <code>&lt;TOKEN_DO_CANAL&gt;</code> pela chave do canal (use o botão 📋 ao lado do token para copiar).<br><br>
      <b>Resposta (JSON):</b><br><br>
      <pre style="background:var(--code-bg);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.6">{{
  "ok": true,
  "resposta": "...",
  "agente": "Agente Vendas",
  "modelo": "bonsai-8b",
  "contexto": [...],
  "ferramentas": [...],
  "webhook": {{"enviado": true, "status": 200}},
  "feedback_url": "http://localhost:8080/portal/api/v1/feedback/123"
}}</pre>
      <br>
      <b>Feedback (opcional):</b> a resposta inclui <code>feedback_url</code>.<br>
      POST <code>/portal/api/v1/feedback/&lt;trace_id&gt;</code> com <code>{{"util": true}}</code>.<br>
      Exemplo: <pre id="pre2" style="background:var(--code-bg);padding:6px;border-radius:4px;font-size:12px">curl -X POST http://localhost:8080/portal/api/v1/feedback/123 \n  -H "Authorization: Bearer &lt;TOKEN&gt;" \n  -H "Content-Type: application/json" \n  -d '{{"util": true}}'</pre> <button class="btn ghost" style="font-size:11px;padding:2px 8px" onclick="copyPre(2,this)">📋 Copiar</button>
      Retorno: <code>{{"ok": true, "feedback_id": 1}}</code>.<br>
      <b>Opcional</b> — a API funciona sem ele. Use para acompanhar qualidade no dashboard de observabilidade.<br>
      Se o canal tiver um <b>Webhook de saída</b>, a resposta também é POSTada na URL configurada.
        <script>
    function copyPre(n,el){{
      var pre=document.getElementById("pre"+n);
      var r=document.createRange();
      r.selectNodeContents(pre);
      var s=window.getSelection();
      s.removeAllRanges();
      s.addRange(r);
      document.execCommand('copy');
      s.removeAllRanges();
      el.textContent='Copiado!';
      setTimeout(function(){{el.textContent="\U0001f4cb Copiar"}},2000);
    }}
    </script>
    {testar_modal}
    {testar_script}
    """
    return templates.page("Canais", content, active="canais", user=_user())


@bp.route("/canais/<int:canal_id>/editar", methods=["GET", "POST"])
@auth.admin_required
def canal_editar(canal_id: int):
    """Edita os dados do canal (nome, tipo, agente, webhook)."""
    canal = db.buscar_canal(canal_id)
    if not canal:
        flash("Canal não encontrado.", "bad")
        return redirect(url_for("portal.canais"))
    agentes = db.listar_agentes()

    if request.method == "POST":
        nome = (request.form.get("nome") or canal["nome"]).strip()
        tipo = request.form.get("tipo") or canal["tipo"]
        agente_id = request.form.get("agente_id") or None
        if agente_id:
            agente_id = int(agente_id)
        webhook_url = (request.form.get("webhook_url") or "").strip() or None
        if not nome:
            flash("Nome do canal é obrigatório.", "warn")
            return redirect(url_for("portal.canal_editar", canal_id=canal_id))
        if not agente_id:
            flash("Selecione um agente para o canal.", "warn")
            return redirect(url_for("portal.canal_editar", canal_id=canal_id))
        wh_headers_raw = (request.form.get("webhook_headers") or "").strip()
        wh_headers = None
        if wh_headers_raw:
            try:
                wh_headers = json.dumps(json.loads(wh_headers_raw), ensure_ascii=False)
            except Exception:  # noqa: BLE001
                flash("Headers do webhook inválidos — use JSON válido (ex: {\"X-Webhook-Secret\": \"abc\"}).", "warn")
                return redirect(url_for("portal.canal_editar", canal_id=canal_id))
        db.atualizar_canal(canal_id, nome=nome, tipo=tipo, agente_id=agente_id,
                           webhook_url=webhook_url, webhook_headers=wh_headers)
        db.registrar_auditoria(
            _user()["login"], "admin", "editar_canal",
            alvo=nome, cliente_id=canal["cliente_id"], ip=request.remote_addr,
        )
        flash(f"Canal '{nome}' atualizado.", "ok")
        return redirect(url_for("portal.canais"))

    opts = "".join(
        f'<option value="{a["id"]}" {"selected" if a["id"] == canal["agente_id"] else ""}>{a["nome"]}</option>'
        for a in agentes
    )
    content = f"""
    <div class="card" style="max-width:640px">
      <h3 style="margin-top:0">Editar canal #{canal_id}</h3>
      <form method="post">
        {templates.csrf_field()}<label>Nome</label>
        <input name="nome" value="{canal['nome']}">
        <label>Tipo</label>
        <select name="tipo">
          <option value="api" {"selected" if canal['tipo'] == 'api' else ''}>API</option>
          <option value="webhook" {"selected" if canal['tipo'] == 'webhook' else ''}>Webhook</option>
        </select>
        <label>Agente</label>
        <select name="agente_id"><option value="">(nenhum)</option>{opts}</select>
        <label>Webhook de saída (URL)</label>
        <input name="webhook_url" value="{canal.get('webhook_url') or ''}" placeholder="https://... (POST da resposta)">
        <label>Headers do webhook (JSON, opcional)</label>
        <textarea name="webhook_headers" rows="2" style="font-family:var(--code-font,monospace);font-size:12px">{templates.h(canal.get('webhook_headers') or '')}</textarea>
        <div class="muted" style="font-size:11px">Para webhooks que exigem autenticação — ex: <code>{{"X-Webhook-Secret": "abc"}}</code> ou <code>{{"Authorization": "Bearer token"}}</code>.</div>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/canais">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Editar canal", content, active="canais", user=_user())


@bp.route("/canais/<int:canal_id>/regenerar")
@auth.admin_required
def canal_regenerar_token(canal_id: int):
    """Gera nova chave para o canal. A anterior para de funcionar imediatamente."""
    canal = db.listar_canais()
    canal = next((c for c in canal if c["id"] == canal_id), None)
    if not canal:
        flash("Canal não encontrado.", "bad")
        return redirect(url_for("portal.canais"))
    novo = db.regenerar_token_canal(canal_id)
    db.registrar_auditoria(
        _user()["login"], "admin", "regenerar_token_canal",
        alvo=canal["nome"], cliente_id=canal["cliente_id"], ip=request.remote_addr,
    )
    flash(f"Nova chave do canal '{canal['nome']}' gerada: {novo}. A chave anterior foi invalidada.", "ok")
    return redirect(url_for("portal.canais"))


@bp.route("/canais/<int:canal_id>/alternar")
@auth.admin_required
def canal_alternar(canal_id: int):
    """Alterna entre ativo e revogado."""
    canal = db.alternar_canal(canal_id)
    if not canal:
        flash("Canal não encontrado.", "bad")
        return redirect(url_for("portal.canais"))
    acao = "revogado" if not canal["ativo"] else "reativado"
    db.registrar_auditoria(
        _user()["login"], "admin", f"{acao}_canal",
        alvo=canal["nome"], cliente_id=canal["cliente_id"], ip=request.remote_addr,
    )
    flash(f"Canal '{canal['nome']}' {acao}.", "ok" if canal["ativo"] else "warn")
    return redirect(url_for("portal.canais"))


# --------------------------------------------------------------------------- #
# Gateway OpenAI-compatível (chats externos: Open WebUI, LibreChat...)        #
# --------------------------------------------------------------------------- #

def _endpoint_gateway() -> str:
    """Endpoint publico do gateway.

    Prioridade: env GATEWAY_PUBLIC_URL (ex: http://192.168.0.10:9003/v1 ou
    http://gateway.empresa.com/v1) > host da requisicao atual. Quando o
    host da requisicao e um tunel publico (nao expoe a porta do gateway),
    mostra o caminho Docker do host (host.docker.internal) — o caso mais
    comum de teste (chat externo em container na mesma maquina).
    """
    pub = os.environ.get("GATEWAY_PUBLIC_URL", "").strip().rstrip("/")
    if pub:
        return pub if pub.endswith("/v1") else pub + "/v1"
    host = request.host.split(":")[0] or "localhost"
    porta = os.environ.get("GATEWAY_PORT", "9003")
    if any(m in host for m in ("ngrok", "trycloudflare", ".tunnel.")):
        return f"http://host.docker.internal:{porta}/v1"
    return f"http://{host}:{porta}/v1"


@bp.route("/gateway", methods=["GET", "POST"])
@auth.admin_required
def gateway():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        canal_id = request.form.get("canal_id") or None
        modo = request.form.get("modo", "completa")
        ativo = 1 if request.form.get("ativo") else 0
        try:
            max_msg = max(1, min(int(request.form.get("max_mensagens") or 6), 100))
            max_tok = max(1, min(int(request.form.get("max_tokens") or 400), 8000))
        except ValueError:
            max_msg, max_tok = 6, 400
        if not nome or not canal_id:
            flash("Nome e canal são obrigatórios.", "warn")
            return redirect(url_for("portal.gateway"))
        gid = db.criar_gateway(nome, int(canal_id), modo=modo, ativo=ativo,
                               max_mensagens=max_msg, max_tokens=max_tok)
        db.registrar_auditoria(_user()["login"], "admin", "criar_gateway", alvo=nome,
                               cliente_id=1, ip=request.remote_addr)
        flash(f"Gateway '{nome}' ativado. Endpoint: {_endpoint_gateway()}", "ok")
        return redirect(url_for("portal.gateway"))

    rows = db.listar_gateways()
    canais = [c for c in db.listar_canais() if c["ativo"]]
    opts = "".join(f'<option value="{c["id"]}">{c["nome"]} → {next((a["nome"] for a in db.listar_agentes() if a["id"] == c["agente_id"]), "(sem agente)")}</option>' for c in canais)
    body = ""
    for g in rows:
        st = "ativo" if g["ativo"] else "pausado"
        body += f"""<tr>
          <td><b>{g['nome']}</b></td>
          <td>{g.get('canal_nome','-')}</td>
          <td>{g.get('agente_nome','-')} <span class="muted">({g.get('agente_area','')})</span></td>
          <td>{templates.badge(g['modo'])}</td>
          <td>{templates.badge(st)}</td>
          <td style="max-width:220px"><code style="font-size:11px">{_endpoint_gateway()}</code></td>
          <td class="row-actions">
            <a href="/portal/gateway/{g['id']}/editar">editar</a>
            <a href="/portal/gateway/{g['id']}/alternar">{"pausar" if g['ativo'] else "ativar"}</a>
            <a href="/portal/gateway/{g['id']}/excluir" onclick="return confirm('Excluir gateway {g['nome']}?')" style="color:var(--bad)">excluir</a>
          </td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Nome</th><th>Canal</th><th>Agente</th><th>Modo</th><th>Status</th><th>Endpoint (OpenAI)</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=7 class="empty">Nenhum gateway ativado.</td></tr>'}</tbody></table>"""
    form = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Ativar gateway (chat externo)</h3>
      <form method="post">
        {templates.csrf_field()}<label>Nome</label><input name="nome" placeholder="Ex: Gateway Vendas (Open WebUI)">
        <label>Canal vinculado (o token autentica o chat externo)</label>
        <select name="canal_id">{opts or '<option value="">(nenhum canal ativo — crie um canal primeiro)</option>'}</select>
        <label>Modo de resposta</label>
        <select name="modo">
          <option value="completa">Resposta completa (JSON)</option>
          <option value="streaming">Streaming (efeito de digitação — SSE)</option>
        </select>
        <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;margin:12px 0 0;font-weight:400;font-size:13px"><input type="checkbox" name="ativo" checked style="width:auto;margin:0;vertical-align:middle"> Gateway ativo</label>
        <div class="form-row" style="margin-top:6px">
          <div><label>Máx. mensagens de contexto</label><input type="number" name="max_mensagens" value="6" min="1" max="100" title="Últimas N mensagens da conversa enviadas ao agente"><div class="muted" style="font-size:11px">Últimas N mensagens (padrão 6)</div></div>
          <div><label>Limite de contexto (tokens, aprox.)</label><input type="number" name="max_tokens" value="400" min="1" max="8000" title="Orçamento total do contexto (~4 chars = 1 token); corta as mensagens mais antigas primeiro"><div class="muted" style="font-size:11px">Orçamento total; corta as antigas primeiro (padrão 400)</div></div>
        </div>
        <div style="margin-top:12px"><button class="btn" type="submit">Ativar gateway</button></div>
      </form>
    </div>"""
    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Gateway OpenAI-compatível: chats externos (Open WebUI, LibreChat, apps) falam o protocolo padrão e o gateway repassa ao agente via API do canal. Endpoint: <code>{_endpoint_gateway()}</code> — API Key = token do canal.
      <div style="margin-top:8px">Dica: se o chat externo roda em <b>Docker</b> na mesma máquina, use <code>http://host.docker.internal:9003/v1</code> (<code>host.docker.internal</code> é o caminho do host visto de dentro do Docker). Em outra máquina da rede: <code>http://IP_DO_SERVIDOR:9003/v1</code>. Para fixar uma URL pública, defina a env <code>GATEWAY_PUBLIC_URL</code>.</div></div>
    </div>{form}<h3 style="margin-top:18px">Gateways ativados</h3>{tabela}"""
    return templates.page("Gateway", content, active="gateway", user=_user())


@bp.route("/gateway/<int:gid>/editar", methods=["GET", "POST"])
@auth.admin_required
def gateway_editar(gid: int):
    g = db.buscar_gateway(gid)
    if not g:
        flash("Gateway não encontrado.", "bad")
        return redirect(url_for("portal.gateway"))
    if request.method == "POST":
        nome = (request.form.get("nome") or g["nome"]).strip()
        canal_id = int(request.form.get("canal_id") or g["canal_id"])
        modo = request.form.get("modo") or g["modo"]
        ativo = 1 if request.form.get("ativo") else 0
        try:
            max_msg = max(1, min(int(request.form.get("max_mensagens") or g.get("max_mensagens", 6)), 100))
            max_tok = max(1, min(int(request.form.get("max_tokens") or g.get("max_tokens", 400)), 8000))
        except ValueError:
            max_msg = int(g.get("max_mensagens", 6))
            max_tok = int(g.get("max_tokens", 400))
        db.atualizar_gateway(gid, nome=nome, canal_id=canal_id, modo=modo, ativo=ativo,
                             max_mensagens=max_msg, max_tokens=max_tok)
        db.registrar_auditoria(_user()["login"], "admin", "editar_gateway", alvo=nome,
                               cliente_id=1, ip=request.remote_addr)
        flash(f"Gateway '{nome}' atualizado.", "ok")
        return redirect(url_for("portal.gateway"))
    canais = db.listar_canais()
    opts = "".join(f'<option value="{c["id"]}" {"selected" if c["id"] == g["canal_id"] else ""}>{c["nome"]}</option>' for c in canais)
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Editar gateway #{gid}</h3>
      <form method="post">
        {templates.csrf_field()}<label>Nome</label><input name="nome" value="{g['nome']}">
        <label>Canal vinculado</label><select name="canal_id">{opts}</select>
        <label>Modo de resposta</label>
        <select name="modo">
          <option value="completa" {"selected" if g['modo']=='completa' else ''}>Resposta completa (JSON)</option>
          <option value="streaming" {"selected" if g['modo']=='streaming' else ''}>Streaming (SSE)</option>
        </select>
        <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;margin:12px 0 0;font-weight:400;font-size:13px"><input type="checkbox" name="ativo" {"checked" if g['ativo'] else ''} style="width:auto;margin:0;vertical-align:middle"> Gateway ativo</label>
        <div class="form-row" style="margin-top:6px">
          <div><label>Máx. mensagens de contexto</label><input type="number" name="max_mensagens" value="{g.get('max_mensagens', 6)}" min="1" max="100" title="Últimas N mensagens da conversa enviadas ao agente"><div class="muted" style="font-size:11px">Últimas N mensagens (padrão 6)</div></div>
          <div><label>Limite de contexto (tokens, aprox.)</label><input type="number" name="max_tokens" value="{g.get('max_tokens', 400)}" min="1" max="8000" title="Orçamento total do contexto (~4 chars = 1 token); corta as mensagens mais antigas primeiro"><div class="muted" style="font-size:11px">Orçamento total; corta as antigas primeiro (padrão 400)</div></div>
        </div>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/gateway">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Editar gateway", content, active="gateway", user=_user())


@bp.route("/gateway/<int:gid>/alternar")
@auth.admin_required
def gateway_alternar(gid: int):
    g = db.buscar_gateway(gid)
    if g:
        novo = 0 if g["ativo"] else 1
        db.atualizar_gateway(gid, ativo=novo)
        db.registrar_auditoria(_user()["login"], "admin",
                               "ativar_gateway" if novo else "pausar_gateway",
                               alvo=g["nome"], cliente_id=1, ip=request.remote_addr)
        flash(f"Gateway '{g['nome']}' {'ativado' if novo else 'pausado'}.", "ok")
    return redirect(url_for("portal.gateway"))


@bp.route("/gateway/<int:gid>/excluir")
@auth.admin_required
def gateway_excluir(gid: int):
    g = db.buscar_gateway(gid)
    if g:
        db.excluir_gateway(gid)
        db.registrar_auditoria(_user()["login"], "admin", "excluir_gateway",
                               alvo=g["nome"], cliente_id=1, ip=request.remote_addr)
        flash(f"Gateway '{g['nome']}' excluído.", "ok")
    return redirect(url_for("portal.gateway"))


# --------------------------------------------------------------------------- #
# Update Channel (canal de atualizacao aprovado pela BlueShift)               #
# --------------------------------------------------------------------------- #

@bp.route("/atualizacoes", methods=["GET", "POST"])
@auth.admin_required
def atualizacoes():
    from blueshift_layer import update_client
    info = update_client.check()
    if request.method == "POST":
        res = update_client.apply()
        if res.get("ok"):
            flash(f"Atualização {'simulada (dev) ' if res.get('dry_run') else ''}aplicada: "
                  f"{res.get('versao')}", "ok")
        else:
            flash(f"Não aplicada: {res.get('motivo')}", "bad")
        return redirect(url_for("portal.atualizacoes"))
    from blueshift_layer import __version__
    # ── Card de licenca da plataforma ──
    import os as _os
    from blueshift_layer import license_client as _lc
    chave = _os.environ.get("BLUESHIFT_LICENSE", "") or ""
    if chave:
        _valida = _lc.validate(chave)
        _meta = _lc.activate(chave) if _valida else {}
        _mascarada = (chave[:12] + "••••" + chave[-6:]) if len(chave) > 20 else "••••••"
        _badge = ('<span class="badge ok">✅ ativa</span>' if _valida
                  else '<span class="badge bad">⚠️ inválida</span>')
        _meta_html = ""
        if _valida and _meta.get("cliente") and _meta["cliente"] not in ("demo", None):
            _meta_html = (f'<div class="muted" style="font-size:12px;margin-top:6px">'
                          f'Cliente: <b>{templates.h(str(_meta.get("cliente","")))}</b> · '
                          f'Perfil: {templates.h(str(_meta.get("perfil","")))}</div>')
        card_licenca = f"""
    <div class="card" style="max-width:680px;margin-top:14px">
      <h3 style="margin-top:0">Licença da plataforma</h3>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <code style="font-size:13px">{templates.h(_mascarada)}</code> {_badge}
      </div>
      {_meta_html}
      <p class="muted" style="font-size:11px;margin-top:8px">A chave de ativação é definida na instalação (variável <code>BLUESHIFT_LICENSE</code>). Para trocar, reinicie o container com a nova chave.</p>
    </div>"""
    else:
        card_licenca = """
    <div class="card" style="max-width:680px;margin-top:14px">
      <h3 style="margin-top:0">Licença da plataforma</h3>
      <span class="badge warn">⚠️ não configurada</span>
      <p class="muted" style="font-size:11px;margin-top:8px">Defina a variável <code>BLUESHIFT_LICENSE</code> na instalação para ativar a plataforma.</p>
    </div>"""
    # ── Configuracao de ambiente (roteamento + areas) ──
    _router_env = _os.environ.get("BLUESHIFT_ROUTER_MODEL", "").strip()
    if _router_env.isdigit():
        _rm = db.buscar_modelo(int(_router_env))
        _router_txt = (f"{_rm['nome']} ({_rm['modelo']}) — id {_router_env}" if _rm
                       else f"id {_router_env} (não encontrado)")
    elif _router_env:
        _rm = next((m for m in db.listar_modelos()
                    if m["nome"].lower() == _router_env.lower()), None)
        _router_txt = (f"{_rm['nome']} ({_rm['modelo']})" if _rm
                       else f"{_router_env} (não encontrado)")
    else:
        _router_txt = "modelo principal de cada agente (padrão)"
    _areas_txt = ", ".join(listar_areas()) or "(nenhuma)"
    card_ambiente = f"""
    <div class="card" style="max-width:680px;margin-top:14px">
      <h3 style="margin-top:0">Configuração de ambiente</h3>
      <div style="font-size:13px;line-height:1.8">
        <div><span class="muted">Modelo de roteamento de conectores:</span> <b>{templates.h(_router_txt)}</b>
          <div class="muted" style="font-size:11px">variável <code>BLUESHIFT_ROUTER_MODEL</code> (id ou nome — o nome é o que aparece na tela Modelos IA)</div></div>
        <div style="margin-top:6px"><span class="muted">Áreas configuradas:</span> {templates.h(_areas_txt)}
          <div class="muted" style="font-size:11px">variável <code>BLUESHIFT_AREAS</code> — departamentos do Workspace</div></div>
      </div>
    </div>"""
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Update Channel (canal aprovado)</h3>
      <p class="muted">Versão instalada da camada BlueShift: <b>{__version__}</b></p>
      <p>Canal: <code>{update_client.UPDATE_URL}</code></p>
      <hr style="border-color:var(--line-soft)">
      {'<p class="muted">Nenhuma atualização disponível no canal.</p>' if not info.get('disponivel') else ''}
      {'<div class="badge ok">Nova versão disponível: ' + str(info.get('disponivel_version')) + '</div>' if info.get('disponivel') else ''}
      {f'<p><b>Notas:</b> {info.get("notes","")}</p>' if info.get('notes') else ''}
      {f'<p class="muted">Aprovado por: {info.get("aprovado_por")} em {info.get("publicado_em")}</p>' if info.get('aprovado_por') else ''}
      {f'<p class="muted">Pacote: <code>{info.get("url")}</code></p>' if info.get('url') else ''}
      {('<form method="post"><div style="margin-top:12px"><button class="btn" type="submit">Aplicar atualização</button></div></form>') if info.get('disponivel') else ''}
    </div>
    <div class="card muted" style="font-size:13px">
      O Update Channel é consultado em <code>BLUESHIFT_UPDATE_URL</code> (default: canal mock em
      <code>localhost:9001</code>). Em produção aponta para o backend real da BlueShift. O install
      é feito via <code>pip install blueshift-layer==versao</code> (dry-run em dev).
    </div>
    {card_licenca}
    {card_ambiente}
    """
    return templates.page("Atualizações", content, active="atualizacoes", user=_user())


# --------------------------------------------------------------------------- #
# Ajuda (popup publico — le DOCUMENTACAO_PB.md direto do disco, sem RAG)      #
# --------------------------------------------------------------------------- #

def _caminho_doc() -> str:
    """Localiza o DOCUMENTACAO_PB.md (repo local ou /opt/blueshift no Docker)."""
    from pathlib import Path
    candidatos = [
        Path(__file__).resolve().parent.parent.parent / "DOCUMENTACAO_PB.md",  # repo local
        Path("/opt/blueshift/DOCUMENTACAO_PB.md"),                            # container
    ]
    for c in candidatos:
        if c.exists():
            return str(c)
    return ""


def _secoes_doc() -> list:
    """Le o arquivo e separa em (titulo, texto) pelas secoes ## e ###."""
    import re as _re
    caminho = _caminho_doc()
    if not caminho:
        return []
    try:
        texto = open(caminho, encoding="utf-8").read()
    except OSError:
        return []
    partes = _re.split(r"\n(?=#{2,3} )", texto)
    secoes = []
    for p in partes:
        m = _re.match(r"#{2,3} (.+)", p.strip())
        if m:
            secoes.append((m.group(1).strip(), p.strip()))
    return secoes


def _secoes_relevantes(pergunta: str, secoes: list, limite_chars: int = 6000) -> list:
    """Seleciona secoes cujo texto contem palavras-chave da pergunta (>=4 chars).

    Normaliza acentos (pergunta sem acento casa com doc acentuada) e da
    PESO 2 para termos que aparecem no TITULO da secao — em empates de
    score, a secao cujo titulo casa a pergunta sobe no ranking (ex:
    'conhecimento' empata em varias secoes, mas so o titulo 5.12 o tem).
    """
    import re as _re
    import unicodedata as _u
    stop = {
        "como", "para", "qual", "quais", "onde", "quando", "porque", "com",
        "uma", "um", "que", "tem", "ser", "pode", "precisa", "fazer", "tela",
        "sistema", "portal", "campo", "campos", "preencher", "resposta",
        "sobre", "etc", "via", "pelo", "pela", "nos", "na", "no", "da", "do",
        "de", "em", "e", "os", "as", "ao", "aos", "nas", "dos", "das", "se",
        "mais", "menos", "outra", "outro", "outros", "entre", "apos", "ate",
        "voce", "vc", "quero", "saber", "existe", "existir", "posso",
    }

    def _norm(s: str) -> str:
        return _u.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    pergunta_n = _norm(pergunta.lower())
    termos = [t for t in _re.findall(r"[a-z0-9]{4,}", pergunta_n) if t not in stop]
    if not termos:
        return []
    pontuados = []
    for titulo, texto in secoes:
        titulo_n = _norm(titulo.lower())
        alvo_n = _norm((titulo + " " + texto).lower())
        score = sum(2 if t in titulo_n else 1 for t in termos if t in alvo_n)
        if score > 0:
            pontuados.append((score, titulo, texto))
    pontuados.sort(key=lambda x: -x[0])
    out = []
    total = 0
    for _score, titulo, texto in pontuados[:5]:
        total += len(texto)
        out.append(f"## {titulo}\n{texto}")
        if total >= limite_chars:
            break
    return out


@bp.route("/api/ajuda/modelos", methods=["GET"])
@auth.rate_limit_por_ip(60, 60)
def api_ajuda_modelos():
    """Lista publica de modelos para o seletor do popup (sem segredos)."""
    modelos = db.listar_modelos()
    return jsonify({
        "ok": True,
        "modelos": [{"id": m["id"], "nome": m["nome"], "modelo": m["modelo"], "tipo": m["tipo"]}
                    for m in modelos],
    })


@bp.route("/api/ajuda", methods=["POST"])
@auth.rate_limit_por_ip(30, 60)
def api_ajuda():
    """Responde a pergunta usando as secoes relevantes do DOCUMENTACAO_PB.md.

    Sem modelo cadastrado: retorna orientacao documental (secao Modelos IA
    da propria doc) — nunca falha em branco.
    """
    data = request.get_json(silent=True) or {}
    pergunta = (data.get("pergunta") or "").strip()
    if not pergunta:
        return jsonify({"ok": False, "erro": "campo 'pergunta' obrigatorio"}), 400

    secoes = _secoes_doc()
    modelos = db.listar_modelos()

    # ── Sem nenhum modelo cadastrado: orientacao vem da propria doc ──
    if not modelos:
        orient = next((t for tit, t in secoes if "Modelos IA" in tit), "")
        return jsonify({
            "ok": False,
            "motivo": "sem_modelo",
            "orientacao": orient,
            "dica": "Cadastre um modelo em Cadastros > Modelos IA para usar a ajuda.",
        })

    mid = data.get("modelo_id")
    modelo = next((m for m in modelos if m["id"] == mid), modelos[0]) if mid else modelos[0]
    if not (modelo.get("base_url") or "").strip() or modelo["base_url"] == "-":
        return jsonify({"ok": False, "erro": "modelo selecionado sem endpoint configurado"}), 400

    relevantes = _secoes_relevantes(pergunta, secoes)
    if not relevantes:
        return jsonify({
            "ok": False,
            "erro": "Nao encontrei na documentacao. Tente reformular a pergunta ou contate o suporte.",
        })

    from . import llm_client
    doc_bloco = "\n\n".join(relevantes)
    system = (
        "Voce e o assistente de ajuda da plataforma BlueShift. "
        "Responda com base APENAS na documentacao fornecida abaixo. "
        "Se a resposta nao estiver na documentacao, diga claramente que nao "
        "encontrou e sugira contatar o suporte. "
        "Seja objetivo, direto e em portugues."
    )
    mensagens = [
        {"role": "system", "content": system + "\n\nDOCUMENTACAO:\n" + doc_bloco},
        {"role": "user", "content": pergunta},
    ]
    out = llm_client.chat(modelo, mensagens)
    # Registra o consumo de tokens (origem "ajuda") — visível em Uso de
    # Tokens / Cost Intelligence. Não grava auditoria (pergunta de ajuda é
    # banal e a rota é pública — inclusive na tela de login).
    try:
        tok = out.get("tokens") or {}
        db.registrar_uso_token(
            modelo.get("cliente_id"), out.get("model") or modelo.get("modelo"),
            int(tok.get("total_tokens") or 0),
            prompt_tokens=int(tok.get("prompt_tokens") or 0),
            completion_tokens=int(tok.get("completion_tokens") or 0),
            modelo_fallback=0, quem="sistema", origem="ajuda",
        )
    except Exception:  # noqa: BLE001 - registro de uso nunca quebra a resposta
        pass
    if out["ok"]:
        return jsonify({
            "ok": True,
            "resposta": out["content"],
            "modelo": out["model"],
            "secoes_usadas": [t.splitlines()[0].replace("## ", "") for t in relevantes],
        })
    return jsonify({"ok": False, "erro": out["error"]}), 502
