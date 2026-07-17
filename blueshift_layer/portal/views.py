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
    return templates.page("Configurar SSO", content, active="sso")


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
    total_agentes = len(db.listar_agentes())
    total_conectores = len(db.listar_conectores())

    # cards de saude por cliente
    cards = ""
    for c in clientes:
        h = db.buscar_health(c["id"]) or {}
        conns = db.listar_conectores(c["id"])
        online = sum(1 for k in conns if k["status"] == "online")
        off = len(conns) - online
        cards += f"""
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong>{c['nome']}</strong>
            {templates.badge(c['status'])}
          </div>
          <div class="muted" style="font-size:12px;margin:4px 0 12px">código: {c['codigo']}</div>
          <div class="grid grid-2" style="gap:10px">
            <div><div class="muted" style="font-size:11px">Container</div>{templates.badge(h.get('container','-'))}</div>
            <div><div class="muted" style="font-size:11px">Modelo local</div>{templates.badge(h.get('modelo_local','-'))}</div>
            <div><div class="muted" style="font-size:11px">Latência</div><b>{h.get('latencia_ms',0)} ms</b></div>
            <div><div class="muted" style="font-size:11px">Tokens/24h</div><b>{h.get('tokens_hoje',0):,}</b></div>
          </div>
          <div style="margin-top:10px;font-size:12px" class="muted">
            Conectores: {online} online / {off} offline ·
            Erros 24h: <b style="color:var(--{'bad' if h.get('erros_24h',0) else 'txt'})">{h.get('erros_24h',0)}</b>
          </div>
        </div>"""

    kpis = f"""
    <div class="grid grid-4">
      <div class="kpi"><div class="label">Clientes</div><div class="value">{total_clientes}</div><div class="sub">ativos na plataforma</div></div>
      <div class="kpi"><div class="label">Usuários</div><div class="value">{total_usuarios}</div><div class="sub">logins cadastrados</div></div>
      <div class="kpi"><div class="label">Agentes</div><div class="value">{total_agentes}</div><div class="sub">instâncias operando</div></div>
      <div class="kpi"><div class="label">Conectores</div><div class="value">{total_conectores}</div><div class="sub">MCP expostos</div></div>
    </div>"""

    content = kpis + '<div class="grid grid-2" style="margin-top:16px">' + cards + "</div>"
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
        <label>Modelo de licença</label>
        <select name="licenca">
          <option value="anual_por_empresa">Anual por empresa</option>
          <option value="anual_por_empresa_plus">Anual + modelo externo</option>
        </select>
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
        body += f"""<tr>
          <td><b>{a['nome']}</b></td>
          <td>{a['area'] or '-'}</td>
          <td>{a['modelo']}</td>
          <td>{a['skills'] or '-'}</td>
          <td>{a['conectores'] or '-'}</td>
          <td>{templates.badge(a['status'])}</td>
          <td>{clientes.get(a['cliente_id'], '?')}</td>
          <td class="row-actions">
            <a href="/portal/agentes/{a['id']}/testar">testar</a>
          </td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Agente</th><th>Área</th><th>Modelo</th><th>Skills</th><th>Conectores</th><th>Status</th><th>Cliente</th><th></th></tr></thead>
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
    if request.method == "POST":
        pergunta = request.form.get("pergunta", "").strip()
        if pergunta:
            out = agente_mod.responder(a, pergunta, u["login"], id_cliente="C001")
            if out["ok"]:
                resposta = out["content"]
                contexto = out["contexto"]
                ferramentas = out.get("ferramentas", [])
                db.registrar_auditoria(u["login"], u["papel"], "testar_agente", alvo=a["nome"],
                                       cliente_id=a["cliente_id"], ip=request.remote_addr,
                                       detalhe=pergunta[:80])
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
        fer_html = "<div class=\"muted\" style=\"margin:10px 0;font-size:13px\"><b>Dados de sistema (conectores MCP executados):</b><ul style=\"margin:6px 0 0 18px\">" + \
            "".join(itens) + "</ul></div>"
    skills_txt = a["skills"] or "-"
    conn_txt = a["conectores"] or "-"
    content = f"""
    <div class="muted" style="margin-bottom:10px">
      Teste do agente <b>{a['nome']}</b> (área {a['area'] or 'geral'}) — modelo <b>{a['modelo']}</b>,
      skills [{skills_txt}], conectores [{conn_txt}]. O agente usa RAG (memória + base) + o modelo real.
    </div>
    <div class="card" style="max-width:760px">
      <form method="post">
        <label>Pergunta para o agente</label>
        <textarea name="pergunta" rows="3" placeholder="Ex: qual o status do cliente 123?">{request.form.get("pergunta","")}</textarea>
        <div style="margin-top:12px"><button class="btn" type="submit">Enviar ao agente</button></div>
      </form>
      {ctx_html}
      {fer_html}
      {f'<div class="card" style="margin-top:14px;background:#0c2230"><b>🤖 {a["nome"]}:</b><p style="margin:8px 0 0">{resposta}</p></div>' if resposta else ''}
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
            conectores = ",".join(request.form.getlist("conectores"))
            modelo_nome = ""
            if modelo_id:
                m = db.buscar_modelo(modelo_id)
                modelo_nome = m["nome"] if m else ""
            db.criar_agente(cid, nome, request.form.get("area", ""), modelo_nome,
                            skills, conectores, modelo_id=modelo_id)
            u = _user()
            db.registrar_auditoria(u["login"], u["papel"], "criar_agente", alvo=nome,
                                   cliente_id=cid, ip=request.remote_addr)
            flash(f"Agente '{nome}' criado.", "ok")
            return redirect(url_for("portal.agentes"))
    opts = "".join(f'<option value="{c["id"]}">{c["nome"]}</option>' for c in clientes)
    mopts = "".join(f'<option value="{m["id"]}">{m["nome"]} ({m["modelo"]})</option>' for m in modelos) \
        or '<option value="">-- cadastre um modelo em Modelos IA --</option>'
    skopts = "".join(
        f'<label class="chk"><input type="checkbox" name="skills" value="{s["name"]}"> {s["name"]} '
        f'<span class="muted">— {s.get("description","")}</span></label>'
        for s in skills_disp
    ) or '<span class="muted">nenhuma skill no catálogo</span>'
    copts = "".join(
        f'<label class="chk"><input type="checkbox" name="conectores" value="{c}"> {c}</label>'
        for c in ["erp", "crm", "rh"]
    )
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
          <div><label>Modelo de IA</label><select name="modelo_id">{mopts}</select></div>
        </div>
        <label>Skills do catálogo</label>
        <div class="chk-group">{skopts}</div>
        <label>Conectores MCP</label>
        <div class="chk-group">{copts}</div>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Montar agente</button>
          <a class="btn ghost" href="/portal/agentes">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Cadastrar agente", content, active="agentes", user=_user())


