"""Helpers de template do Portal BlueShift.

Centraliza o layout (header/menus) para manter DRY. Cada view passa apenas
o bloco de conteudo. Estilo dark/azul da marca BlueShift.
"""


import secrets


def _flashes() -> str:
    """Renderiza mensagens flash do Flask (get_flashed_messages)."""
    from flask import get_flashed_messages

    msgs = get_flashed_messages(with_categories=True)
    if not msgs:
        return ""
    out = ""
    for cat, msg in msgs:
        out += f'<div class="flash {cat}">{msg}</div>\n'
    return out


def page(title: str, content: str, active: str = "", user: dict | None = None,
         show_nav: bool = True) -> str:
    """Monta a pagina completa com header e menu lateral."""
    nav = _nav(active, user) if (show_nav and user) else ""
    user_box = ""
    if user:
        user_box = f"""
        <div class="userbox">
          <div class="avatar">{_inicial(user.get('nome', '?'))}</div>
          <div>
            <div class="uname">{user.get('nome','')}</div>
            <div class="urole">{_papel_pt(user.get('papel',''))}</div>
          </div>
          <a class="logout" href="/portal/logout">Sair</a>
        </div>"""
    flashes = _flashes()
    js = """<script>
function toggleSubmenu(el){var i=el.nextElementSibling,o=i.style.display==="block";i.style.display=o?"none":"block";el.querySelector(".arrow").textContent=o?"\u25b8":"\u25be";el.classList.toggle("open")}
function toggleSidebar(){var s=document.getElementById("sidebar"),c=s.classList.toggle("collapsed"),i=s.querySelector(".toggle-sidebar .nav-icon");i.textContent=c?"\u25b6":"\u25c0";var b=s.querySelector(".toggle-sidebar .nav-label");b.textContent=c?"":"Recolher"}
</script>"""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · BlueShift</title>
<style>{CSS}</style>
{js}
</head>
<body>
<div class="topbar">
  <div class="brand">BlueShift <span>IA Platform</span></div>
  <div class="topbar-sub">Portal do Cliente</div>
  {user_box}
</div>
<div class="layout">
  {nav}
  <main class="content">
    <h1 class="page-title">{title}</h1>
    {flashes}
    {content}
  </main>
