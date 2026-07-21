# BlueShift IA Platform — Passo-a-Passo de Desenvolvimento

> **Pré-condição:** Python 3.11+ instalado na máquina de desenvolvimento (MacBook M3).
> **Base:** BlueShift é **Flask standalone** — 100% Python puro. Licença anual por empresa, genérico por área, portal obrigatório.

---

## Princípio fundamental (leia antes)

```
BlueShift = plataforma Flask standalone (sem motor externo) → É o que você desenvolve e versiona
```

---

## Passo 0 — Pré-requisitos (verificar na máquina)

```bash
python3 --version     # 3.11+  (ok no M3)
docker --version      # opcional agora
git --version
```

---

## Passo 1 — Criar o projeto BlueShift (com venv)

```bash
cd /Users/claudineivillada/Python/Blueshift_IA_Platform/bp-proj
python3 -m venv bp-venv
source bp-venv/bin/activate
pip install --upgrade pip
pip install -e .          # instala flask/mcp/psycopg + registra o entry point 'blueshift'
blueshift --help          # deve listar init / activate / status / update / portal / mcp
```

✅ Se aparecer o help com `portal` e `mcp`, o ambiente está pronto.

⚠️ **NÃO rode `python bootstrap.py`** neste repositório. O `bootstrap.py` é o
scaffold inicial (stubs vazios) e, se rodado, **sobrescreve** o
`pyproject.toml`, `cli.py`, conectores, skills e Dockerfile reais por stubs vazios,
apagando toda a plataforma já construída. Ele só serve para criar um projeto do zero
em outra pasta — nunca dentro deste.

Teste contínuo:
```bash
blueshift activate BS-DEV-teste123    # deve imprimir LICENSE OK
blueshift portal                      # sobe o Portal do Cliente (http://localhost:8080/portal)
python tests/test_fallback.py         # testa fallback de modelo
```

---

## Passo 2 — Desenvolvimento iterativo

Agora é iterativo. Você pede e o assistente AI escreve os arquivos. Exemplos de pedidos:

- "Crie o `license_server` mock em Flask"
- "Implemente um novo conector MCP"
- "Gere uma nova tela no Portal"
- "Ajuste o `Dockerfile`"

O assistente edita/cria arquivos direto na pasta do BlueShift. Você revisa, testa e pede ajustes.

Teste contínuo:
```bash
blueshift activate BS-DEV-teste123    # deve imprimir LICENSE OK
```

---

## Passo 3 — Versionar no Git (seu repo)

```bash
cd /Users/claudineivillada/Python/Blueshift_IA_Platform/bp-proj
git init
git add .
git commit -m "BlueShift IA Platform — Flask standalone, Python puro"
git branch -M main
git remote add origin <URL_DO_SEU_REPO>
git push -u origin main
```

---

## Passo 4 — Deploy (Docker, quando pronto)

```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker run -e BLUESHIFT_LICENSE=BS-DEV-teste123 blueshift/platform
```

## Checklist de alinhamento

- [x] Ambiente = venv + `pip install -e .` (sem bootstrap)
- [x] Git novo é só do BlueShift
- [x] Deploy = Docker com a plataforma dentro

## O que NÃO fazer

- ❌ **Não rodar `python bootstrap.py` dentro deste repo** (apaga a plataforma construída — sobrescreve por stubs vazios)
- ❌ Não fazer `git clone` dentro da pasta do BlueShift

## Arquivos relacionados (mesmo diretório)

- `blueshift-ia-platform.html` — prospecto visual
- `blueshift_dev_guide.md` — detalhe técnico da estrutura
- `bootstrap.py` — ⚠️ SCAFFOLD INICIAL (STUBs vazios). **Não rode dentro deste repo.** Só serve para criar projeto do zero em outra pasta.
