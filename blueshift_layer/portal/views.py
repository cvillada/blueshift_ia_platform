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
    Blueprint, request, redirect, url_for, session, flash, current_app, jsonify,
)
import json
import urllib.parse
from . import db, auth, templates, sso
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


# ---------------------------------------------------------------------------
# Autenticacao
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
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
    content = """
    <div class="card" style="max-width:380px">
      <h3 style="margin-top:0">Acesso ao Portal</h3>
      <form method="post">
        <label>Login</label>
        <input name="login" placeholder="admin" autofocus>
        <label>Senha</label>
        <input name="senha" type="password" placeholder="••••••">
        <div style="margin-top:16px">
          <button class="btn" type="submit">Entrar</button>
        </div>
      </form>
      <p class="muted" style="margin-top:14px;font-size:12px">
        Demo: admin / admin123</p>
      <hr style="margin:18px 0;border-color:#1e2a3a">
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
# --------------------------------------------------------------------------- #

_AREAS = ["vendas", "suporte", "financeiro", "rh", "operacoes"]


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

    # métricas da área
    n_agentes = len(agentes)
    n_docs = len(docs)
    n_usuarios_area = len([x for x in db.listar_usuarios() if (x["area"] or "") == area_sel]) if area_sel else len(db.listar_usuarios())

    sel = ""
    if papel == "admin":
        opts = "".join(
            f'<option value="{a}"{" selected" if a == area_sel else ""}>{a}</option>'
            for a in _AREAS
        )
        sel = f'<form method="get" style="margin-bottom:14px"><label>Área</label><select name="area" onchange="this.form.submit()"><option value="">todas</option>{opts}</select></form>'

    cards_agentes = ""
    for a in agentes:
        cards_agentes += f"""
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong>{a['nome']}</strong>{templates.badge(a['status'])}</div>
          <div class="muted" style="font-size:12px;margin:6px 0">modelo {a['modelo']} · skills [{a['skills'] or '-'}]</div>
          <a class="btn ghost" href="/portal/agentes/{a['id']}/testar">testar agente</a>
        </div>"""

    kpis = f"""
    <div class="grid grid-4">
      <div class="kpi"><div class="label">Área</div><div class="value" style="font-size:18px;text-transform:capitalize">{area_sel or 'todas'}</div></div>
      <div class="kpi"><div class="label">Agentes</div><div class="value">{n_agentes}</div><div class="sub">da área</div></div>
      <div class="kpi"><div class="label">Usuários</div><div class="value">{n_usuarios_area}</div><div class="sub">na área</div></div>
      <div class="kpi"><div class="label">Base de conhecimento</div><div class="value">{n_docs}</div><div class="sub">documentos</div></div>
    </div>"""

    content = kpis + sel + ('<div class="grid grid-2" style="margin-top:16px">' + cards_agentes + "</div>"
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
        <div class="form-row">
          <div><label>Código *</label><input name="codigo" placeholder="ex: porto"></div>
          <div><label>Nome *</label><input name="nome" placeholder="ex: Porto Seguros"></div>
        </div>
        <div class="form-row">
          <div><label>Empresa</label><input name="empresa"></div>
          <div><label>Email de contato</label><input name="email" type="email"></div>
        </div>
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
        <div class="form-row">
          <div><label>Código</label><input name="codigo" value="{c['codigo']}"></div>
          <div><label>Nome</label><input name="nome" value="{c['nome']}"></div>
        </div>
        <div class="form-row">
          <div><label>Empresa</label><input name="empresa" value="{c['empresa'] or ''}"></div>
          <div><label>Email</label><input name="email" value="{c['email'] or ''}"></div>
        </div>
        <div class="form-row">
          <div><label>Licença</label>
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
        </tr>"""
    tabela = f"""<table><thead><tr><th>Nome</th><th>Login</th><th>Papel</th><th>Área</th><th>Cliente</th><th>Status</th></tr></thead>
      <tbody>{body or '<tr><td colspan=6 class="empty">Nenhum usuário.</td></tr>'}</tbody></table>"""
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
    opts = "".join(f'<option value="{c["id"]}">{c["nome"]}</option>' for c in clientes)
    content = f"""
    <div class="card" style="max-width:640px">
      <h3 style="margin-top:0">Cadastrar usuário</h3>
      <form method="post">
        <label>Cliente</label><select name="cliente_id"><option value="">-- selecione --</option>{opts}</select>
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
    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Agent Factory: monte agentes a partir do catálogo de skills + conectores MCP + modelo de IA.</div>
      <a class="btn" href="/portal/agentes/novo">+ Montar agente</a>
    </div>{tabela}"""
    return templates.page("Agentes", content, active="agentes", user=_user())


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
    if request.method == "POST":
        pergunta = request.form.get("pergunta", "").strip()
        if pergunta:
            out = agente_mod.responder(a, pergunta, u["login"], id_cliente="C001")
            fallback_usado = out.get("model_fallback", False)
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
    content = f"""
    <div class="muted" style="margin-bottom:10px">
      Teste do agente <b>{a['nome']}</b> (área {area or 'geral'}) — modelo <b>{a['modelo']}</b>,
      skills [{a['skills'] or '-'}], {conn_info}.
    </div>
    <div class="card" style="max-width:760px">
      <form method="post">
        <label>Pergunta para o agente</label>
        <textarea name="pergunta" rows="3" placeholder="Ex: qual o status do cliente 123?">{request.form.get("pergunta","")}</textarea>
        <div style="margin-top:12px"><button class="btn" type="submit">Enviar ao agente</button></div>
      </form>
      {ctx_html}
      {fer_html}
      {f'<div class="card" style="margin-top:14px;background:#0c2230"><b>🤖 {a["nome"]}:</b><p style="margin:8px 0 0">{resposta}</p>{badge_fallback}</div>' if resposta else ''}
      {f'<div class="badge warn" style="margin-top:12px">⚠️ {erro}</div>' if erro else ''}
    </div>
    <div style="margin-top:14px"><a class="btn ghost" href="/portal/agentes">← Voltar</a></div>"""
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
                            modelo_secundario_id=modelo_sec_id)
            u = _user()
            db.registrar_auditoria(u["login"], u["papel"], "criar_agente", alvo=nome,
                                   cliente_id=cid, ip=request.remote_addr)
            flash(f"Agente '{nome}' criado.", "ok")
            return redirect(url_for("portal.agentes"))
    opts = "".join(f'<option value="{c["id"]}">{c["nome"]}</option>' for c in clientes)
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
        <div class="form-row">
          <div><label>Cliente</label><select name="cliente_id"><option value="">-- selecione --</option>{opts}</select></div>
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
        <div class="form-row">
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
      <a class="btn" href="/portal/skills/novo">+ Nova skill</a>
    </div>{tabela}"""
    return templates.page("Skills", content, active="skills", user=_user())


_MODAL_HTML = """
<div class="modal-overlay" id="modal-ia" onclick="if(event.target===this)fecharModalIA()">
  <div class="modal-box">
    <h3>✨ Gerar skill com IA</h3>
    <p class="muted" style="font-size:13px">Descreva o que a skill deve fazer. A IA usara o primeiro modelo cadastrado em Modelos IA para gerar o conteudo.</p>
    <textarea id="ia-prompt" rows="4" placeholder="Ex: Agente de suporte que consulta a base de conhecimento..."></textarea>
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
  var b=document.getElementById("btn-gerar");b.classList.add("loading");b.disabled=true;b.innerHTML="\u23f3 Gerando...";
  document.getElementById("ia-erro").style.display="none";
  fetch("/portal/skills/gerar-ia",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt:p})})
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
    content = """
    <div class="card" style="max-width:700px">
      <h3 style="margin-top:0">Nova skill</h3>
      <form method="post">
        <div class="form-row">
          <div><label>Nome (identificador)</label><input name="nome" placeholder="ex: vendas"></div>
          <div><label>Versão</label><input name="version" value="1.0.0"></div>
        </div>
        <label>Descrição</label><input name="descricao" id="skill-desc" placeholder="Agente de vendas - consulta ERP, propoe produtos">
        <label>
          Conteúdo (SKILL.md body — instruções do agente)
          <button type="button" class="btn-ia" onclick="abrirModalIA()" style="margin-left:8px">✨ Gerar com IA</button>
        </label>
        <textarea name="body" id="skill-body" rows="10" placeholder="# Comportamento&#10;1. Ao perguntarem status, consulte o ERP&#10;2. Nunca invente dados"></textarea>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Criar skill</button>
          <a class="btn ghost" href="/portal/skills">Cancelar</a>
        </div>
      </form>
    </div>"""
    content += _MODAL_HTML
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
        <div class="form-row">
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
    content += _MODAL_HTML
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
    _AREAS = ["vendas", "suporte", "financeiro", "rh", "operacoes"]

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
            config["command"] = request.form.get("mcp_command", "").strip()
            config["tool"] = request.form.get("mcp_tool", "").strip()
            args_raw = request.form.get("mcp_args", "{}").strip()
            try:
                config["args"] = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                config["args"] = {}
        elif tipo == "sql":
            config["dsn_env"] = request.form.get("sql_dsn_env", "").strip()
            config["dsn"] = request.form.get("sql_dsn", "").strip()
            config["query"] = request.form.get("sql_query", "").strip()

        config["descricao"] = request.form.get("descricao", "").strip()

        db.criar_conector(cid, nome, tipo=tipo, area=area, config=config)
        db.registrar_auditoria(_user()["login"], "admin", "criar_conector",
                               alvo=nome, cliente_id=cid, ip=request.remote_addr)
        flash(f"Conector '{nome}' criado na área {area}.", "ok")
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
        body += f"""<tr>
          <td><b>{k['nome']}</b></td>
          <td>{tipo_icon} {k['tipo']}</td>
          <td>{k['area'] or '-'}</td>
          <td class="muted" style="max-width:300px;overflow:hidden;text-overflow:ellipsis">{cfg_resumo}</td>
          <td>{templates.badge(k['status'])}</td>
          <td class="muted">{k['ultimo_heartbeat'] or '-'}</td>
          <td class="row-actions">
            <a href="{url_for('portal.conector_editar', cid=k['id'])}">editar</a>
            <a href="{url_for('portal.conector_excluir', cid=k['id'])}" onclick="return confirm('Excluir conector \'{k['nome']}\'?')">excluir</a>
          </td></tr>"""

    opts_area = "".join(f'<option value="{a}" {"selected" if a == area_sel else ""}>{a}</option>' for a in _AREAS)
    opts_cliente = "".join(f'<option value="{i}" {"selected" if i == cid_sel else ""}>{n}</option>' for i, n in clientes.items())
    content = f"""
    <div class="card" style="max-width:720px">
      <h3 style="margin-top:0">Cadastrar fonte externa</h3>
      <p class="muted">Conecte APIs, servidores MCP ou consultas SQL como fonte de dados para os agentes da área.</p>
      <form method="post">
        <div class="form-row">
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
            <div><label>Headers (JSON)</label><input name="api_headers" placeholder='{{"Authorization":"Bearer xxx"}}'></div>
          </div>
          <label>Body (JSON, só POST)</label><input name="api_body" placeholder='{{"id": "{{id_cliente}}"}}'>
        </div>
        <div id="conn-fields-mcp" style="display:none">
          <label>Comando</label><input name="mcp_command" placeholder="python /opt/blueshift/mcp_server.py">
          <label>Ferramenta (tool)</label><input name="mcp_tool" placeholder="erp_buscar_cliente">
          <label>Argumentos (JSON)</label><input name="mcp_args" placeholder='{{"id_cliente": "{{id_cliente}}"}}'>
        </div>
        <div id="conn-fields-sql" style="display:none">
          <label>DSN (variável de ambiente)</label><input name="sql_dsn_env" placeholder="ERP_DSN">
          <label>DSN direto (opcional)</label><input name="sql_dsn" placeholder="host=... dbname=...">
          <label>Query SQL</label><textarea name="sql_query" rows="3" placeholder="SELECT * FROM vw_clientes WHERE id_cliente = '{{id_cliente}}'"></textarea>
        </div>
        <label>Descrição</label><input name="descricao" placeholder="O que este conector faz">
        <div style="margin-top:14px"><button class="btn" type="submit">Cadastrar conector</button></div>
      </form>
    </div>
    <script>
    function toggleConnFields() {{
      var t = document.getElementById('conn-tipo').value;
      document.getElementById('conn-fields-api').style.display = t === 'api' ? '' : 'none';
      document.getElementById('conn-fields-mcp').style.display = t === 'mcp' ? '' : 'none';
      document.getElementById('conn-fields-sql').style.display = t === 'sql' ? '' : 'none';
    }}
    </script>
    <div class="card">
      <h3 style="margin-top:0">Fontes externas cadastradas</h3>
      <form method="get" style="margin-bottom:12px;display:flex;gap:8px;align-items:end">
        <div><label>Cliente</label><select name="cliente_id">{opts_cliente}</select></div>
        <div><label>Área</label><select name="area"><option value="">todas</option>{opts_area}</select></div>
        <div><button class="btn ghost" type="submit">Filtrar</button></div>
      </form>
      <table><thead><tr><th>Nome</th><th>Tipo</th><th>Área</th><th>Config</th><th>Status</th><th>Heartbeat</th><th></th></tr></thead>
        <tbody>{body or '<tr><td colspan="7" class="muted">Nenhum conector cadastrado. Crie um acima.</td></tr>'}</tbody></table>
    </div>"""
    return templates.page("Conectores", content, active="conectores", user=_user())


