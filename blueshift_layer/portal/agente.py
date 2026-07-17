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

    Retorna dict {ok, content, model, error, contexto, ferramentas}.
    """
    cliente_id = agente["cliente_id"]
    modelo = db.buscar_modelo(agente["modelo_id"]) if agente.get("modelo_id") else None
    if not modelo:
        return {"ok": False, "content": "", "model": None,
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
    out = llm_client.chat(modelo, mensagens)
    if out["ok"]:
        # grava na memoria do usuario (isolada)
        db.criar_memoria(cliente_id, usuario, f"[{agente['nome']}] P: {pergunta} | R: {out['content']}",
                         tipo="conversa")
    return {"ok": out["ok"], "content": out["content"], "model": out["model"],
            "error": out["error"], "contexto": contexto, "ferramentas": ferramentas}


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
