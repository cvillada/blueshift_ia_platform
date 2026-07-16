#!/usr/bin/env python3
"""Teste de fumaça do Portal do Cliente BlueShift (Camada 4)."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# forca SQLite temporario para nao poluir o data/ do projeto
_tmp = tempfile.mkdtemp()
os.environ["BLUESHIFT_PORTAL_DB"] = str(Path(_tmp) / "portal_test.db")

from blueshift_layer.portal import create_app, db as portal_db


def test_app_factory():
    app = create_app()
    assert app is not None
    # seed demo cria pelo menos 1 cliente
    assert len(portal_db.listar_clientes()) >= 1


def test_login_admin():
    app = create_app()
    client = app.test_client()
    # sem login -> monitorar redireciona para login
    r = client.get("/portal/monitorar", follow_redirects=False)
    assert r.status_code == 302
    # login correto
    r = client.post("/portal/login", data={"login": "admin", "senha": "admin123"},
                    follow_redirects=False)
    assert r.status_code == 302


def test_crud_cliente():
    # limpa e recria
    cid = portal_db.criar_cliente("teste", "Cliente Teste")
    assert portal_db.buscar_cliente(cid)["nome"] == "Cliente Teste"
    portal_db.atualizar_cliente(cid, status="suspenso")
    assert portal_db.buscar_cliente(cid)["status"] == "suspenso"


def test_crud_agente_e_usuario():
    cid = portal_db.criar_cliente("acme", "Acme")
    uid = portal_db.criar_usuario(cid, "Joao", "joao", "123", "gestor", "vendas")
    assert portal_db.autenticar("joao", "123")["papel"] == "gestor"
    aid = portal_db.criar_agente(cid, "Agente X", "vendas", "finetuned-v1", "vendas", "erp")
    assert portal_db.listar_agentes(cid)[0]["nome"] == "Agente X"


def test_rotas_protegidas_renderizam():
    app = create_app()
    client = app.test_client()
    client.post("/portal/login", data={"login": "admin", "senha": "admin123"})
    for rota in ["/portal/monitorar", "/portal/clientes", "/portal/usuarios",
                 "/portal/agentes", "/portal/conectores"]:
        r = client.get(rota)
        assert r.status_code == 200, f"{rota} retornou {r.status_code}"


if __name__ == "__main__":
    test_app_factory()
    test_login_admin()
    test_crud_cliente()
    test_crud_agente_e_usuario()
    test_rotas_protegidas_renderizam()
    print("PORTAL SMOKE TESTS PASSOU")