@bp.route("/conectores/<int:cid>/editar", methods=["GET", "POST"])
@auth.admin_required
def conector_editar(cid: int):
    con = db.buscar_conector(cid)
    if not con:
        flash("Conector não encontrado.", "bad")
        return redirect(url_for("portal.conectores"))
    cfg = _parse_config(con.get("config", "{}"))
    _AREAS = ["vendas", "suporte", "financeiro", "rh", "operacoes"]

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
            config["command"] = request.form.get("mcp_command", "").strip()
            config["tool"] = request.form.get("mcp_tool", "").strip()
            args_raw = request.form.get("mcp_args", "{}").strip()
            try:
                config["args"] = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                config["args"] = {}
        elif tipo == "sql":
            config["dsn_env"] = request.form.get("sql_dsn_env", "").strip()
            config["dsn"] = request.form.get("sql_dsn", "").strip()
            config["query"] = request.form.get("sql_query", "").strip()

        config["descricao"] = request.form.get("descricao", "").strip()

        if not nome:
            flash("Nome é obrigatório.", "warn")
            return redirect(url_for("portal.conector_editar", cid=cid))

        db.atualizar_conector(cid, nome=nome, area=area, tipo=tipo, config=config)
        db.registrar_auditoria(_user()["login"], "admin", "editar_conector",
                               alvo=nome, ip=request.remote_addr)
        flash(f"Conector '{nome}' atualizado.", "ok")
        return redirect(url_for("portal.conectores"))

    opts_area = "".join(f'<option value="{a}" {"selected" if a == con["area"] else ""}>{a}</option>' for a in _AREAS)
    content = f"""
    <div class="card" style="max-width:720px">
      <h3 style="margin-top:0">Editar conector #{cid}</h3>
      <form method="post">
        <div class="form-row">
          <div><label>Nome</label><input name="nome" value="{con['nome']}"></div>
          <div><label>Área</label><select name="area">{opts_area}</select></div>
        </div>
        <div class="form-row">
          <div><label>Tipo</label><select name="tipo"><option value="api" {"selected" if con['tipo']=='api' else ''}>API</option><option value="mcp" {"selected" if con['tipo']=='mcp' else ''}>MCP</option><option value="sql" {"selected" if con['tipo']=='sql' else ''}>SQL</option></select></div>
        </div>
        <label>Config (JSON)</label><textarea name="config_json" rows="6" style="font-family:monospace;font-size:12px">{json.dumps(cfg, indent=2, ensure_ascii=False)}</textarea>
        <p class="muted" style="font-size:12px">Edite o JSON de configuração diretamente.</p>
        <label>Descrição</label><input name="descricao" value="{cfg.get('descricao','')}">
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/conectores">Cancelar</a>
        </div>
      </form>
    </div>"""
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
      <tbody>{body or '<tr><td colspan=7 class="empty">Nenhum consumo registrado ainda.</td></tr>'}</tbody></table>"""
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

@bp.route("/auditoria")
@auth.admin_required
def auditoria():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    rows = db.listar_auditoria(200)
    body = ""
    for a in rows:
        cliente = clientes.get(a["cliente_id"], "-") if a["cliente_id"] else "-"
        body += f"""<tr>
          <td class="muted">{a['criado_em']}</td>
          <td><b>{a['usuario']}</b></td>
          <td>{templates.badge(a['papel'])}</td>
          <td>{a['acao']}</td>
          <td>{a['alvo'] or '-'}</td>
          <td>{cliente}</td>
          <td class="muted">{a['ip'] or '-'}</td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Data/Hora</th><th>Usuário</th><th>Papel</th><th>Ação</th><th>Alvo</th><th>Cliente</th><th>IP</th></tr></thead>
      <tbody>{body or '<tr><td colspan=7 class="empty">Nenhum evento registrado.</td></tr>'}</tbody></table>"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Rastreabilidade completa (LGPD): todo login e toda ação sensível é registrada com usuário, papel, alvo, cliente e IP.
    </div>{tabela}"""
    return templates.page("Auditoria", content, active="auditoria", user=_user())


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
    body = ""
    for m in rows:
        body += f"""<tr>
          <td>{templates.badge(m['tipo'])}</td>
          <td>{m['conteudo']}</td>
          <td>{m['usuario']}</td>
          <td class="muted">{m['criado_em']}</td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Tipo</th><th>Conteúdo</th><th>Usuário</th><th>Quando</th></tr></thead>
      <tbody>{body or '<tr><td colspan=4 class="empty">Nenhuma memória.</td></tr>'}</tbody></table>"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Memória persistente por usuário (banco vetorial local). Isolada por login — cada usuário vê só a própria.
    </div>
    <div class="card" style="max-width:680px;margin-bottom:16px">
      <h3 style="margin-top:0">Salvar memória</h3>
      <form method="post">
        <label>Cliente</label>
          <select name="cliente_id">
            {''.join(f'<option value="{c["id"]}" {"selected" if c["id"]==cliente_id else ""}>{c["nome"]}</option>' for c in db.listar_clientes())}
          </select>
        <label>Tipo</label>
          <select name="tipo"><option value="conversa">Conversa</option><option value="preferencia">Preferência</option><option value="contexto">Contexto</option></select>
        <label>Conteúdo</label><textarea name="conteudo" rows="3" placeholder="Ex: cliente prefere contato por email"></textarea>
        <div style="margin-top:12px"><button class="btn" type="submit">Salvar memória</button></div>
      </form>
    </div>
    {tabela}"""
    return templates.page("Memória", content, active="memoria", user=u)


@bp.route("/conhecimento", methods=["GET", "POST"])
@auth.login_required
def conhecimento():
    u = _user()
    _AREAS = ["vendas", "suporte", "financeiro", "rh", "operacoes"]

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

    body = ""
    for d in docs:
        preview = d['conteudo'][:120] + ("…" if len(d['conteudo']) > 120 else "")
        acessos_txt = f"{d.get('acessos',0)} acesso(s)" if d.get('acessos', 0) else "0 acesso"
        ultimo = f" · último: {d.get('ultimo_acesso','-')[:10]}" if d.get('ultimo_acesso') else ""
        body += f"""<tr>
          <td><b>{d['titulo']}</b><br><span class="muted" style="font-size:11px">{d.get('area') or '-'} · {d.get('fonte','manual')}</span></td>
          <td>{templates.badge(d['categoria'])}</td>
          <td class="muted">{preview}</td>
          <td style="font-size:12px">{acessos_txt}{ultimo}</td>
          <td class="muted">{d['criado_em'][:10]}</td>
          <td class="row-actions">
            <a href="{url_for('portal.conhecimento_editar', did=d['id'])}">editar</a>
            <a href="{url_for('portal.conhecimento_excluir', did=d['id'])}" onclick="return confirm('Excluir documento?')" style="color:var(--bad)">excluir</a>
          </td></tr>"""

    # --- Estatisticas ---
    stats = db.contar_documentos(cliente_id=cid_sel)

    opts_cliente = "".join(f'<option value="{c["id"]}" {"selected" if c["id"]==cid_sel else ""}>{c["nome"]}</option>' for c in db.listar_clientes())
    opts_area = "".join(f'<option value="{a}" {"selected" if a==area_sel else ""}>{a}</option>' for a in _AREAS)

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
        <input type="hidden" name="_action" value="add">
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
        <input type="hidden" name="_action" value="csv_import">
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
        <input type="hidden" name="_action" value="pdf_import">
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
    <div class="card">
      <h3 style="margin-top:0">Documentos</h3>
      <form method="get" style="margin-bottom:10px;display:flex;gap:8px;align-items:end">
        <div><label>Cliente</label><select name="cliente_id" onchange="this.form.submit()"><option value="">todos</option>{''.join(f'<option value="{c["id"]}" {"selected" if c["id"]==cid_sel else ""}>{c["nome"]}</option>' for c in db.listar_clientes())}</select></div>
        <div><label>Área</label><select name="area" onchange="this.form.submit()"><option value="">todas</option>{opts_area}</select></div>
      </form>
      <table><thead><tr><th>Título</th><th>Categoria</th><th>Conteúdo</th><th>Acessos</th><th>Quando</th><th></th></tr></thead>
        <tbody>{body or '<tr><td colspan="6" class="muted">Nenhum documento.</td></tr>'}</tbody></table>
    </div>"""
    return templates.page("Base de Conhecimento", content, active="conhecimento", user=u)


