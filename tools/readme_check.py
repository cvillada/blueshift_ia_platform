#!/usr/bin/env python3
"""Gate de traducao — README (raiz) e as paginas de docs/ que tem traducao.

Por que existe: traducao que ninguem checa envelhece calada. O leitor estrangeiro
abre o README em ingles, ve uma versao antiga do produto e nao tem como saber.
Este script tem o MESMO principio do tools/doc_check.py:

    ele nao prova qualidade de traducao — prova que ninguem ESQUECEU de atualizar.

Como funciona: cada arquivo traduzido carrega no topo um marcador com o hash
sha256 (12 primeiros digitos) do arquivo de ORIGEM no momento da traducao:

    <!-- sync: README.md@8299efd394e6 -->

Se a origem mudar e a traducao nao, a checagem falha e diz qual arquivo atualizar.
Alem do hash, confere que a traducao nao foi truncada (numero de cabecalhos e de
blocos de codigo igual ao da origem e tamanho minimo) e que a barra de idiomas
aponta para os arquivos irmaos.

Escopo: so os arquivos de vitrine listados em PARES. O restante de docs/ segue
em pt-BR — a decisao de traduzir outra pagina e acrescentar a linha em PARES
(e criar o arquivo).

Uso:
  python tools/readme_check.py          # falha se alguma traducao estiver fora de sincronia
  python tools/readme_check.py --lista  # so mostra o estado (nao falha)
  python tools/readme_check.py --sync   # regrava os hashes (SO depois de revisar a traducao)
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Arquivos de vitrine traduzidos: origem -> traducoes (caminhos relativos a raiz).
# Para traduzir outra pagina de docs/: crie os arquivos e acrescente aqui.
PARES = {
    "README.md": ["README.en.md", "README.es.md"],
    "docs/00-visao-geral.md": ["docs/en/00-visao-geral.md", "docs/es/00-visao-geral.md"],
    "docs/01-arquitetura.md": ["docs/en/01-arquitetura.md", "docs/es/01-arquitetura.md"],
    "docs/02-como-executar.md": ["docs/en/02-como-executar.md", "docs/es/02-como-executar.md"],
    "docs/12-api-reference.md": ["docs/en/12-api-reference.md", "docs/es/12-api-reference.md"],
}

RE_MARCA = re.compile(r"<!--\s*sync:\s*([^\s@]+)@([0-9a-f]{6,64})\b")
RE_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _hash(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()[:12]


def _conta_inicio(texto: str, prefixo: str) -> int:
    return sum(1 for l in texto.splitlines() if l.startswith(prefixo))


def _conta_blocos(texto: str) -> int:
    return sum(1 for l in texto.splitlines() if l.strip().startswith("```")) // 2


def _barra_ok(origem_rel: str, traducao: Path, texto: str) -> bool:
    """Barra de idiomas: a traducao precisa linkar a origem e os irmaos nas 15 1as linhas."""
    cabeca = "\n".join(texto.splitlines()[:15])
    alvos = set()
    for link in RE_LINK.findall(cabeca):
        if "://" in link or link.startswith("#"):
            continue
        alvos.add((traducao.parent / link).resolve())
    esperados = {(RAIZ / origem_rel).resolve()}
    for irmao in PARES[origem_rel]:
        if (RAIZ / irmao) != traducao:
            esperados.add((RAIZ / irmao).resolve())
    return esperados <= alvos


def _checa(origem_rel: str, traducao_rel: str, lista: bool) -> list:
    origem = RAIZ / origem_rel
    traducao = RAIZ / traducao_rel
    problemas = []

    if not origem.exists():
        return [f"{origem_rel}: origem nao existe"]
    if not traducao.exists():
        return [f"{traducao_rel}: nao existe (origem {origem_rel})"]

    texto = traducao.read_text(encoding="utf-8")
    fonte = origem.read_text(encoding="utf-8")

    m = RE_MARCA.search("\n".join(texto.splitlines()[:15]))
    if not m:
        problemas.append(f"{traducao_rel}: sem marcador <!-- sync: {origem_rel}@hash --> no topo")
    else:
        alvo, marca = m.group(1), m.group(2)
        if alvo != Path(origem_rel).name:
            problemas.append(f"{traducao_rel}: marcador aponta para '{alvo}' (esperado '{Path(origem_rel).name}')")
        if marca != _hash(origem):
            problemas.append(f"{traducao_rel}: FORA DE SINCRONIA com {origem_rel} "
                             f"(marcador {marca} != origem {_hash(origem)})")

    if not _barra_ok(origem_rel, traducao, texto):
        problemas.append(f"{traducao_rel}: barra de idiomas ausente/incompleta nas 15 primeiras linhas")

    n_cab, n_cab_f = _conta_inicio(texto, "#"), _conta_inicio(fonte, "#")
    if n_cab != n_cab_f:
        problemas.append(f"{traducao_rel}: {n_cab} cabecalhos (origem tem {n_cab_f}) — traducao truncada?")

    n_blo, n_blo_f = _conta_blocos(texto), _conta_blocos(fonte)
    if n_blo != n_blo_f:
        problemas.append(f"{traducao_rel}: {n_blo} blocos de codigo (origem tem {n_blo_f}) — traducao truncada?")

    if len(texto) < 0.8 * len(fonte):
        problemas.append(f"{traducao_rel}: {len(texto)} chars (origem tem {len(fonte)}) — traducao truncada?")

    if lista or problemas:
        marca_txt = "OK" if not problemas else "PENDENTE"
        print(f"  [{marca_txt}] {traducao_rel}  <-  {origem_rel}")
    return problemas


def _regrava_hashes() -> int:
    total = 0
    for origem_rel, traducoes in PARES.items():
        origem = RAIZ / origem_rel
        if not origem.exists():
            continue
        novo = _hash(origem)
        for traducao_rel in traducoes:
            traducao = RAIZ / traducao_rel
            if not traducao.exists():
                continue
            texto = traducao.read_text(encoding="utf-8")
            atual = RE_MARCA.search(texto)
            if not atual or atual.group(2) == novo:      # ja em sincronia: nao mexe
                continue
            texto2, n = RE_MARCA.subn(
                lambda mm: f"<!-- sync: {Path(origem_rel).name}@{novo}", texto, count=1)
            if n:
                traducao.write_text(texto2, encoding="utf-8")
                total += 1
                print(f"  marcador regravado: {traducao_rel} -> {Path(origem_rel).name}@{novo}")
    if total:
        print(f"\n{total} marcador(es) regravado(s). "
              "Lembre: o hash e uma trava, nao uma prova — a traducao precisa ter sido revisada.")
    return 0


def main(argv: list) -> int:
    lista = "--lista" in argv
    if "--sync" in argv:
        return _regrava_hashes()

    print("checagem de traducao (README + paginas de docs/ traduzidas):")
    problemas = []
    for origem_rel, traducoes in PARES.items():
        for traducao_rel in traducoes:
            problemas += _checa(origem_rel, traducao_rel, lista)

    if problemas:
        print("\nPENDENCIAS:")
        for p in problemas:
            print(f"  - {p}")
        print("\nComo resolver: atualize a traducao a partir da origem (o texto em portugues mudou)")
        print("e so depois rode  python tools/readme_check.py --sync  para regravar o hash.")
        return 1 if not lista else 0

    print("\nOK — todas as traducoes em sincronia com a origem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
