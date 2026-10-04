"""Orquestrador de Agentes da BlueShift.

Liga o Agente (cadastrado no Portal) ao seu Modelo de IA, às Skills do catálogo
e à base de conhecimento (RAG) do cliente — entregando o "agente de verdade"
do PRD (§7/§8-C): um modelo + skills + contexto dinâmico, 100% on-premise.
"""
from __future__ import annotations

import os
import re
import time
import threading
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
    """Remove a skill do banco e da pasta do catálogo. Retorna True.

    Recusa (False) quando algum agente usa a skill — integridade referencial:
    `agentes.skills` é um CSV de nomes sem chave estrangeira, então apagar uma
    skill EM USO deixava o agente com referência pendurada (instruções sumiam
    do prompt sem erro nenhum, ou pior: caíam na cópia do arquivo embarcado e
    o conteúdo do agente MUDava sem aviso). Quem chama mostra a mensagem.
    """
    if agentes_com_skill(nome):
        return False
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


# Limite do corpo da skill enviado ao prompt (chars por skill). Historico:
# era 4000 FIXO e cortava EM SILENCIO 2 skills do catalogo real (rh 5.259 e
# operacoes 4.826 chars) — e as regras de formato/comportamento ficam no FIM
# do SKILL.md, exatamente o trecho perdido. 8000 cobre o catalogo inteiro;
# ajustavel por env (BLUESHIFT_SKILL_BODY_MAX) sem rebuild da imagem.
_SKILL_BODY_MAX = 8000


def _skill_body_max() -> int:
    """Limite efetivo do corpo da skill (env BLUESHIFT_SKILL_BODY_MAX > constante)."""
    try:
        return max(0, int(os.environ.get("BLUESHIFT_SKILL_BODY_MAX", "").strip()
                          or _SKILL_BODY_MAX))
    except (TypeError, ValueError):
        return _SKILL_BODY_MAX


# Formato da resposta (v0.11.8). O modelo principal (reasoning) gastava a maior
# parte da geracao "pensando em voz alta" e recapitulando os dados: medido na
# prod, 4.471 tokens gerados para 121 chars de resposta (41,8s de espera).
# A diretiva corta o padrao em ~2,2x SEM tocar em max_tokens — provado inerte
# (8132 e 1500 geram o MESMO texto) e capaz apenas de cortar a resposta.
# A clausula de excecao existe porque sem ela o modelo se recusava a atender
# pedido explicito de texto longo ("historia de 1000 palavras": 1.021 chars
# antes, 4.793 chars com ela). Vai ANTES do bloco de SKILLS de proposito: a
# regra de formato da skill do cliente, quando existir, continua ganhando.
_DIRETIVA_RESPOSTA = (
    "FORMATO DA RESPOSTA: seja objetivo — responda direto o que foi perguntado, "
    "sem repetir os mesmos números em texto E em tabela, sem recapitular os "
    "dados recebidos e sem explicar seu raciocínio. Use tabela apenas quando "
    "houver dados comparáveis. Se o usuário pedir explicitamente um texto longo "
    "(ex.: 'conte uma história de 1000 palavras', 'relatório completo'), atenda "
    "o pedido dele: a objetividade vale para o padrão, não para um pedido "
    "explícito.\n"
)


# Dado ausente (v0.11.9 / B6). Medido: com o conector devolvendo `{"sum": null}`
# o modelo respondia "o total foi de 50 milhoes de reais" — numero que nao
# existe em lugar nenhum (alucinacao sobre resultado vazio). A instrucao separa
# os dois casos que o modelo confundia: "o campo veio nulo/vazio" e "a pergunta
# nao tem resposta nos dados".
_DIRETIVA_DADOS_AUSENTES = (
    "DADOS AUSENTES: quando o valor pedido nao estiver nos dados (campo nulo, "
    "lista vazia, resultado 'sem dados' ou consulta nao executada), diga "
    "claramente que nao ha esse dado disponivel e o que faltou — NUNCA estime, "
    "aproxime, arredonde por conta propria nem invente numero, nome ou data. "
    "Se parte dos dados veio e parte nao, responda apenas o que veio.\n"
)

# Ordem/atualidade nao afirmada (v0.11.11). Medido no trace #337: a consulta
# devolveu 20 linhas SEM ordenacao e a resposta as apresentou como "os filmes
# mais recentes" — qualificador que o dado nao sustenta (o usuario pediu "o
# ULTIMO filme alugado" e recebeu uma lista arbitraria). Mesma familia do
# guard de numero inventado: aqui o que se inventa e a ORDEM.
#
# Reescrita (v0.11.11, E2E do cliente 22): agora o bloco de dados informa o
# CRITERIO da consulta ("consulta: ordenado por X (maior/mais recente primeiro)")
# — sem o texto do SQL. Com o criterio, a ordem das linhas E autoridade e a
# resposta pode afirmar; sem o criterio, continua proibido afirmar. E quando a
# contagem do topo empata, o que se afirma e o EMPATE, nunca um vencedor unico
# (o trace #370 respondeu "BARBARELLA STREETCAR e o top 1" num empate de 22).
_DIRETIVA_ORDEM_NAO_AFIRMADA = (
    "ORDEM E ATUALIDADE: o bloco de dados pode trazer o criterio da consulta "
    "(\"consulta: ordenado por <coluna> (maior/mais recente primeiro)\"). Com "
    "esse criterio a ORDEM DAS LINHAS e a resposta: a PRIMEIRA linha e o maior/"
    "mais recente e voce PODE afirmar isso, sem ressalva de ordenacao. Sem o "
    "criterio, nao afirme ser 'o mais recente', 'o ultimo', 'o primeiro', 'o "
    "maior' ou 'o principal' (consulta sem ORDER BY ou lista sem ranking): "
    "apresente os itens como estao e diga que a consulta nao trouxe essa "
    "ordenacao. EMPATE: se o topo vier com contagens iguais entre si (ou a "
    "contagem for 1), o que existe e EMPATE — diga que ha empate e quantos itens "
    "(e qual e a contagem de cada um); NUNCA apresente um registro como unico "
    "vencedor.\n"
)

# Atribuicao por origem (v0.11.11). Medido no trace #340: dois conectores
# devolveram um campo "endereço" (o SQL do Sakila trouxe o endereço do cliente; o
# conector de CEP trouxe a rua do CEP) e a resposta deu a rua do CEP usando o valor
# do OUTRO bloco. O rotulo do bloco existe justamente para isso: o dado responde a
# parte da pergunta correspondente ao conector que o trouxe.
_DIRETIVA_ATRIBUICAO = (
    "ORIGEM DO DADO: cada bloco de dados vem rotulado com o worker/area/conector "
    "que o produziu. Use cada valor para a parte da pergunta que aquele conector "
    "responde — nunca troque o dado de um conector pelo de outro, mesmo que dois "
    "blocos tenham um campo com o mesmo nome (ex.: um endereco que veio do "
    "conector de CEP responde a pergunta de CEP; o endereco que veio da consulta "
    "SQL responde a pergunta do cliente). Cite a origem (area ou conector) SOMENTE "
    "quando for preciso separar duas respostas parecidas — e cite o nome de "
    "negocio, nao o interno. NAO reproduza o SQL, o nome da tool nem o texto do "
    "bloco na resposta, e nao comece a resposta anunciando o conector executado.\n"
)


def _resultado_vazio(resultado) -> bool:
    """True quando o conector respondeu mas SEM dado util (B6, v0.11.9).

    Nulo nao e dado: `{"sum": null}`, `[]`, `{}` ou lista de vazios significam
    "a consulta rodou e nao trouxe valor". O modelo tratava isso como numeros
    disponiveis e completava por conta propria. Zero e vazio sao coisas
    diferentes: `{"sum": 0}` e RESPOSTA (devolve False aqui).
    """
    if resultado is None:
        return True
    if isinstance(resultado, str):
        return resultado.strip() in ("", "[]", "{}", "null", "None")
    if isinstance(resultado, (list, tuple)):
        return len(resultado) == 0 or all(_resultado_vazio(x) for x in resultado)
    if isinstance(resultado, dict):
        return not resultado or all(_resultado_vazio(v) for v in resultado.values())
    return False


def _skills_blocos(skills_csv: str) -> tuple[str, list[str]]:
    """(bloco de instrucao, nomes que NAO resolveram) das skills do agente.

    Envia nome + descricao + CORPO do SKILL.md (via ler_skill: banco primeiro,
    arquivo como fallback). O corpo e parte da instrucao — sem ele o modelo so
    via a descricao e ignorava regras de formato/comportamento escritas no
    corpo (ex.: "responda apenas texto, sem tabelas nem figuras").

    Um nome que nao resolve era ignorado em SILENCIO (continue mudo): o agente
    perdia as instrucoes e continuava respondendo normalmente, sem log nem
    aviso. Agora o nome volta na segunda posicao da tupla — vai para o tracing
    e para a tela do agente.
    """
    nomes = [s.strip().lower() for s in (skills_csv or "").split(",") if s.strip()]
    limite = _skill_body_max()
    partes: list[str] = []
    ausentes: list[str] = []
    for n in nomes:
        s = ler_skill(n)
        if not s:
            ausentes.append(n)
            continue
        desc = (s.get("description") or "").strip() or n
        corpo = (s.get("body") or "").strip()
        bloco = f"### Skill: {n}\nDescricao: {desc}"
        if corpo:
            if len(corpo) > limite:
                bloco += "\n" + corpo[:limite] + "\n[...corpo truncado...]"
            else:
                bloco += "\n" + corpo
        partes.append(bloco)
    return "\n\n".join(partes), ausentes


