"""Helpers de template do Portal BlueShift.

Centraliza o layout (header/menus) para manter DRY. Cada view passa apenas
o bloco de conteudo. Estilo dark/azul da marca BlueShift.
"""


import html
import secrets
from flask import session


def csrf_token() -> str:
    """Retorna ou cria o token CSRF na sessao."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def csrf_field() -> str:
    """Campo hidden para formularios."""
    return f'<input type="hidden" name="_csrf_token" value="{csrf_token()}">'


def h(texto: str | None) -> str:
    """Escapa HTML para prevenir XSS."""
    return html.escape(texto or "")


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
function toggleSubmenu(el){var i=el.nextElementSibling,o=i.style.display==="block";i.style.display=o?"none":"block";el.querySelector(".arrow").textContent=o?"▸":"▾";el.classList.toggle("open")}
function toggleSidebar(){var s=document.getElementById("sidebar"),b=document.getElementById("ham-btn");s.classList.toggle("collapsed");b.textContent=s.classList.contains("collapsed")?"☰":"⋮"}
window.addEventListener("load",function(){var b=document.getElementById("ham-btn");if(b&&!document.getElementById("sidebar").classList.contains("collapsed"))b.textContent="⋮"})
var AJUDA_MODELOS=[];
function abrirAjuda(){var p=document.getElementById("ajuda-popup");if(!p)return;p.style.display="flex";if(!AJUDA_MODELOS.length)carregarModelosAjuda()}
function fecharAjuda(){var p=document.getElementById("ajuda-popup");if(p)p.style.display="none"}
function carregarModelosAjuda(){fetch("/portal/api/ajuda/modelos").then(function(r){return r.json()}).then(function(d){AJUDA_MODELOS=d.modelos||[];var s=document.getElementById("ajuda-modelo");if(!s)return;if(!AJUDA_MODELOS.length){s.innerHTML='<option value="">-- nenhum modelo cadastrado --</option>'}else{s.innerHTML=AJUDA_MODELOS.map(function(m){return '<option value="'+m.id+'">'+m.nome+' ('+m.modelo+')</option>'}).join('')}})}
function escAjuda(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function enviarAjuda(){var p=document.getElementById("ajuda-pergunta").value.trim();var box=document.getElementById("ajuda-resposta");if(!p){box.innerHTML='<div class="badge warn">Digite uma pergunta.</div>';return}var mid=document.getElementById("ajuda-modelo").value;box.innerHTML='<div class="badge neutral">⏳ Consultando a documentação...</div>';fetch("/portal/api/ajuda",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({pergunta:p,modelo_id:mid?parseInt(mid,10):null})}).then(function(r){return r.json()}).then(function(d){if(d.ok){box.innerHTML='<div class="muted" style="font-size:11px;margin-bottom:6px">Resposta ('+escAjuda(d.modelo)+')</div><div class="ajuda-resposta">'+escAjuda(d.resposta)+'</div>'}else if(d.motivo==="sem_modelo"){var h='<div class="badge warn">⚠️ Nenhum modelo de IA cadastrado.</div><p style="font-size:12px;margin:8px 0">'+escAjuda(d.dica||"")+'</p>';if(d.orientacao){h+='<div style="background:var(--code-bg);padding:10px;border-radius:8px;font-size:12px;max-height:200px;overflow-y:auto;white-space:pre-wrap">'+escAjuda(d.orientacao)+'</div>'}box.innerHTML=h}else{box.innerHTML='<div class="badge bad">'+escAjuda(d.erro||"Erro ao consultar.")+'</div>'}}).catch(function(e){box.innerHTML='<div class="badge bad">Erro: '+escAjuda(e.message)+'</div>'})}
(function(){function init(){var pop=document.getElementById("ajuda-popup"),hdr=document.getElementById("ajuda-header");if(!pop||!hdr)return;var drag=false,ox=0,oy=0,px=0,py=0;hdr.addEventListener("mousedown",function(e){if(e.target.tagName==="BUTTON")return;drag=true;ox=e.clientX;oy=e.clientY;px=pop.offsetLeft;py=pop.offsetTop;e.preventDefault()});document.addEventListener("mousemove",function(e){if(!drag)return;pop.style.left=(px+e.clientX-ox)+"px";pop.style.top=(py+e.clientY-oy)+"px";pop.style.right="auto"});document.addEventListener("mouseup",function(){drag=false})}if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",init)}else{init()}})();
function temaIcone(t){return t==="light"?"☀️":(t==="dark"?"🌙":"💻")}
function aplicarTema(t){if(t==="system"){t=window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.setAttribute("data-theme",t)}
function setTema(t){try{localStorage.setItem("bs_theme",t)}catch(e){}aplicarTema(t);var i=document.getElementById("theme-icon");if(i)i.textContent=temaIcone(t);var m=document.getElementById("theme-menu");if(m)m.classList.remove("show")}
function toggleTemaMenu(e){e.stopPropagation();var m=document.getElementById("theme-menu");if(m)m.classList.toggle("show")}
document.addEventListener("click",function(e){var m=document.getElementById("theme-menu");if(m&&!e.target.closest(".theme-wrap"))m.classList.remove("show")})
window.addEventListener("load",function(){var t="dark";try{t=localStorage.getItem("bs_theme")||"dark"}catch(e){}aplicarTema(t);var i=document.getElementById("theme-icon");if(i)i.textContent=temaIcone(t)})
if(window.matchMedia){window.matchMedia("(prefers-color-scheme: light)").addEventListener("change",function(){var t="dark";try{t=localStorage.getItem("bs_theme")||"dark"}catch(e){}if(t==="system")aplicarTema("system")})}
function escFluxo(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function abrirFluxo(d){
  var skills=(d.skills&&d.skills.length)?d.skills:[];
  var conns=(d.conectores&&d.conectores.length)?d.conectores:[];
  var n=Math.max(skills.length,conns.length,1);
  var H=150+n*92;
  var C={ent:"#3b82f6",llm:"#f59e0b",skill:"#22c55e",res:"#e879f9",conn:"#38bdf8",mut:"#aab6d4"};
  var wEnt=100,wConn=140,wLlm=140,wSki=140,wRes=110,wEnv=80,gap=36;
  var xEnt=16;
  var xConn=xEnt+wEnt+gap;
  var xLlm=conns.length?xConn+wConn+gap:xEnt+wEnt+gap;
  var xSki=xLlm+wLlm+gap;
  var xRes=skills.length?xSki+wSki+gap:xLlm+wLlm+gap;
  var xEnv=xRes+wRes+gap;
  var W=xEnv+wEnv+16;
  var cy=H/2;
  var nodes=[],edges=[],map={},seq=0;
  function addNode(x,y,w,h,cor,icone,titulo,sub){
    var id="n"+(seq++); var o={id:id,x:x,y:y,w:w,h:h,cor:cor,icone:icone,titulo:titulo,sub:sub||"",el:null};
    nodes.push(o); map[id]=o; return o;
  }
  function addEdge(from,to){edges.push({from:from.id,to:to.id,el:null});}
  var nEnt=addNode(xEnt,cy-38,wEnt,76,C.ent,"💬","Entrada","Chat / API");
  var nCon=[],nSki=[];
  if(conns.length){var yc0=cy-((conns.length*58-16)/2);for(var i=0;i<conns.length;i++){nCon.push(addNode(xConn,yc0+i*58,wConn,50,C.conn,"🔌",conns[i].nome,conns[i].tipo));}}
  var nLlm=addNode(xLlm,cy-40,wLlm,80,C.llm,"🧠","LLM",d.modelo+(d.fallback?" · fb: "+d.fallback:""));
  if(skills.length){var ys0=cy-((skills.length*56-14)/2);for(var i=0;i<skills.length;i++){nSki.push(addNode(xSki,ys0+i*56,wSki,42,C.skill,"⚙️",skills[i],""));}}
  var nRes=addNode(xRes,cy-38,wRes,76,C.res,"📤","Resposta","final");
  var nEnv=addNode(xEnv,cy-38,wEnv,76,C.ent,"📡","Envio","Chat/API");
  if(nCon.length){for(var i=0;i<nCon.length;i++){addEdge(nEnt,nCon[i]);addEdge(nCon[i],nLlm);}}
  else{addEdge(nEnt,nLlm);}
  if(nSki.length){for(var i=0;i<nSki.length;i++){addEdge(nLlm,nSki[i]);addEdge(nSki[i],nRes);}}
  else{addEdge(nLlm,nRes);}
  addEdge(nRes,nEnv);
  var s='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;display:block;min-width:'+(W*0.6)+'px">';
  s+='<defs><marker id="mk" markerWidth="4.5" markerHeight="4.5" refX="4" refY="2.25" orient="auto"><path d="M0,0 L4.5,2.25 L0,4.5 Z" fill="'+C.mut+'"/></marker></defs>';
  for(var i=0;i<nodes.length;i++){
    var o=nodes[i];
    s+='<rect id="r'+o.id+'" data-node="'+o.id+'" x="'+o.x+'" y="'+o.y+'" width="'+o.w+'" height="'+o.h+'" rx="10" fill="var(--panel2)" stroke="'+o.cor+'" stroke-width="1.5" style="cursor:move"/>';
    if(o.sub){
      s+='<text id="t1'+o.id+'" x="'+(o.x+o.w/2)+'" y="'+(o.y+22)+'" text-anchor="middle" font-size="13" fill="'+o.cor+'" style="pointer-events:none">'+o.icone+' '+escFluxo(o.titulo)+'</text>';
      s+='<text id="t2'+o.id+'" x="'+(o.x+o.w/2)+'" y="'+(o.y+38)+'" text-anchor="middle" font-size="10" fill="'+C.mut+'" style="pointer-events:none">'+escFluxo(o.sub)+'</text>';
    }else{
      s+='<text id="t1'+o.id+'" x="'+(o.x+o.w/2)+'" y="'+(o.y+o.h/2+5)+'" text-anchor="middle" font-size="13" fill="'+o.cor+'" style="pointer-events:none">'+o.icone+' '+escFluxo(o.titulo)+'</text>';
    }
  }
  for(var i=0;i<edges.length;i++){
    var e=edges[i];var a=map[e.from],b=map[e.to];
    s+='<path id="e'+i+'" d="M'+(a.x+a.w)+','+(a.y+a.h/2)+' L'+(b.x)+','+(b.y+b.h/2)+'" fill="none" stroke="'+C.mut+'" stroke-width="2" marker-end="url(#mk)"/>';
  }
  s+='</svg>';
  var cont=document.getElementById("fluxo-conteudo");
  cont.innerHTML=s;
  document.getElementById("fluxo-titulo").textContent="Fluxo do agente: "+d.nome;
  document.getElementById("fluxo-popup").style.display="flex";
  var svg=cont.querySelector("svg");
  for(var i=0;i<nodes.length;i++){var o=nodes[i];o.el={rect:document.getElementById("r"+o.id),t1:document.getElementById("t1"+o.id),t2:document.getElementById("t2"+o.id)};}
  for(var i=0;i<edges.length;i++){edges[i].el=document.getElementById("e"+i);}
  var escala=Math.max(svg.getBoundingClientRect().width,1)/W;
  function edgeD(e){var a=map[e.from],b=map[e.to];return "M"+(a.x+a.w)+","+(a.y+a.h/2)+" L"+(b.x)+","+(b.y+b.h/2);}
  if(!window.__fluxoDrag){
    window.__fluxoDrag={node:null,dx:0,dy:0,escala:1,edges:[],edgeD:null};
    document.addEventListener("mousemove",function(ev){
      var D=window.__fluxoDrag;if(!D.node)return;
      var o=D.node;
      o.x=(ev.clientX-D.dx)/D.escala;o.y=(ev.clientY-D.dy)/D.escala;
      o.el.rect.setAttribute("x",o.x);o.el.rect.setAttribute("y",o.y);
      o.el.t1.setAttribute("x",o.x+o.w/2);o.el.t1.setAttribute("y",o.sub?(o.y+22):(o.y+o.h/2+5));
      if(o.el.t2){o.el.t2.setAttribute("x",o.x+o.w/2);o.el.t2.setAttribute("y",o.y+38);}
      var es=D.edges;
      for(var i=0;i<es.length;i++){var e=es[i];if(e.from===o.id||e.to===o.id){e.el.setAttribute("d",D.edgeD(e));}}
    });
    document.addEventListener("mouseup",function(){if(window.__fluxoDrag)window.__fluxoDrag.node=null});
  }
  window.__fluxoDrag.escala=escala;
  svg.addEventListener("mousedown",function(ev){
    var r=ev.target;if(r.tagName!=="rect")return;
    var o=map[r.getAttribute("data-node")];if(!o)return;
    var D=window.__fluxoDrag;D.node=o;D.escala=escala;D.edges=edges;D.edgeD=edgeD;
    D.dx=ev.clientX-o.x*escala;D.dy=ev.clientY-o.y*escala;
    ev.preventDefault();
  });
}
function fecharFluxo(){var p=document.getElementById("fluxo-popup");if(p)p.style.display="none"}
</script>"""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · BlueShift</title>
<script>try{{var t=localStorage.getItem("bs_theme")||"dark";if(t==="system")t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
<style>{CSS}</style>
{js}
</head>
<body>
<div class="topbar">
  <div class="brand">BlueShift <span>IA Platform</span></div>
  <div class="topbar-sub">Portal do Cliente</div>
  <div class="theme-wrap">
    <button class="theme-btn" id="theme-btn" onclick="toggleTemaMenu(event)" title="Tema (claro/escuro/sistema)"><span id="theme-icon">🌙</span></button>
    <div class="theme-menu" id="theme-menu">
      <a onclick="setTema('light')">☀️ Claro</a>
      <a onclick="setTema('dark')">🌙 Escuro</a>
      <a onclick="setTema('system')">💻 Sistema</a>
    </div>
  </div>
  <button class="theme-btn" onclick="abrirAjuda()" title="Ajuda (documentação)">❓</button>
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
<div class="ajuda-popup" id="ajuda-popup" style="display:none">
  <div class="ajuda-header" id="ajuda-header">
    <span>💡 Ajuda BlueShift</span>
    <button class="ajuda-fechar" onclick="fecharAjuda()" title="Fechar">✕</button>
  </div>
  <div class="ajuda-body">
    <label style="margin-top:0">Modelo de IA</label>
    <select id="ajuda-modelo"><option value="">-- carregando --</option></select>
    <label>Pergunta</label>
    <textarea id="ajuda-pergunta" rows="3" placeholder="Ex: como preencho o campo Host de um conector SQL?"></textarea>
    <div style="margin-top:10px"><button class="btn" onclick="enviarAjuda()">Perguntar</button></div>
    <div id="ajuda-resposta" style="margin-top:12px"></div>
    <div class="muted" style="font-size:10px;margin-top:10px">Respostas baseadas no DOCUMENTACAO_PB.md — edite o arquivo para atualizar a ajuda.</div>
  </div>
</div>
<div class="fluxo-popup" id="fluxo-popup" style="display:none" onclick="if(event.target===this)fecharFluxo()">
  <div class="fluxo-card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <h3 style="margin:0" id="fluxo-titulo">Fluxo do agente</h3>
      <button class="btn ghost" onclick="fecharFluxo()" title="Fechar">✕</button>
    </div>
    <div id="fluxo-conteudo" class="fluxo-canvas"></div>
    <div class="muted" style="font-size:10px;margin-top:14px">Fluxo de execução do agente: a pergunta entra (Chat/API), o LLM processa com o modelo e as skills, e a resposta é enviada de volta (Chat/API). Dados dinâmicos deste agente.</div>
  </div>
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
        "alertas_config": "\U0001f514",
        "canais": "\U0001f4e1", "gateway": "\U0001f500", "memoria": "\U0001f4be",
        "conhecimento": "\U0001f4da", "chat": "\U0001f4ac",
        "uso_tokens": "\U0001f4b0", "auditoria": "\U0001f4cb",
        'observabilidade': '\U0001f4ca', 'teste_ab': '\U0001f91d', 'atualizacoes': '\U0001f504', 'sso': '\U0001f511',
        'fine_tuning': '\U0001f9e9',
        "lgpd": "\U0001f6e1\ufe0f",
        # Icones dos grupos (submenus)
        "grupo_cadastros": "\U0001f465", "grupo_inteligencia": "\U0001f4a1",
        "grupo_operacao": "\U0001f4c8", "grupo_config": "\U0001f527",
    }
    _nl = lambda key, label, href, cls_extra="": (
        f'<a class="navlink{cls_extra}" href="{href}" title="{label}">'
        f'<span class="nav-icon">{ICONS.get(key, chr(0x2753))}</span>'
        f'<span class="nav-label">{label}</span></a>'
    )

    # Itens principais (sempre visiveis)
    itens = [
        ("monitorar", "Monitorar", "/portal/monitorar"),
        ("workspace", "Workspace", "/portal/workspace"),
    ]
    ICONS["ajuda"] = "\U0001f4a1"

    # Submenus: (rotulo, icone_grupo, [(key, label, href), ...])
    submenus = [
        ("Cadastros", "grupo_cadastros", [
            # Ordem = sequencia de configuracao: base (clientes/usuarios) ->
            # modelos/skills -> agentes (monta) -> conectores/canais (entrega)
            ("clientes", "Clientes", "/portal/clientes"),
            ("usuarios", "Usuários", "/portal/usuarios"),
            ("modelos", "Modelos IA", "/portal/modelos"),
            ("skills", "Skills", "/portal/skills"),
            ("agentes", "Agentes", "/portal/agentes"),
            ("conectores", "Conectores", "/portal/conectores"),
            ("canais", "Canais", "/portal/canais"),
            ("gateway", "Gateway", "/portal/gateway"),
        ]),
        ("Inteligência", "grupo_inteligencia", [
            ("memoria", "Memória", "/portal/memoria"),
            ("conhecimento", "Conhecimento", "/portal/conhecimento"),
            ("chat", "Chat", "/portal/chat"),
            ("teste_ab", "Teste A/B", "/portal/teste-ab"),
            ("fine_tuning", "Fine-Tuning", "/portal/fine-tuning"),
        ]),
        ("Operação", "grupo_operacao", [
            ("observabilidade", "Observabilidade", "/portal/observabilidade"),
            ("auditoria", "Auditoria", "/portal/auditoria"),
            ("uso_tokens", "Uso de Tokens", "/portal/uso-tokens"),
        ]),
        ("Configurações", "grupo_config", [
            ("alertas_config", "Alertas", "/portal/alertas-config"),
            ("lgpd", "LGPD", "/portal/lgpd"),
            ("sso", "SSO (OIDC)", "/portal/sso/config"),
            ("atualizacoes", "Atualizações", "/portal/atualizacoes"),
        ]),
    ]

    seta_aberto = "\u25be"
    seta_fechado = "\u25b8"
    links = """<div style="text-align:right;margin-bottom:4px"><button class="ham-sidebar" id="ham-btn" onclick="toggleSidebar()" title="Menu">☰</button></div><hr style="border-color:var(--line-soft);margin:4px 0 8px">"""
    for key, label, href in itens:
        links += _nl(key, label, href, " active" if key == active else "")

    # Submenus (Cadastros, Inteligencia, Operacao, Configuracoes)
    for rotulo, icone_grupo, itens_sub in submenus:
        keys_sub = {k for k, _, _ in itens_sub}
        aberto = active in keys_sub
        seta = seta_aberto if aberto else seta_fechado
        display = "block" if aberto else "none"
        sub_html = "".join(
            _nl(k, l, h, " active" if k == active else "")
            for k, l, h in itens_sub
        )
        links += f"""
    <div class="submenu">
      <a class="navlink sub-toggle{" open" if aberto else ""}" onclick="toggleSubmenu(this)" title="{rotulo}">
        <span class="nav-icon">{ICONS.get(icone_grupo, "")}</span>
        <span class="nav-label"><span class="arrow">{seta}</span> {rotulo}</span>
      </a>
      <div class="sub-items" style="display:{display}">
        {sub_html}
      </div>
    </div>"""

    links += ('<hr style="border-color:var(--line-soft);margin:8px 0 4px">'
              '<a class="navlink" href="#" onclick="abrirAjuda();return false" title="Ajuda (documentação)">'
              f'<span class="nav-icon">{ICONS.get("ajuda", chr(0x2753))}</span>'
              '<span class="nav-label">Ajuda</span></a>')

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
--ok:#22c55e;--warn:#f59e0b;--bad:#ef4444;
--input-bg:#0e1726;--code-bg:#0e1726;--panel-soft:#1a2744;--deep:#0c2230;
--line-soft:#1e2a3a;--muted-soft:#8899bb;--neutral:#222c44;
--brand-txt:#ffffff;--topbar-a:#0e1830;--topbar-b:#101a33;}
[data-theme="light"]{--bg:#eef1f7;--panel:#ffffff;--panel2:#e9edf5;--line:#d5dcea;
--txt:#1a2338;--muted:#5b6b8c;--blue:#2563eb;--blue2:#1d4ed8;
--ok:#15803d;--warn:#b45309;--bad:#b91c1c;
--input-bg:#ffffff;--code-bg:#f1f4fa;--panel-soft:#e8edf6;--deep:#e6edf8;
--line-soft:#dfe5f0;--muted-soft:#64748b;--neutral:#e5e9f3;
--brand-txt:#0e1830;--topbar-a:#ffffff;--topbar-b:#e9edf5;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--txt);font-size:14px;line-height:1.5}
.topbar{height:56px;display:flex;align-items:center;gap:16px;padding:0 20px;
background:linear-gradient(90deg,var(--topbar-a),var(--topbar-b));border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}
.hamburger{background:none;border:none;color:var(--muted);font-size:22px;cursor:pointer;padding:4px 8px;border-radius:6px;line-height:1}
.hamburger:hover{color:#fff;background:var(--panel2)}
.ham-sidebar{background:none;border:none;color:var(--muted);font-size:18px;cursor:pointer;padding:2px 6px;border-radius:4px;line-height:1}
.ham-sidebar:hover{color:#fff;background:var(--panel2)}
.brand{font-weight:800;letter-spacing:.3px;font-size:18px;color:var(--brand-txt)}
.brand span{color:var(--blue);font-weight:600}
.topbar-sub{color:var(--muted);font-size:13px;border-left:1px solid var(--line);padding-left:16px}
.userbox{display:flex;align-items:center;gap:10px}
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
.sidebar-by{padding:8px 10px;font-size:11px;color:var(--muted);text-align:center;letter-spacing:.5px}
.navlink{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;color:var(--muted);text-decoration:none;font-weight:500;font-size:14px;white-space:nowrap;overflow:hidden}
.navlink:hover{background:var(--panel2);color:var(--txt)}
.navlink.active{background:var(--blue2);color:#fff}
.navlink .nav-icon{flex-shrink:0;width:22px;text-align:center;font-size:16px;line-height:1}
.navlink .nav-label{overflow:hidden;text-overflow:ellipsis}
.navlink.sub-toggle{cursor:pointer;user-select:none}
.navlink.sub-toggle.open{color:var(--txt)}
.navlink .arrow{display:inline-block;width:14px}
.sub-items{margin-top:2px;display:flex;flex-direction:column;gap:3px}
.sub-items .navlink{padding-left:42px;font-size:13px}
.content{flex:1;padding:22px 26px}
.page-title{margin:0 0 18px;font-size:22px;font-weight:700}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:16px}
.grid{display:grid;gap:14px}
.grid-2{grid-template-columns:repeat(2,1fr)}
.grid-3{grid-template-columns:repeat(3,1fr)}
.grid-4{grid-template-columns:repeat(4,1fr)}
@media(max-width:900px){.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}}
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
.badge.neutral{background:var(--neutral);color:var(--muted)}
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
background:var(--input-bg);color:var(--txt);font-size:13px;margin-top:4px}
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
.bar{height:8px;border-radius:999px;background:var(--neutral);overflow:hidden}
.bar > i{display:block;height:100%;background:linear-gradient(90deg,var(--blue),#22d3ee)}
.health-card .value{font-size:30px}
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:100;justify-content:center;align-items:center}
.modal-overlay.show{display:flex}
.modal-box{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:24px;max-width:640px;width:90%;max-height:80vh;overflow-y:auto}
.modal-box h3{margin:0 0 12px;color:var(--txt)}
.modal-box textarea{width:100%;min-height:120px;margin:8px 0;font-family:monospace;font-size:12px}
.modal-actions{display:flex;gap:8px;margin-top:12px}
.modal-actions .btn-spin{position:relative;display:inline-flex;align-items:center;gap:6px}
.modal-actions .btn-spin.loading{pointer-events:none}
.modal-actions .btn-spin.loading::after{content:"";width:14px;height:14px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;display:inline-block}
.btn-spin{position:relative;display:inline-flex;align-items:center;gap:6px}
.btn-spin.loading{pointer-events:none}
.btn-spin.loading::after{content:"";width:14px;height:14px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;display:inline-block}
@keyframes spin{to{transform:rotate(360deg)}}
.btn-ia{background:linear-gradient(135deg,#7c3aed,#2563eb);color:#fff;border:none;cursor:pointer;padding:8px 14px;border-radius:8px;font-size:13px;font-weight:600}
.btn-ia:hover{filter:brightness(1.2)}
.theme-wrap{position:relative;margin-left:auto;display:flex;align-items:center}
.theme-btn{background:none;border:1px solid var(--line);border-radius:8px;color:var(--txt);font-size:16px;cursor:pointer;padding:6px 9px;line-height:1}
.theme-btn:hover{background:var(--panel2)}
.theme-menu{display:none;position:absolute;top:calc(100% + 8px);right:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:4px;box-shadow:0 10px 30px rgba(0,0,0,.4);z-index:60;min-width:150px}
.theme-menu.show{display:block}
.theme-menu a{display:flex;align-items:center;gap:9px;padding:8px 12px;border-radius:8px;color:var(--txt);text-decoration:none;font-size:13px;cursor:pointer;white-space:nowrap}
.theme-menu a:hover{background:var(--panel2)}
.ajuda-popup{position:fixed;right:24px;bottom:24px;width:440px;max-width:calc(100vw - 40px);background:var(--panel);border:1px solid var(--line);border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,.5);z-index:200;flex-direction:column;max-height:70vh}
.fluxo-popup{position:fixed;inset:0;background:rgba(0,0,0,.55);align-items:center;justify-content:center;z-index:300}
.fluxo-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px;width:min(1120px,96vw);max-height:94vh;overflow-y:auto;box-shadow:0 12px 40px rgba(0,0,0,.5)}
.fluxo-canvas{background:radial-gradient(var(--line-soft) 1px,transparent 1px);background-size:18px 18px;border:1px solid var(--line);border-radius:10px;padding:8px;overflow-x:auto}
.ajuda-header{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid var(--line);cursor:move;user-select:none;font-weight:700;font-size:13px}
.ajuda-body{padding:12px 14px;overflow-y:auto}
.ajuda-body .ajuda-resposta{font-size:13px;line-height:1.6;white-space:pre-wrap}
.ajuda-fechar{background:none;border:none;color:var(--muted);font-size:16px;cursor:pointer;padding:2px 6px;border-radius:6px;line-height:1}
.ajuda-fechar:hover{color:var(--txt);background:var(--panel2)}

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