# ---------------------------------------------------------------------------
# CONECTORES (status)
# ---------------------------------------------------------------------------

@bp.route("/conectores")
@auth.login_required
def conectores():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    rows = db.listar_conectores()
    body = ""
    for k in rows:
        body += f"""<tr>
          <td><b>{k['nome']}</b></td>
          <td>{k['tipo']}</td>
          <td>{templates.badge(k['status'])}</td>
          <td class="muted">{k['ultimo_heartbeat'] or '-'}</td>
          <td>{clientes.get(k['cliente_id'], '?')}</td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Conector</th><th>Tipo</th><th>Status</th><th>Último heartbeat</th><th>Cliente</th></tr></thead>
      <tbody>{body or '<tr><td colspan=5 class="empty">Nenhum conector.</td></tr>'}</tbody></table>"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">Connector Pack (MCP): ERP, CRM e RH expostos por cliente. Health em tempo real.</div>
    {tabela}"""
    return templates.page("Conectores", content, active="conectores", user=_user())


# ---------------------------------------------------------------------------
# BILLING (faturas / licenca anual por empresa)
# ---------------------------------------------------------------------------

@bp.route("/billing")
@auth.login_required
def billing():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    rows = db.listar_faturas()
    # KPIs financeiros
    total_pendente = sum(r["valor"] for r in rows if r["status"] == "pendente")
    total_pago = sum(r["valor"] for r in rows if r["status"] == "paga")
    total_geral = sum(r["valor"] for r in rows)
    body = ""
    for f in rows:
        body += f"""<tr>
          <td><b>{f['descricao']}</b><div class="muted" style="font-size:12px">{f['tipo']}</div></td>
          <td>R$ {f['valor']:,.2f}</td>
          <td>{f['vencimento'] or '-'}</td>
          <td>{templates.badge(f['status'])}</td>
          <td>{clientes.get(f['cliente_id'], '?')}</td>
          <td class="row-actions">
            <a href="{url_for('portal.fatura_status', fid=f['id'], acao='paga' if f['status']!='paga' else 'pendente')}">
              {'marcar paga' if f['status']!='paga' else 'reabrir'}</a>
          </td></tr>"""
    tabela = f"""<table><thead><tr><th>Item</th><th>Valor</th><th>Vencimento</th><th>Status</th><th>Cliente</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=6 class="empty">Nenhuma fatura.</td></tr>'}</tbody></table>"""
    kpis = f"""
    <div class="grid grid-3" style="margin-bottom:16px">
      <div class="kpi"><div class="label">Total faturado</div><div class="value">R$ {total_geral:,.0f}</div><div class="sub">todas as faturas</div></div>
      <div class="kpi"><div class="label">Pendente</div><div class="value">R$ {total_pendente:,.0f}</div><div class="sub">a receber</div></div>
      <div class="kpi"><div class="label">Recebido</div><div class="value">R$ {total_pago:,.0f}</div><div class="sub">já pago</div></div>
    </div>"""
    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Modelo de cobrança: licença anual por empresa (não por token).</div>
      <a class="btn" href="/portal/billing/novo">+ Nova fatura</a>
    </div>{kpis}{tabela}"""
    return templates.page("Billing", content, active="billing", user=_user())


@bp.route("/billing/novo", methods=["GET", "POST"])
@auth.admin_required
def billing_novo():
    clientes = db.listar_clientes()
    if request.method == "POST":
        cid = int(request.form.get("cliente_id", 0))
        descricao = request.form.get("descricao", "").strip()
        try:
            valor = float(request.form.get("valor", 0) or 0)
        except ValueError:
            valor = 0.0
        if not (cid and descricao):
            flash("Cliente e descrição são obrigatórios.", "warn")
        else:
            db.criar_fatura(
                cid, request.form.get("tipo", "licenca_anual"), descricao, valor,
                request.form.get("moeda", "BRL"), request.form.get("vencimento", ""),
                request.form.get("status", "pendente"),
            )
            u = _user()
            db.registrar_auditoria(u["login"], u["papel"], "criar_fatura", alvo=descricao,
                                   cliente_id=cid, ip=request.remote_addr, detalhe=f"R$ {valor:,.2f}")
            flash("Fatura criada.", "ok")
            return redirect(url_for("portal.billing"))
    opts = "".join(f'<option value="{c["id"]}">{c["nome"]}</option>' for c in clientes)
    content = f"""
    <div class="card" style="max-width:640px">
      <h3 style="margin-top:0">Nova fatura</h3>
      <form method="post">
        <label>Cliente</label><select name="cliente_id"><option value="">-- selecione --</option>{opts}</select>
        <label>Tipo</label>
          <select name="tipo"><option value="licenca_anual">Licença anual</option><option value="implantacao">Taxa de implantação</option><option value="finetuning_custom">Fine-tuning custom</option></select>
        <label>Descrição</label><input name="descricao" placeholder="ex: Licença anual BlueShift 2026">
        <div class="form-row">
          <div><label>Valor (R$)</label><input name="valor" type="number" step="0.01" placeholder="120000.00"></div>
          <div><label>Vencimento</label><input name="vencimento" type="date"></div>
        </div>
        <label>Status</label>
          <select name="status"><option value="pendente">Pendente</option><option value="paga">Paga</option><option value="atrasada">Atrasada</option></select>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Salvar fatura</button>
          <a class="btn ghost" href="/portal/billing">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Nova fatura", content, active="billing", user=_user())


