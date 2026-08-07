"""Gerador de graficos (barras/pizza/linha) para o agente.

Recebe um SPEC JSON vindo do LLM especificador e devolve um PNG em
base64 para ser embutido na resposta markdown do chat:

    spec = {
        "tipo": "barras" | "pizza" | "linha",
        "titulo": "Top 5 clientes",
        "dados": [{"rotulo": "148", "valor": 46}, ...]   # max 20 pontos
    }

Regras:
- Valores precisam ser numericos (float/str numerica); rotulos viram str.
- Spec invalido (tipo desconhecido, <2 pontos, valores nao numericos)
  retorna None — o chamador cai no fallback textual (nada quebra).
- Nao usa dados fora do spec: o LLM especificador recebe os dados REAIS
  dos conectores e so mapeia (nao inventa).
"""

import base64
import io
import json
import re

# Cores do tema BlueShift (var(--panel) #141b2e / var(--blue) #3b82f6 ...)
_FUNDO = "#141b2e"
_TEXTO = "#e2e8f0"
_MUTED = "#93a0bd"
_CORES = ["#3b82f6", "#22c55e", "#f59e0b", "#e879f9", "#38bdf8",
          "#ef4444", "#a3e635", "#f472b6", "#60a5fa", "#4ade80"]

_TIPOS = ("barras", "pizza", "linha")

_MAX_PONTOS = 20


def _parse_spec(spec: str | dict) -> dict | None:
    """Normaliza o spec (string JSON ou dict) para {tipo, titulo, dados}."""
    if isinstance(spec, str):
        m = re.search(r"\{.*\}", spec, re.DOTALL)
        if not m:
            return None
        try:
            spec = json.loads(m.group(0))
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(spec, dict):
        return None
    tipo = str(spec.get("tipo", "")).strip().lower()
    if tipo not in _TIPOS:
        return None
    titulo = str(spec.get("titulo", "") or "").strip()[:80]
    dados = spec.get("dados")
    if not isinstance(dados, list):
        return None
    pontos = []
    for d in dados[: _MAX_PONTOS]:
        if not isinstance(d, dict):
            continue
        rotulo = str(d.get("rotulo") if d.get("rotulo") is not None else d.get("label", ""))
        try:
            valor = float(d.get("valor") if d.get("valor") is not None else d.get("value"))
        except (TypeError, ValueError):
            continue
        pontos.append({"rotulo": rotulo[:40], "valor": valor})
    if len(pontos) < 2:
        return None
    return {"tipo": tipo, "titulo": titulo or "Gráfico", "dados": pontos}


def gerar_png_base64(spec: str | dict) -> str | None:
    """Gera o PNG (base64) do spec; None se o spec for invalido."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    s = _parse_spec(spec)
    if not s:
        return None
    dados = s["dados"]
    rotulos = [d["rotulo"] for d in dados]
    valores = [d["valor"] for d in dados]

    plt.rcParams.update({
        "figure.facecolor": _FUNDO,
        "axes.facecolor": _FUNDO,
        "savefig.facecolor": _FUNDO,
        "text.color": _TEXTO,
        "axes.labelcolor": _TEXTO,
        "xtick.color": _MUTED,
        "ytick.color": _MUTED,
        "axes.edgecolor": _MUTED,
        "font.size": 9,
    })

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=110)

    if s["tipo"] == "barras":
        cores = [_CORES[i % len(_CORES)] for i in range(len(valores))]
        ax.bar(rotulos, valores, color=cores)
        ax.set_title(s["titulo"], color=_TEXTO, fontsize=11, pad=10)
        for i, v in enumerate(valores):
            ax.text(i, v, f"{v:g}", ha="center", va="bottom", fontsize=8, color=_MUTED)
        ax.tick_params(axis="x", rotation=25 if len(rotulos) > 5 else 0)
        ax.yaxis.grid(True, color="#2a3550", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    elif s["tipo"] == "pizza":
        cores = [_CORES[i % len(_CORES)] for i in range(len(valores))]
        total = sum(valores) or 1
        ax.pie(valores, labels=rotulos, autopct=lambda p: f"{p:.0f}%",
               colors=cores, startangle=90, textprops={"color": _TEXTO, "fontsize": 8},
               pctdistance=0.75)
        ax.set_title(s["titulo"], color=_TEXTO, fontsize=11, pad=10)

    else:  # linha
        ax.plot(range(len(valores)), valores, marker="o", color=_CORES[0],
                linewidth=2, markersize=4)
        ax.set_xticks(range(len(rotulos)))
        ax.set_xticklabels(rotulos, rotation=25 if len(rotulos) > 5 else 0)
        ax.set_title(s["titulo"], color=_TEXTO, fontsize=11, pad=10)
        ax.yaxis.grid(True, color="#2a3550", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return b64


def marcar_grafico_md(b64: str) -> str:
    """Monta o markdown da imagem (data URI) para embutir na resposta."""
    return f"![grafico](data:image/png;base64,{b64})"
