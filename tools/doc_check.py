#!/usr/bin/env python3
"""Checagem doc x codigo do CL Agents — o gate que impede a doc de envelhecer.

Percorre o codigo e confere se o que existe na plataforma esta documentado em
`docs/*.md`:

  - rotas do portal          (@bp.route em blueshift_layer/portal/views.py)
  - campos de formulario     (name="..."  em blueshift_layer/portal/views.py)
  - variaveis de ambiente    (BLUESHIFT_* / GATEWAY_* em todo o pacote)
  - tabelas do banco         (CREATE TABLE IF NOT EXISTS em portal/db.py)

Um campo pode ser documentado pelo NOME TECNICO (`a2a_url`) ou pelo ROTULO da
tela, desde que o rotulo esteja em `docs/_mapa_apelidos.json`. A checagem por
rotulo e um alarme (nao uma prova): o valor real esta em impedir que um campo,
rota ou tabela NOVA entre sem documentacao.

USO (na raiz do repo)
  python tools/doc_check.py             # falha (exit 1) se surgir item NOVO sem doc
  python tools/doc_check.py --lista     # mostra a divida conhecida (pendentes)
  python tools/doc_check.py --baseline  # regrava docs/_pendentes.json (use com consciencia)

Convencao de docs: docs/README.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
PENDENTES = DOCS / "_pendentes.json"
APELIDOS = DOCS / "_mapa_apelidos.json"


def _texto_docs() -> str:
    """Concatena as paginas de docs/ (ignora arquivos com _ e o README)."""
    partes = []
    for f in sorted(DOCS.glob("*.md")):
        if f.name.startswith("_") or f.name == "README.md":
            continue
        partes.append(f.read_text(encoding="utf-8"))
    return "\n".join(partes)


def _documentado(item: str, texto: str, apelidos: dict) -> bool:
    if item in texto:
        return True
    rotulo = apelidos.get(item)
    return bool(rotulo and rotulo in texto)


# Campos de formulario que sao "encanamento" (ids ocultos / parametros de rota) e
# nao tem leitura possivel pelo operador — nao entram na checagem de doc.
_IGNORAR_CAMPOS = {"canal_id", "csrf_token", "_acao", "_action", "_csrf_token", "corte"}


def coletar() -> dict:
    views = (RAIZ / "blueshift_layer/portal/views.py").read_text(encoding="utf-8")
    dbpy = (RAIZ / "blueshift_layer/portal/db.py").read_text(encoding="utf-8")
    pacote = "\n".join(
        f.read_text(encoding="utf-8", errors="ignore")
        for f in (RAIZ / "blueshift_layer").rglob("*.py")
        if "__pycache__" not in str(f)
    )

    rotas = sorted({r for r in re.findall(r'@bp\.route\("([^"]+)"', views)})
    campos = sorted({c for c in re.findall(r'name="([a-z][a-z0-9_]*)"', views)
                     if not c.startswith("_") and c not in _IGNORAR_CAMPOS})
    envs = sorted(set(re.findall(r'"(BLUESHIFT_[A-Z_]+|GATEWAY_[A-Z_]+)"', pacote)))
    tabelas = sorted(set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", dbpy)))
    return {"rotas": rotas, "campos": campos, "envs": envs, "tabelas": tabelas}


def _candidatos_rota(rota: str) -> list[str]:
    """Formas aceitaveis de citar a rota na doc (a rota exata nem sempre aparece)."""
    base = re.sub(r"<[^>]+>", "", rota).rstrip("/")
    partes = [p for p in base.split("/") if p]
    cands = [rota, base]
    if partes:
        cands.append("/" + "/".join(partes[:1]))
    if len(partes) > 1:
        cands.append("/" + "/".join(partes[:2]))
    return [c for c in dict.fromkeys(cands) if c]


def analisar() -> dict:
    texto = _texto_docs()
    apelidos = json.loads(APELIDOS.read_text(encoding="utf-8")) if APELIDOS.exists() else {}
    itens = coletar()

    gaps: dict[str, list[str]] = {}
    for rota in itens["rotas"]:
        if not any(c in texto for c in _candidatos_rota(rota)):
            gaps.setdefault("rotas", []).append(rota)
    for campo in itens["campos"]:
        if not _documentado(campo, texto, apelidos):
            gaps.setdefault("campos", []).append(campo)
    for env in itens["envs"]:
        if env not in texto:
            gaps.setdefault("envs", []).append(env)
    for tabela in itens["tabelas"]:
        if tabela not in texto:
            gaps.setdefault("tabelas", []).append(tabela)
    total = {k: len(v) for k, v in itens.items()}
    return {"gaps": gaps, "total": total}


def main() -> int:
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    r = analisar()
    gaps = r["gaps"]
    if modo == "--baseline":
        PENDENTES.write_text(json.dumps(gaps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"baseline gravado em {PENDENTES.relative_to(RAIZ)}: "
              + ", ".join(f"{k}={len(v)}" for k, v in gaps.items()))
        return 0

    conhecidos = json.loads(PENDENTES.read_text(encoding="utf-8")) if PENDENTES.exists() else {}
    if modo == "--lista":
        for k, v in gaps.items():
            print(f"[{k}] {len(v)} pendente(s):")
            for item in v:
                print("   ", item)
        return 0

    novos = {k: [i for i in v if i not in conhecidos.get(k, [])] for k, v in gaps.items()}
    novos = {k: v for k, v in novos.items() if v}
    print("cobertura do codigo na doc:",
          " | ".join(f"{k} {r['total'][k] - len(gaps.get(k, []))}/{r['total'][k]}" for k in r["total"]))
    if novos:
        print("\nNAO DOCUMENTADO (novo — inclua em docs/ ou aceite no baseline):")
        for k, v in novos.items():
            for item in v:
                print(f"   [{k}] {item}")
        print("\nDica: documente em docs/ (ver docs/README.md) ou, se for interno, "
              "rode `python tools/doc_check.py --baseline`.")
        return 1
    pend = sum(len(v) for v in gaps.values())
    print(f"OK — nenhum item novo sem documentacao."
          + (f" (divida conhecida: {pend} item(ns) — ver --lista)" if pend else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