@bp.route("/conhecimento/<int:did>/editar", methods=["GET", "POST"])
@auth.admin_required
def conhecimento_editar(did: int):
    doc = db.buscar_documento(did)
    if not doc:
        flash("Documento não encontrado.", "bad")
        return redirect(url_for("portal.conhecimento"))
    _AREAS = ["vendas", "suporte", "financeiro", "rh", "operacoes"]
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
    opts_area = "".join(f'<option value="{a}" {"selected" if a==doc.get("area","") else ""}>{a}</option>' for a in _AREAS)
    opts_cliente = "".join(f'<option value="{c["id"]}" {"selected" if c["id"]==doc["cliente_id"] else ""}>{c["nome"]}</option>' for c in db.listar_clientes())
    content = f"""
    <div class="card" style="max-width:700px">
      <h3 style="margin-top:0">Editar documento #{did}</h3>
      <form method="post">
        <div class="form-row">
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
    tabela = f"""<table><thead><tr><th>Nome</th><th>Tipo</th><th>Endpoint</th><th>Modelo</th><th>Status</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=5 class="empty">Nenhum modelo cadastrado.</td></tr>'}</tbody></table>"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Cadastro de LLMs por cliente (OpenAI-compatible: LM Studio, vLLM, Ollama). O chat de teste usa estes modelos.
    </div>
    <div class="card" style="max-width:680px;margin-bottom:16px">
      <h3 style="margin-top:0">Cadastrar modelo de IA</h3>
      <form method="post">
        <label>Cliente</label>
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
        db.atualizar_modelo(mid, **campos)
        db.registrar_auditoria(_user()["login"], "admin", "editar_modelo", alvo=request.form.get("nome", m["nome"]),
                               cliente_id=m["cliente_id"], ip=request.remote_addr)
        flash("Modelo atualizado.", "ok")
        return redirect(url_for("portal.modelos"))
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Editar modelo #{mid}: {m['nome']}</h3>
      <form method="post">
        <label>Nome</label><input name="nome" value="{m['nome']}">
        <label>Endpoint (base_url)</label><input name="base_url" value="{m['base_url']}">
        <label>Modelo</label><input name="modelo" value="{m['modelo']}">
        <label>Tipo</label>
          <select name="tipo"><option value="local" {"selected" if m['tipo']=='local' else ""}>Local</option><option value="hibrido" {"selected" if m['tipo']=='hibrido' else ""}>Híbrido</option></select>
        <label>API Key</label><input name="api_key" value="{m.get('api_key') or ''}">
        <label>Max tokens</label><input name="max_tokens" type="number" value="{m.get('max_tokens') or 4096}" style="width:200px">
        <div class="muted" style="font-size:11px;margin-top:4px">Aumente para modelos com thinking (8192, 16384). Timeout: 180s.</div>
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
        <label>Modelo de IA</label><select name="modelo_id">{opts}</select>
        <label>Pergunta</label><textarea name="pergunta" rows="3" placeholder="Ex: qual a política de privacidade da BlueShift?">{request.form.get("pergunta","")}</textarea>
        <div style="margin-top:12px"><button class="btn" type="submit">Enviar</button></div>
      </form>
      {ctx_html}
      {fer_html}
      {f'<div class="card" style="margin-top:14px;background:#0c2230"><b>🤖 {modelo_usado or "IA"}:</b><p style="margin:8px 0 0">{resposta}</p></div>' if resposta else ''}
      {f'<div class="badge warn" style="margin-top:12px">⚠️ {erro}</div>' if erro else ''}
    </div>"""
    return templates.page("Chat de Teste", content, active="chat", user=u)


# --------------------------------------------------------------------------- #
# Canal real (API / webhook) — integracao maquina-a-maquina com o agente      #
# --------------------------------------------------------------------------- #

@bp.route("/api/v1/agente", methods=["POST"])
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
    id_cliente = data.get("id_cliente") or "C001"
    out = agente_mod.responder(a, pergunta, usuario, id_cliente=id_cliente)
    db.registrar_auditoria(
        f"canal:{canal['id']}", "sistema", "api_agente", alvo=a["nome"],
        cliente_id=canal["cliente_id"], ip=request.remote_addr, detalhe=pergunta[:80],
    )
    resposta = {
        "ok": out["ok"],
        "resposta": out["content"],
        "agente": a["nome"],
        "modelo": out.get("model"),
        "contexto": [c["texto"] for c in out.get("contexto", [])],
        "ferramentas": out.get("ferramentas", []),
        "erro": out.get("error"),
    }
    # webhook de saida (item 3): POST da resposta para a URL configurada no canal
    if canal.get("webhook_url"):
        wh = agente_mod.enviar_webhook(canal["webhook_url"], {
            "canal": canal["nome"],
            "agente": a["nome"],
            "pergunta": pergunta,
            "resposta": out["content"],
            "modelo": out.get("model"),
        })
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
        db.criar_canal(cid, nome, agente_id, tipo=tipo, webhook_url=webhook_url)
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
        body += f"""<tr>
          <td><b>{c['nome']}</b></td>
          <td>{c['tipo']}</td>
          <td>{ag}</td>
          <td style="max-width:260px"><code style="font-size:11px">{c['token']}</code>
            <button class="btn-copy" onclick="navigator.clipboard.writeText('{c['token']}')" title="Copiar chave">📋</button>
          </td>
          <td>{templates.badge(st)}</td>
          <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis"><code>{wh}</code></td>
          <td class="row-actions">
            <a href="{url_for('portal.canal_editar', canal_id=c['id'])}">editar</a>
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
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Criar canal de integração</h3>
      <form method="post">
        <label>Cliente</label><select name="cliente_id">{''.join(f'<option value="{i}">{n}</option>' for i,n in clientes.items())}</select>
        <label>Nome</label><input name="nome" placeholder="Ex: Webhook Vendas Site">
        <label>Tipo</label><select name="tipo"><option value="api">API</option><option value="webhook">Webhook</option></select>
        <label>Agente</label><select name="agente_id"><option value="">(nenhum)</option>{''.join(f'<option value="{a["id"]}">{a["nome"]}</option>' for a in agentes)}</select>
        <label>Webhook de saída (URL)</label><input name="webhook_url" placeholder="https://... (POST da resposta)">
        <div style="margin-top:12px"><button class="btn" type="submit">Criar canal</button></div>
      </form>
    </div>
    {token_tooltip}
    <div class="card">
      <h3 style="margin-top:0">Canais cadastrados</h3>
      <table><thead><tr><th>Nome</th><th>Tipo</th><th>Agente</th><th>Chave (token)</th><th>Status</th><th>Webhook saída</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan="7" class="muted">nenhum canal cadastrado</td></tr>'}</tbody></table>
    </div>
    <div class="card muted" style="font-size:13px">
      <b>Como usar (canal real):</b><br><br>
      Faça uma requisição <code>POST</code> para o endpoint do agente usando o token do canal:<br><br>
      <pre style="background:#0e1726;padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.6">curl -X POST http://localhost:8080/portal/api/v1/agente \u005c<br>  -H "Authorization: Bearer &lt;TOKEN_DO_CANAL&gt;" \u005c<br>  -H "Content-Type: application/json" \u005c<br>  -d '{{"pergunta": "Qual o hist\u00f3rico do cliente C001?"}}'</pre>
      <br>
      Substitua <code>&lt;TOKEN_DO_CANAL&gt;</code> pela chave do canal (use o botão 📋 ao lado do token para copiar).<br><br>
      <b>Resposta (JSON):</b><br><br>
      <pre style="background:#0e1726;padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.6">{{
  "ok": true,
  "resposta": "...",
  "agente": "Agente Vendas",
  "modelo": "bonsai-8b",
  "contexto": [...],
  "ferramentas": [...],
  "webhook": {{"enviado": true, "status": 200}}
}}</pre>
      Se o canal tiver um <b>Webhook de saída</b>, a resposta também é POSTada na URL configurada.
    </div>
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
        db.atualizar_canal(canal_id, nome=nome, tipo=tipo, agente_id=agente_id, webhook_url=webhook_url)
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
        <label>Nome</label>
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
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Update Channel (canal aprovado)</h3>
      <p class="muted">Versão instalada da camada BlueShift: <b>{__version__}</b></p>
      <p>Canal: <code>{update_client.UPDATE_URL}</code></p>
      <hr style="border-color:#16344a">
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
    """
    return templates.page("Atualizações", content, active="atualizacoes", user=_user())
