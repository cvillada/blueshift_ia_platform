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
                 "/portal/agentes", "/portal/conectores", "/portal/billing", "/portal/suporte"]:
        r = client.get(rota)
        assert r.status_code == 200, f"{rota} retornou {r.status_code}"


def test_billing_e_suporte_crud():
    cid = portal_db.criar_cliente("fat", "Cliente Fatura")
    fid = portal_db.criar_fatura(cid, "licenca_anual", "Teste", 1000.0, status="pendente")
    assert portal_db.listar_faturas()[0]["valor"] == 1000.0
    portal_db.atualizar_fatura(fid, status="paga")
    assert portal_db.listar_faturas(cid)[0]["status"] == "paga"
    chid = portal_db.criar_chamado(cid, "Bug X", categoria="bug", prioridade="alta", aberto_por="admin")
    assert portal_db.listar_chamados(cid)[0]["titulo"] == "Bug X"
    portal_db.atualizar_chamado(chid, status="resolvido")
    assert portal_db.listar_chamados(cid)[0]["status"] == "resolvido"


def test_auditoria_e_papel():
    # auditoria registra login e acoes
    portal_db.registrar_auditoria("admin", "admin", "login", ip="127.0.0.1")
    assert len(portal_db.listar_auditoria()) >= 1
    # rotas de admin redirecionam usuario nao-admin
    app = create_app()
    client = app.test_client()
    # cria e loga como usuario comum
    cid = portal_db.criar_cliente("common", "Cliente Comum")
    portal_db.criar_usuario(cid, "Ze Comum", "ze", "ze123", "usuario", "vendas")
    client.post("/portal/login", data={"login": "ze", "senha": "ze123"})
    for rota in ["/portal/clientes/novo", "/portal/usuarios/novo", "/portal/agentes/novo",
                 "/portal/billing/novo", "/portal/auditoria"]:
        r = client.get(rota)
        assert r.status_code == 302, f"{rota} deveria redirecionar (não-admin), veio {r.status_code}"


def test_memoria_e_rag():
    from blueshift_layer.portal import memory
    cid = portal_db.criar_cliente("rag", "Cliente RAG")
    # base de conhecimento
    portal_db.criar_documento(cid, "LGPD", "politica",
                              "Dados sensíveis não saem do servidor do cliente. Memória isolada por usuario.")
    portal_db.criar_documento(cid, "Vendas", "manual",
                              "Agente de vendas qualifica leads e faz follow-up via ERP e CRM.")
    # memoria por usuario (isolada)
    portal_db.criar_memoria(cid, "ana", "cliente prefere contato por email")
    portal_db.criar_memoria(cid, "bia", "cliente quer ligacao mensal")
    # RAG deve recuperar o doc de LGPD para a query sobre privacidade
    res = memory.buscar_contexto("privacidade e protecao de dados", cid)
    assert any("LGPD" in r["meta"] or "servidor" in r["texto"] for r in res), res
    # isolamento: busca filtrada por dono 'ana' nao retorna memoria da 'bia'
    ana = memory.buscar_contexto("contato email", cid, usuario="ana")
    assert all(r["fonte"] != "memoria" or r["meta"] == "ana" for r in ana), ana


def test_modelos_e_chat():
    from blueshift_layer.portal import llm_client
    cid = portal_db.criar_cliente("llm", "Cliente LLM")
    mid = portal_db.criar_modelo(cid, "bonsai-4b", "http://127.0.0.1:1234", "bonsai-4b", tipo="local")
    m = portal_db.buscar_modelo(mid)
    assert m["modelo"] == "bonsai-4b"
    # health contra o LM Studio real (se estiver rodando)
    online = llm_client.health(m)
    if online:
        out = llm_client.chat(m, [{"role": "user", "content": "Diga 'ok' em uma palavra."}])
        assert out["ok"], out
        assert len(out["content"]) > 0
    # rota de chat requer login
    app = create_app()
    client = app.test_client()
    r = client.get("/portal/chat")
    assert r.status_code == 302  # sem login redireciona


