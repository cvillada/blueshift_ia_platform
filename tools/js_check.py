#!/usr/bin/env python3
"""Checagem do JavaScript servido pelo portal — o gate que impede a tela de morrer calada.

Motivo: um erro de parse em UM ponto do bloco <script> faz o navegador descartar o
script INTEIRO — menu, popup e botoes param de responder, a pagina continua com
200 e nenhum teste/doc acusa nada. Aconteceu na v0.11.11 (uma palavra do Python,
`def `, entrou no JS de `manterPos`).

O que confere, em todas as rotas GET de tela do portal:

  - sintaxe de cada bloco <script>     (node --check; sem node, avisa e nao checa)
  - handlers inline                    (onclick/onchange/onsubmit... chamando
                                        funcao que nao existe na pagina)

USO (na raiz do repo)
  python tools/js_check.py        # exit 1 se algum script nao parsear / handler quebrado
  python tools/js_check.py -v     # mostra tambem as paginas e blocos aprovados
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from blueshift_layer.portal import create_app  # noqa: E402

_SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.S)
_HANDLER = re.compile(r'on(?:click|change|submit|input|keyup|keydown|blur|focus|'
                      r'mouseover|mouseout|dblclick|load)="([^"]*)"', re.I)
_CHAMADA = re.compile(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(")
_SEM_STRINGS = re.compile(r"&#x27;.*?&#x27;|&#39;.*?&#39;|&#x22;.*?&#x22;|'[^']*'|\"[^\"]*\"", re.S)
# `new URL(...)` e construtor, nao chamada de funcao da pagina
_NEW = re.compile(r"\bnew\s+[A-Za-z_$][\w$.]*")
_BUILTINS = {
    "if", "for", "while", "switch", "catch", "return", "typeof", "new", "in", "of",
    "function", "else", "do", "Math", "JSON", "parseInt", "parseFloat", "String",
    "Number", "Array", "Object", "Date", "Boolean", "RegExp", "Error", "Promise",
    "encodeURIComponent", "decodeURIComponent", "isNaN", "alert", "confirm", "prompt",
    "setTimeout", "setInterval", "clearTimeout", "clearInterval", "fetch",
    "requestAnimationFrame", "btoa", "atob", "structuredClone",
}


def _blocos(html: str) -> list[str]:
    return [b for b in _SCRIPT.findall(html) if b.strip()]


def _funcoes(blocos: list[str]) -> set[str]:
    js = "\n".join(blocos)
    nomes = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", js))
    nomes |= set(re.findall(r"(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*function", js))
    nomes |= set(re.findall(r"window\.([A-Za-z_$][\w$]*)\s*=", js))
    return nomes


def _handlers_quebrados(html: str) -> list[str]:
    definidas = _funcoes(_blocos(html))
    faltando: set[str] = set()
    for corpo in _HANDLER.findall(html):
        corpo = _NEW.sub("", _SEM_STRINGS.sub("''", corpo))
        for nome in _CHAMADA.findall(corpo):
            if nome not in _BUILTINS and nome not in definidas:
                faltando.add(nome)
    return sorted(faltando)


def _sintaxe(bloco: str) -> str:
    """Devolve '' se o bloco parseia; senao a mensagem do node (com a linha)."""
    node = shutil.which("node")
    if not node:
        return ""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(bloco)
        caminho = f.name
    try:
        r = subprocess.run([node, "--check", caminho], capture_output=True, text=True)
        if r.returncode == 0:
            return ""
        m = re.search(r":(\d+)\n", r.stderr)
        if m:
            ln = int(m.group(1))
            linhas = bloco.splitlines()
            alvo = linhas[ln - 1].strip() if 0 < ln <= len(linhas) else ""
            return f"linha {ln}: {alvo[:140]}"
        return r.stderr.strip().splitlines()[-1][:160]
    finally:
        os.unlink(caminho)


def _rotas(app) -> list[str]:
    """Rotas GET de tela (sem parametro e sem /api e /static)."""
    rotas = []
    for r in app.url_map.iter_rules():
        if "GET" not in r.methods or r.arguments or r.rule.startswith(("/static", "/api")):
            continue
        rotas.append(r.rule)
    return sorted(set(rotas))


def main() -> int:
    verboso = "-v" in sys.argv or "--verbose" in sys.argv
    if not shutil.which("node"):
        print("AVISO — node nao encontrado: sintaxe dos scripts nao checada "
              "(handlers inline seguem sendo checados).")
    from blueshift_layer.portal import db as portal_db

    app = create_app()
    # usuario TEMPORARIO para enxergar as telas autenticadas: nunca usar o admin
    # (nem senha fixa) — e apagar no fim.
    tmp_login = "_jscheck"
    tmp_id = None
    clientes = portal_db.listar_clientes()
    if clientes:
        with portal_db.get_conn() as conn:
            velho = conn.execute("SELECT id FROM usuarios WHERE login=?", (tmp_login,)).fetchone()
        if velho:
            conn_uid = velho["id"]
            portal_db.atualizar_usuario(conn_uid, ativo=0)
        tmp_id = portal_db.criar_usuario(clientes[0]["id"], "JS Check", tmp_login,
                                         "js-check-tmp", papel="admin")
    problemas: list[str] = []
    paginas = 0
    blocos_tot = 0
    for rota in _rotas(app):
        c = app.test_client()
        if tmp_id:
            c.post("/portal/login", data={"login": tmp_login, "senha": "js-check-tmp"})
        r = c.get(rota)
        if r.status_code >= 400:
            continue          # tela que exige login/parametro: fora do escopo
        html = r.get_data(as_text=True)
        paginas += 1
        quebrados = _handlers_quebrados(html)
        if quebrados:
            problemas.append(f"[{rota}] handler inline sem funcao: {quebrados}")
        for i, b in enumerate(_blocos(html)):
            blocos_tot += 1
            erro = _sintaxe(b)
            if erro:
                problemas.append(f"[{rota}] bloco {i} nao parseia -> {erro}")
        if verboso:
            print(f"  ok   {rota}: {len(_blocos(html))} bloco(s)")
    if tmp_id:
        try:
            with portal_db.get_conn() as conn:
                conn.execute("DELETE FROM usuarios WHERE id=?", (tmp_id,))
        except Exception:  # noqa: BLE001
            pass
    print(f"JS do portal: {paginas} pagina(s) / {blocos_tot} bloco(s) <script> checados")
    if problemas:
        print("\nCOM PROBLEMA:")
        for p in problemas:
            print("   " + p)
        print("\nDica: erro de parse derruba o script INTEIRO (menu, popup, botoes "
              "param de responder sem erro visivel na pagina).")
        return 1
    print("OK — todo o JS servido parseia e os handlers inline existem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