</div>
</body>
</html>"""


def _nav(active: str, user: dict | None) -> str:
    # Icones por pagina
    ICONS = {
        "monitorar": "\U0001f4ca", "workspace": "\U0001f3e2",
        "clientes": "\U0001f465", "usuarios": "\U0001f464",
        "agentes": "\U0001f916", "skills": "\u2699\ufe0f",
        "modelos": "\U0001f9e0", "conectores": "\U0001f50c",
        "canais": "\U0001f4e1", "memoria": "\U0001f4be",
        "conhecimento": "\U0001f4da", "chat": "\U0001f4ac",
        "uso_tokens": "\U0001f4b0", "auditoria": "\U0001f4cb",
        "atualizacoes": "\U0001f504", "sso": "\U0001f511",
    }
    _nl = lambda key, label, href, cls_extra="": (
        f'<a class="navlink{cls_extra}" href="{href}" title="{label}">'
        f'<span class="nav-icon">{ICONS.get(key, chr(0x2753))}</span>'
        f'<span class="nav-label">{label}</span></a>'
    )

    # Itens principais
    itens = [
        ("monitorar", "Monitorar", "/portal/monitorar"),
        ("workspace", "Workspace", "/portal/workspace"),
    ]
    cadastro_itens = [
        ("clientes", "Clientes", "/portal/clientes"),
        ("usuarios", "Usuários", "/portal/usuarios"),
        ("agentes", "Agentes", "/portal/agentes"),
        ("skills", "Skills", "/portal/skills"),
        ("modelos", "Modelos IA", "/portal/modelos"),
        ("conectores", "Conectores", "/portal/conectores"),
        ("canais", "Canais", "/portal/canais"),
    ]
    cadastro_keys = {k for k, _, _ in cadastro_itens}
    cadastro_aberto = active in cadastro_keys
    outros = [
        ("memoria", "Memória", "/portal/memoria"),
        ("conhecimento", "Conhecimento", "/portal/conhecimento"),
        ("chat", "Chat", "/portal/chat"),
        ("uso_tokens", "Uso de Tokens", "/portal/uso-tokens"),
        ("auditoria", "Auditoria", "/portal/auditoria"),
        ("atualizacoes", "Atualizações", "/portal/atualizacoes"),
        ("sso", "SSO (OIDC)", "/portal/sso/config"),
    ]

    seta_aberto = "\u25be"
    seta_fechado = "\u25b8"
    links = ""
    for key, label, href in itens:
        links += _nl(key, label, href, " active" if key == active else "")

    # Submenu Cadastros
    seta = seta_aberto if cadastro_aberto else seta_fechado
    display = "block" if cadastro_aberto else "none"
    cadastro_html = "".join(
        _nl(k, l, h, " active" if k == active else "")
        for k, l, h in cadastro_itens
    )
    links += f"""
    <div class="submenu">
      <a class="navlink sub-toggle{" open" if cadastro_aberto else ""}" onclick="toggleSubmenu(this)" title="Cadastros">
        <span class="nav-icon">{ICONS.get("clientes", "")}</span>
        <span class="nav-label"><span class="arrow">{seta}</span> Cadastros</span>
      </a>
      <div class="sub-items" style="display:{display}">
        {cadastro_html}
      </div>
    </div>"""

    for key, label, href in outros:
        links += _nl(key, label, href, " active" if key == active else "")

    links += """
    <div class="sidebar-footer">
      <a class="navlink toggle-sidebar" onclick="toggleSidebar()" title="Recolher menu"><span class="nav-icon">\u25c0</span><span class="nav-label">Recolher</span></a>
    </div>"""

    return '<nav class="sidebar" id="sidebar">' + links + "</nav>"


def _papel_pt(p: str) -> str:
    return {
        "admin": "Administrador",
        "gestor": "Gestor",
        "usuario": "Usuário",
        "sistema": "Sistema (API)",
    }.get(p, p)


def _inicial(nome: str) -> str:
    return (nome or "?").strip()[0].upper()


def badge(status: str) -> str:
    s = (status or "").lower()
    cor = {
        "ativo": "ok", "online": "ok", "saudavel": "ok", "ok": "ok",
        "suspenso": "warn", "pausado": "warn", "degradado": "warn",
        "expirado": "offline", "offline": "bad", "parado": "bad", "indisponivel": "bad",
        "sobrecarregado": "warn",
    }.get(s, "neutral")
    return f'<span class="badge {cor}">{status}</span>'


# CSS compartilhado (marca BlueShift: azul/indigo sobre fundo escuro)
CSS = """
:root{--bg:#0b1020;--panel:#141b2e;--panel2:#1b2438;--line:#26304a;
--txt:#e7ecf5;--muted:#93a0bd;--blue:#3b82f6;--blue2:#2563eb;
--ok:#22c55e;--warn:#f59e0b;--bad:#ef4444;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--txt);font-size:14px;line-height:1.5}
.topbar{height:56px;display:flex;align-items:center;gap:16px;padding:0 20px;
background:linear-gradient(90deg,#0e1830,#101a33);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}
.brand{font-weight:800;letter-spacing:.3px;font-size:18px;color:#fff}
.brand span{color:var(--blue);font-weight:600}
.topbar-sub{color:var(--muted);font-size:13px;border-left:1px solid var(--line);padding-left:16px}
.userbox{margin-left:auto;display:flex;align-items:center;gap:10px}
.avatar{width:34px;height:34px;border-radius:50%;background:var(--blue2);display:flex;align-items:center;
justify-content:center;font-weight:700;color:#fff}
.uname{font-weight:600}
.urole{color:var(--muted);font-size:12px}
.logout{color:var(--muted);text-decoration:none;font-size:12px;margin-left:6px}
.logout:hover{color:var(--txt)}
.layout{display:flex;min-height:calc(100vh - 56px)}
.sidebar{width:200px;background:var(--panel);border-right:1px solid var(--line);padding:14px 10px;display:flex;flex-direction:column;gap:4px;transition:width .2s}
.sidebar.collapsed{width:52px;overflow:hidden}
.sidebar.collapsed .navlink{justify-content:center;padding:10px 0}
.sidebar.collapsed .nav-label{display:none}
.sidebar.collapsed .sub-items{display:none!important}
.sidebar.collapsed .sidebar-footer .navlink{justify-content:center}
.sidebar-footer{margin-top:auto;padding-top:10px;border-top:1px solid var(--line)}
.navlink{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;color:var(--muted);text-decoration:none;font-weight:500;font-size:14px;white-space:nowrap;overflow:hidden}
.navlink:hover{background:var(--panel2);color:var(--txt)}
.navlink.active{background:var(--blue2);color:#fff}
.navlink .nav-icon{flex-shrink:0;width:22px;text-align:center;font-size:16px;line-height:1}
.navlink .nav-label{overflow:hidden;text-overflow:ellipsis}
.navlink.sub-toggle{cursor:pointer;user-select:none}
.navlink.sub-toggle.open{color:var(--txt)}
.navlink .arrow{display:inline-block;width:14px}
.content{flex:1;padding:22px 26px}
.page-title{margin:0 0 18px;font-size:22px;font-weight:700}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:16px}
.grid{display:grid;gap:14px}
.grid-2{grid-template-columns:repeat(2,1fr)}
.grid-3{grid-template-columns:repeat(3,1fr)}
.grid-4{grid-template-columns:repeat(4,1fr)}
@media(max-width:900px){.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}.sidebar{display:none}}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpi .label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.5px}
.kpi .value{font-size:26px;font-weight:800;margin-top:6px}
.kpi .sub{color:var(--muted);font-size:12px;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:11px 14px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.4px;background:var(--panel2)}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:12px;font-weight:700}
.badge.ok{background:rgba(34,197,94,.15);color:var(--ok)}
.badge.warn{background:rgba(245,158,11,.15);color:var(--warn)}
.badge.bad{background:rgba(239,68,68,.15);color:var(--bad)}
.badge.neutral{background:#222c44;color:var(--muted)}
.btn{display:inline-block;padding:9px 14px;border-radius:8px;border:1px solid var(--blue2);
background:var(--blue2);color:#fff;font-weight:600;text-decoration:none;cursor:pointer;font-size:13px}
.btn:hover{background:var(--blue)}
.btn.ghost{background:transparent;color:var(--blue);border-color:var(--line)}
.btn.danger{background:transparent;border-color:#5a2330;color:var(--bad)}
.btn-copy{background:none;border:none;cursor:pointer;font-size:14px;padding:2px 4px;vertical-align:middle;border-radius:4px}
.btn-copy:hover{background:var(--panel2)}
.btn-sso{display:inline-block;padding:9px 14px;border-radius:8px;border:1px solid #3b82f6;
background:linear-gradient(90deg,#1e3a8a,#2563eb);color:#fff;font-weight:600;text-decoration:none;
cursor:pointer;font-size:13px;width:100%;text-align:center}
.btn-sso:hover{background:linear-gradient(90deg,#2563eb,#3b82f6)}
input,select,textarea{width:100%;padding:9px 11px;border-radius:8px;border:1px solid var(--line);
background:#0e1726;color:var(--txt);font-size:13px;margin-top:4px}
label{display:block;margin-top:12px;color:var(--muted);font-size:13px;font-weight:600}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:700px){.form-row{grid-template-columns:1fr}}
.chk-group{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:4px 0 6px}
.chk{display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap}
.chk input{flex-shrink:0;margin:0}
.chk .muted{white-space:normal}
.flash{padding:10px 14px;border-radius:8px;margin-bottom:14px;font-weight:600}
.flash.ok{background:rgba(34,197,94,.12);color:var(--ok)}
.flash.warn{background:rgba(245,158,11,.12);color:var(--warn)}
.flash.bad{background:rgba(239,68,68,.12);color:var(--bad)}
.muted{color:var(--muted)}
.row-actions a{margin-right:8px;color:var(--blue);text-decoration:none;font-weight:600;font-size:13px}
.empty{padding:30px;text-align:center;color:var(--muted)}
.bar{height:8px;border-radius:999px;background:#222c44;overflow:hidden}
.bar > i{display:block;height:100%;background:linear-gradient(90deg,var(--blue),#22d3ee)}
.health-card .value{font-size:30px}
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:100;justify-content:center;align-items:center}
.modal-overlay.show{display:flex}
.modal-box{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:24px;max-width:640px;width:90%;max-height:80vh;overflow-y:auto}
.modal-box h3{margin:0 0 12px;color:var(--txt)}
.modal-box textarea{width:100%;min-height:120px;margin:8px 0;font-family:monospace;font-size:12px}
.modal-actions{display:flex;gap:8px;margin-top:12px}
.modal-actions .btn-spin{position:relative}
.modal-actions .btn-spin.loading{color:transparent}
.modal-actions .btn-spin.loading::after{content:"";position:absolute;inset:0;margin:auto;width:16px;height:16px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin .6s linear}
@keyframes spin{to{transform:rotate(360deg)}}
.btn-ia{background:linear-gradient(135deg,#7c3aed,#2563eb);color:#fff;border:none;cursor:pointer;padding:8px 14px;border-radius:8px;font-size:13px;font-weight:600}
.btn-ia:hover{filter:brightness(1.2)}

"""


def form_sso_config(cfg: dict) -> str:
    """Formulario de configuracao do provedor SSO (OIDC)."""
    cfg = cfg or {}
    ativo = "checked" if cfg.get("ativo") else ""
    dev = "checked" if cfg.get("dev_mode") else ""
    auto = "checked" if cfg.get("auto_criar") else ""
    return f"""
    <div class="card" style="max-width:620px">
      <h3 style="margin-top:0">Provedor de Identidade (OIDC)</h3>
      <p class="muted">Configure o login federado. Em <b>modo dev</b> usamos um
      IdP mock interno para testar o fluxo sem um provedor real. O <b>login local
      continua ativo</b> normalmente.</p>
      <form method="post">
        <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;margin:0;font-weight:400;font-size:13px"><input type="checkbox" name="ativo" {ativo} style="width:auto;margin:0;vertical-align:middle"> SSO ativo</label>
        <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;margin:0;font-weight:400;font-size:13px"><input type="checkbox" name="dev_mode" {dev} style="width:auto;margin:0;vertical-align:middle"> Modo dev (IdP mock interno - para teste)</label>
        <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;margin:0;font-weight:400;font-size:13px"><input type="checkbox" name="auto_criar" {auto} style="width:auto;margin:0;vertical-align:middle"> Criar usuario automaticamente se nao cadastrado</label>
        <label>Issuer (URL base do IdP)</label>
        <input name="issuer" placeholder="https://login.microsoftonline.com/.../v2.0" value="{cfg.get('issuer','')}">
        <label>Client ID</label>
        <input name="client_id" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" value="{cfg.get('client_id','')}">
        <label>Client Secret</label>
        <input name="client_secret" type="password" placeholder="••••••" value="{cfg.get('client_secret','')}">
        <label>Redirect URI (deve apontar para /portal/sso/callback)</label>
        <input name="redirect_uri" placeholder="http://host:8080/portal/sso/callback" value="{cfg.get('redirect_uri','')}">
        <label>Domínio de admin (emails com este dominio viram admin)</label>
        <input name="dominio_admin" placeholder="@suaempresa.com.br" value="{cfg.get('dominio_admin','')}">
        <div style="margin-top:18px">
          <button class="btn" type="submit">Salvar</button>
          <a class="btn ghost" href="/portal/sso/login">Testar login SSO</a>
        </div>
      </form>
    </div>"""
