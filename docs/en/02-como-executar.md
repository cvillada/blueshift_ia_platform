<!-- sync: 02-como-executar.md@eb92964854ad | checar: python tools/readme_check.py -->
🌐 [Português](../02-como-executar.md) · **English** · [Español](../es/02-como-executar.md)

## 3. How to Run

### 3.1 Local (development)

```bash
# virtual environment
python -m venv bp-venv && source bp-venv/bin/activate
pip install -e .

# starts the portal (default: 0.0.0.0:8080)
blueshift portal

# or with custom host/port
blueshift portal --host 0.0.0.0 --port 8080 --debug
```

The first boot creates the `data/portal.db` database and seeds the demo
(1 client, 5 users, 5 agents, sample models and connectors).

### 3.2 Docker (production / delivery)

> **🔑 Before installing in production, request the activation key** —
> company registration (legal name, CNPJ and contact) → key issued right away:
> **https://static.190.55.99.91.clients.your-server.de:9096/**
> (`BS-DEV-*` key is only valid in dev; production without a real key = not activated).

```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker volume create blueshift_data
docker run -d --name blueshift-platform -p 8090:8080 \
  -v blueshift_data:/data/blueshift \
  -e BLUESHIFT_PORTAL_DB=/data/blueshift/portal.db \
  -e BLUESHIFT_LICENSE=SUA-CHAVE-DA-BLUESHIFT \
  blueshift/platform blueshift portal
```

> In production, validation is online against the BlueShift License Server:
> also set `BLUESHIFT_LICENSE_URL=<url-da-pagina-de-solicitacao>/v1/validate`
> in the `.env` (the default points to the local mock, which only knows dev keys).

Or via docker-compose (with `BLUESHIFT_AREAS` and `TZ=America/Sao_Paulo`):
```bash
docker compose up -d --build
```

> **Update via Git:** the compose mounts the repository (default: the compose
> directory itself; in production, a clone at `/opt/blueshift/repo`)
> and the host's `docker.sock` into the portal container — the screen
> Settings (Configurações) → Updates (Atualizações) reads the repo version and triggers the rebuild
> (data preserved).

Access: `http://localhost:8090/portal/login`

### 3.3 Environment variables

| Variable | Default | Effect |
|:---------|:-------|:-------|
| `BLUESHIFT_PORTAL_DB` | `data/portal.db` | SQLite database path |
| `BLUESHIFT_PORTAL_SECRET` | random | Session secret key |
| `BLUESHIFT_PORTAL_SECURE` | empty | `1/true` → Secure cookie (HTTPS) |
| `BLUESHIFT_AREAS` | vendas,suporte,financeiro,rh,operacoes | **Initial seed** of the areas — afterwards the Registry (Cadastros) → Areas (Áreas) screen dominates (database) |
| `BLUESHIFT_LICENSE` | empty | **Activation key issued by BlueShift** (company registration — link in the installation/license section of this document); empty = not activated. `BS-DEV-*` only with `BLUESHIFT_DEV=1` |
| `BLUESHIFT_LICENSE_URL` | localhost:9000 | License validation URL — production/customer: BlueShift License Server (`<url-da-pagina-de-solicitacao>/v1/validate`); default = local mock (dev only) |
| `BLUESHIFT_REPO_DIR` | /opt/blueshift/repo | Directory of the git clone (Update via Git — Updates screen) |
| `BLUESHIFT_ROUTER_MODEL` | empty | **ROUTING** model (see §5.8 — routing model): **ID or NAME** of the model (the name is what appears in the Models AI (Modelos IA) screen, which also displays the ID); empty = main model of each agent (**not recommended** — it makes every question more expensive). Rule: **small, smart and fast** (INSTRUCT, never reasoning). Examples: `qwen3-4b-instruct-2507` (validated in production) and `hermes-3-llama-3.1-8b` |
| `GATEWAY_PORT` | 9003 | Published port of the OpenAI-compatible Gateway (external chats) |
| `GATEWAY_PUBLIC_URL` | empty | Public gateway URL shown on the screen (e.g. `http://192.168.0.10:9003/v1`) — without it, the request host is used. External chat in Docker on the same machine: `http://host.docker.internal:9003/v1` |
| `BLUESHIFT_PORTAL_SECRET` | empty | Portal SESSION key — must be **FIXED across deploys** (without it, every rebuild generates a new key and takes down all logins; the logged-in user is dropped, with a redirect to the login on the next click). Change it in production and keep it stable |
| `BLUESHIFT_SEED_DEMO` | 1 | `1` = XPTO demo data (dev); `0` = clean database → the first entry becomes Initial setup (Configuração inicial) (end customer) |
| `BLUESHIFT_DEV` | 0 | **Production/customer = 0** (the Updates screen applies for real; `BS-DEV-*` keys are NOT valid); dev = 1 (dry-run + BS-DEV-* license) |
| `TZ` | UTC | Time zone (use `America/Sao_Paulo`) |

> The `.env.example` in the root lists every variable with comments — copy
> it to `.env` before installing. Without Docker: `set -a; . ./.env; set +a` and
> run `blueshift portal`.

---
### Internal variables (no need to set them)

| Variable | Default | What it is for |
|:---------|:------:|:---------------|
| `BLUESHIFT_CHANNEL_FILE` | `/opt/blueshift/data/channels.json` | File used by the channel/license server built into dev |
| `BLUESHIFT_LICENSE_PORT` | `9000` | License Server port (mock in dev; in production validation is external) |
