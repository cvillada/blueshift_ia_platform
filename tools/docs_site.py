#!/usr/bin/env python3
"""Gera o SITE PÚBLICO de documentação do CL Agents (pré-venda) a partir de docs/.

Fonte única: as MESMAS páginas que o portal usa (`docs/*.md`) — quem entra no
site é o que estiver listado em `docs/_publico.txt` (curadoria explícita; o
resto continua só no produto). O markdown → HTML reaproveita o renderizador do
portal (`blueshift_layer.portal.views`), então site e produto nunca divergem.

Saída (padrão `dist/docs_site/`, autocontida — sem CDN, funciona offline):
  index.html, <slug>.html, site.css, site.js, busca.json, llms.txt, llms-full.txt

USO (na raiz do repo, com o venv do projeto)
  ./bp-venv/bin/python tools/docs_site.py [--out dist/docs_site]

Publicar: copiar a pasta gerada para o servidor web (estático).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as _html
import json
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from blueshift_layer.portal import views  # noqa: E402

SITE_NOME = "CL Agents"
SITE_SUB = "by BlueShift IA Platform"
CONTATO = "https://blueshift.com.br/FaleComBlueShift"

CSS = """*{box-sizing:border-box}
:root{--bg:#f7f8fb;--panel:#fff;--line:#e3e7ef;--txt:#141b2b;--muted:#5b6b8c;
--brand:#2563eb;--brand2:#1d4ed8;--code:#f2f4f9;--soft:#eef2fb}
[data-theme="dark"]{--bg:#0d1220;--panel:#141b2e;--line:#26304a;--txt:#e7ecf5;
--muted:#93a0bd;--brand:#3b82f6;--brand2:#60a5fa;--code:#0e1726;--soft:#1a2744}
body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.65 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--brand)}
header.top{display:flex;align-items:center;gap:12px;padding:12px 18px;background:var(--panel);
border-bottom:1px solid var(--line);position:sticky;top:0;z-index:9}
header.top b{font-size:16px}
header.top .sub{color:var(--muted);font-size:12px}
header.top .ver{color:var(--muted);font-size:11px;border:1px solid var(--line);border-radius:20px;padding:2px 9px}
header.top .esp{flex:1}
header.top .cta{background:var(--brand);color:#fff;text-decoration:none;font-size:12.5px;
padding:7px 12px;border-radius:8px}
header.top button{background:transparent;border:1px solid var(--line);color:var(--txt);
border-radius:8px;padding:6px 9px;cursor:pointer}
.wrap{display:flex;gap:26px;max-width:1220px;margin:0 auto;padding:22px 18px}
.side{flex:0 0 258px;position:sticky;top:74px;max-height:84vh;overflow:auto}
.busca{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:9px;
background:var(--panel);color:var(--txt);font-size:13px;margin-bottom:8px}
.res a{display:block;background:var(--panel);border:1px solid var(--line);border-radius:9px;
padding:8px 10px;margin-bottom:6px;text-decoration:none;color:var(--txt);font-size:13px}
.res .tr{display:block;color:var(--muted);font-size:11.5px;margin-top:3px}
.grp{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
margin:16px 0 6px}
.side a.item{display:block;padding:6px 10px;border-radius:8px;text-decoration:none;
color:var(--txt);font-size:13px;border:1px solid transparent}
.side a.item:hover{background:var(--soft);border-color:var(--line)}
.side a.item.on{background:var(--soft);border-color:var(--brand);font-weight:600}
.main{flex:1;min-width:0;display:flex;gap:22px;align-items:flex-start}
article{background:var(--panel);border:1px solid var(--line);border-radius:14px;
padding:26px 30px;flex:1;min-width:0}
article h1{font-size:26px;margin-top:0}
article h2{font-size:20px;border-bottom:1px solid var(--line);padding-bottom:6px;margin-top:30px}
article h3{font-size:16.5px;margin-top:24px}
article code{background:var(--code);padding:1.5px 5px;border-radius:5px;font-size:13px}
article pre{background:var(--code);border:1px solid var(--line);border-radius:10px;
padding:14px 16px;overflow:auto;position:relative}
article pre code{background:none;padding:0}
article table{border-collapse:collapse;width:100%;font-size:13.5px}
.tab{overflow-x:auto;margin:10px 0}
article th,article td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
article th{background:var(--soft)}
article blockquote{border-left:3px solid var(--brand);margin:14px 0;padding:2px 14px;color:var(--muted)}
.toc{flex:0 0 200px;position:sticky;top:74px;max-height:84vh;overflow:auto;font-size:12.5px}
.toc a{display:block;color:var(--muted);text-decoration:none;padding:3px 0}
.toc a:hover{color:var(--brand)}
.copiar{position:absolute;top:8px;right:8px;font-size:10.5px;background:var(--panel);
color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:3px 8px;cursor:pointer}
.pgfoot{display:flex;justify-content:space-between;margin-top:18px;font-size:13px}
footer{max-width:1220px;margin:0 auto;padding:18px;color:var(--muted);font-size:12px;
border-top:1px solid var(--line)}
@media (max-width:1000px){.toc{display:none}}
@media (max-width:760px){.wrap{flex-direction:column}.side{position:static;max-height:none;width:100%}
header.top .cta{display:none}}
@media print{.side,.toc,header.top,.pgfoot,.copiar{display:none!important}
article{border:0;padding:0}}
"""

JS = """(function(){
  var r=document.documentElement,t=localStorage.getItem('bs_docs_tema');
  if(t)r.setAttribute('data-theme',t);
  var b=document.getElementById('tema');
  if(b){b.textContent=r.getAttribute('data-theme')==='dark'?'\\u2600\\ufe0f':'\\u{1f319}';
    b.onclick=function(){var d=r.getAttribute('data-theme')==='dark'?'light':'dark';
      r.setAttribute('data-theme',d);localStorage.setItem('bs_docs_tema',d);
      b.textContent=d==='dark'?'\\u2600\\ufe0f':'\\u{1f319}';};}
  function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  var pres=document.querySelectorAll('article pre');
  for(var i=0;i<pres.length;i++){(function(pre){
    var bt=document.createElement('button');bt.className='copiar';bt.textContent='copiar';
    bt.onclick=function(){var c=pre.querySelector('code');if(!c||!navigator.clipboard)return;
      navigator.clipboard.writeText(c.innerText).then(function(){bt.textContent='copiado';
        setTimeout(function(){bt.textContent='copiar';},1500);});};
    pre.appendChild(bt);})(pres[i]);}
  var tabs=document.querySelectorAll('article table');
  for(var j=0;j<tabs.length;j++){if(tabs[j].parentNode.className==='tab')continue;
    var w=document.createElement('div');w.className='tab';
    tabs[j].parentNode.insertBefore(w,tabs[j]);w.appendChild(tabs[j]);}
  var inp=document.getElementById('busca'),res=document.getElementById('res');
  if(inp&&res){
    var idx=null,t=null;
    function carrega(){ if(idx)return Promise.resolve(idx);
      return fetch('busca.json').then(function(x){return x.json();}).then(function(d){idx=d;return d;}); }
    inp.addEventListener('input',function(){
      clearTimeout(t);var q=inp.value.trim().toLowerCase();
      if(q.length<2){res.innerHTML='';return;}
      t=setTimeout(function(){carrega().then(function(d){
        var out=d.filter(function(p){return p.texto.indexOf(q)>=0||p.titulo.toLowerCase().indexOf(q)>=0;}).slice(0,10);
        res.innerHTML=out.length?out.map(function(p){
          return '<a href="'+p.slug+'.html"><b>'+esc(p.titulo)+'</b><span class="tr">'+esc(p.grupo)+'</span></a>';
        }).join(''):'<div style="color:var(--muted);font-size:11.5px">nada encontrado</div>';
      });},160);});
    inp.addEventListener('keydown',function(e){if(e.key==='Enter'){var a=res.querySelector('a');if(a)location.href=a.href;}});
  }
})();"""


def _paginas_publicas() -> list:
    """Nav curado: [(grupo, [paginas])] conforme docs/_publico.txt."""
    arquivo = views._dir_docs() and Path(views._dir_docs()) / "_publico.txt"
    if not arquivo or not arquivo.exists():
        raise SystemExit("docs/_publico.txt nao encontrado (curadoria do site publico)")
    metad = {p["slug"]: p for p in views._paginas_doc_meta()}
    grupos, atual = [], None
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        l = linha.strip()
        if not l:
            continue
        if l.startswith("#"):
            titulo = l.lstrip("# ").strip()
            if titulo:
                atual = {"titulo": titulo, "paginas": []}
                grupos.append(atual)
            continue
        p = metad.get(l)
        if not p:
            print(f"  aviso: '{l}' esta em _publico.txt mas nao existe em docs/")
            continue
        if atual is None:
            atual = {"titulo": "Documentação", "paginas": []}
            grupos.append(atual)
        atual["paginas"].append(p)
    return [g for g in grupos if g["paginas"]]


def _link_publico(corpo: str, publicos: set) -> str:
    """Troca /portal/docs/<slug> por <slug>.html.

    Links para páginas que NÃO estão no site público já viram texto simples no
    passo anterior (`views._links_doc` recebe só a lista pública).
    """
    def _rep(m):
        slug = m.group(1)
        return f'href="{slug}.html"' if slug in publicos else "href=\"#\""
    return re.sub(r'href="/portal/docs/([^"#]+)"', _rep, corpo)


def _ancora_toc(corpo: str) -> str:
    achados = re.findall(r'<h([34]) id="([^"]+)">(.*?)</h\1>', corpo)
    itens = "".join(f'<a href="#{anc}">{txt}</a>' for _n, anc, txt in achados[1:])
    return f'<div class="toc"><div class="grp" style="margin-top:0">Nesta página</div>{itens}</div>' if itens else ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera o site público de documentação")
    ap.add_argument("--out", default=str(RAIZ / "dist" / "docs_site"))
    args = ap.parse_args()
    saida = Path(args.out)
    if saida.exists():
        shutil.rmtree(saida)
    saida.mkdir(parents=True)

    grupos = _paginas_publicas()
    todas = [p for g in grupos for p in g["paginas"]]
    publicos = {p["slug"] for p in todas}
    versao = views._versao_plataforma()
    data = dt.date.today().strftime("%d/%m/%Y")
    print(f"site publico: {len(todas)} paginas em {len(grupos)} grupos (v{versao})")

    nav = ""
    for g in grupos:
        nav += f'<div class="grp">{_html.escape(g["titulo"])}</div>'
        nav += "".join(f'<a class="item" href="{p["slug"]}.html">{_html.escape(p["curto"])}</a>'
                       for p in g["paginas"])
    ordem = [p["slug"] for p in todas]

    busca_idx = []
    for p in todas:
        md = views._links_doc(p["md"], todas)
        corpo = views._ancorar_doc(views._md_para_html(md))
        corpo = _link_publico(corpo, publicos)
        titulo = _html.escape(p["curto"])
        pos = ordem.index(p["slug"])
        ante = ordem[pos - 1] if pos > 0 else None
        prox = ordem[pos + 1] if pos + 1 < len(ordem) else None
        pgfoot = "<div class=\"pgfoot\">"
        pgfoot += (f'<a href="{ante}.html">← anterior</a>' if ante else "<span></span>")
        pgfoot += (f'<a href="{prox}.html">próximo →</a>' if prox else "<span></span>")
        pgfoot += "</div>"
        pagina = f"""<!doctype html>
