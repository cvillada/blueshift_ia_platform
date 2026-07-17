"""Registry do Connector Pack (BlueShift).

Instancia os conectores reais (ERP/CRM/RH) e expõe execução de ferramentas
(MCP) de forma uniforme. Usado pelo orquestrador de agentes e pelo Portal.

Em produção, cada conector aponta para o sistema real do cliente (via env /
DSN). Aqui usamos dados de exemplo embarcados para demonstração on-premise.
"""
from __future__ import annotations

from .mcp_erp import ErpConnector
from .mcp_crm import CrmConnector
from .mcp_rh import RhConnector

_REGISTRY = {
    "erp": ErpConnector,
    "crm": CrmConnector,
    "rh": RhConnector,
}

# instâncias singletons (leves; dados de exemplo em memória)
_INSTANCES: dict = {}


def obter(nome: str):
    """Retorna a instância do conector pelo nome (erp/crm/rh)."""
    if nome not in _REGISTRY:
        raise KeyError(f"Conector '{nome}' desconhecido. Disponíveis: {list(_REGISTRY)}")
    if nome not in _INSTANCES:
        _INSTANCES[nome] = _REGISTRY[nome]()
    return _INSTANCES[nome]


def ferramentas_disponiveis() -> dict:
    """{conector: [tools]} para exibição no Portal."""
    return {nome: conn().tools() for nome, conn in _REGISTRY.items()}


def executar(conector: str, tool: str, **kwargs) -> object:
    """Executa uma ferramenta de um conector e retorna o resultado (Python object)."""
    inst = obter(conector)
    if not hasattr(inst, tool):
        raise AttributeError(f"Conector '{conector}' não tem a ferramenta '{tool}'.")
    return getattr(inst, tool)(**kwargs)


def executar_csv(conectores_csv: str, id_cliente: str = "C001") -> list[dict]:
    """Executa as tools relevantes dos conectores listados (ex: 'erp,crm').

    Retorna lista de {conector, tool, args, resultado} para compor o contexto
    do agente. Não quebra se um conector/tool falhar — registra o erro.
    """
    out: list[dict] = []
    nomes = [c.strip().lower() for c in (conectores_csv or "").split(",") if c.strip()]
    # mapeia tool padrão por conector (busca de cliente)
    padrao = {
        "erp": ("buscar_cliente", {"id_cliente": id_cliente}),
        "crm": ("historico_contato", {"id_cliente": id_cliente}),
        "rh": ("consultar_colaborador", {"id_colab": id_cliente.replace("C", "E")}),
    }
    for nome in nomes:
        if nome not in padrao:
            continue
        tool, args = padrao[nome]
        try:
            res = executar(nome, tool, **args)
            out.append({"conector": nome, "tool": tool, "args": args, "resultado": res})
        except Exception as e:  # noqa: BLE001 - tolerância no contexto
            out.append({"conector": nome, "tool": tool, "args": args, "erro": str(e)})
    return out
