"""Banco vetorial local da BlueShift (100% offline, sem libs externas).

Implementa o "Contexto Dinamico" do PRD (§8-C):
  1. Memoria por usuario  -> cada usuario logado tem memoria persistente isolada
  2. RAG                  -> base de conhecimento do cliente (manual, politica,
                             base de conhecimento, contrato) recuperada por similaridade

Embeddings: TF-IDF local + similaridade de cosseno, em Python puro (sem numpy).
Assim a plataforma entrega contexto dinamico sem dependencia de rede nem libs
pesadas -- mantendo o padrao on-premise do projeto.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter

from . import db

_STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "para", "com", "em", "um", "uma", "que", "por",
    "se", "na", "no", "as", "os", "ao", "ou", "ja", "sem", "suas", "seus", "sua",
    "pelo", "pela", "nos", "nas", "nos", "dos", "das", "como", "mas", "foi", "sao",
    "the", "of", "and", "to", "in", "is", "for", "on", "by", "it", "this", "that",
}


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9à-ú]{2,}", text.lower()) if t not in _STOPWORDS]


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Retorna vetor esparso {termo: peso} usando TF-IDF local."""
    if not tokens:
        return {}
    tf = Counter(tokens)
    n = len(tokens)
    vec: dict[str, float] = {}
    for term, freq in tf.items():
        tf_weight = freq / n
        vec[term] = tf_weight * idf.get(term, math.log(2))  # IDF desconhecido ~ log(2)
    return vec


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(t, 0.0) * b.get(t, 0.0) for t in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class VectorStore:
    """Banco vetorial local em memoria (reconstruido a partir do SQLite).

    Mantem os embeddings (TF-IDF) em memoria para busca rapida; a fonte da
    verdade continua no SQLite (db.py), entao nada se perde entre reinicios.
    """

    def __init__(self):
        self._docs: list[dict] = []  # {id, dono, texto, vetor, fonte}
        self._idf: dict[str, float] = {}

    def rebuild(self, rows: list[dict]) -> None:
        """Recebe linhas ja carregadas do SQLite e (re)computa IDF + vetores."""
        df: Counter[str] = Counter()
        for r in rows:
            toks = _tokenize(r["conteudo"])
            r["_toks"] = toks
            for t in set(toks):
                df[t] += 1
        n_docs = max(len(rows), 1)
        self._idf = {t: math.log((n_docs + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self._docs = []
        for r in rows:
            vec = _tfidf_vector(r["_toks"], self._idf)
            self._docs.append({
                "id": r["id"], "dono": r.get("usuario") or r.get("titulo"),
                "texto": r["conteudo"], "vetor": vec, "fonte": r.get("_fonte", "doc"),
                "meta": r.get("_meta", ""),
                "area": r.get("area", "") or "",
            })

    def search(self, query: str, dono: str | None = None, top_k: int = 5,
               area: str | None = None) -> list[dict]:
        qvec = _tfidf_vector(_tokenize(query), self._idf)
        scored = []
        for d in self._docs:
            # isolamento por usuario so se aplica a memorias; documentos (RAG)
            # sao do cliente inteiro e sempre participam da busca
            if dono and d["fonte"] == "memoria" and d["dono"] != dono:
                continue
            # isolamento por area: doc com area definida so entra na area igual.
            # docs sem area (dados antigos) continuam entrando (compatibilidade).
            if area and d.get("area"):
                if d["area"] != area:
                    continue
            score = _cosine(qvec, d["vetor"])
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"id": d["id"], "texto": d["texto"], "score": round(score, 4),
                 "fonte": d["fonte"], "meta": d["meta"]} for score, d in scored[:top_k]]


# ---------------------------------------------------------------------------
# Ponte com o db.py (unico ponto de acesso ao SQLite)
# ---------------------------------------------------------------------------

def salvar_memoria(cliente_id, usuario, conteudo, tipo="conversa") -> int:
    """Salva um trecho de memoria do usuario e registra no RAG local."""
    return db.criar_memoria(cliente_id, usuario, conteudo, tipo)


def salvar_documento(cliente_id, titulo, categoria, conteudo) -> int:
    return db.criar_documento(cliente_id, titulo, categoria, conteudo)


def construir_store(cliente_id: int | None = None) -> VectorStore:
    """Monta o VectorStore unindo memorias de longo prazo + documentos (RAG).

    Importante (PRD §8-C / isolamento): so entram na recuperacao de contexto
    as memorias de tipo 'preferencia'/'contexto' do USUARIO — memorias de
    'conversa' ficam de fora para nao poluir o RAG nem criar loop.
    """
    rows: list[dict] = []
    mem = db.listar_memorias(cliente_id)
    for m in mem:
        if m.get("tipo") in ("preferencia", "contexto"):
            rows.append({**m, "_fonte": "memoria", "_meta": m["usuario"]})
    docs = db.listar_documentos(cliente_id)
    for d in docs:
        rows.append({**d, "_fonte": "base_conhecimento", "_meta": d["categoria"]})
    store = VectorStore()
    store.rebuild(rows)
    return store


def buscar_contexto(query: str, cliente_id: int, usuario: str | None = None,
                    top_k: int = 5, registrar_acesso: bool = True,
                    area: str | None = None) -> list[dict]:
    """Busca hibrida: memoria de longo prazo do usuario + base de conhecimento.

    Documentos (RAG) sempre entram (sao do cliente inteiro). Memorias sao
    filtradas por dono quando `usuario` e informado (isolamento por login).

    Args:
        registrar_acesso: se True, incrementa contador de acesso nos documentos encontrados.
                          Passar False quando a busca for para dedup interno (evita poluir metricas).
    """
    store = construir_store(cliente_id)
    resultados = store.search(query, dono=usuario, top_k=top_k, area=area)
    if registrar_acesso:
        for r in resultados:
            if r.get("fonte") == "base_conhecimento" and r.get("id"):
                try:
                    db.registrar_acesso_documento(r["id"])
                except Exception:
                    pass
    return resultados