def _skills_text(skills_csv: str) -> str:
    """Bloco de instrucao das skills (so o texto) — ver _skills_blocos."""
    return _skills_blocos(skills_csv)[0]


def skills_ausentes(skills_csv: str) -> list[str]:
    """Nomes do CSV do agente que nao resolvem (nem no banco, nem no catalogo)."""
    return _skills_blocos(skills_csv)[1]


def agentes_com_skill(nome: str) -> list[str]:
    """Nomes dos agentes que usam a skill (integridade referencial).

    `agentes.skills` e um CSV de nomes SEM chave estrangeira: nada impedia
    apagar uma skill EM USO — e ai o agente ficava com referencia pendurada
    (as instrucoes sumiam do prompt sem erro, ou caiam numa copia do arquivo
    embarcado e MUDavam de conteudo sem aviso). Compara TOKEN a token do CSV,
    nunca substring — senao 'rh' casaria com 'rh_normas'.
    """
    alvo = (nome or "").strip().lower()
    if not alvo:
        return []
    usam = []
    for a in db.listar_agentes():
        nomes = [s.strip().lower() for s in (a.get("skills") or "").split(",") if s.strip()]
        if alvo in nomes:
            usam.append(a.get("nome") or f"#{a.get('id')}")
    return usam


def _pede_grafico(pergunta: str) -> bool:
    """True se o usuario pediu um grafico/visualizacao."""
    p = " " + pergunta.lower().strip()
    return any(m in p for m in (
        " grafico", " gráfico", " pizza", " barras", " barra", " linha de ",
        " tendencia", " tendência", " visualiz", " chart", " graficamente",
    ))


def _resumo_dados(ferramentas: list[dict], max_linhas: int = 20) -> str:
    """Resumo compacto dos dados dos conectores para o LLM especificador."""
    blocos = []
    for f in ferramentas:
        if "erro" in f or not f.get("resultado"):
            continue
        res = f.get("resultado")
        linhas = []
        if isinstance(res, list):
            for r in res:
                # resultado da sql:analise vem em blocos {"sql", "linhas"}
                if isinstance(r, dict) and "linhas" in r:
                    linhas.extend(r["linhas"][:max_linhas])
                else:
                    linhas.append(r)
        else:
            linhas.append(res)
        txt = "\n".join(str(x)[:200] for x in linhas[:max_linhas])
        blocos.append(f"[{f.get('conector')}.{f.get('tool')}]\n{txt}")
    return "\n".join(blocos)[:3000]


def _especificar_grafico(pergunta: str, resumo: str, modelo: dict) -> str | None:
    """LLM especificador: dados reais -> spec JSON {tipo, titulo, dados}."""
    from . import llm_client
    mensagens = [
        {"role": "system", "content": (
            "Voce transforma dados em especificacao de grafico. Responda APENAS "
            "um JSON valido, sem markdown, sem explicacoes: "
            "{\"tipo\": \"barras\"|\"pizza\"|\"linha\", \"titulo\": \"...\", "
            "\"dados\": [{\"rotulo\": \"...\", \"valor\": 123}]}. "
            "Use APENAS os valores dos DADOS fornecidos (nunca invente). "
            "Maximo 20 pontos. Tipo: pizza para proporcoes, barras para "
            "comparacao/ranking, linha para tendencia.")},
        {"role": "user", "content": f"PEDIDO: {pergunta}\n\nDADOS:\n{resumo}\n\nJSON:"},
    ]
    out = llm_client.chat(modelo, mensagens, max_tokens=250, temperatura=0.0)
    if not out.get("ok"):
        return None
    return (out.get("content") or "").strip() or None


def _mascarar_spec_rotulos(spec: str, lgpd_cfg: dict) -> str:
    """Aplica as mascaras LGPD nos ROTULOS do spec do grafico.

    A imagem e saida — precisa respeitar a mesma politica de mascara do
    texto (senao nomes/emails pessoais vazariam completos na imagem).
    """
    from . import mask as _mask_mod
    try:
        d = _json.loads(spec) if isinstance(spec, str) else spec
        if not isinstance(d, dict):
            return spec
        for item in d.get("dados") or []:
            if isinstance(item, dict) and item.get("rotulo"):
                item["rotulo"] = _mask_mod.aplicar_mascaras(str(item["rotulo"]), lgpd_cfg)
        return _json.dumps(d, ensure_ascii=False)
    except Exception:  # noqa: BLE001 — mascara e best-effort
        return spec


def _modelo_da_env(var: str) -> dict | None:
    """Resolve o modelo apontado por uma variavel de ambiente.

    Aceita o ID numerico OU o nome exibido na tela Modelos IA (o nome e o que
    o operador tem a mao — o ID muda de instalacao para instalacao). Vazio ou
    nao encontrado devolve None: quem chama decide o padrao. Infra (env) e
    nao configuracao de negocio, por isso nao e coluna no banco.
    """
    import os as _os
    valor = (_os.environ.get(var, "") or "").strip()
    if not valor:
        return None
    if valor.isdigit():
        return db.buscar_modelo(int(valor))
    alvo = valor.lower()
    return next((m for m in db.listar_modelos()
                 if (m.get("nome") or "").lower() == alvo), None)


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


def _extrair_parametros_por_placeholders(pergunta: str, placeholders: set[str]) -> dict:
    """Extrai 'chave valor' / 'chave: valor' / 'chave=valor' para os placeholders
    dos conectores escolhidos (P1).

    Generico: a definicao do conector (URL/args/query) e a fonte das chaves —
    nenhuma lista hardcoded de campos. Cobre 'cep 03679040', 'cep: 03679-040',
    'id 58', 'pedido PED-99', etc. O valor vira string (sem normalizacao).
    """
    params: dict[str, str] = {}
    for ph in sorted(placeholders):
        if ph in params:
            continue
        # chave=valor ou chave: valor (token sem espaco)
        m = re.search(rf"\b{re.escape(ph)}\b\s*[=:]\s*(\S+)", pergunta, re.IGNORECASE)
        if not m:
            # chave + numero (com hifen/ponto: 03679-040, 58, 12.345)
            m = re.search(rf"\b{re.escape(ph)}\b\s+(\d[\d.\-]*)", pergunta, re.IGNORECASE)
        if m:
            valor = m.group(1).strip().rstrip(".,;!?\"'")
            if valor:
                params[ph] = valor
    return params


def _extrair_parametros_ia(pergunta: str, placeholders: set[str],
                           modelo: dict) -> dict | None:
    """Extrai parametros da pergunta via IA (linguagem natural).

    Complementa o regex (P1): cobre variacoes que o determinismo nao
    reconhece (ex: \\"id cliente igual a 58\\"). Retorna dict ou None
    (falha — o chamador segue sem os parametros).

    Robusto a modelo (P2): max_tokens generoso (256) + retry automatico com
    512 se a resposta vier vazia ou com JSON invalido + exemplo few-shot no
    prompt. Nao depende de ajuste manual de max_tokens por modelo.
    """
    if not placeholders:
        return None
    lista = ", ".join(sorted(placeholders))
    from . import llm_client
    system = (
        "Voce extrai parametros de uma pergunta do usuario para chamadas de "
        "ferramentas. Retorne APENAS um JSON valido com os valores encontrados "
        "(strings). Se nenhum parametro for encontrado, retorne {}.\n"
        "Exemplo: pergunta 'qual o endereco do cep 03679-040?' com parametros "
        "[cep] -> {\"cep\": \"03679040\"}.\n"
        "Nao escreva texto fora do JSON."
    )
    mensagens = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Pergunta: {pergunta}\n\nParametros disponiveis: {lista}\n\nJSON:"},
    ]
    for mt in (256, 512):
        out = llm_client.chat(modelo, mensagens, max_tokens=mt, temperatura=0.0)
        if not out.get("ok"):
            return None
        texto = (out.get("content") or "").strip()
        # limpa cercas ```json ... ```
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        if not m:
            continue
        try:
            dados = _json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(dados, dict):
            continue
        return {str(k): str(v) for k, v in dados.items() if v is not None and str(v).strip()}
    return None