@bp.route("/billing/<int:fid>/<acao>")
@auth.admin_required
def fatura_status(fid: int, acao: str):
    if acao in ("paga", "pendente", "atrasada", "cancelada"):
        db.atualizar_fatura(fid, status=acao)
        u = _user()
        db.registrar_auditoria(u["login"], u["papel"], "alterar_fatura", alvo=acao,
                               cliente_id=None, ip=request.remote_addr, detalhe=f"fatura #{fid}")
        flash(f"Fatura {acao}.", "ok")
    return redirect(url_for("portal.billing"))


# ---------------------------------------------------------------------------
# SUPORTE (chamados)
# ---------------------------------------------------------------------------

@bp.route("/suporte")
@auth.login_required
def suporte():
    clientes = {c["id"]: c["nome"] for c in db.listar_clientes()}
    rows = db.listar_chamados()
    abertos = sum(1 for r in rows if r["status"] in ("aberto", "em_andamento"))
    resolvidos = sum(1 for r in rows if r["status"] in ("resolvido", "fechado"))
    body = ""
    for c in rows:
        body += f"""<tr>
          <td><b>{c['titulo']}</b><div class="muted" style="font-size:12px">{c['descricao'] or ''}</div></td>
          <td>{templates.badge(c['categoria'])}</td>
          <td>{templates.badge(c['prioridade'])}</td>
          <td>{templates.badge(c['status'])}</td>
          <td>{c['aberto_por'] or '-'}</td>
          <td>{clientes.get(c['cliente_id'], '?')}</td>
          <td class="row-actions">
            <a href="{url_for('portal.chamado_status', cid=c['id'], acao='resolvido' if c['status']!='resolvido' else 'aberto')}">
              {'resolver' if c['status']!='resolvido' else 'reabrir'}</a>
          </td></tr>"""
    tabela = f"""<table><thead><tr><th>Chamado</th><th>Categoria</th><th>Prioridade</th><th>Status</th><th>Aberto por</th><th>Cliente</th><th></th></tr></thead>
      <tbody>{body or '<tr><td colspan=7 class="empty">Nenhum chamado.</td></tr>'}</tbody></table>"""
    kpis = f"""
    <div class="grid grid-3" style="margin-bottom:16px">
      <div class="kpi"><div class="label">Chamados abertos</div><div class="value">{abertos}</div><div class="sub">em andamento</div></div>
      <div class="kpi"><div class="label">Resolvidos</div><div class="value">{resolvidos}</div><div class="sub">fechados</div></div>
      <div class="kpi"><div class="label">Total</div><div class="value">{len(rows)}</div><div class="sub">acumulado</div></div>
    </div>"""
    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Suporte técnico, treinamento e acompanhamento de incidentes.</div>
      <a class="btn" href="/portal/suporte/novo">+ Abrir chamado</a>
    </div>{kpis}{tabela}"""
    return templates.page("Suporte", content, active="suporte", user=_user())


@bp.route("/suporte/novo", methods=["GET", "POST"])
@auth.login_required
def suporte_novo():
    clientes = db.listar_clientes()
    user = _user()
    if request.method == "POST":
        cid = int(request.form.get("cliente_id", 0))
        titulo = request.form.get("titulo", "").strip()
        if not (cid and titulo):
            flash("Cliente e título são obrigatórios.", "warn")
        else:
            db.criar_chamado(
                cid, titulo, request.form.get("descricao", ""),
                request.form.get("categoria", "suporte"),
                request.form.get("prioridade", "media"),
                user.get("login", "") if user else "",
            )
            if user:
                db.registrar_auditoria(user["login"], user["papel"], "abrir_chamado",
                                       alvo=titulo, cliente_id=cid, ip=request.remote_addr)
            flash("Chamado aberto.", "ok")
            return redirect(url_for("portal.suporte"))
    opts = "".join(f'<option value="{c["id"]}">{c["nome"]}</option>' for c in clientes)
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Abrir chamado</h3>
      <form method="post">
        <label>Cliente</label><select name="cliente_id"><option value="">-- selecione --</option>{opts}</select>
        <label>Título</label><input name="titulo" placeholder="ex: Conector CRM retornando vazio">
        <label>Descrição</label><textarea name="descricao" rows="4" placeholder="Detalhe o problema ou pedido"></textarea>
        <div class="form-row">
          <div><label>Categoria</label>
            <select name="categoria"><option value="suporte">Suporte</option><option value="bug">Bug</option><option value="melhoria">Melhoria</option><option value="treinamento">Treinamento</option></select></div>
          <div><label>Prioridade</label>
            <select name="prioridade"><option value="baixa">Baixa</option><option value="media" selected>Média</option><option value="alta">Alta</option><option value="critica">Crítica</option></select></div>
        </div>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn" type="submit">Abrir chamado</button>
          <a class="btn ghost" href="/portal/suporte">Cancelar</a>
        </div>
      </form>
    </div>"""
    return templates.page("Abrir chamado", content, active="suporte", user=_user())


