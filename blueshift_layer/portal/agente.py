"""Orquestrador de Agentes da BlueShift.

Liga o Agente (cadastrado no Portal) ao seu Modelo de IA, às Skills do catálogo
e à base de conhecimento (RAG) do cliente — entregando o "agente de verdade"
do PRD (§7/§8-C): um modelo + skills + contexto dinâmico, 100% on-premise.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

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
            with open(skill_md, encoding="utf-8") as f:
                texto = f.read()
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


def listar_skills_catalogo() -> list[tuple[str, dict, str]]:
    """Retorna lista de (nome, meta, body) de todas as skills do catálogo."""
    skills: list[tuple[str, dict, str]] = []
    if not os.path.isdir(_SKILLS_DIR):
        return skills
    for nome in sorted(os.listdir(_SKILLS_DIR)):
        skill_md = os.path.join(_SKILLS_DIR, nome, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        s = ler_skill(nome)
        if s:
            skills.append((s["name"], s, s.get("body", "")))
    return skills


def _skill_path(nome: str) -> str:
    """Caminho absoluto para o SKILL.md de uma skill.

    Valida o nome para prevenir path traversal (../).
    So permite nomes simples: letras, numeros, underline.
    """
    if not nome:
        return ""
    # Bloqueia qualquer tentativa de path traversal
    if "/" in nome or "\\" in nome or ".." in nome or not nome.isidentifier():
        return ""
    return os.path.join(_SKILLS_DIR, nome, "SKILL.md")


def ler_skill(nome: str) -> dict | None:
    """Retorna {name, description, version, body} de uma skill, ou None se nao existir."""
    path = _skill_path(nome)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            texto = f.read()
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
    """Executa o agente: RAG → conectores da área → modelo + skills.

    Hierarquia de execução:
      1. RAG (memória do usuário + base de conhecimento) — mais rápido
      2. Conectores da área do agente (API/MCP/SQL) — só se precisar de dado externo
      3. LLM com todo o contexto montado

    Fallback de modelo: tenta o `modelo_id` do agente; se o endpoint falhar
    tenta `modelo_secundario_id` antes de desistir.

    Retorna dict {ok, content, model, model_fallback, error, contexto, ferramentas}.
    """
    cliente_id = agente["cliente_id"]
    modelo = db.buscar_modelo(agente["modelo_id"]) if agente.get("modelo_id") else None
    if not modelo:
        return {"ok": False, "content": "", "model": None, "model_fallback": False,
                "error": "Agente não tem um Modelo de IA válido cadastrado.", "contexto": [],
                "ferramentas": []}

    # --- 1. RAG: contexto da base de conhecimento (mais rápido) ---
    contexto = memory.buscar_contexto(pergunta, cliente_id, usuario=usuario, top_k=4)

    # --- 2. Conectores da área do agente (se houver) ---
    ferramentas = []
    area = agente.get("area") or ""
    if area:
        try:
            from ..connector_pack import registry
            # Extrai parâmetros da pergunta (IDs, emails, códigos)
            params = _extrair_parametros(pergunta)
            params.setdefault("id_cliente", id_cliente)
            ferramentas = registry.executar_conectores_area(
                cliente_id, area, pergunta, parametros=params,
            )
        except Exception as e:  # noqa: BLE001
            ferramentas = [{"erro": str(e)}]

    # --- 3. Monta o prompt com skills + contexto + dados ---
    skills_txt = _skills_text(agente.get("skills", ""))

    system = (
        f"Você é o agente corporativo '{agente['nome']}' da BlueShift "
        f"(área: {area or 'geral'}).\n"
    )
    if skills_txt:
        system += f"\nSKILLS DISPONÍVEIS (use conforme adequado):\n{skills_txt}\n"

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
                blocos.append(f"[{f.get('conector','?')}] erro: {f['erro']}")
            else:
                blocos.append(f"[{f.get('conector')}.{f.get('tool')}] "
                              f"args={f.get('args')} -> {f.get('resultado')}")
        system += "\n\nDADOS DE SISTEMA (conectores executados):\n" + "\n".join(blocos)
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
        db.criar_memoria(cliente_id, usuario, f"[{agente['nome']}] P: {pergunta} | R: {out['content']}",
                         tipo="conversa")
        detalhe = pergunta[:80] + (f" [fallback->{modelo_usado}]" if usou_fallback else "")
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

        # --- RAG automatico: salva resultado dos conectores no knowledge base ---
        _salvar_no_knowledge(cliente_id, area, pergunta, out["content"], ferramentas)

    return {"ok": out["ok"], "content": out["content"], "model": out["model"],
            "model_fallback": usou_fallback, "error": out["error"],
            "contexto": contexto, "ferramentas": ferramentas}


def _salvar_no_knowledge(cliente_id: int, area: str, pergunta: str, resposta: str,
                         ferramentas: list[dict]) -> None:
    """Guarda o resultado dos conectores + resposta no RAG para consultas futuras.

    Só salva se:
    - Houver dados de conectores (ferramentas com resultado)
    - Não existir chunk muito similar (evita duplicatas)
    """
    dados_conectores = [f for f in ferramentas if "resultado" in f and f.get("resultado")]
    if not dados_conectores:
        return

    blocos = []
    fontes = set()
    for f in dados_conectores:
        fonte = f.get("conector", "desconhecido")
        fontes.add(fonte)
        res = f.get("resultado", "")
        # Limita a 300 chars por ferramenta pra nao explodir o RAG
        res_str = str(res)[:300]
        blocos.append(f"[{fonte}.{f.get('tool','?')}] {res_str}")

    texto = f"Pergunta: {pergunta[:200]}\nResposta: {resposta[:500]}\nDados: {' | '.join(blocos)}"
    if len(texto) < 30:
        return

    # Verifica se ja existe algo similar (evita duplicar a cada pergunta identica)
    from . import memory as memory_mod
    existing = memory_mod.buscar_contexto(pergunta, cliente_id, usuario=None, top_k=1, registrar_acesso=False)
    for e in existing:
        if e.get("score", 0) > 0.95 and pergunta[:50] in e.get("texto", ""):
            return  # ja tem no RAG, nao duplica

    titulo = f"RAG auto: {area}/{pergunta[:60]}"
    try:
        db.criar_documento(
            cliente_id=cliente_id, titulo=titulo, categoria="base_conhecimento",
            conteudo=texto, area=area, fonte=f"conector:{','.join(sorted(fontes))}",
        )
    except Exception:
        pass  # fallback silencioso — RAG e best-effort


# Padrão para extrair parâmetros da pergunta do usuário
_RE_PARAMS = re.compile(
    r"(C\d{2,}|E\d{2,}|OP-\d+|[\w.]+@[\w.]+\.[\w.]+|\d{4}-\d{2}(?:-\d{2})?)",
    re.IGNORECASE,
)


def _extrair_parametros(pergunta: str) -> dict:
    """Extrai IDs, emails e datas da pergunta para passar aos conectores.

    Também captura números soltos após palavras-chave (ex: 'cliente 2' → id_cliente=2).
    """
    params: dict[str, str] = {}
    for match in _RE_PARAMS.finditer(pergunta):
        val = match.group(1)
        if "@" in val and "email" not in params:
            params["email"] = val
        elif val.upper().startswith("C") and "id_cliente" not in params:
            params["id_cliente"] = val.upper()
        elif val.upper().startswith("E") and "id_colab" not in params:
            params["id_colab"] = val.upper()
        elif val.upper().startswith("OP-") and "id_oportunidade" not in params:
            params["id_oportunidade"] = val.upper()
        elif re.match(r"^\d{4}-\d{2}", val) and "data" not in params:
            params["data"] = val
    # Fallback: extrai números soltos após palavras-chave (ex: 'cliente 2', 'cliente id 2')
    if "id_cliente" not in params:
        m = re.search(
            r"(?:cliente|customer)\s+id\s*[#:]?\s*(\d+)"  # "cliente id 2"
            r"|(?:cliente|customer)\s*[#:]?\s*(\d+)"       # "cliente 2"
            r"|\bid\s*[#:]?\s*(\d+)(?:\s|$)",              # "id 2"
            pergunta, re.IGNORECASE,
        )
        if m:
            params["id_cliente"] = next(v for v in m.groups() if v is not None)
    if "id_colab" not in params:
        m = re.search(r"(?:colaborador|funcionario|employee|colab)\s*[#:]?\s*(\d+)", pergunta, re.IGNORECASE)
        if m:
            params["id_colab"] = m.group(1)
    return params


def enviar_webhook(webhook_url: str, payload: dict) -> dict:
    """Dispara a resposta do agente para a URL de saida do canal (best-effort).

    Usa urllib (sem libs externas). Falhas nao quebram a resposta da API —
    apenas sao reportadas em 'erro' para auditoria/debug.

    Retry: ate 3 tentativas com backoff exponencial (2s, 4s).
    """
    import json
    import urllib.request
    import urllib.error
    import time

    if not webhook_url:
        return {"enviado": False, "motivo": "sem_webhook"}
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    erros: list[str] = []
    for tentativa in range(3):
        try:
            req = urllib.request.Request(
                webhook_url,
                data=body_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {"enviado": True, "status": resp.status}
        except Exception as e:  # noqa: BLE001 - webhook e best-effort
            erros.append(str(e))
            if tentativa < 2:
                time.sleep(2 ** tentativa)  # 2s, 4s
    return {"enviado": False, "erro": "; ".join(erros), "tentativas": len(erros)}
