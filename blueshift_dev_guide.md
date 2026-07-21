# BlueShift IA Platform — Guia de Desenvolvimento (Dev Guide)

> **Público:** Desenvolvedor rodando a plataforma localmente (MacBook M3 do desenvolvedor)
> **Objetivo:** Montar toda a estrutura de diretórios e arquivos-base do produto BlueShift em Python puro.
> **Decisões do PRD aplicadas:** Licença MIT ✅ · Docker + License Key ✅ · Genérico (sem vertical) ✅ · Licença anual ✅ · Portal obrigatório ✅ · Nome canônico "BlueShift IA Platform" ✅ · Segmentação por área da empresa ✅

---

## Como o desenvolvimento funciona (fluxo resumido)

```
MÁQUINA DE DEV
└── ~/bp-proj           → SEU projeto (venv + camada BlueShift)
    ├── bp-venv/         → venv do projeto
    ├── blueshift_layer/ → código da plataforma (Flask puro)
    └── docker/Dockerfile→ empacota a plataforma em container
```

**Regra de ouro:** BlueShift é um **Flask standalone** — 100% Python puro, sem dependência de motor externo. O desenvolvimento e o Git são da plataforma, numa pasta própria.

Para o passo-a-passo completo de como iniciar, veja **`blueshift_passo_a_passo.md`** (mesmo diretório).

---

## 0. Pré-requisitos (MacBook M3)

- Python 3.11+ (`brew install python@3.11`)
- Git
- Docker Desktop (para empacotamento em container — não obrigatório para desenvolver)
- Terminal (zsh padrão do macOS)

Verifique:
```bash
python3 --version     # esperado 3.11+
docker --version      # opcional agora
```

---

## 1. Criação do Venv e Setup

O BlueShift usa um **venv isolado** para não poluir o Python do sistema.

```bash
# 1. Criar/entrar na pasta do projeto
cd ~/bp-proj

# 2. Criar/ativar venv
python3 -m venv bp-venv
source bp-venv/bin/activate

# 3. Atualizar pip
pip install --upgrade pip

# 4. Instalar a plataforma BlueShift (registra o entry point 'blueshift')
pip install -e .
```

> O projeto já está construído (Portal do Cliente, Agent Factory, RAG,
> conectores, MCP, SSO, etc.). Basta `pip install -e .` para ter o comando
> `blueshift` disponível.

---

## 2. Estrutura de Diretórios

```
~/bp-proj/
├── pyproject.toml              # build do pacote blueshift-layer
├── requirements.txt            # dependências Python
├── README.md                   # instruções rápidas
├── .gitignore
├── blueshift_layer/            # código do produto
│   ├── __init__.py
│   ├── cli.py                  # comandos: init, activate, update, status, portal, mcp
│   ├── license_client.py       # valida chave no License Server
│   ├── installer.py            # cria perfil do cliente no 1º boot
│   ├── update_client.py        # checa Update Channel aprovado
│   ├── config/
│   │   └── default_config.yaml # config padrão do container
│   ├── connector_pack/         # servidores MCP prontos
│   │   ├── __init__.py
│   │   ├── registry.py         # executa ferramentas dos conectores
│   │   ├── mcp_server.py       # servidor MCP stdio (JSON-RPC 2.0)
│   │   ├── mcp_erp.py          # conector ERP (Postgres ou fallback exemplo)
│   │   ├── mcp_crm.py          # conector CRM (exemplo local)
│   │   └── mcp_rh.py           # conector RH (exemplo local)
│   ├── portal/                 # Portal do Cliente
│   │   ├── __init__.py         # app factory create_app()
│   │   ├── db.py               # SQLite centralizado
│   │   ├── auth.py             # RBAC (admin/gestor/usuario/sistema)
│   │   ├── views.py            # rotas e telas
│   │   ├── templates.py        # layout dark/azul da marca
│   │   ├── memory.py           # banco vetorial local (TF-IDF + cosseno)
│   │   ├── llm_client.py       # client LLM OpenAI-compatible
│   │   ├── agente.py           # orquestrador de agentes
│   │   └── sso.py              # login federado OIDC
│   └── template_skills/        # template skills (genéricos por área)
│       ├── vendas/SKILL.md
│       ├── suporte/SKILL.md
│       ├── financeiro/SKILL.md
│       ├── rh/SKILL.md
│       └── operacoes/SKILL.md
├── docker/
│   └── Dockerfile              # imagem BlueShift
└── tests/
    └── test_fallback.py        # teste de fallback de modelo
```

---

## 3. Teste contínuo

```bash
blueshift activate BS-DEV-teste123    # deve imprimir LICENSE OK
blueshift portal                      # sobe o Portal (http://localhost:8080/portal)
python tests/test_fallback.py         # testa fallback de modelo
```

---

## 4. Desenvolvimento iterativo

O desenvolvimento é iterativo. Você pede e o assistente AI escreve os arquivos. Exemplos de pedidos:

- "Crie uma tela de relatórios no Portal"
- "Adicione um novo conector no connector_pack"
- "Ajuste o Dockerfile para subir o License Server junto"

Teste contínuo:
```bash
blueshift activate BS-DEV-teste123    # deve imprimir LICENSE OK
```

---

## 5. Versionar no Git

```bash
cd ~/bp-proj
git init
git add .
git commit -m "BlueShift IA Platform — Flask standalone, Python puro"
git branch -M main
git remote add origin <URL_DO_SEU_REPO>
git push -u origin main
```

---

## 6. Deploy (Docker, quando pronto)

```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker run -e BLUESHIFT_LICENSE=BS-DEV-teste123 blueshift/platform
```

## O que NÃO fazer

- ❌ Não rodar `python bootstrap.py` dentro deste repo (apaga a plataforma construída)
- ❌ Não fazer `git clone` de outro projeto dentro da pasta do BlueShift
