"""Views do Portal BlueShift (Camada 4).

Telas:
  - login/logout        -> autenticacao do admin
  - monitorar           -> dashboard de saude (container/modelo/conectores/agentes)
  - clientes            -> gerenciar + cadastrar clientes
  - usuarios            -> gerenciar + cadastrar usuarios (papeis)
  - agentes             -> Agent Factory (gerenciar + cadastrar)
  - conectores          -> status dos conectores MCP
"""
from __future__ import annotations

from flask import (
    Blueprint, request, redirect, url_for, session, flash, current_app,
)
from . import db, auth, templates

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
    </div>"""
    return templates.page("Login", content, active="", show_nav=False)


@bp.route("/logout")
def logout():
    auth.fazer_logout()
    return redirect(url_for("portal.login"))


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
@auth.login_required
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
@auth.login_required
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
@auth.login_required
def cliente_alternar(cid: int, acao: str):
    if acao in ("ativo", "suspenso", "expirado"):
        db.atualizar_cliente(cid, status=acao)
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
@auth.login_required
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
        </tr>"""
    tabela = f"""<table><thead><tr><th>Agente</th><th>Área</th><th>Modelo</th><th>Skills</th><th>Conectores</th><th>Status</th><th>Cliente</th></tr></thead>
      <tbody>{body or '<tr><td colspan=7 class="empty">Nenhum agente.</td></tr>'}</tbody></table>"""
    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="muted">Agent Factory: monte agentes a partir do catálogo de skills + conectores MCP.</div>
      <a class="btn" href="/portal/agentes/novo">+ Cadastrar agente</a>
    </div>{tabela}"""
    return templates.page("Agentes", content, active="agentes", user=_user())


@bp.route("/agentes/novo", methods=["GET", "POST"])
@auth.login_required
def agente_novo():
    clientes = db.listar_clientes()
    if request.method == "POST":
        cid = int(request.form.get("cliente_id", 0))
        nome = request.form.get("nome", "").strip()
        if not (cid and nome):
            flash("Cliente e nome são obrigatórios.", "warn")
        else:
            db.criar_agente(
                cid, nome,
                request.form.get("area", ""),
                request.form.get("modelo", "finetuned-v1"),
                request.form.get("skills", ""),
                request.form.get("conectores", ""),
            )
            flash(f"Agente '{nome}' criado.", "ok")
            return redirect(url_for("portal.agentes"))
    opts = "".join(f'<option value="{c["id"]}">{c["nome"]}</option>' for c in clientes)
    content = f"""
    <div class="card" style="max-width:680px">
      <h3 style="margin-top:0">Cadastrar agente (Agent Factory)</h3>
      <form method="post">
        <div class="form-row">
          <div><label>Cliente</label><select name="cliente_id"><option value="">-- selecione --</option>{opts}</select></div>
          <div><label>Nome do agente</label><input name="nome" placeholder="ex: Agente Vendas"></div>
        </div>
        <div class="form-row">
          <div><label>Área</label>
            <select name="area"><option value="">--</option><option>vendas</option><option>suporte</option><option>financeiro</option><option>rh</option><option>operacoes</option></select></div>
          <div><label>Modelo</label>
            <select name="modelo"><option>finetuned-v1</option><option>gpt-4o</option><option>claude-3.5</option><option>gemini-1.5</option></select></div>
        </div>
        <label>Skills (separadas por vírgula)</label>
        <input name="skills" placeholder="vendas, suporte">
        <label>Conectores MCP (separados por vírgula)</label>
        <input name="conectores" placeholder="erp, crm">
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