def _selecionar_conectores(pergunta: str, conectores: list[dict],
                           modelo_roteador: dict) -> tuple[list[int] | None, str | None]:
    """Roteia conectores por relevancia E classifica a intencao da pergunta.

    Retorno: (ids, intencao)
      ([]  , _)    -> nenhum conector relevante (responde so com RAG)
      ([ids], _)   -> executar apenas estes conectores
      (None, _)    -> falha na selecao -> executa TODOS (comportamento antigo)
      intencao     -> "analise" | "dado" | None (None = nao classificou; o
                      motor cai no marcador lexico como fallback)

    A intencao decide o caminho do conector SQL: analise -> SELECT dinamico
    sobre o schema real; dado -> query fixa (rapida e exata). A classificacao
    viaja no MESMO voto do roteador (custo zero de latencia) e e robusta a
    flexao do verbo ("liste", "lista", "mostre"), que a lista lexica errava.

    Conectores SEM descricao nunca sao excluidos (entram sempre).
    """
    if not conectores:
        # Tupla, nao lista: o chamador desempacota (ids, intencao). Devolver
        # lista aqui estourava "not enough values to unpack" — que o except
        # do chamador transformava em erro visivel no prompt por um motivo
        # que nao era erro nenhum (area sem conector ativo).
        return [], None
    from ..connector_pack import registry as _reg
    sempre = [c["id"] for c in conectores if not (_reg._parse_config(c.get("config", "{}")).get("descricao") or "").strip()]
    com_desc = [c for c in conectores if (_reg._parse_config(c.get("config", "{}")).get("descricao") or "").strip()]
    if not com_desc:
        # tudo sem descricao -> executa tudo (mesma correcao de tupla acima)
        return [c["id"] for c in conectores], None
    linhas = "\n".join(
        f"{i+1}. {c['nome']} ({c['tipo']}) — {_reg._parse_config(c.get('config', '{}')).get('descricao', '')[:120]}"
        for i, c in enumerate(com_desc)
    )
    from . import llm_client
    mensagens = [
        {"role": "system", "content": (
            "Voce e o roteador de ferramentas de um agente de IA corporativo. "
            "Escolha UMA opcao da lista que ajudaria a responder a pergunta do "
            "usuario e classifique a INTENCAO dela. Responda APENAS no formato "
            "'<numero> <dado|analise>' — exemplo: '3 analise'. Use 'dado' para "
            "pedido de dado especifico, cadastro, consulta pontual ou lista "
            "simples; use 'analise' para analise, agregacao, ranking, "
            "comparacao, contagem ('quantos'), media, total, resumo ou "
            "distribuicao. Se nenhuma opcao ajudar, use 0 (ex.: '0 dado').")},
        {"role": "user", "content": f"Pergunta: {pergunta}\n\nOpcoes:\n0. nenhum\n{linhas}\n\nNumero:"},
    ]
    out = None
    import re as _re
    # Voto majoritario: 3 tentativas — modelos (principalmente externos com
    # reasoning) sao NAO-DETERMINISTICOS mesmo com temperatura 0.0. A
    # resposta valida e a que se repete; incompreensivel/erro nao e voto.
    votos: list = []  # "nenhum" | id(int) | None(incompreensivel)
    votos_int: list = []  # "analise" | "dado" (por voto valido)
    for _ in range(3):
        # max_tokens generoso + retry (mesmo tratamento do extrator P2):
        # modelos locais (ex: 9B llama.cpp) devolvem VAZIO com max_tokens=100
        # e o roteador cairia em falha -> None -> executa todos sem params.
        out = None
        for mt in (256, 512):
            out = llm_client.chat(modelo_roteador, mensagens, max_tokens=mt, temperatura=0.0)
            if out.get("ok") and (out.get("content") or "").strip():
                break
        if not out or not out.get("ok"):
            votos.append(None)
            continue
        texto = (out.get("content") or "").strip().lower()
        nums = [int(n) for n in _re.findall(r"\d+", texto)]
        # intencao: normaliza acento ("análise" nao casaria com "analis" cru)
        import unicodedata as _unic
        _sacento = _unic.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
        if "analis" in _sacento:
            votos_int.append("analise")
        elif "dado" in _sacento:
            votos_int.append("dado")
        if "nenhum" in texto or 0 in nums:
            votos.append("nenhum")
        else:
            sel = [com_desc[i - 1]["id"] for i in nums if 1 <= i <= len(com_desc)]
            votos.append(sel[0] if sel else None)
    # intencao: maioria simples; empate -> "dado" (caminho deterministico)
    intencao = None
    if votos_int:
        n_an = votos_int.count("analise")
        n_da = votos_int.count("dado")
        if n_an > n_da:
            intencao = "analise"
        elif n_da:
            intencao = "dado"

    ids_ok = {v for v in votos if isinstance(v, int)}
    viu_nenhum = "nenhum" in votos
    if ids_ok and not viu_nenhum:
        return sorted(set(sempre + list(ids_ok))), intencao
    if viu_nenhum and not ids_ok:
        # Reforco por NOME: se o nome de um conector aparece na pergunta,
        # executa mesmo assim (match deterministico e forte — ex: "CEP").
        pergunta_l = pergunta.lower()
        reforco = [c["id"] for c in com_desc if c["nome"].lower() in pergunta_l]
        return sorted(set(sempre + reforco)), intencao
    return None, intencao  # ambiguo ou falha total -> executa todos (seguro)


# --------------------------------------------------------------------------- #
# Mestre + workers (v0.11.11)                                                 #
# --------------------------------------------------------------------------- #
# Um agente "mestre" pode orquestrar uma lista ORDENADA de agentes workers.
# Decisoes (com o Nei):
#   - sem workers = comportamento atual, ZERO mudanca;
#   - worker e FOLHA (profundidade 1): nunca dispara outro worker;
#   - workers rodam em PARALELO, com teto de simultaneidade; a ORDEM do cadastro
#     decide a APRESENTACAO (blocos e trace) e nunca a ordem de conclusao —
#     blocos em ordem variavel mudam o prompt e a resposta para a MESMA pergunta;
#   - transporte do worker = CHAMADA DE FUNCAO (mesmo processo, mesmo banco).
#     O conector `api` para o gateway/portal exigiria 1 canal + 1 gateway por
#     worker (e cairia SILENCIOSAMENTE em outro agente se o worker nao estivesse
#     publicado), rodaria o responder() inteiro (~2 LLM por worker + memoria +
#     trace) e nao permite pedir "so conectores";
#   - modo worker = SO os conectores da area do worker: sem RAG, sem LLM final,
#     sem memoria de conversa, sem trace proprio. Custo = 1 consulta inteligente.
_MAX_WORKERS_CONCORRENTES = 3   # teto de simultaneidade (LLM local costuma ter 1 slot)
_MAX_WORKERS_AVISO = 5          # acima disso a tela avisa (quem monta decide)
_MAX_WORKERS_LIMITE = 10        # corte duro no cadastro
_WORKER_TIMEOUT_S = 60          # teto por worker: o que nao termina vira bloco honesto

# Skill PROPRIA do worker (v0.11.11). O agente sozinho nao muda; quando um worker
# TEM skill, ela governa o que ele ENTREGA: o worker le os dados brutos da area
# dele e devolve um bloco organizado para o mestre. Sao +1 chamada de LLM por
# worker COM skill (worker sem skill = zero chamada, comportamento de antes).
_WORKER_LEITURA_TOKENS = 400    # teto da leitura organizada (curta de proposito)
_WORKER_LEITURA_CHARS = 1200    # teto do que a leitura ocupa no prompt do mestre
# As leituras dos workers vao UMA POR VEZ: o dado bruto de cada worker continua em
# paralelo, mas a chamada de leitura e serializada. Motivo medido (trace #357/#358):
# com dois workers lendo ao mesmo tempo num servidor local de UM slot o segundo
# recebe HTTP 500 e o worker volta SEM leitura. Serializar custa ~1 leitura por
# worker e devolve a leitura de todos (comportamento correto > paralelismo aqui).
_LEITURA_LOCK = threading.Lock()


def workers_do_agente(agente: dict) -> list[int]:
    """IDs da lista ORDENADA `workers` (CSV). Ignora lixo e repetidos."""
    vistos: set[int] = set()
    ids: list[int] = []
    for parte in (agente.get("workers") or "").split(","):
        parte = parte.strip()
        if not parte.isdigit():
            continue
        wid = int(parte)
        if wid not in vistos:
            vistos.add(wid)
            ids.append(wid)
    return ids


def agentes_que_usam_worker(wid: int) -> list[str]:
    """Nomes dos agentes cujo `workers` cita este ID (integridade ao excluir).

    `agentes.workers` e CSV sem chave estrangeira: sem esta checagem, excluir um
    worker deixaria um ID pendurado na lista do mestre (o worker simplesmente
    pararia de existir no meio da cadeia, sem aviso).
    """
    usam = []
    for a in db.listar_agentes():
        if wid in workers_do_agente(a):
            usam.append(a.get("nome") or f"#{a.get('id')}")
    return usam


def mestre_do_worker(wid: int, cliente_id: int | None = None) -> dict | None:
    """Mestre que orquestra este agente (None = ele não é worker de ninguém).

    Usado na tela do agente (esconder o card de workers e mostrar o caminho de
    volta) e nas rotas de worker (worker é folha: não pode virar mestre).
    """
    for a in db.listar_agentes(cliente_id=cliente_id):
        if wid in workers_do_agente(a):
            return a
    return None


def papeis_workers(agentes: list[dict]) -> tuple[dict[int, dict], dict[int, int]]:
    """(worker_id -> mestre, mestre_id -> quantos workers) em UMA passada.

    A listagem de agentes mostra as duas etiquetas ("mestre de N" / "worker de
    X"): com uma consulta por linha seriam N+1 varreduras de `agentes`.
    """
    mestre_de: dict[int, dict] = {}
    contagem: dict[int, int] = {}
    for a in agentes:
        ids = workers_do_agente(a)
        if not ids:
            continue
        contagem[a["id"]] = len(ids)
        for wid in ids:
            mestre_de.setdefault(wid, a)
    return mestre_de, contagem


