#!/usr/bin/env python3
"""BlueShift — Bootstrap da estrutura de diretórios e arquivos-base (camada sobre Hermes).
Salve este arquivo como bootstrap.py na raiz do projeto e rode: python bootstrap.py
Cria toda a árvore do projeto BlueShift em Python puro. Não toca no Hermes-Agent.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILES = {}

FILES["pyproject.toml"] = '''\
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "blueshift-layer"
version = "0.1.0"
description = "BlueShift IA Platform — camada sobre Hermes-Agent (on-premise, Docker + license key)"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31",
    "pyyaml>=6.0",
    "mcp>=1.0",
]

[project.scripts]
blueshift = "blueshift_layer.cli:main"

[tool.setuptools]
packages = ["blueshift_layer"]
'''

FILES["requirements.txt"] = '''\
requests>=2.31
pyyaml>=6.0
mcp>=1.0
'''

FILES["LICENSE"] = '''\
MIT License

Copyright (c) 2025 Nous Research
(Componente Hermes-Agent - licenca MIT. BlueShift e camada sobre o Hermes.)

Copyright (c) 2026 BlueShift

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
'''

FILES[".gitignore"] = '''\
.venv/
__pycache__/
*.pyc
.env
models/
data/
blueshift_profile_*/
'''

FILES["README.md"] = '''\
# BlueShift IA Platform (dev)

Camada empacotada sobre o Hermes-Agent (MIT) para entrega on-premise via Docker + license key.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
blueshift --help
```

## Comandos
- `blueshift init <cliente>` — cria profile do cliente
- `blueshift activate <chave>` — valida license key
- `blueshift status` — mostra estado do container
- `blueshift update` — checa atualizacoes aprovadas
'''

FILES["blueshift_layer/__init__.py"] = '''\
"""BlueShift IA Platform - camada sobre Hermes-Agent."""
__version__ = "0.1.0"
'''

FILES["blueshift_layer/cli.py"] = '''\
#!/usr/bin/env python3
"""CLI do BlueShift. Comandos: init, activate, status, update."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blueshift_layer import license_client, installer, update_client


def main():
    p = argparse.ArgumentParser(prog="blueshift", description="BlueShift IA Platform")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("init", help="Cria profile de cliente").add_argument("cliente")
    sub.add_parser("activate", help="Valida license key").add_argument("chave")
    sub.add_parser("status", help="Mostra estado do container")
    sub.add_parser("update", help="Checa atualizacoes aprovadas")

    args = p.parse_args()
    if args.cmd == "init":
        installer.create_profile(args.cliente)
    elif args.cmd == "activate":
        ok = license_client.validate(args.chave)
        print("LICENSE", "OK" if ok else "INVALIDA")
    elif args.cmd == "status":
        print("BlueShift status: container ativo (modo dev)")
    elif args.cmd == "update":
        update_client.check()
    else:
        p.print_help()


if __name__ == "__main__":
    main()
'''

FILES["blueshift_layer/license_client.py"] = '''\
#!/usr/bin/env python3
"""Valida a license key no License Server BlueShift.

MODO DEV: aponta para endpoint mockado (LICENSE_SERVER_URL).
Em producao, trocar pela URL real do License Server (backend BlueShift).
"""
import os
import requests

# Em dev, use um mock local. Em producao: https://license.blueshift.app/v1/validate
LICENSE_SERVER_URL = os.getenv("BLUESHIFT_LICENSE_URL", "http://localhost:9000/v1/validate")
TIMEOUT = 10


def validate(key: str) -> bool:
    """Retorna True se a chave for valida junto ao License Server."""
    if not key:
        return False
    # MODO DEV: aceita qualquer chave comecando com "BS-DEV-" para desenvolvimento local.
    # REMOVER este atalho antes de producao.
    if key.startswith("BS-DEV-"):
        return True
    try:
        r = requests.post(LICENSE_SERVER_URL, json={"key": key}, timeout=TIMEOUT)
        return r.status_code == 200 and r.json().get("valid", False)
    except requests.RequestException:
        # Sem rede: bloqueia (modo "locked") - exceto em dev com flag.
        return os.getenv("BLUESHIFT_DEV") == "1"


def activate(key: str) -> dict:
    """Ativa a chave e retorna metadados (cliente, perfil, modelo autorizado)."""
    if not validate(key):
        return {"valid": False}
    return {"valid": True, "cliente": "demo", "perfil": "cliente_demo", "modelo": "finetuned-v1"}
'''

FILES["blueshift_layer/installer.py"] = '''\
#!/usr/bin/env python3
"""Installer: cria o profile do cliente no Hermes no 1o boot.

Como BlueShift e LAYER sobre Hermes, o installer apenas invoca:
  hermes profile create <cliente>
e popula as pastas de skills/connectors dentro do profile.
"""
import os
import subprocess
from pathlib import Path