@bp.route("/suporte/<int:cid>/<acao>")
@auth.admin_required
def chamado_status(cid: int, acao: str):
    if acao in ("aberto", "em_andamento", "resolvido", "fechado"):
        db.atualizar_chamado(cid, status=acao)
        u = _user()
        db.registrar_auditoria(u["login"], u["papel"], "alterar_chamado", alvo=acao,
                               cliente_id=None, ip=request.remote_addr, detalhe=f"chamado #{cid}")
        flash(f"Chamado {acao}.", "ok")
    return redirect(url_for("portal.suporte"))


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
    if request.method == "POST":
        cid = int(request.form.get("cliente_id", 0))
        titulo = request.form.get("titulo", "").strip()
        texto = request.form.get("conteudo", "").strip()
        if cid and titulo and texto:
            db.criar_documento(cid, titulo, request.form.get("categoria", "manual"), texto)
            db.registrar_auditoria(u["login"], u["papel"], "salvar_documento", alvo=titulo,
                                   cliente_id=cid, ip=request.remote_addr)
            flash("Documento adicionado à base de conhecimento (RAG).", "ok")
            return redirect(url_for("portal.conhecimento"))
    docs = db.listar_documentos()
    body = ""
    for d in docs:
        body += f"""<tr>
          <td><b>{d['titulo']}</b></td>
          <td>{templates.badge(d['categoria'])}</td>
          <td>{d['conteudo'][:120]}{'…' if len(d['conteudo']) > 120 else ''}</td>
          <td class="muted">{d['criado_em']}</td>
        </tr>"""
    tabela = f"""<table><thead><tr><th>Título</th><th>Categoria</th><th>Conteúdo</th><th>Quando</th></tr></thead>
      <tbody>{body or '<tr><td colspan=4 class="empty">Nenhum documento.</td></tr>'}</tbody></table>"""
    content = f"""
    <div class="muted" style="margin-bottom:14px">
      Base de conhecimento do cliente (RAG): manual, política, base de conhecimento, contrato.
      Recuperada por similaridade no momento da inferência.
    </div>
    <div class="card" style="max-width:680px;margin-bottom:16px">
      <h3 style="margin-top:0">Adicionar documento (RAG)</h3>
      <form method="post">
        <label>Cliente</label>
          <select name="cliente_id">
            {''.join(f'<option value="{c["id"]}">{c["nome"]}</option>' for c in db.listar_clientes())}
          </select>
        <label>Título</label><input name="titulo" placeholder="Ex: Política de Privacidade">
        <label>Categoria</label>
          <select name="categoria"><option value="manual">Manual</option><option value="politica">Política</option><option value="base_conhecimento">Base de Conhecimento</option><option value="contrato">Contrato</option></select>
        <label>Conteúdo</label><textarea name="conteudo" rows="4" placeholder="Texto do documento"></textarea>
        <div style="margin-top:12px"><button class="btn" type="submit">Adicionar</button></div>
      </form>
    </div>
    {tabela}"""
    return templates.page("Base de Conhecimento", content, active="conhecimento", user=u)


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
                            api_key=request.form.get("api_key") or None)
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
        </tr>"""
    tabela = f"""<table><thead><tr><th>Nome</th><th>Tipo</th><th>Endpoint</th><th>Modelo</th><th>Status</th></tr></thead>
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
        <label>Nome</label><input name="nome" placeholder="ex: bonsai-4b">
        <label>Endpoint (base_url)</label><input name="base_url" placeholder="http://127.0.0.1:1234">
        <label>Modelo</label><input name="modelo" placeholder="ex: bonsai-4b">
        <label>Tipo</label>
          <select name="tipo"><option value="local">Local (LM Studio)</option><option value="hibrido">Híbrido externo</option></select>
        <label>API Key (opcional)</label><input name="api_key" placeholder="deixe em branco se não usar">
        <div style="margin-top:12px"><button class="btn" type="submit">Cadastrar</button></div>
      </form>
    </div>
    {tabela}"""
    return templates.page("Modelos de IA", content, active="modelos", user=_user())


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
        nome = request.form.get("nome", "").strip() or "Canal sem nome"
        agente_id = request.form.get("agente_id") or None
        if agente_id:
            agente_id = int(agente_id)
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
        body += f"""<tr><td>{c['nome']}</td><td>{c['tipo']}</td><td>{ag}</td>
          <td><code>{c['token']}</code></td>
          <td>{'ativo' if c['ativo'] else 'inativo'}</td>
          <td><code>{wh}</code></td></tr>"""
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
    <div class="card">
      <h3 style="margin-top:0">Canais</h3>
      <table><thead><tr><th>Nome</th><th>Tipo</th><th>Agente</th><th>Token</th><th>Status</th><th>Webhook saída</th></tr></thead>
      <tbody>{body or '<tr><td colspan="6" class="muted">nenhum canal</td></tr>'}</tbody></table>
    </div>
    <div class="card muted" style="font-size:13px">
      <b>Como usar (canal real):</b><br>
      <code>POST /portal/api/v1/agente</code> com header <code>Authorization: Bearer &lt;TOKEN&gt;</code>
      e body JSON <code>{{"pergunta": "..."}}</code>. O agente do canal responde via LLM + RAG + conectores.
      Se o canal tiver um <b>Webhook de saída</b>, a resposta também é POSTada nessa URL.
    </div>
    """
    return templates.page("Canais", content, active="canais", user=_user())


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