def validar_workers(mestre_id: int | None, cliente_id: int, ids: list[int]) -> list[str]:
    """Erros de cadastro da lista de workers (lista vazia = tudo certo).

    Bloqueia: worker inexistente, de outro cliente, o proprio mestre, worker que
    ja tem workers (folha — senao "sem limite" vira grafo/ciclo e recursao) e
    lista acima do teto. Avisos (pausado/sem area/sem conector/area repetida)
    NAO entram aqui: aparecem na tela e nao impedem o cadastro.
    """
    erros: list[str] = []
    if len(ids) > _MAX_WORKERS_LIMITE:
        erros.append(f"no máximo {_MAX_WORKERS_LIMITE} workers por agente")
    for wid in ids:
        if mestre_id and wid == mestre_id:
            erros.append("um agente não pode ser worker de si mesmo")
            continue
        w = db.buscar_agente(wid)
        if not w:
            erros.append(f"worker #{wid} não existe")
            continue
        if w.get("cliente_id") != cliente_id:
            erros.append(f"worker '{w.get('nome')}' é de outro cliente")
            continue
        if workers_do_agente(w):
            erros.append(f"worker '{w.get('nome')}' já é um mestre "
                         "(worker não pode ter workers — profundidade 1)")
    return erros


def avisos_workers(mestre: dict | None, ids: list[int]) -> list[str]:
    """Avisos que NAO bloqueiam o cadastro (regra de operacao, nao de banco).

    Voz nao entra no codigo: a plataforma nao tem marca de "agente de voz" (o
    CL_Fone e cliente externo do gateway), entao a regra "voz sem worker" e
    operacional e documentada — aqui so o que da para conferir no cadastro.
    """
    avisos: list[str] = []
    if not ids:
        return avisos
    if len(ids) > _MAX_WORKERS_AVISO:
        avisos.append(f"{len(ids)} workers: cada um é uma consulta à fonte e o "
                      "mestre só responde depois do mais lento")
    mestre_id = (mestre or {}).get("id")
    area_mestre = ((mestre or {}).get("area") or "").strip()
    if mestre_id and area_mestre:
        ativos = [c for c in db.listar_conectores(cliente_id=(mestre or {}).get("cliente_id"),
                                                  area=area_mestre) if c.get("ativo", 1)]
        if ativos:
            avisos.append(
                f"a área '{area_mestre}' do mestre tem {len(ativos)} conector(es) "
                "ativo(s): o mestre VAI executá-los também, além dos workers "
                "(para mestre só despachante, use uma área sem conectores)")
    areas: dict[str, list[str]] = {}
    for wid in ids:
        w = db.buscar_agente(wid)
        if not w:
            continue
        nome = w.get("nome") or f"#{wid}"
        if (w.get("status") or "ativo") == "pausado":
            avisos.append(f"worker '{nome}' está PAUSADO — não será consultado")
        area = (w.get("area") or "").strip()
        if not area:
            avisos.append(f"worker '{nome}' está sem área — não há conector para ele")
        else:
            if not [c for c in db.listar_conectores(cliente_id=w["cliente_id"], area=area)
                    if c.get("ativo", 1)]:
                avisos.append(f"worker '{nome}': a área '{area}' não tem conector "
                              "ativo — ele volta sem dados")
            areas.setdefault(area, []).append(nome)
    for area, nomes in areas.items():
        if len(nomes) > 1:
            avisos.append(f"workers na mesma área '{area}' ({', '.join(nomes)}) "
                          "consultam os MESMOS conectores — consulta repetida")
    return avisos


def _origem_da_ferramenta(f: dict) -> str:
    """Rotulo de origem de um bloco: `WORKER 1: X (area) | conector 'Y'`.

    Sem worker (conector do proprio agente) devolve so o conector — o texto que
    ja existia, para o caso sem workers nao mudar nada. Com worker, o motivo do
    descarte passa a dizer DE QUEM foi: era o buraco que deixava o mestre atribuir
    a falta de parametro de um worker (ex.: Airbnb) a resposta de outro dominio.
    """
    w = f.get("worker")
    c = f.get("conector")
    if w and c:
        return f"{w} | conector '{c}'"
    return str(c or w or "conector")


