"""Orquestrador de Agentes da BlueShift.

Liga o Agente (cadastrado no Portal) ao seu Modelo de IA, às Skills do catálogo
e à base de conhecimento (RAG) do cliente — entregando o "agente de verdade"
do PRD (§7/§8-C): um modelo + skills + contexto dinâmico, 100% on-premise.
"""
from __future__ import annotations

import os
import re

from . import db, memory, llm_client

# catálogo de skills embarcado (template_skills/)
_SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "template_skills")


def listar_skills() -> list[dict]:
    """Lista skills disponíveis no catálogo (pastas com SKILL.md + frontmatter)."""
    skills: list[dict] = []
    if not os.path.isdir(_SKILLS_DIR):
        return skills
    for nome in sorted(os.listdir(_SKILLS_DIR)):
        skill_md = os.path.join(_SKILLS_DIR, nome, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        try:
            texto = open(skill_md, encoding="utf-8").read()
        except OSError:
            continue
        fm = re.search(r"^---\s*\n(.*?)\n---", texto, re.DOTALL)
        meta = {"name": nome, "description": nome}
        if fm:
            for line in fm.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
        skills.append(meta)
    return skills


def _skill_path(nome: str) -> str:
    """Caminho absoluto para o SKILL.md de uma skill."""
    return os.path.join(_SKILLS_DIR, nome, "SKILL.md")


def ler_skill(nome: str) -> dict | None:
    """Retorna {name, description, version, body} de uma skill, ou None se nao existir."""
    path = _skill_path(nome)
    if not os.path.isfile(path):
        return None
    try:
        texto = open(path, encoding="utf-8").read()
    except OSError:
        return None
    fm = re.search(r"^---\s*\n(.*?)\n---", texto, re.DOTALL)
    meta = {"name": nome, "description": nome, "version": "1.0.0", "body": ""}
    if fm:
        for line in fm.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
        meta["body"] = texto[fm.end():].strip()
    else:
        meta["body"] = texto.strip()
    return meta


def salvar_skill(nome: str, descricao: str, body: str, version: str = "1.0.0") -> None:
    """Cria ou atualiza um arquivo SKILL.md."""
    dest = os.path.join(_SKILLS_DIR, nome)
    os.makedirs(dest, exist_ok=True)
    conteudo = (
        f"---\nname: {nome}\ndescription: \"{descricao}\"\nversion: {version}\n---\n\n"
        f"{body.strip()}\n"
    )
    with open(os.path.join(dest, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(conteudo)


def deletar_skill(nome: str) -> bool:
    """Remove a pasta da skill. Retorna True se removeu."""
    import shutil
    path = os.path.join(_SKILLS_DIR, nome)
    if os.path.isdir(path):
        shutil.rmtree(path)
        return True
    return False


def _skills_text(skills_csv: str) -> str:
    """Monta bloco de instrução das skills a partir da lista 'vendas,suporte'."""
    nomes = [s.strip().lower() for s in (skills_csv or "").split(",") if s.strip()]
    catalogo = {s["name"]: s for s in listar_skills()}
    partes = []
    for n in nomes:
        s = catalogo.get(n)
        if s:
            partes.append(f"- {s['name']}: {s.get('description', '')}")
    return "\n".join(partes)


def responder(agente: dict, pergunta: str, usuario: str, id_cliente: str = "C001") -> dict:
    """Executa o agente: RAG (memória + conhecimento) + conectores MCP reais + modelo + skills.

    Fallback de modelo: tenta o `modelo_id` do agente; se o endpoint falhar
    (indisponível/erro de conexão), tenta `modelo_secundario_id` antes de
    desistir. O modelo efetivamente usado é registrado em `modelo_usado` e na
    auditoria, para o fluxo de ponta a ponta (API -> Agente -> resposta) entregar
    uma resposta mesmo quando um endpoint cai.

    Retorna dict {ok, content, model, model_fallback, error, contexto, ferramentas}.
    """
    cliente_id = agente["cliente_id"]
    modelo = db.buscar_modelo(agente["modelo_id"]) if agente.get("modelo_id") else None
    if not modelo:
        return {"ok": False, "content": "", "model": None, "model_fallback": False,
                "error": "Agente não tem um Modelo de IA válido cadastrado.", "contexto": [],
                "ferramentas": []}

    # contexto dinamico: memoria de longo prazo do usuario + base do cliente
    contexto = memory.buscar_contexto(pergunta, cliente_id, usuario=usuario, top_k=4)

    # conectores MCP reais: executa as ferramentas e injeta os resultados
    ferramentas = []
    conectores = agente.get("conectores", "")
    if conectores:
        try:
            from ..connector_pack import registry
            ferramentas = registry.executar_csv(conectores, id_cliente=id_cliente)
        except Exception as e:  # noqa: BLE001
            ferramentas = [{"erro": str(e)}]

    skills_txt = _skills_text(agente.get("skills", ""))

    system = (
        f"Você é o agente corporativo '{agente['nome']}' da BlueShift "
        f"(área: {agente.get('area') or 'geral'}).\n"
    )
    if skills_txt:
        system += f"\nSKILLS DISPONÍVEIS (use conforme adequado):\n{skills_txt}\n"
    if conectores:
        system += f"\nCONECTORES MCP DISPONÍVEIS: {conectores}\n"
    system += (
        "\nUse o contexto e os DADOS DE SISTEMA abaixo para responder com precisão. "
        "Se não houver resposta, diga que não sabe.\n\n"
        "CONTEXTO (base de conhecimento):\n"
        + ("\n".join(f"- {c['texto']}" for c in contexto) or "(vazio)")
    )
    if ferramentas:
        blocos = []
        for f in ferramentas:
            if "erro" in f:
                blocos.append(f"[{(f.get('conector') or '?')}] erro: {f['erro']}")
            else:
                blocos.append(f"[{(f.get('conector') or '?')}.{f.get('tool')}] "
                              f"args={f.get('args')} -> {f.get('resultado')}")
        system += "\n\nDADOS DE SISTEMA (conectores MCP executados):\n" + "\n".join(blocos)
    mensagens = [
        {"role": "system", "content": system},
        {"role": "user", "content": pergunta},
    ]

    # --- tentativa principal ---
    out = llm_client.chat(modelo, mensagens)
    modelo_usado = modelo["modelo"]
    usou_fallback = False

    # --- fallback: modelo secundário se o principal falhou ---
    if not out["ok"] and agente.get("modelo_secundario_id") and agente["modelo_secundario_id"] != agente["modelo_id"]:
        modelo2 = db.buscar_modelo(agente["modelo_secundario_id"])
        if modelo2:
            out2 = llm_client.chat(modelo2, mensagens)
            if out2["ok"]:
                out = out2
                modelo_usado = modelo2["modelo"]
                usou_fallback = True

    if out["ok"]:
        # grava na memoria do usuario (isolada)
        db.criar_memoria(cliente_id, usuario, f"[{agente['nome']}] P: {pergunta} | R: {out['content']}",
                         tipo="conversa")
        detalhe = pergunta[:80] + (f" [fallback->{modelo_usado}]" if usou_fallback else "")
        # registra tokens consumidos (analise de uso)
        tok = out.get("tokens") or {}
        db.registrar_uso_token(
            cliente_id=cliente_id, modelo=modelo_usado,
            total_tokens=tok.get("total_tokens", 0),
            prompt_tokens=tok.get("prompt_tokens", 0),
            completion_tokens=tok.get("completion_tokens", 0),
            agente_id=agente.get("id"),
            modelo_fallback=1 if usou_fallback else 0,
            quem=usuario, origem="chat",
        )
        db.registrar_auditoria(usuario, "sistema", "agente_responder", alvo=agente["nome"],
                               cliente_id=cliente_id, detalhe=detalhe)
    return {"ok": out["ok"], "content": out["content"], "model": out["model"],
            "model_fallback": usou_fallback, "error": out["error"],
            "contexto": contexto, "ferramentas": ferramentas}


def enviar_webhook(webhook_url: str, payload: dict) -> dict:
    """Dispara a resposta do agente para a URL de saida do canal (best-effort).

    Usa urllib (sem libs externas). Falhas nao quebram a resposta da API —
    apenas sao reportadas em 'erro' para auditoria/debug.
    """
    import json
    import urllib.request
    import urllib.error

    if not webhook_url:
        return {"enviado": False, "motivo": "sem_webhook"}
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"enviado": True, "status": resp.status}
    except Exception as e:  # noqa: BLE001 - webhook e best-effort
        return {"enviado": False, "erro": str(e)}
