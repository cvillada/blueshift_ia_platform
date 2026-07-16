"""Helpers de template do Portal BlueShift.

Centraliza o layout (header/menus) para manter DRY. Cada view passa apenas
o bloco de conteudo. Estilo dark/azul da marca BlueShift.
"""


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
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · BlueShift</title>
<style>{CSS}</style>
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
    {content}
  </main>
</div>
</body>
</html>"""


def _nav(active: str, user: dict | None) -> str:
    itens = [
        ("monitorar", "Monitorar", "/portal/monitorar"),
        ("clientes", "Clientes", "/portal/clientes"),
        ("usuarios", "Usuários", "/portal/usuarios"),
        ("agentes", "Agentes", "/portal/agentes"),
        ("conectores", "Conectores", "/portal/conectores"),
    ]
    links = ""
    for key, label, href in itens:
        cls = " active" if key == active else ""
        links += f'<a class="navlink{cls}" href="{href}">{label}</a>'
    return f'<nav class="sidebar">{links}</nav>'


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
        "expirado": "bad", "offline": "bad", "parado": "bad", "indisponivel": "bad",
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
.sidebar{width:200px;background:var(--panel);border-right:1px solid var(--line);padding:14px 10px;display:flex;flex-direction:column;gap:4px}
.navlink{display:block;padding:10px 12px;border-radius:8px;color:var(--muted);text-decoration:none;font-weight:600}
.navlink:hover{background:var(--panel2);color:var(--txt)}
.navlink.active{background:var(--blue2);color:#fff}
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
input,select,textarea{width:100%;padding:9px 11px;border-radius:8px;border:1px solid var(--line);
background:#0e1726;color:var(--txt);font-size:13px;margin-top:4px}
label{display:block;margin-top:12px;color:var(--muted);font-size:13px;font-weight:600}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:700px){.form-row{grid-template-columns:1fr}}
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
"""
