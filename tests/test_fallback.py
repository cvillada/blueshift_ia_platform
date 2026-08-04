#!/usr/bin/env python3
"""Teste do fallback de modelo no orquestrador do agente (BlueShift).

Prova que, se o modelo principal falha (endpoint indisponível), o agente
tenta o modelo_secundario_id e entrega uma resposta — exatamente o cenario
de "usuario final / sistema interno batendo na API e tudo tem que estar
rodando e interligado".

Usa monkeypatch manual em llm_client.chat (sem rede, sem modelo real).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blueshift_layer.portal import db, agente as agente_mod


def _setup():
    db.init_db()
    cid = db.listar_clientes()[0]["id"]
    m1 = db.criar_modelo(cid, "principal-fake", "http://127.0.0.1:1", "principal-fake", tipo="local")
    m2 = db.criar_modelo(cid, "fallback-fake", "http://127.0.0.1:2", "fallback-fake", tipo="local")
    return cid, m1, m2


def _chatarra():
    pass


def test_fallback_quando_principal_falha():
    cid, m1, m2 = _setup()
    chamadas = {"principal": 0, "secundario": 0, "roteamento": 0}

    def fake_chat(modelo, mensagens, max_tokens=None, **kw):
        if max_tokens == 100:
            # chamada de ROTEAMENTO de conectores (max_tokens=50)
            chamadas["roteamento"] += 1
            return {"ok": True, "content": "nenhum", "model": modelo.get("modelo"), "error": None}
        if modelo["modelo"] == "principal-fake":
            chamadas["principal"] += 1
            return {"ok": False, "content": "", "model": "principal-fake",
                    "error": "nao foi possivel conectar ao endpoint (mock down)"}
        if modelo["modelo"] == "fallback-fake":
            chamadas["secundario"] += 1
            return {"ok": True, "content": "resposta via fallback", "model": "fallback-fake", "error": None}
        return {"ok": False, "content": "", "model": modelo.get("modelo"), "error": "desconhecido"}

    agente_mod.llm_client.chat = fake_chat

    aid = db.criar_agente(cid, "Agente Teste Fallback", "vendas", "principal-fake",
                          modelo_id=m1, modelo_secundario_id=m2)
    agente = db.buscar_agente(aid)
    assert agente is not None
    out = agente_mod.responder(agente, "qual o status?", "tester", id_cliente="C001")

    assert chamadas["roteamento"] == 3, "roteamento deve rodar 1x (max_tokens=100)"
    assert chamadas["principal"] == 1, "deve tentar o principal"
    assert chamadas["secundario"] == 1, "deve tentar o fallback apos falha"
    assert out["ok"] is True, "fallback deve entregar resposta"
    assert out["model_fallback"] is True, "model_fallback deve ser True"
    assert out["content"] == "resposta via fallback"
    print("FALLBACK TEST PASSOU  (principal falhou -> fallback entregou resposta)")


def test_sem_fallback_se_principal_ok():
    cid, m1, m2 = _setup()
    chamadas = {"principal": 0, "secundario": 0, "roteamento": 0}

    def fake_chat(modelo, mensagens, max_tokens=None, **kw):
        if max_tokens == 100:
            chamadas["roteamento"] += 1
            return {"ok": True, "content": "nenhum", "model": modelo.get("modelo"), "error": None}
        if modelo["modelo"] == "principal-fake":
            chamadas["principal"] += 1
            return {"ok": True, "content": "resposta principal", "model": "principal-fake", "error": None}
        chamadas["secundario"] += 1
        return {"ok": True, "content": "resposta fallback", "model": "fallback-fake", "error": None}

    agente_mod.llm_client.chat = fake_chat

    aid = db.criar_agente(cid, "Agente Teste OK", "vendas", "principal-fake",
                          modelo_id=m1, modelo_secundario_id=m2)
    agente = db.buscar_agente(aid)
    assert agente is not None
    out = agente_mod.responder(agente, "oi", "tester", id_cliente="C001")

    assert chamadas["roteamento"] == 3
    assert chamadas["principal"] == 1
    assert chamadas["secundario"] == 0, "nao deve usar fallback se principal ok"
    assert out["model_fallback"] is False
    print("NO-FALLBACK TEST PASSOU (principal ok -> sem fallback)")


if __name__ == "__main__":
    test_fallback_quando_principal_falha()
    test_sem_fallback_se_principal_ok()
    # restaura
    import importlib
    importlib.reload(agente_mod)
    print("TODOS OS TESTES DE FALLBACK PASSARAM")