<html lang="pt-BR" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo} — {SITE_NOME}</title>
<meta name="description" content="{_html.escape(p['titulo'])}">
<link rel="stylesheet" href="site.css"></head><body>
<header class="top"><b>{SITE_NOME}</b><span class="sub">{SITE_SUB}</span>
<span class="ver">v{versao}</span><span class="esp"></span>
<button id="tema" type="button" title="claro/escuro">🌙</button>
<a class="cta" href="{CONTATO}">Fale com a BlueShift</a></header>
<div class="wrap">
  <aside class="side">
    <input id="busca" class="busca" placeholder="🔎 buscar na documentação..." autocomplete="off">
    <div id="res" class="res"></div>
    {nav}
  </aside>
  <main class="main">
    <article>{corpo}{pgfoot}</article>
    {_ancora_toc(corpo)}
  </main>
</div>
<footer>Documentação {SITE_NOME} v{versao} — atualizada em {data}.
Gerada de <code>docs/</code> · <a href="llms.txt">llms.txt</a></footer>
<script src="site.js"></script></body></html>
"""
        (saida / f"{p['slug']}.html").write_text(pagina, encoding="utf-8")
        if p["slug"] == ordem[0]:
            (saida / "index.html").write_text(pagina, encoding="utf-8")
        busca_idx.append({
            "slug": p["slug"], "titulo": p["curto"], "grupo": p["grupo"],
            "texto": re.sub(r"\s+", " ", re.sub(r"[#*`|>\[\]()]", " ",
                                                p["md"].lower())).strip()[:4000],
        })

    (saida / "site.css").write_text(CSS, encoding="utf-8")
    (saida / "site.js").write_text(JS, encoding="utf-8")
    (saida / "busca.json").write_text(json.dumps(busca_idx, ensure_ascii=False), encoding="utf-8")

    linhas = [f"# {SITE_NOME} — documentação", "",
              f"> Documentação da plataforma {SITE_NOME} ({SITE_SUB}). Versão {versao}, atualizada em {data}.", ""]
    for g in grupos:
        linhas.append(f"## {g['titulo']}")
        for p in g["paginas"]:
            linhas.append(f"- [{p['curto']}]({p['slug']}.html): {p['titulo']}")
        linhas.append("")
    (saida / "llms.txt").write_text("\n".join(linhas), encoding="utf-8")

    completo = [f"# {SITE_NOME} — documentação completa (v{versao}, {data})", ""]
    for p in todas:
        completo.append(f"\\n\\n===== {p['curto']} ({p['slug']}) =====\\n")
        completo.append(p["md"])
    (saida / "llms-full.txt").write_text("\\n".join(completo), encoding="utf-8")

    print(f"gerado em {saida}:")
    for f in sorted(saida.iterdir()):
        print(f"   {f.name:<26} {f.stat().st_size:>9,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