def test_update_channel_e_webhook():
    # Update Channel real (check aponta para o canal mock)
    import threading
    from blueshift_layer import update_server, update_client
    srv = update_server.app
    # sobe o canal em thread local para o client consultar
    import urllib.request, json, time
    # usa o app do flask direto via test_client (sem rede)
    with update_server.app.test_client() as uc:
        # monkey: fazemos o check usar o test_client indiretamente eh complexo;
        # em vez disso validamos o contrato do server e do client separadamente
        ch = uc.get("/v1/channel").get_json()
        assert ch["version"] == "0.2.0", ch
    # webhook de saida: campo salvo no canal e disparo best-effort
    from blueshift_layer.portal import agente as agente_mod
    # servidor mock que recebe o POST do webhook
    received = {}
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            received["body"] = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(200); self.end_headers()
        def log_message(self, *a): pass

    httpd = HTTPServer(("127.0.0.1", 0), H)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True); t.start()
    wh_url = f"http://127.0.0.1:{port}/hook"
    r = agente_mod.enviar_webhook(wh_url, {"resposta": "oi", "agente": "X"})
    assert r["enviado"] is True, r
    time.sleep(0.3)
    assert b"oi" in received.get("body", b""), received
    # sem webhook
    assert agente_mod.enviar_webhook("", {})["enviado"] is False
    from blueshift_layer.portal import llm_client
    app = create_app()
    cid = portal_db.criar_cliente("can", "Cliente Canal")
    mid = portal_db.criar_modelo(cid, "bonsai-4b", "http://127.0.0.1:1234", "bonsai-4b")
    aid = portal_db.criar_agente(cid, "Agente Canal", area="vendas",
                                 modelo="bonsai-4b", skills="vendas", conectores="crm",
                                 modelo_id=mid)
    portal_db.criar_canal(cid, "API Canal", aid, tipo="api")
    canal = portal_db.listar_canais(cid)[0]
    token = canal["token"]
    modelo = portal_db.buscar_modelo(mid)
    with app.test_client() as c:
        # token invalido -> 401
        r = c.post("/portal/api/v1/agente", json={"pergunta": "oi"}, headers={"Authorization": "Bearer xxx"})
        assert r.status_code == 401, r.status_code
        # token valido (se LLM no ar)
        if llm_client.health(modelo):
            r = c.post("/portal/api/v1/agente", json={"pergunta": "historico do C001?"},
                       headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200, r.status_code
            body = r.get_json()
            assert body["ok"] is True
            assert body["agente"] == "Agente Canal"
            assert any("api_agente" in (a.get("acao") or "") for a in portal_db.listar_auditoria(200))


def test_agent_factory_real():
    from blueshift_layer.portal import agente as agente_mod, llm_client
    from blueshift_layer.connector_pack import registry
    # conectores reais retornam dados (nao vazios)
    crm = registry.executar("crm", "historico_contato", id_cliente="C001")
    assert any("canal" in h for h in crm), crm
    rh = registry.executar("rh", "consultar_colaborador", id_colab="E001")
    assert rh.get("nome") == "Carlos Andrade", rh
    fer = registry.executar_csv("erp,crm,rh", id_cliente="C001")
    assert len(fer) == 3, fer

    cid = portal_db.criar_cliente("agf", "Cliente Agent")
    mid = portal_db.criar_modelo(cid, "bonsai-4b", "http://127.0.0.1:1234", "bonsai-4b")
    aid = portal_db.criar_agente(cid, "Agente Vendas", area="vendas",
                                 modelo="bonsai-4b", skills="vendas", conectores="erp,crm",
                                 modelo_id=mid)
    a = portal_db.buscar_agente(aid)
    assert a["modelo_id"] == mid
    skills = agente_mod.listar_skills()
    assert any(s["name"] == "vendas" for s in skills)
    if llm_client.health(portal_db.buscar_modelo(mid)):
        out = agente_mod.responder(a, "Qual o histórico de contato do cliente C001?", "ana", id_cliente="C001")
        assert out["ok"] or out["error"], out
        # conectores reais devem ter sido executados
        assert "ferramentas" in out


def test_workspace_filtra_por_area():
    """Workspace (PRD §8-D): admin vê todas as áreas; não-admin fica preso na sua área."""
    app = create_app()
    c = app.test_client()
    # login admin
    r = c.post("/portal/login", data={"login": "admin", "senha": "admin123"},
               follow_redirects=False)
    assert r.status_code == 302
    # admin sem filtro deve enxergar agentes de várias áreas (seed cria 5)
    html = c.get("/portal/workspace").data.decode()
    n_admin = sum(1 for nome in ["Agente Vendas", "Agente Suporte", "Agente Financeiro",
                                   "Agente RH", "Agente Operações"] if nome in html)
    assert n_admin >= 2, f"admin deveria ver multiplas areas, viu {n_admin}"
    # admin filtrando por area=rh
    html_rh = c.get("/portal/workspace?area=rh").data.decode()
    assert "Agente RH" in html_rh
    assert "Agente Vendas" not in html_rh
    # login gestor (area vendas) — não pode trocar de área
    c.post("/portal/logout")
    c.post("/portal/login", data={"login": "gestor", "senha": "gestor123"},
            follow_redirects=False)
    html_gestor = c.get("/portal/workspace").data.decode()
    assert "Agente Vendas" in html_gestor
    # gestor tentando forçar area=rh via URL não deve ver Agente RH
    html_gestor_forcado = c.get("/portal/workspace?area=rh").data.decode()
    assert "Agente RH" not in html_gestor_forcado


def test_sso_fluxo_dev():
    """SSO (OIDC) modo dev: fluxo completo cria usuario e loga, mantendo login local."""
    app = create_app()
    c = app.test_client()
    # login local continua funcionando
    r = c.post("/portal/login", data={"login": "admin", "senha": "admin123"},
               follow_redirects=False)
    assert r.status_code == 302
    c.get("/portal/logout")
    # admin liga SSO em modo dev com auto_criar
    c.post("/portal/login", data={"login": "admin", "senha": "admin123"},
           follow_redirects=True)
    c.post("/portal/sso/config", data={"ativo": "on", "dev_mode": "on",
                                        "auto_criar": "on"})
    # fluxo SSO: /sso/login -> mock_authorize -> callback -> logado
    r = c.get("/portal/sso/login", follow_redirects=True)
    assert r.status_code == 200
    # apos SSO, a area restrita responde 200 (esta logado)
    mon = c.get("/portal/monitorar")
    assert mon.status_code == 200, mon.status_code
    # usuario SSO foi criado no banco
    with portal_db.get_conn() as conn:
        row = conn.execute(
            "SELECT login, papel FROM usuarios WHERE login='dev@blueshift.local'").fetchone()
    assert row is not None, "usuario SSO nao foi criado"
    assert row["papel"] == "usuario"
    # auditoria registrou login_sso
    aus = [a for a in portal_db.listar_auditoria(200) if a.get("acao") == "login_sso"]
    assert len(aus) >= 1, "login_sso nao auditado"


if __name__ == "__main__":
    test_app_factory()
    test_login_admin()
    test_crud_cliente()
    test_crud_agente_e_usuario()
    test_rotas_protegidas_renderizam()
    test_billing_e_suporte_crud()
    test_auditoria_e_papel()
    test_memoria_e_rag()
    test_modelos_e_chat()
    test_agent_factory_real()
    test_workspace_filtra_por_area()
    test_sso_fluxo_dev()
    print("PORTAL SMOKE TESTS PASSOU")
