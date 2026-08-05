"""Orquestrador de Agentes da BlueShift.

Liga o Agente (cadastrado no Portal) ao seu Modelo de IA, às Skills do catálogo
e à base de conhecimento (RAG) do cliente — entregando o "agente de verdade"
do PRD (§7/§8-C): um modelo + skills + contexto dinâmico, 100% on-premise.
"""
from __future__ import annotations

import os
import re
import json as _json
from pathlib import Path

from . import db, memory, llm_client

# catálogo de skills embarcado (template_skills/)
_SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "template_skills")


def listar_skills() -> list[dict]:
    """Lista skills do catálogo (template_skills/) + banco (fonte oficial).

    Skills salvas via UI vivem no banco (volume persistente) — os arquivos
    SKILL.md em template_skills/ NÃO sobrevivem a rebuilds do container.
    O banco domina quando o mesmo nome existe nos dois lugares.
    """
    skills: list[dict] = []
    if os.path.isdir(_SKILLS_DIR):
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
    # Banco: fonte oficial de armazenamento — skills criadas pela UI
    try:
        from . import db as _db
        por_nome = {s["name"]: s for s in skills}
        for s in _db.listar_skills_db():
            por_nome[s["name"]] = s
        skills = [por_nome[k] for k in sorted(por_nome)]
    except Exception:  # noqa: BLE001
        pass
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
    """Retorna {name, description, version, body} de uma skill.

    Prioridade: banco de dados (persistente) > arquivo SKILL.md.
    """
    # Tenta banco primeiro (persiste entre rebuilds do Docker)
    from . import db as _db
    skill = _db.carregar_skill_db(nome)
    if skill:
        return skill

    # Fallback: arquivo SKILL.md
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
    """Cria ou atualiza um arquivo SKILL.md e registra no banco para persistencia.

    O arquivo SKILL.md ainda e escrito para compatibilidade com listar_skills(),
    mas a fonte oficial de armazenamento e o banco de dados (volume persistente).
    """
    # Salva no banco (persiste mesmo apos rebuild do container)
    from . import db as _db
    _db.salvar_skill_db(nome, descricao, body, version)

    # Arquivo local (tambem escreve para listar_skills() funcionar)
    dest = os.path.join(_SKILLS_DIR, nome)
    os.makedirs(dest, exist_ok=True)
    conteudo = (
        f"---\nname: {nome}\ndescription: \"{descricao}\"\nversion: {version}\n---\n\n"
        f"{body.strip()}\n"
    )
    with open(os.path.join(dest, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(conteudo)


def deletar_skill(nome: str) -> bool:
    """Remove a skill do banco e da pasta do catálogo. Retorna True."""
    # Banco (fonte oficial — persiste entre rebuilds)
    from . import db as _db
    try:
        _db.deletar_skill_db(nome)
    except Exception:  # noqa: BLE001
        pass
    # Arquivo local
    import shutil
    path = os.path.join(_SKILLS_DIR, nome)
    if os.path.isdir(path):
        shutil.rmtree(path)
    return True


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


def _placeholders_conectores(conectores: list[dict], ids: list[int] | None) -> set[str]:
    """Reune os placeholders {param} usados pelos conectores escolhidos."""
    import re as _re
    from ..connector_pack import registry as _reg
    ph: set[str] = set()
    for c in conectores:
        if ids is not None and c["id"] not in ids:
            continue
        cfg = _reg._parse_config(c.get("config", "{}"))
        ph.update(_re.findall(r"\{(\w+)\}", _json.dumps(cfg, ensure_ascii=False)))
    return ph


def _extrair_parametros_ia(pergunta: str, placeholders: set[str],
                           modelo: dict) -> dict | None:
    """Extrai parametros da pergunta via IA (linguagem natural).

    Complementa o regex _extrair_parametros: cobre variacoes que o regex
    nao reconhece (ex: \"id cliente igual a 58\"). Retorna dict ou None
    (falha — o chamador mantem o regex como fallback).
    """
    if not placeholders:
        return None
    lista = ", ".join(sorted(placeholders))
    from . import llm_client
    mensagens = [
        {"role": "system", "content": (
            "Voce extrai parametros de uma pergunta do usuario para chamadas "
            "de ferramentas. Retorne APENAS um JSON valido com os valores "
            "encontrados (strings). Se nenhum parametro for encontrado, "
            "retorne {}.")},
        {"role": "user", "content": f"Pergunta: {pergunta}\n\nParametros disponiveis: {lista}\n\nJSON:"},
    ]
    out = llm_client.chat(modelo, mensagens, max_tokens=100, temperatura=0.0)
    if not out.get("ok"):
        return None
    texto = (out.get("content") or "").strip()
    # limpa cercas ```json ... ```
    import re as _re
    m = _re.search(r"\{.*\}", texto, _re.DOTALL)
    if not m:
        return None
    try:
        dados = _json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(dados, dict):
        return None
    return {str(k): str(v) for k, v in dados.items() if v is not None and str(v).strip()}


def _selecionar_conectores(pergunta: str, conectores: list[dict],
                           modelo_roteador: dict) -> list[int] | None:
    """Roteia conectores por relevancia via LLM (a mesma IA do agente).

    Retorno:
      []     -> nenhum conector relevante (responde so com RAG)
      [ids]  -> executar apenas estes conectores
      None   -> falha na selecao -> executa TODOS (comportamento antigo)

    Conectores SEM descricao nunca sao excluidos (entram sempre).
    """
    if not conectores:
        return []
    from ..connector_pack import registry as _reg
    sempre = [c["id"] for c in conectores if not (_reg._parse_config(c.get("config", "{}")).get("descricao") or "").strip()]
    com_desc = [c for c in conectores if (_reg._parse_config(c.get("config", "{}")).get("descricao") or "").strip()]
    if not com_desc:
        return [c["id"] for c in conectores]  # tudo sem descricao -> executa tudo
    linhas = "\n".join(
        f"{i+1}. {c['nome']} ({c['tipo']}) — {_reg._parse_config(c.get('config', '{}')).get('descricao', '')[:120]}"
        for i, c in enumerate(com_desc)
    )
    from . import llm_client
    mensagens = [
        {"role": "system", "content": (
            "Voce e o roteador de ferramentas de um agente de IA corporativo. "
            "Escolha UMA opcao da lista que ajudaria a responder a pergunta "
            "do usuario. Responda APENAS com o numero da opcao (0 se nenhuma "
            "ajudar).")},
        {"role": "user", "content": f"Pergunta: {pergunta}\n\nOpcoes:\n0. nenhum\n{linhas}\n\nNumero:"},
    ]
    out = None
    import re as _re
    # Voto majoritario: 3 tentativas — modelos (principalmente externos com
    # reasoning) sao NAO-DETERMINISTICOS mesmo com temperatura 0.0. A
    # resposta valida e a que se repete; incompreensivel/erro nao e voto.
    votos: list = []  # "nenhum" | id(int) | None(incompreensivel)
    for _ in range(3):
        out = llm_client.chat(modelo_roteador, mensagens, max_tokens=100, temperatura=0.0)
        if not out.get("ok"):
            votos.append(None)
            continue
        texto = (out.get("content") or "").strip().lower()
        nums = [int(n) for n in _re.findall(r"\d+", texto)]
        if "nenhum" in texto or 0 in nums:
            votos.append("nenhum")
        else:
            sel = [com_desc[i - 1]["id"] for i in nums if 1 <= i <= len(com_desc)]
            votos.append(sel[0] if sel else None)
    ids_ok = {v for v in votos if isinstance(v, int)}
    viu_nenhum = "nenhum" in votos
    if ids_ok and not viu_nenhum:
        return sorted(set(sempre + list(ids_ok)))
    if viu_nenhum and not ids_ok:
        # Reforco por NOME: se o nome de um conector aparece na pergunta,
        # executa mesmo assim (match deterministico e forte — ex: "CEP").
        pergunta_l = pergunta.lower()
        reforco = [c["id"] for c in com_desc if c["nome"].lower() in pergunta_l]
        return sorted(set(sempre + reforco))
    return None  # ambiguo ou falha total -> executa todos (seguro)


def responder(agente: dict, pergunta: str, usuario: str, id_cliente: str = "",
              anonimizar: bool = True) -> dict:
    """Executa o agente: conectores (1º) → RAG complementar → modelo + skills.

    Hierarquia de execução:
      1. Conectores da área do agente (API/MCP/SQL) — fonte primária de dados
      2. RAG (memória + base de conhecimento) — sempre busca, mas com menos
         documentos (top_k=2) se conectores já retornaram dados vivos
      3. LLM com skills + contexto + dados montado

    Fallback de modelo: tenta o `modelo_id` do agente; se o endpoint falhar
    tenta `modelo_secundario_id` antes de desistir.

    id_cliente: opcional. Se fornecido, usado como fallback se a extração
    automática não encontrar. Padrão vazio — nenhum ID forçado.
    """
    import time as _time
    _t0 = _time.time()
    cliente_id = agente["cliente_id"]
    modelo = db.buscar_modelo(agente["modelo_id"]) if agente.get("modelo_id") else None
    if not modelo:
        return {"ok": False, "content": "", "model": None, "model_fallback": False,
                "error": "Agente não tem um Modelo de IA válido cadastrado.", "contexto": [],
                "ferramentas": []}

    # --- 1. Conectores da área do agente (fonte primária de dados) ---
    ferramentas = []
    area = agente.get("area") or ""
    if area:
        try:
            from ..connector_pack import registry
            params = _extrair_parametros(pergunta)
            # ── Roteamento inteligente: a IA escolhe QUAIS conectores usar ──
            # (env BLUESHIFT_ROUTER_MODEL aceita o ID ou o NOME do modelo —
            #  o nome e o que aparece na tela Modelos IA; vazio = principal)
            import os as _os
            _router_id = _os.environ.get("BLUESHIFT_ROUTER_MODEL", "").strip()
            if _router_id.isdigit():
                modelo_roteador = db.buscar_modelo(int(_router_id))
            elif _router_id:
                modelo_roteador = next(
                    (m for m in db.listar_modelos()
                     if m["nome"].lower() == _router_id.lower()), None)
            else:
                modelo_roteador = None
            modelo_roteador = modelo_roteador or modelo
            conectores_area = db.listar_conectores(cliente_id=cliente_id, area=area)
            somente_ids = _selecionar_conectores(pergunta, conectores_area, modelo_roteador)
            # B: IA completa parametros que o regex nao pegou (ex: "id cliente
            # igual a 58") — usa os placeholders dos conectores escolhidos
            if somente_ids:
                ph = _placeholders_conectores(conectores_area, somente_ids)
                params_ia = _extrair_parametros_ia(pergunta, ph, modelo_roteador)
                if params_ia:
                    for k, v in params_ia.items():
                        if k in ph and k not in params:
                            params[k] = v
            ferramentas = registry.executar_conectores_area(
                cliente_id, area, pergunta, parametros=params,
                somente_ids=somente_ids,
            )
        except Exception as e:  # noqa: BLE001
            ferramentas = [{"erro": str(e)}]

    # --- 2. RAG: complementa contexto mesmo se conectores retornaram dados ---
    tem_dados_vivos = any(
        f.get("resultado") for f in ferramentas
    )
    top_k = 2 if tem_dados_vivos else 4
    contexto = memory.buscar_contexto(pergunta, cliente_id, usuario=usuario, top_k=top_k, area=area)

    # Filtra contexto RAG: remove documentos com id_cliente diferente do extraido
    id_filtro = params.get("id_cliente", "") if "params" in dir() else ""
    if id_filtro:
        contexto = [c for c in contexto if id_filtro not in c.get("texto", "")]
        # Se filtrou tudo e tem dados vivos, ok. Senao busca sem filtro.
        if not contexto and not tem_dados_vivos:
            contexto = memory.buscar_contexto(pergunta, cliente_id, usuario=usuario, top_k=top_k, area=area)

    # --- 3. Monta o prompt com skills + contexto + dados ---
    skills_txt = _skills_text(agente.get("skills", ""))

    system = (
        f"Você é o agente corporativo '{agente['nome']}' da BlueShift "
        f"(área: {area or 'geral'}).\n"
    )
    if skills_txt:
        system += f"\nSKILLS DISPONÍVEIS (use conforme adequado):\n{skills_txt}\n"

    system += (
        "\nUse os DADOS DE SISTEMA abaixo como fonte PRIMARIA — eles contem "
        "informacoes ATUAIS dos bancos e sistemas da empresa. "
        "O CONTEXTO (base de conhecimento) pode conter informacoes desatualizadas "
        "e deve ser usado apenas como referencia SECUNDARIA.\n\n"
    )
    if ferramentas:
        blocos = []
        for f in ferramentas:
            if "erro" in f:
                continue  # erro vai pro trace, mas nao polui o prompt do LLM
            blocos.append(f"[{f.get('conector')}.{f.get('tool')}] "
                          f"args={f.get('args')} -> {f.get('resultado')}")
        if blocos:
            system += "DADOS DE SISTEMA (conectores executados — FONTE PRIMARIA):\n" + "\n".join(blocos) + "\n\n"
    if not tem_dados_vivos:
        # C: guardrail anti-alucinacao — conectores rodaram sem dados vivos
        system += (
            "\nSe a informacao pedida nao estiver nos dados acima, NAO invente "
            "valores (datas, nomes, numeros, IDs). Responda que nao encontrou "
            "a informacao e sugira reformular (ex: informar id_cliente=58).\n"
        )
    system += (
        "CONTEXTO (base de conhecimento — FONTE SECUNDARIA, pode estar desatualizado):\n"
        + ("\n".join(f"- {c['texto']}" for c in contexto) or "(vazio)")
    )
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

    tok = out.get("tokens") or {}

    # --- Tracing: salva o rastreio detalhado da execucao ---
    import time as _time
    tempo_ms = int((_time.time() - _t0) * 1000)
    trace_id = db.salvar_trace(
        pergunta=pergunta,
        params=params if "params" in dir() else {},
        conectores=ferramentas,
        rag=[{"texto": c["texto"][:200]} for c in contexto],
        modelo=modelo_usado,
        modelo_fallback=usou_fallback,
        tokens=tok,
        resposta=out.get("content", ""),
        tempo_ms=tempo_ms,
        agente_id=agente.get("id"),
    )

    if out["ok"]:
        db.criar_memoria(cliente_id, usuario, f"[{agente['nome']}] P: {pergunta} | R: {out['content']}",
                         tipo="conversa", area=area)
        detalhe = f"trace:{trace_id} | {pergunta[:60]}" + (f" | fallback->{modelo_usado}" if usou_fallback else "")
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

    # --- Feedback implicito: detecta pergunta repetida ---
    if out["ok"] and agente.get("id"):
        try:
            db.verificar_pergunta_repetida(agente["id"], pergunta)
        except Exception:
            pass

    # --- Anonimizacao LGPD na saida (Arts. 12, 13) ---
    if out["ok"] and anonimizar and agente.get("lgpd_ativado", 1):
        lgpd_cfg = db.carregar_lgpd_config()
        if lgpd_cfg.get("anonimizar_llm") == "1":
            from . import mask as _mask
            out["content"] = _mask.aplicar_mascaras(out["content"], lgpd_cfg)

    return {"ok": out["ok"], "content": out["content"], "model": out["model"],
            "model_fallback": usou_fallback, "error": out["error"],
            "contexto": contexto, "ferramentas": ferramentas,
            "trace_id": trace_id,
            "feedback_url": f"/portal/api/v1/feedback/{trace_id}" if out["ok"] else None,
            "tokens": out.get("tokens", {}),
            "tempo_ms": tempo_ms,
            }


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
    existing = memory_mod.buscar_contexto(pergunta, cliente_id, usuario=None, top_k=1, registrar_acesso=False, area=area)
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


# --------------------------------------------------------------------------- #
# Extrator inteligente de parâmetros da pergunta do usuário
# --------------------------------------------------------------------------- #

# Mapeamento de prefixos conhecidos para nomes de parâmetros
_PREFIX_MAP = {
    "c": "id_cliente",
    "e": "id_colab",
    "op": "id_oportunidade",
    "ped": "id_pedido",
}

# Regex para capturar códigos como C001, E001, PED-99, FUNC42
_RE_CODIGO = re.compile(r"([A-Za-z]+)-?(\d{2,})")

# Regex para email
_RE_EMAIL = re.compile(r"[\w.]+@[\w.]+\.[\w.]+")


def _extrair_parametros(pergunta: str) -> dict:
    """Extrai parâmetros da pergunta do usuário de forma genérica.

    Reconhece automaticamente:
      - Códigos: C001, E001, PED-99, FUNC42 → prefixo vira nome do param
      - Emails: usuario@dominio.com
      - Datas: 2026-07-22
      - chave='valor' na pergunta
      - Números após palavras-chave (fallback)

    Não usa default C001 — se não extrair, o placeholder {param} na query
    fica literal (e o banco retorna vazio, que é mais honesto).
    """
    params: dict[str, str] = {}

    # --- 1. Códigos (C001, E001, PED-99, FUNC42, OP-123) ---
    for m in _RE_CODIGO.finditer(pergunta):
        prefixo = m.group(1).lower()
        numero = m.group(2)
        chave = _PREFIX_MAP.get(prefixo, f"id_{prefixo}")
        if chave not in params:
            # Preserva maiusculas do codigo original (C001, nao c001)
            params[chave] = f"{m.group(1).upper()}{numero}" if prefixo in ("c", "e") else m.group(0).upper()

    # --- 2. Email ---
    m = _RE_EMAIL.search(pergunta)
    if m and "email" not in params:
        params["email"] = m.group(0)

    # --- 3. Data (YYYY-MM-DD) ---
    m = re.search(r"\b(\d{4}-\d{2}(?:-\d{2})?)\b", pergunta)
    if m and "data" not in params:
        params["data"] = m.group(1)

    # --- 4. Fallback: números após palavras-chave (se ainda não extraiu) ---
    if "id_cliente" not in params:
        m = re.search(
            r"(?:cliente|customer)\s+id\s*[#:]?\s*(\d+)"   # "cliente id 2"
            r"|(?:cliente|customer)\s*[#:]?\s*(\d+)"        # "cliente 2"
            r"|\bid\s*[#:]?\s*(\d+)(?:[\s?.!,;:'`]|$)"     # "id 2" ou "id 22?"
            r"|id_cliente\s*[#:=]?\s*(\d+)",                # "id_cliente 22" ou "id_cliente=10"
            pergunta, re.IGNORECASE,
        )
        if m:
            params["id_cliente"] = next(v for v in m.groups() if v is not None)
    if "id_colab" not in params:
        m = re.search(r"(?:colaborador|funcionario|employee|colab)\s*[#:]?\s*(\d+)", pergunta, re.IGNORECASE)
        if m:
            params["id_colab"] = m.group(1)

    # --- 5. Extrator genérico: chave='valor' ou chave="valor" ---
    for m in re.finditer(r"""([\w_]+)\s*=\s*['\"]([^'\"]+)['\"]""", pergunta):
        chave = m.group(1).lower()
        valor = m.group(2)
        if chave not in params:
            params[chave] = valor

    # --- 6. Extrator de numero: chave=123 (sem aspas) ---
    for m in re.finditer(r"""([\w_]+)\s*=\s*(\d{2,})""", pergunta):
        chave = m.group(1).lower()
        valor = m.group(2)
        if chave not in params:
            params[chave] = valor

    return params


def enviar_webhook(webhook_url: str, payload: dict,
                   headers_extra: dict | None = None) -> dict:
    """Dispara a resposta do agente para a URL de saida do canal (best-effort).

    Usa urllib (sem libs externas). Falhas nao quebram a resposta da API —
    apenas sao reportadas em 'erro' para auditoria/debug.

    headers_extra: headers adicionais do canal (ex: X-Webhook-Secret,
    Authorization) — configurados no campo "Headers (JSON)" do canal.

    Retry: ate 3 tentativas com backoff exponencial (2s, 4s).
    """
    import json
    import urllib.request
    import urllib.error
    import time

    if not webhook_url:
        return {"enviado": False, "motivo": "sem_webhook"}
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if headers_extra:
        for k, v in headers_extra.items():
            if k and v is not None:
                headers[str(k)] = str(v)
    erros: list[str] = []
    for tentativa in range(3):
        try:
            req = urllib.request.Request(
                webhook_url,
                data=body_bytes,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {"enviado": True, "status": resp.status}
        except Exception as e:  # noqa: BLE001 - webhook e best-effort
            erros.append(str(e))
            if tentativa < 2:
                time.sleep(2 ** tentativa)  # 2s, 4s
    return {"enviado": False, "erro": "; ".join(erros), "tentativas": len(erros)}