def _leitura_do_worker(worker: dict, pergunta: str, ferramentas: list[dict],
                       modelo: dict | None) -> tuple[str, str, dict]:
    """Skill PROPRIA do worker: organiza os dados da area antes de entregar ao mestre.

    O agente sozinho NAO muda (quem escreve a resposta ao usuario e sempre o
    agente/mestre, com a skill DELE). Quando o worker TEM skill, ela passa a
    governar o que ele entrega: ele le os dados brutos da area e devolve um bloco
    organizado (ordem, agrupamento, rotulo, o que faltou).

    O dado BRUTO continua indo junto para o mestre: e a auditoria (o Rastreio
    mostra os dois) e o guard de honestidade — se a leitura inventasse, o numero
    bruto esta no mesmo bloco para desmentir.

    Devolve (leitura, erro, tokens). Sem skill no worker: ("", "", {}) — nenhuma
    chamada extra, comportamento identico ao que ja existia.
    """
    if not (worker.get("skills") or "").strip():
        return "", "", {}
    skill_txt, ausentes = _skills_blocos(worker["skills"])
    if ausentes:
        # Skill que nao resolve e configuracao quebrada: o worker volta com o dado
        # bruto (que ja esta no bloco) e o motivo vai para o prompt e o Rastreio.
        return "", f"skill do worker nao encontrada: {', '.join(ausentes)}", {}
    if not modelo:
        return "", "worker com skill, mas sem modelo (o mestre nao tem modelo)", {}
    _d = _blocos_dados(ferramentas)
    if not _d["blocos"]:
        # sem dado do conector nao ha o que organizar; o guard do prompt do mestre
        # (motivo/sem dados) ja conta a verdade — nao gastamos LLM a toa.
        return "", "", {}
    nome = worker.get("nome") or f"#{worker.get('id')}"
    area = (worker.get("area") or "").strip()
    system = (
        f"Voce e o agente '{nome}' (area '{area}') da empresa. Voce NAO responde "
        "ao usuario final: voce ORGANIZA os dados da sua area e devolve para o "
        "agente que responde ao usuario. Aplique a SUA SKILL aos dados abaixo.\n\n"
        "FORMATO DA SUA RESPOSTA: escreva APENAS o dado da sua area em texto "
        "corrido e curto (no maximo 10 linhas), como voce contaria para um "
        "colega. NUNCA copie o bloco de dados recebido, nunca escreva 'args=', "
        "'->', JSON, chaves ou o SQL, e nao repita o nome interno do conector; "
        "nao explique seu raciocinio. Se os dados da sua area nao tem nada a ver "
        "com a pergunta, responda exatamente: fora da minha area.\n\n"
        "SKILLS DO WORKER (as regras abaixo DEVEM ser seguidas):\n"
        + skill_txt + "\n\n" + _DIRETIVA_DADOS_AUSENTES + _DIRETIVA_ORDEM_NAO_AFIRMADA
    )
    avisos: list[str] = []
    if _d["motivos"]:
        avisos.append("conectores nao executados: " + "; ".join(_d["motivos"]))
    if _d["ausentes"]:
        avisos.append("faltou informar: " + ", ".join(sorted(set(_d["ausentes"]))))
    if _d["sem_dados"]:
        avisos.append("a consulta rodou e voltou SEM valores: " + ", ".join(_d["sem_dados"]))
    user = (f"PERGUNTA DO USUARIO: {pergunta}\n\nDADOS DA SUA AREA:\n"
            + "\n".join(_d["blocos"])
            + ("\n\nAVISOS:\n" + "\n".join(avisos) if avisos else "")
            + "\n\nDevolva APENAS o dado da sua area organizado pela sua skill:")
    # RETRY com teto maior e ESPERA: modelo local devolve VAZIO com max_tokens
    # curto e devolve HTTP 500 quando esta ocupado (mesmo tratamento do extrator
    # P2 e do roteador). Medido no trace #357: a leitura do worker de CEP voltou
    # vazia/500 e virava erro na tela — sem retry, um worker com skill ia a zero
    # por causa de uma resposta vazia do modelo ou de um pico no servidor.
    conteudo, tokens, _erro_llm = "", {}, ""
    for _i, _mt in enumerate((_WORKER_LEITURA_TOKENS, _WORKER_LEITURA_TOKENS * 2,
                              _WORKER_LEITURA_TOKENS * 2)):
        if _i:
            time.sleep(0.6 * _i)  # espera o servidor de IA liberar (1 slot)
        with _LEITURA_LOCK:  # uma leitura por vez (servidor de LLM com 1 slot)
            out = llm_client.chat(
                modelo, [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
                max_tokens=_mt, temperatura=0.0)
        tokens = _somar_tokens(tokens, out.get("tokens") or {})
        conteudo = (out.get("content") or "").strip()
        if out.get("ok") and conteudo:
            break
        _erro_llm = out.get("erro") or out.get("error") or ""
    if not conteudo:
        return "", ("leitura pela skill falhou: o modelo nao devolveu texto "
                    f"({_erro_llm or 'resposta vazia'}) — o dado bruto da area foi "
                    "entregue ao mestre"), tokens
    return conteudo[:_WORKER_LEITURA_CHARS], "", tokens


def executar_worker(agente_worker: dict, pergunta: str, params: dict,
                    modelo_sql: dict | None, modelo_escalada: dict | None) -> dict:
    """Modo worker: SO os conectores da area do worker. Devolve o bloco de dados.

    A LEITURA pela skill propria do worker NAO acontece aqui: ela roda na fase 2
    de `_executar_workers`, depois que TODOS os workers terminaram os conectores
    (o passo de leitura e LLM e, sobreposto a geracao de SQL de outro worker, o
    servidor de um slot devolvia HTTP 500 — medido nos traces #357/#359).

    Roda na thread do worker (o acumulador de tokens do caminho SQL e por thread,
    por isso a leitura aqui). Nao grava memoria/trace e nao roda RAG nem LLM
    final: quem consolida e o mestre, uma unica vez.
    """
    from ..connector_pack import registry
    nome = agente_worker.get("nome") or f"#{agente_worker.get('id')}"
    area = (agente_worker.get("area") or "").strip()
    if (agente_worker.get("status") or "ativo") == "pausado":
        return {"nome": nome, "area": area, "ferramentas": [],
                "erro": "worker pausado — nenhuma consulta foi feita", "ms": 0,
                "tokens": {}}
    if not area:
        return {"nome": nome, "area": area, "ferramentas": [],
                "erro": "worker sem área — nenhum conector aplicável", "ms": 0,
                "tokens": {}}
    _t0 = time.time()
    erro = ""
    try:
        ferramentas = registry.executar_conectores_area(
            agente_worker["cliente_id"], area, pergunta, parametros=dict(params or {}),
            somente_ids=None, modelo=modelo_sql, intencao=None,
            modelo_escalada=modelo_escalada)
    except Exception as e:  # noqa: BLE001 — worker que falha vira BLOCO, nao excecao
        ferramentas, erro = [], str(e)
    return {"nome": nome, "area": area, "ferramentas": ferramentas, "erro": erro,
            "tokens": registry.consumir_tokens_sql(),
            "ms": int((time.time() - _t0) * 1000)}


def _executar_workers(mestre: dict, pergunta: str, params: dict,
                      modelo_sql: dict | None, modelo_escalada: dict | None,
                      modelo_mestre: dict | None = None) -> list[dict]:
    """Roda os workers em PARALELO e devolve os resultados NA ORDEM declarada.

    Teto de simultaneidade (`_MAX_WORKERS_CONCORRENTES`): o gargalo real e o
    servidor de LLM (a consulta inteligente de cada worker) e o banco do cliente
    — N conexoes simultaneas num ERP licenciado por sessao nao e detalhe. Teto
    por worker + deadline GLOBAL: um worker travado nao segura a resposta alem do
    combinado, e o que nao terminou entra como bloco honesto (nunca como numero).
    """
    from concurrent.futures import ThreadPoolExecutor
    ids = workers_do_agente(mestre)
    if not ids:
        return []
    resultados: dict[int, dict] = {}
    fila: list[tuple[int, dict]] = []
    for i, wid in enumerate(ids):
        w = db.buscar_agente(wid)
        if w:
            fila.append((i, w))
        else:
            resultados[i] = {
                "nome": f"worker #{wid}", "area": "", "ferramentas": [], "tokens": {},
                "erro": "worker não encontrado — atualize a lista de workers do mestre",
                "ms": 0}
    _limite = time.time() + _WORKER_TIMEOUT_S
    if fila:
        pool = ThreadPoolExecutor(max_workers=min(len(fila), _MAX_WORKERS_CONCORRENTES))
        try:
            futuros = {pool.submit(executar_worker, w, pergunta, params,
                                   modelo_sql, modelo_escalada): (i, w) for i, w in fila}
            for fut, (i, w) in futuros.items():
                try:
                    resultados[i] = fut.result(timeout=max(0.0, _limite - time.time()))
                except Exception:  # noqa: BLE001 — timeout/erro do worker
                    resultados[i] = {
                        "nome": w.get("nome") or f"worker #{w.get('id')}",
                        "area": (w.get("area") or ""), "ferramentas": [], "tokens": {},
                        "erro": f"não respondeu em {_WORKER_TIMEOUT_S}s (sem dados)",
                        "ms": _WORKER_TIMEOUT_S * 1000}
        finally:
            # wait=False: thread orfa termina sozinha quando o driver expirar —
            # nunca segura a resposta do mestre (mesmo padrao do _com_timeout).
            pool.shutdown(wait=False)
    # --- FASE 2: leitura pela skill PROPRIA de cada worker -------------------
    # Depois de TODOS os conectores: a leitura e uma chamada de LLM e, quando
    # rodava dentro da thread do worker, ficava sobreposta a geracao de SQL do
    # outro worker — num servidor de um slot isso volta HTTP 500 e o worker
    # entregava sem leitura (traces #357/#359). Aqui as leituras rodam uma por
    # vez, com o dado bruto de todos ja pronto; o que nao couber no prazo entra
    # sem leitura (o dado bruto vai do mesmo jeito).
    for i, w in fila:
        r = resultados.get(i)
        if not r or r.get("erro") or not (w.get("skills") or "").strip():
            continue
        if time.time() > _limite:
            r["ferramentas"] = list(r.get("ferramentas") or []) + [{
                "conector": w.get("nome") or f"worker #{w.get('id')}",
                "tool": "skill (worker)", "skill": (w.get("skills") or "").strip(),
                "erro": "sem tempo de organizar pela skill (o dado bruto foi entregue)"}]
            continue
        leitura, erro_leitura, tok = _leitura_do_worker(
            w, pergunta, r.get("ferramentas") or [], modelo_mestre)
        r["tokens"] = _somar_tokens(r.get("tokens") or {}, tok)
        if leitura:
            r["ferramentas"] = list(r.get("ferramentas") or []) + [{
                "conector": w.get("nome") or f"worker #{w.get('id')}",
                "tool": "skill (worker)", "args": None,
                "skill": (w.get("skills") or "").strip(),
                "resultado": {"leitura": leitura}}]
        elif erro_leitura:
            r["ferramentas"] = list(r.get("ferramentas") or []) + [{
                "conector": w.get("nome") or f"worker #{w.get('id')}",
                "tool": "skill (worker)", "skill": (w.get("skills") or "").strip(),
                "erro": erro_leitura}]
    return [resultados[i] for i in range(len(ids))]


def _ferramentas_dos_workers(resultados: list[dict]) -> tuple[list[dict], dict]:
    """Converte as saidas dos workers em blocos rotulados + tokens consumidos.

    Rotulo (P2): a saida do worker entra no DADOS DE SISTEMA como
    `[WORKER n: Nome (area) | conector.tool]` — bloco rotulado, nunca o texto
    solto que disparava tool_call cru em modelo tool-tuned. Worker que falhou
    vira erro com motivo: o guard do prompt (que ja existe) conta a verdade.
    """
    ferramentas: list[dict] = []
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for i, r in enumerate(resultados, start=1):
        etiqueta = f"WORKER {i}: {r.get('nome')}" + (f" ({r['area']})" if r.get("area") else "")
        if r.get("erro"):
            ferramentas.append({"conector": etiqueta, "tipo": "worker", "erro": r["erro"]})
        for f in r.get("ferramentas") or []:
            ferramentas.append({**f, "worker": etiqueta})
        for k in tokens:
            tokens[k] += int((r.get("tokens") or {}).get(k, 0) or 0)
    return ferramentas, tokens


def _render_resultado(res, teto_chars: int = 1200) -> str:
    """Renderiza o resultado do conector como TEXTO LEGIVEL para o prompt.

    Antes o bloco ia como `args=<repr> -> <repr>` — o dump Python do resultado,
    com o SQL dentro. Medido (v0.11.11): o modelo RECITAVA esse dump na resposta
    ao usuario ("o conector X foi executado com a consulta SELECT ...") e o worker
    com skill EOAVA o bloco em vez de organizar o dado. O dump tambem gastava
    token a toa. Aqui: as chaves internas (sql/query/consulta) SAEM do prompt (o
    Rastreio continua guardando o SQL gerado), as linhas viram `coluna=valor` e o
    total e limitado por caracteres.
    """
    _ignorar = {"sql", "query", "consulta"}

    def _curto(v) -> str:
        if isinstance(v, (dict, list)):
            s = _json.dumps(v, ensure_ascii=False, default=str)
        else:
            s = str(v)
        s = " ".join(s.split())
        return s[:80] + ("…" if len(s) > 80 else "")

    def _linha(d: dict) -> str:
        return ", ".join(f"{k}={_curto(v)}" for k, v in d.items()
                         if str(k).lower() not in _ignorar)

    dados = res
    # {"sql": ..., "linhas": [...]} / {"rows": [...]} -> usa so as linhas
    if isinstance(dados, list) and len(dados) == 1 and isinstance(dados[0], dict):
        for _k in ("linhas", "rows"):
            if _k in dados[0]:
                dados = dados[0][_k]
                break
    if isinstance(dados, dict) and not any(str(k).lower() not in _ignorar for k in dados):
        return "(sem valores)"
    if isinstance(dados, list):
        if not dados:
            return "(nenhuma linha)"
        if isinstance(dados[0], dict):
            return (f"{len(dados)} linha(s): "
                    + " | ".join(_linha(d) for d in dados if isinstance(d, dict)))[:teto_chars]
        return (f"{len(dados)} valor(es): "
                + ", ".join(_curto(x) for x in dados))[:teto_chars]
    if isinstance(dados, dict):
        return _linha(dados)[:teto_chars] or "(sem valores)"
    return _curto(dados)


def _blocos_dados(ferramentas: list[dict]) -> dict:
    """Monta os blocos de DADOS DE SISTEMA e as notas de guarda do prompt.

    Extraido do bloco inline do prompt (mesma semantica, um unico lugar) para que
    os guards de honestidade — parametro ausente, motivo do descarte, resultado
    SEM DADOS e truncamento por volume — valham IGUAL para o mestre e para os
    workers. Worker rotulado entra como `[WORKER n: Nome (area) | conector.tool]`;
    worker que falhou entra como erro com motivo (nunca como numero inventado).
    """
    blocos: list[str] = []
    ausentes: list[str] = []
    ausentes_orig: list[str] = []
    motivos: list[str] = []
    sem_dados: list[str] = []
    truncado = False
    for f in ferramentas:
        if f.get("truncado"):
            truncado = True
        if "erro" in f:
            # erro vai pro trace; parametro_ausente vira AVISO no prompt
            _e = str(f.get("erro", ""))
            _orig = _origem_da_ferramenta(f)
            if _e.startswith("parametro_ausente:"):
                _ps = [x.strip() for x in _e.split(":", 1)[1].split(",") if x.strip()]
                ausentes.extend(_ps)
                # COM ORIGEM: o mestre nao pode usar a falta de parametro de um
                # worker como motivo para nao responder o que outro JA trouxe
                # (medido: "nao da para contar os filmes porque falta adults,
                # cep, checkin..." — parametros do Airbnb/CEP).
                ausentes_orig.append(f"{_orig} — falta: {', '.join(_ps)}")
            else:
                # sem isto o modelo recebia ZERO sinal e improvisava dados
                motivos.append(f"{_orig}: {f.get('motivo') or _e}")
            continue
        if f.get("motivo"):
            motivos.append(f"{_origem_da_ferramenta(f)}: {f['motivo']}")
        _vazio = _resultado_vazio(f.get("resultado"))
        if _vazio:
            # v0.11.9 / B6 — o resultado sem valores precisa ser DITO no
            # bloco: `{"sum": null}` sozinho o modelo lia como "sem
            # informacao" e completava o numero que faltava.
            sem_dados.append(str(f.get("conector") or "conector"))
        _rot = f"{f['worker']} | " if f.get("worker") else ""
        _tool = f" · {f.get('tool')}" if f.get("tool") else ""
        # criterio da consulta (ordenacao/limite/agregacao) SEM o texto do SQL:
        # e o que autoriza a resposta a afirmar "o mais recente" (e a nao afirmar
        # quando o bloco nao traz ordenacao)
        _crit = str(f.get("criterio") or "").strip()
        blocos.append(f"[{_rot}{f.get('conector')}{_tool}] "
                      + (f"(consulta: {_crit}) " if _crit else "")
                      + _render_resultado(f.get("resultado"))
                      + (" (SEM DADOS: a consulta rodou e nao retornou valores)"
                         if _vazio else ""))
    return {"blocos": blocos, "ausentes": ausentes, "ausentes_orig": ausentes_orig,
            "motivos": motivos,
            "sem_dados": sem_dados, "truncado": truncado}


def _tokens_sql_da_thread() -> dict:
    """Le (e zera) o consumo de tokens do caminho SQL da thread atual."""
    from ..connector_pack import registry
    return registry.consumir_tokens_sql()


def _somar_tokens(*fontes: dict) -> dict:
    """Soma acumuladores de tokens do caminho SQL (mestre + cada worker)."""
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for f in fontes:
        for k in total:
            total[k] += int((f or {}).get(k, 0) or 0)
    return total


def responder(agente: dict, pergunta: str, usuario: str, id_cliente: str = "",
              anonimizar: bool = True, contexto_extra: str = "",
              tools: list | None = None, tool_choice=None,
              tool_results: list | None = None) -> dict:
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

    contexto_extra: opcional (chats externos via gateway). Mensagens
    anteriores da conversa — entram APENAS no prompt do LLM (para o
    modelo entender referencias tipo "e o dele?"). NAO afeta roteador/
    extrator/RAG e NAO é gravado no trace/memória — lá fica a pergunta
    real (última mensagem).
    """
    import time as _time
    _t0 = _time.time()
    # Marcos de tempo por fase (ms) — preenchem o trace (instrumentacao de
    # latencia: roteador / conectores / rag / llm separados do total).
    _ms_rot = _ms_conn = _ms_rag = _ms_llm = 0.0
    _marca = _t0
    cliente_id = agente["cliente_id"]
    # Agente pausado nao atende (portal, API e gateway passam por aqui).
    if (agente.get("status") or "ativo") == "pausado":
        return {"ok": False, "content": "", "model": None, "model_fallback": False,
                "error": "Agente pausado — reative na tela Agentes para voltar a atender.",
                "contexto": [], "ferramentas": []}
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
            modelo_roteador = _modelo_da_env("BLUESHIFT_ROUTER_MODEL") or modelo
            # ── Modelo da CONSULTA INTELIGENTE (text-to-SQL) ──
            # Default = o mesmo do roteador (comportamento de sempre). O
            # modelo PRINCIPAL do agente entra como escalada automatica, so
            # quando a tentativa configurada nao entrega linha — medido: o
            # pequeno acerta as consultas simples e erra as pesadas por
            # inventar coluna, e o principal faz 8/8 (a ~10s por consulta).
            modelo_sql = _modelo_da_env("BLUESHIFT_SQL_MODEL") or modelo_roteador
            # Conectores inativos (ativo=0) ficam FORA do pipeline: nao entram
            # nas opcoes do roteador (nao gastam voto) nem sao executados.
            conectores_area = [c for c in db.listar_conectores(cliente_id=cliente_id, area=area)
                               if c.get("ativo", 1)]
            _marca = _time.time()  # inicio: roteador (3 votos + extracao IA)
            somente_ids, intencao = _selecionar_conectores(pergunta, conectores_area,
                                                           modelo_roteador)
            # P1: determinístico por placeholder — roda SEMPRE, inclusive quando
            # o roteador falha (None -> executa TODOS os conectores da área):
            # ph = placeholders dos escolhidos ou de todos da área. A definição
            # do conector é a fonte das chaves ("cep 03679040", "cep: x",
            # "id 58"); custo zero.
            ph = _placeholders_conectores(conectores_area, somente_ids)
            params_ph = _extrair_parametros_por_placeholders(pergunta, ph)
            for k, v in params_ph.items():
                if k not in params:
                    params[k] = v
            if somente_ids:
                # P2: IA completa o que o determinismo não pegou (robusto a
                # modelo — retry automático, sem ajuste de max_tokens)
                params_ia = _extrair_parametros_ia(pergunta, ph, modelo_roteador)
                if params_ia:
                    for k, v in params_ia.items():
                        if k in ph and k not in params:
                            params[k] = v
            _ms_rot = (_time.time() - _marca) * 1000
            _marca = _time.time()  # inicio: execucao dos conectores
            ferramentas = registry.executar_conectores_area(
                cliente_id, area, pergunta, parametros=params,
                somente_ids=somente_ids, modelo=modelo_sql, intencao=intencao,
                modelo_escalada=modelo,
            )
            _ms_conn = (_time.time() - _marca) * 1000
        except Exception as e:  # noqa: BLE001
            ferramentas = [{"erro": str(e)}]

    # Consumo de tokens do caminho SQL DESTA thread (conectores do mestre): o
    # llm_client ja devolvia `usage` e ele era DESCARTADO — sem isso o custo do
    # text-to-SQL (do proprio agente e de cada worker) nao aparecia em relatorio.
    _tok_sql = _tokens_sql_da_thread()

    # --- 1b. Workers do mestre (v0.11.11) — em PARALELO, ordem do cadastro ---
    # Modo worker: cada worker roda SO os conectores da propria area (sem RAG,
    # sem LLM final, sem memoria, sem trace proprio) e devolve um BLOCO rotulado.
    # O mestre recebe todos os blocos e consolida uma unica vez, na mesma
    # chamada final — sem prompt novo, entao as diretivas anti-alucinacao e
    # anti-tag que ja valem para os conectores valem para os workers tambem.
    _workers_res: list[dict] = []
    if workers_do_agente(agente):
        _marca = _time.time()
        _workers_res = _executar_workers(
            agente, pergunta, locals().get("params") or {},
            locals().get("modelo_sql") or modelo, modelo, modelo)
        _ms_conn += (_time.time() - _marca) * 1000
        _f_workers, _t_workers = _ferramentas_dos_workers(_workers_res)
        ferramentas = list(ferramentas) + _f_workers
        _tok_sql = _somar_tokens(_tok_sql, _t_workers)

    # --- 2. RAG: complementa contexto mesmo se conectores retornaram dados ---
    tem_dados_vivos = any(
        f.get("resultado") for f in ferramentas
    )
    top_k = 2 if tem_dados_vivos else 4
    _marca = _time.time()  # inicio: RAG (busca + possivel refiltro)
    contexto = memory.buscar_contexto(pergunta, cliente_id, usuario=usuario, top_k=top_k, area=area)

    # Filtra contexto RAG: remove documentos com id_cliente diferente do extraido
    id_filtro = params.get("id_cliente", "") if "params" in dir() else ""
    if id_filtro:
        contexto = [c for c in contexto if id_filtro not in c.get("texto", "")]
        # Se filtrou tudo e tem dados vivos, ok. Senao busca sem filtro.
        if not contexto and not tem_dados_vivos:
            contexto = memory.buscar_contexto(pergunta, cliente_id, usuario=usuario, top_k=top_k, area=area)
    _ms_rag = (_time.time() - _marca) * 1000

    # --- 3. Monta o prompt com skills + contexto + dados ---
    skills_txt, skills_faltantes = _skills_blocos(agente.get("skills", ""))

    system = (
        f"Você é o agente corporativo '{agente['nome']}' "
        f"(área: {area or 'geral'}).\n"
        f"{_DIRETIVA_RESPOSTA}"
        f"{_DIRETIVA_DADOS_AUSENTES}"
        f"{_DIRETIVA_ORDEM_NAO_AFIRMADA}"
        f"{_DIRETIVA_ATRIBUICAO}"
    )
    if skills_txt:
        system += ("\nSKILLS DO AGENTE (instrucoes das skills anexadas — as "
                   "regras de formato e comportamento DEVEM ser seguidas):\n"
                   + skills_txt + "\n")

    system += (
        "\nUse os DADOS DE SISTEMA abaixo como fonte PRIMARIA — eles contem "
        "informacoes ATUAIS dos bancos e sistemas da empresa. "
        "O CONTEXTO (base de conhecimento) pode conter informacoes desatualizadas "
        "e deve ser usado apenas como referencia SECUNDARIA.\n\n"
        "IMPORTANTE: as ferramentas/conectores JA foram executados pelo sistema "
        "e seus resultados estao nos DADOS DE SISTEMA/CONTEXTO. NAO emita "
        "chamadas de funcao nem tags (<tool_call>, <function=...>, <parameter=...) "
        "— responda apenas em texto corrido.\n\n"
    )
    _dados = _blocos_dados(ferramentas)
    ausentes_nota: list = _dados["ausentes"]
    motivos_nota: list = _dados["motivos"]      # diagnostico honesto: consulta nao feita e por que
    sem_dados_nota: list = _dados["sem_dados"]  # consulta RODOU e voltou sem valor (B6)
    truncado_nota = _dados["truncado"]          # consulta bateu no teto de linhas
    if _dados["blocos"]:
        system += ("DADOS DE SISTEMA (conectores executados — FONTE PRIMARIA):\n"
                   + "\n".join(_dados["blocos"]) + "\n\n")
    if any(f.get("tool") == "skill (worker)" for f in ferramentas):
        # O worker passou a ter skill PROPRIA: a leitura dele entra como bloco
        # rotulado e o dado bruto continua ao lado. Dizer isso ao mestre evita que
        # ele trate o texto do worker como numero novo (honestidade: bruto manda).
        system += (
            "SOBRE OS WORKERS: os blocos `[WORKER n: ... · skill (worker)]` "
            "sao a LEITURA ORGANIZADA que cada worker fez do dado da area dele, "
            "seguindo a skill DAQUELE worker. O bloco do conector ao lado e o DADO "
            "BRUTO (a verdade): use a leitura como organizacao e, se divergir, "
            "vale o dado bruto — nunca tire numero que nao esteja no bruto.\n\n"
        )
    if ausentes_nota:
        _faltas = ", ".join(sorted(set(ausentes_nota)))
        if _dados["blocos"]:
            # HA dado vivo: a falta e PARCIAL e nao pode virar "peca ao usuario"
            # enterrando o que JA veio (medido no teste de producao: "5 produtos
            # em 2026" tinha os dados do conector inteligente, mas o
            # `parametro_ausente` do conector "Top Produtos (param ano/limite)"
            # — nome batendo com a pergunta — fez o modelo responder "falta o
            # ano" e descartar a resposta pronta). Com dado nos blocos, a falta
            # vira NOTA, nao ordem de parar.
            system += (
                "\nNOTA: alguns conectores nao rodaram por falta de parametro ("
                + _faltas + "), mas os DADOS DE SISTEMA acima ja trazem o que a "
                "pergunta pede. Responda com o que veio; cite o que ficou sem "
                "dado apenas se alguma PARTE da pergunta depender do parametro "
                "que faltou.\n"
            )
        else:
            # Reforço anti-alucinação: o conector NAO rodou — o modelo nao pode
            # responder com memoria/treino nem citar o conector como fonte.
            system += (
                "\nAVISO: a chamada ao conector NAO foi executada porque faltou "
                "informar: " + _faltas + ". Peca esse "
                "dado ao usuario de forma natural e NAO responda com dados de "
                "memoria/treino nem cite o conector como fonte. NUNCA emita "
                "tool_call nem tags (<tool_call>, <function=, <parameter=) — "
                "responda apenas em texto corrido pedindo o dado.\n"
            )
        if _dados.get("ausentes_orig"):
            # Cada falta PERTENCE a uma origem: sem isto o modelo tratava o
            # parametro que falta no worker A como impedimento para responder o
            # dado que o worker B JA trouxe (medido com workers de areas
            # diferentes na mesma pergunta).
            system += (
                "Origem de cada falta (vale so para o conector citado — o que "
                "JA veio dos outros conectores deve ser respondido normalmente "
                "e NAO depende disso):\n- "
                + "\n- ".join(_dados["ausentes_orig"]) + "\n"
            )
    if motivos_nota:
        # Diagnostico honesto (v0.11.2): quando a consulta nao foi feita, o
        # modelo PRECISA saber disso — antes o erro so existia no trace, o
        # prompt ficava sem sinal e o modelo inventava ("liste os vendedores").
        system += ("\nOBSERVACAO SOBRE CONECTORES: " + "; ".join(motivos_nota)
                   + ". Explique ao usuario o motivo real quando for relevante e "
                   "NUNCA invente valores, nomes, numeros ou IDs para preencher a "
                   "lacuna.\n")
    if sem_dados_nota:
        # Guarda de codigo, nao so de prompt: sem isto o modelo recebia
        # `{"sum": null}` como se fosse um numero e inventava a resposta.
        system += (
            "\nAVISO: o(s) conector(es) " + ", ".join(sorted(set(sem_dados_nota)))
            + " respondeu/responderam SEM DADOS (nenhum valor retornado). Nao ha "
            "numero para responder: diga que nao existe esse dado disponivel para "
            "a pergunta e NAO estime, aproxime nem invente valores.\n")
    if truncado_nota:
        system += ("\nOBSERVACAO SOBRE VOLUME: a consulta foi limitada a 50 linhas. "
                   "Se a pergunta pedir total/contagem, deixe claro que a listagem "
                   "pode estar limitada — nao afirme que existem exatamente os "
                   "registros listados.\n")
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
    user_content = pergunta
    if contexto_extra:
        user_content = (
            "CONTEXTO DA CONVERSA (mensagens anteriores do usuario):\n"
            f"{contexto_extra}\n\nPERGUNTA ATUAL:\n{pergunta}"
        )
    # ── Grafico: pedido + dados dos conectores -> especificador (LLM) ->  ──
    # renderizador (PNG base64) -> imagem ANEXADA apos a resposta do LLM  ──
    # (nao depende do modelo incluir: o sistema garante a imagem).         ──
    grafico_md = ""
    if _pede_grafico(pergunta):
        try:
            resumo_dados = _resumo_dados(ferramentas)
            if resumo_dados:
                spec_modelo = locals().get("modelo_roteador") or modelo
                _marca = _time.time()  # inicio: LLM (spec de grafico)
                spec = _especificar_grafico(pergunta, resumo_dados, spec_modelo)
                _ms_llm += (_time.time() - _marca) * 1000
                if spec:
                    from . import grafico as grafico_mod
                    # A imagem e saida: aplica a mesma politica de mascara
                    # LGPD do texto (mask_nome/email/endereco nos rotulos).
                    try:
                        if agente.get("lgpd_ativado", 1):
                            _lgpd = db.carregar_lgpd_config()
                            if _lgpd.get("anonimizar_llm") == "1":
                                spec = _mascarar_spec_rotulos(spec, _lgpd)
                    except Exception:  # noqa: BLE001
                        pass
                    b64 = grafico_mod.gerar_png_base64(spec)
                    if b64:
                        grafico_md = grafico_mod.marcar_grafico_md(b64)
                        user_content += (
                            "\n\nO usuario pediu um GRAFICO. Os dados e a imagem "
                            "foram gerados pelo sistema e a imagem sera ANEXADA "
                            "automaticamente a sua resposta. NAO inclua nenhuma "
                            "tag de imagem nem markdown de imagem (nenhum "
                            "![...](...)). Apenas resuma os dados em 2-3 linhas "
                            "e explique o grafico em texto."
                        )
        except Exception:  # noqa: BLE001 — grafico e best-effort
            pass
    # --- Ferramentas do CLIENTE (tool calling): quando o gateway libera (switch
    # por gateway) e o cliente manda `tools`, o agente recebe os schemas e pode
    # CHAMAR a ferramenta em vez de responder — quem executa e o cliente, nada
    # roda aqui. O resultado volta na proxima mensagem em `tool_results`.
    if tools:
        _nomes = ", ".join(
            (t.get("function") or {}).get("name", "?") for t in tools
            if isinstance(t, dict)) or "(sem nome)"
        system += (
            "\n\nFERRAMENTAS DISPONIVEIS: o cliente enviou ferramentas "
            f"({_nomes}). Quando a resposta depender de um dado que so a "
            "ferramenta pode buscar, CHAME a ferramenta em vez de inventar o "
            "dado. Nao descreva a chamada em texto."
        )
    if tool_results:
        _linhas = []
        for r in tool_results:
            if not isinstance(r, dict):
                continue
            _linhas.append(f"- {r.get('name') or 'ferramenta'}: "
                           f"{str(r.get('content') or '')[:2000]}")
        if _linhas:
            user_content += ("\n\nRESULTADO DAS FERRAMENTAS (executadas pelo "
                             "cliente):\n" + "\n".join(_linhas) +
                             "\n\nUse esse resultado para responder. Se ainda "
                             "faltar um dado, chame a ferramenta de novo.")
        # A pergunta antiga ja foi respondida com a chamada: as ferramentas
        # seguem disponiveis para o proximo passo da conversa.
    mensagens = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    # --- tentativa principal ---
    _marca = _time.time()  # inicio: LLM (resposta principal)
    out = llm_client.chat(modelo, mensagens, tools=tools or None,
                          tool_choice=tool_choice if tools else None)
    _ms_llm += (_time.time() - _marca) * 1000
    modelo_usado = modelo["modelo"]
    usou_fallback = False
    # Chamada de ferramenta NAO e resposta vazia: content vem nulo/"" nesse
    # caso (contrato OpenAI) e nao pode disparar o fallback nem a mensagem
    # de "nao consegui responder".
    tem_tool_calls = bool(out.get("tool_calls"))

    # --- fallback: modelo secundário se o principal FALHOU ou voltou VAZIO
    # (modelos com reasoning — ex: deepseek — podem devolver content "")
    _vazio = out["ok"] and not tem_tool_calls and not (out.get("content") or "").strip()
    if (not out["ok"] or _vazio) and agente.get("modelo_secundario_id") and agente["modelo_secundario_id"] != agente["modelo_id"]:
        modelo2 = db.buscar_modelo(agente["modelo_secundario_id"])
        if modelo2:
            _marca = _time.time()  # inicio: LLM (fallback)
            out2 = llm_client.chat(modelo2, mensagens)
            _ms_llm += (_time.time() - _marca) * 1000
            if out2["ok"] and (out2.get("content") or "").strip():
                out = out2
                modelo_usado = modelo2["modelo"]
                usou_fallback = True

    # --- Guard de resposta (fronteira, independe do modelo): fine-tunes com
    # formato de tool-call emitem <tool_call>/<think> cru no content mesmo
    # com o prompt anti-tag — o usuario nunca recebe o tag cru; recebe o
    # pedido do dado ausente (ou cai na mensagem de vazio, logo abaixo).
    if out["ok"] and not tem_tool_calls:
        out["content"] = _limpar_resposta_guard(out.get("content") or "", ausentes_nota)

    # --- LLM devolveu VAZIO (principal e fallback): resposta amigavel em
    # vez de "" — o usuario/sistema externo nunca recebe resposta em branco
    # (chamada de ferramenta nao e vazio: o cliente recebe `tool_calls`)
    if out["ok"] and not tem_tool_calls and not (out.get("content") or "").strip():
        out["content"] = (
            "Não consegui montar a resposta agora — o modelo de IA não "
            "retornou texto. Por favor, tente a mesma pergunta em instantes."
        )

    # Anexa a imagem do grafico gerado (o sistema garante — nao depende
    # do LLM final incluir a data URI na resposta).
    if grafico_md and "data:image/png;base64" not in (out.get("content") or ""):
        out["content"] = (out.get("content") or "").rstrip() + "\n\n" + grafico_md

    tok = out.get("tokens") or {}

    # --- Tracing: salva o rastreio detalhado da execucao ---
    import time as _time
    tempo_ms = int((_time.time() - _t0) * 1000)
    # Escalada da consulta inteligente (Fase 2): True quando o SELECT que
    # respondeu veio do modelo de REFORCO — o modelo configurado gerou algo
    # que nao rodou (tipicamente coluna inexistente). Sem este campo, o
    # suporte nao sabe se a resposta veio do caminho rapido ou do lento.
    escalada_sql = any(f.get("escalada") for f in ferramentas)
    trace_id = db.salvar_trace(
        pergunta=pergunta,
        params=params if "params" in dir() else {},
        conectores=ferramentas,
        rag=[{"texto": c["texto"][:200]} for c in contexto],
        modelo=modelo_usado,
        modelo_fallback=usou_fallback,
        tokens=tok,
        resposta=_limpar_imagens(out.get("content", "")),
        tempo_ms=tempo_ms,
        roteador_ms=int(_ms_rot),
        conectores_ms=int(_ms_conn),
        rag_ms=int(_ms_rag),
        llm_ms=int(_ms_llm),
        agente_id=agente.get("id"),
        skills_ausentes=",".join(skills_faltantes),
        escalada_sql=escalada_sql,
    )

    if out["ok"]:
        # Memoria de conversa: nao grava resposta contaminada com tag de
        # tool_call cru (contagio RAG — o chunk ensinaria o modelo a imitar)
        if not _tem_tool_call(out["content"]):
            db.criar_memoria(cliente_id, usuario, f"[{agente['nome']}] P: {pergunta} | R: {_limpar_imagens(out['content'])}",
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

    # Consumo do caminho da CONSULTA INTELIGENTE (text-to-SQL) em registro
    # proprio: e outra chamada ao provedor (e outra despesa), feita pelo modelo
    # do roteador/SQL — nao pelo modelo que assinou a resposta. Antes ficava
    # invisivel; com mestre+workers sao N chamadas por pergunta. Registra mesmo
    # se a resposta final falhou: a consulta foi paga de qualquer forma.
    if _tok_sql.get("total_tokens"):
        try:
            db.registrar_uso_token(
                cliente_id=cliente_id,
                modelo=(locals().get("modelo_sql") or modelo).get("modelo", modelo_usado),
                total_tokens=_tok_sql.get("total_tokens", 0),
                prompt_tokens=_tok_sql.get("prompt_tokens", 0),
                completion_tokens=_tok_sql.get("completion_tokens", 0),
                agente_id=agente.get("id"),
                quem=usuario, origem="sql",
            )
        except Exception:  # noqa: BLE001 — contabilidade nao derruba a resposta
            pass

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

    # --- Remove markdown de imagem inventado pelo LLM (so a data URI
    # real do grafico e legitima; placeholders falsos quebram o chat) ---
    if out["ok"]:
        out["content"] = _limpar_markdown_imagem_falso(out["content"])

    return {"ok": out["ok"], "content": out["content"], "model": out["model"],
            "model_fallback": usou_fallback, "error": out["error"],
            "tool_calls": out.get("tool_calls") or None,
            "contexto": contexto, "ferramentas": ferramentas,
            "trace_id": trace_id,
            "feedback_url": f"/portal/api/v1/feedback/{trace_id}" if out["ok"] else None,
            "tokens": out.get("tokens", {}),
            "tempo_ms": tempo_ms,
            }


def _limpar_markdown_imagem_falso(texto: str) -> str:
    """Remove markdowns de imagem que NAO sao a data URI real do grafico.

    O LLM pequeno inventa placeholders de imagem com path inexistente
    (ex: ![Graf](graficos/barra_...png)) mesmo com a instrucao de nao
    incluir — o chat externo tenta carregar e mostra imagem quebrada.
    A unica imagem legitima e a data URI anexada pelo sistema.
    """
    return re.sub(
        r"!\[[^\]]*\]\((?!data:image/png;base64)[^)]*\)", "", texto or "")


def _limpar_imagens(texto: str) -> str:
    """Remove data URIs de imagem da resposta antes de gravar (memoria/RAG/trace).

    O grafico e anexado como base64 (~20KB) — nao pode poluir a base de
    conhecimento, a memoria ou o trace. Vira um marcador curto.
    """
    return re.sub(
        r"!\[[^\]]*\]\(data:image/png;base64,[A-Za-z0-9+/=]+\)",
        "[imagem do grafico]", texto or "")


def _tem_tool_call(texto: str) -> bool:
    """True se o texto contem tag de tool_call cru (<tool_call>, <function=,
    <parameter=) — resposta contaminada que, se vira chunk de RAG/memoria,
    faz o LLM imitar o formato (contagio few-shot). Nunca deve ser gravada.
    """
    return bool(re.search(r"<tool_call>|<function=|<parameter=", texto or ""))


def _limpar_resposta_guard(content: str, ausentes_nota: list[str]) -> str:
    """Guarda de fronteira da resposta (independe do modelo).

    Modelos fine-tunados com formato de tool-call (ex: ornith) emitem
    <tool_call>/<function= crus no content mesmo com o prompt anti-tag, e
    modelos de reasoning vazam <think>...</think> para o content. Aqui:
      1. remove blocos <think>...</think> (raciocinio vazado);
      2. se sobrou tag de chamada crua, retorna o pedido do(s) dado(s)
         ausente(s) — ou "" (vazio) quando nao ha dado a pedir (o chamador
         cai na mensagem generica de resposta vazia).
    """
    resp = (content or "").strip()
    if "<think>" in resp:
        resp = re.sub(r"<think>.*?</think>", "", resp, flags=re.S).strip()
    if _tem_tool_call(resp):
        if ausentes_nota:
            return (
                "Não consegui consultar porque faltou informar: "
                + ", ".join(sorted(set(ausentes_nota)))
                + ". Por favor, informe esse dado para eu buscar a informação."
            )
        return ""
    return resp


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
    # Anti-SSRF no momento do envio (nao so no cadastro): bloqueia URL que
    # aponte para endereco interno — cobre canal cadastrado antes da
    # validacao e DNS rebinding (host que resolve interno na hora do POST).
    from . import db as _db
    _erro_url = _db.validar_webhook_url(webhook_url)
    if _erro_url:
        return {"enviado": False, "motivo": "url_interna_bloqueada", "erro": _erro_url}
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
