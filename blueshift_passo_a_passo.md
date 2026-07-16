# BlueShift IA Platform — Passo-a-Passo de Desenvolvimento

> **Pré-condição:** Hermes-Agent v0.18.2 **já instalado** na máquina de desenvolvimento (MacBook M3).
> Quem vai construir a plataforma é o **próprio Hermes** (rodando aí), escrevendo os arquivos do BlueShift a pedido do desenvolvedor.
> **Base:** BlueShift é **camada sobre** o Hermes (MIT), NÃO fork. Licença anual por empresa, genérico por área, portal obrigatório.

---

## Princípio fundamental (leia antes)

```
Hermes  = motor (já instalado na máquina)        → NÃO edite, NÃO copie pro projeto
BlueShift = camada que empacota o Hermes          → É o que você desenvolve e versiona
```

Você baixa os fontes do Hermes **apenas para consultar** (pasta `_ref`, read-only). O desenvolvimento acontece numa pasta **separada**, com venv. O Hermes já instalado é o motor que a camada usa.

---

## Passo 0 — Pré-requisitos (verificar na máquina)

```bash
python3 --version     # 3.11+  (ok no M3)
docker --version      # opcional agora
hermes --version      # v0.18.2  (já instalado ✅)
git --version
```

Se o `hermes --version` não for v0.18.2, alinhe antes de continuar (a camada fixa essa versão no Dockerfile).

---

## Passo 1 — Baixar os fontes do Hermes (só referência)

```bash
mkdir -p ~/Dev/_ref && cd ~/Dev/_ref
git clone <URL_DO_SEU_FORK_HERMES> hermes-ref
cd hermes-ref && git checkout v0.18.2
```

📌 Isso é **apenas para consultar** o código do motor quando precisar entender como o Hermes faz algo (profiles, MCP, skills). Não escreva nada aqui. Marque o repo no GitHub como "espelho / read-only".

---

## Passo 2 — Criar o projeto BlueShift (outra pasta, com venv)

```bash
mkdir -p ~/Dev/blueshift-ia-platform && cd ~/Dev/blueshift-ia-platform
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

📌 O Hermes **já está instalado na máquina** e serve de motor. Aqui dentro do venv é onde a *camada* BlueShift vai morar. Você NÃO precisa reinstalar o Hermes.

---

## Passo 3 — Montar a estrutura (bootstrap)

Copie o arquivo `bootstrap.py` (fornecido junto com este guia, e também embutido no `blueshift_dev_guide.md` Seção 3) para a raiz do projeto e rode:

```bash
cp <origem>/bootstrap.py ./
python bootstrap.py
```

Isso cria toda a árvore: `blueshift_layer/`, `connector_pack/`, `template_skills/`, `docker/`, `tests/`, `LICENSE`, `pyproject.toml`, etc.

Depois:

```bash
pip install -e .
blueshift --help        # deve listar init / activate / status / update
```

✅ Se aparecer o help, o scaffold está pronto.

---

## Passo 4 — Construir a plataforma com o Hermes

Agora é iterative. Você pede e **o Hermes (rodando na máquina) escreve os arquivos** em `~/Dev/blueshift-ia-platform/`. Exemplos de pedidos:

- "Hermes, crie o `license_server` mock em Flask"
- "Hermes, implemente o `mcp_erp.py` real conectando a um Postgres de exemplo"
- "Hermes, gere o Portal do Cliente (Flask) com telas de gerenciar/cadastrar/monitorar"
- "Hermes, adicione o `operacoes` aos template_skills"
- "Hermes, ajuste o `Dockerfile` para subir o License Server junto"

O Hermes edita/cria arquivos direto na pasta do BlueShift. Você revisa, testa e pede ajustes.

Teste contínuo:
```bash
blueshift activate BS-DEV-teste123    # deve imprimir LICENSE OK
python tests/test_smoke.py            # deve imprimir SMOKE TESTS PASSOU
```

---

## Passo 5 — Versionar no Git (seu repo novo)

```bash
cd ~/Dev/blueshift-ia-platform
git init
git add .
git commit -m "BlueShift IA Platform — camada sobre Hermes v0.18.2 (MIT)"
git branch -M main
git remote add origin <URL_DO_SEU_REPO_BLUESHIFT>
git push -u origin main
```

📌 O repo contém **sua camada**, não o código do Hermes. O Hermes entra como dependência no `Dockerfile` (`pip install hermes-agent==0.18.2`).

---

## Passo 6 — Deploy (Docker, quando pronto)

```bash
docker build -t blueshift/platform .
docker run -e BLUESHIFT_LICENSE=XXXX-XXXX blueshift/platform
```

O `Dockerfile` (já gerado pelo bootstrap) instala o `hermes-agent==0.18.2` + sua camada. Para o cliente: `docker run -e BLUESHIFT_LICENSE=<chave> blueshift/platform`.

---

## Checklist de alinhamento

- [x] Fontes do Hermes numa pasta (`_ref`), BlueShift noutra (`blueshift-ia-platform`)
- [x] Hermes já instalado = não reinstala; serve de motor
- [x] Bootstrap monta a camada (venv + `blueshift_layer/`)
- [x] Hermes escreve os arquivos do BlueShift a pedido do desenvolvedor
- [x] Git novo é só da camada BlueShift
- [x] Deploy = Docker com Hermes dentro como dependência

## O que NÃO fazer

- ❌ Não fazer `git clone` do Hermes **dentro** da pasta do BlueShift
- ❌ Não editar `hermes_cli/` pensando "vou customizar o motor" (quem faz isso, vira fork e perde updates)
- ❌ Não usar `pip install -e ../hermes-ref` (amarra seu BlueShift ao código editável do fork)

## Arquivos relacionados (mesmo diretório)

- `blueshift_prd.md` — PRD do produto (decisões, feature matrix)
- `blueshift-ia-platform.html` — prospecto visual
- `blueshift_dev_guide.md` — detalhe técnico da estrutura + bootstrap embutido
- `bootstrap.py` — script que monta a estrutura (Passo 3)