HERMES_BIN = os.getenv("HERMES_BIN", "hermes")
PROFILES_DIR = Path(os.getenv("HOME", "~")) / ".hermes" / "profiles"


def create_profile(cliente: str):
    """Cria profile isolado do cliente no Hermes."""
    print(f"[installer] criando profile Hermes: {cliente}")
    try:
        subprocess.run([HERMES_BIN, "profile", "create", cliente], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[installer] erro ao criar profile: {e}")
        return False
    # Popular templates de skill e connectors no profile
    dest = PROFILES_DIR / cliente / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    print(f"[installer] profile {cliente} pronto em {PROFILES_DIR / cliente}")
    return True


def populate_templates(cliente: str):
    """Copia template_skills para o profile do cliente (parametrizavel por area da empresa)."""
    src = Path(__file__).resolve().parent / "template_skills"
    dest = PROFILES_DIR / cliente / "skills"
    if src.exists():
        for skill in src.iterdir():
            if skill.is_dir():
                print(f"[installer] skill disponivel: {skill.name}")
    print(f"[installer] templates prontos em {dest}")
'''

FILES["blueshift_layer/update_client.py"] = '''\
#!/usr/bin/env python3
"""Update Client: checa o Update Channel aprovado pela BlueShift.

Como usamos LAYER sobre Hermes, as atualizacoes do motor vem do proprio Hermes.
O BlueShift so versiona sua camada (connectors, skills, installer).
"""
import requests

UPDATE_URL = "http://localhost:9001/v1/channel"  # mock em dev


def check():
    """Verifica se ha nova versao da camada BlueShift aprovada."""
    print("[update] checando Update Channel...")
    try:
        r = requests.get(UPDATE_URL, timeout=10)
        if r.status_code == 200:
            print(f"[update] versao disponivel: {r.json().get('version', 'desconhecida')}")
        else:
            print("[update] nenhuma atualizacao (canal vazio)")
    except requests.RequestException:
        print("[update] canal indisponivel (modo offline OK - Hermes continua funcionando)")


def apply(version: str):
    """Aplica atualizacao da camada (pip install da nova versao)."""
    print(f"[update] aplicando BlueShift {version}...")
    # Em producao: pip install blueshift-layer==version
    print("[update] concluido")
'''

FILES["blueshift_layer/config/default_config.yaml"] = '''\
# Config padrao do container BlueShift (camada sobre Hermes)
blueshift:
  versao: "0.1.0"
  license_server: "http://localhost:9000/v1/validate"
  update_channel: "http://localhost:9001/v1/channel"

hermes:
  bin: "hermes"
  versao_base: "0.18.2"   # MIT, Nous Research

modelo:
  default: "finetuned-v1"
  base_url: "http://localhost:8000/v1"   # vLLM local (GPU do cliente)
  externo_opcional: true                  # OpenAI/Claude/Gemini sob controle

perfil:
  isolamento: "por_cliente"              # 1 profile Hermes por cliente
  memoria: "por_usuario"                 # banco vetorial local

acesso:
  hierarquia: ["admin", "gestor", "usuario", "sistema"]
  mcp_scope: "minimo"                    # principio do menor privilegio
'''

FILES["blueshift_layer/connector_pack/__init__.py"] = '''\
"""Connector Pack - servidores MCP prontos para sistemas internos."""
'''

FILES["blueshift_layer/connector_pack/base.py"] = '''\
#!/usr/bin/env python3
"""Classe base para servidores MCP do Connector Pack.

Cada conector (ERP/CRM/RH) herda de BaseConnector e implementa as tools.
Em producao, conecta ao banco/sistema real do cliente.
"""
from abc import ABC, abstractmethod


class BaseConnector(ABC):
    name: str = "base"

    @abstractmethod
    def tools(self) -> list:
        """Retorna a lista de ferramentas (tools) expostas via MCP."""
        ...

    def run(self):
        """Inicia o servidor MCP (stdio)."""
        print(f"[mcp:{self.name}] servidor iniciado (stdio)")
        # Em producao: usar mcp.server.stdio para expor as tools
'''

FILES["blueshift_layer/connector_pack/mcp_erp.py"] = '''\
#!/usr/bin/env python3
"""Conector ERP (stub). Substitua pela integracao real do cliente."""
from .base import BaseConnector


class ErpConnector(BaseConnector):
    name = "erp"

    def tools(self) -> list:
        return [
            "buscar_cliente",
            "listar_pedidos",
            "criar_oportunidade",
        ]

    def buscar_cliente(self, id_cliente: str) -> dict:
        # TODO: conectar ao ERP real (banco do cliente)
        return {"id": id_cliente, "nome": "MOCK", "pedidos": []}

    def listar_pedidos(self, id_cliente: str) -> list:
        return []

    def criar_oportunidade(self, cliente: str, itens: list) -> str:
        return "OPPORTUNITY_MOCK_123"


if __name__ == "__main__":
    ErpConnector().run()
'''

FILES["blueshift_layer/connector_pack/mcp_crm.py"] = '''\
#!/usr/bin/env python3
"""Conector CRM (stub)."""
from .base import BaseConnector


class CrmConnector(BaseConnector):
    name = "crm"

    def tools(self) -> list:
        return ["historico_contato", "proximos_passos"]

    def historico_contato(self, id_cliente: str) -> list:
        return []

    def proximos_passos(self, id_cliente: str) -> list:
        return []


if __name__ == "__main__":
    CrmConnector().run()
'''

FILES["blueshift_layer/connector_pack/mcp_rh.py"] = '''\
#!/usr/bin/env python3
"""Conector RH (stub)."""
from .base import BaseConnector


class RhConnector(BaseConnector):
    name = "rh"

    def tools(self) -> list:
        return ["consultar_folha", "consultar_colaborador"]

    def consultar_folha(self, mes: str) -> dict:
        return {"mes": mes, "total": 0.0}

    def consultar_colaborador(self, id_colab: str) -> dict:
        return {"id": id_colab, "nome": "MOCK"}


if __name__ == "__main__":
    RhConnector().run()
'''

FILES["blueshift_layer/template_skills/vendas/SKILL.md"] = '''\
---
name: vendas
description: "Agente de vendas - consulta ERP, propoe produtos, faz follow-up"
version: 1.0.0
---

# Agente de Vendas (template generico)

## Ferramentas (MCP)
- erp.buscar_cliente
- erp.listar_pedidos
- crm.historico_contato

## Comportamento
1. Ao perguntarem "status do cliente X": consulte erp.buscar_cliente(X)
2. Nunca invente numero de pedido - confirme no ERP
3. Tom consultivo, nao pushy
'''

FILES["blueshift_layer/template_skills/suporte/SKILL.md"] = '''\
---
name: suporte
description: "Agente de suporte - abre chamado, consulta base de conhecimento"
version: 1.0.0
---

# Agente de Suporte (template generico)

## Ferramentas (MCP)
- crm.historico_contato
- erp.buscar_cliente

## Comportamento
1. Identifique o cliente antes de agir
2. Registre o chamado no sistema
3. Use linguagem clara e empatica
'''

FILES["blueshift_layer/template_skills/financeiro/SKILL.md"] = '''\
---
name: financeiro
description: "Agente financeiro - fecha caixa, gera relatorio"
version: 1.0.0
---

# Agente Financeiro (template generico)

## Ferramentas (MCP)
- erp.listar_pedidos

## Comportamento
1. Consolide dados do periodo solicitado
2. Gere relatorio em linguagem natural
3. Nunca exponha dados sensiveis sem autorizacao
'''

FILES["blueshift_layer/template_skills/rh/SKILL.md"] = '''\
---
name: rh
description: "Agente de RH - consulta folha, responde colaborador"
version: 1.0.0
---

# Agente de RH (template generico)

## Ferramentas (MCP)
- rh.consultar_folha
- rh.consultar_colaborador

## Comportamento
1. Valide permissao antes de expor dados de RH
2. Responda em linguagem acessivel
3. Respeite LGPD
'''

FILES["docker/Dockerfile"] = '''\
# BlueShift IA Platform - imagem Docker (Fase 2)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /opt/blueshift

# Hermes-Agent como dependencia (MIT, nao modificado)
RUN pip install hermes-agent==0.18.2

COPY . /opt/blueshift
RUN pip install --no-cache-dir -e .

# Volume persistente: modelo fine-tuned + memoria do cliente
VOLUME ["/opt/blueshift/models", "/opt/blueshift/data"]

ENV BLUESHIFT_LICENSE=""
EXPOSE 8080

CMD ["blueshift", "status"]
'''

FILES["tests/test_smoke.py"] = '''\
#!/usr/bin/env python3
"""Teste de fumaca: valida estrutura e imports basicos."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blueshift_layer import license_client, installer, update_client
from blueshift_layer.connector_pack import mcp_erp, mcp_crm, mcp_rh


def test_license_dev_key():
    assert license_client.validate("BS-DEV-qualquer") is True


def test_connectors_exist():
    assert hasattr(mcp_erp.ErpConnector, "tools")
    assert hasattr(mcp_crm.CrmConnector, "tools")
    assert hasattr(mcp_rh.RhConnector, "tools")


def test_installer_callable():
    assert callable(installer.create_profile)


if __name__ == "__main__":
    test_license_dev_key()
    test_connectors_exist()
    test_installer_callable()
    print("SMOKE TESTS PASSOU")
'''


def main():
    for rel, content in FILES.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  ok {rel}")
    print(f"\nEstrutura BlueShift criada em: {ROOT}")
    print("Proximo passo: source .venv/bin/activate && pip install -e .")


if __name__ == "__main__":
    main()
