## 3. Como Executar

### 3.1 Local (desenvolvimento)

```bash
# ambiente virtual
python -m venv bp-venv && source bp-venv/bin/activate
pip install -e .

# sobe o portal (padrão: 0.0.0.0:8080)
blueshift portal

# ou com host/porta customizados
blueshift portal --host 0.0.0.0 --port 8080 --debug
```

O primeiro boot cria o banco `data/portal.db` e semeia o demo
(1 cliente, 5 usuários, 5 agentes, modelos e conectores de exemplo).

### 3.2 Docker (produção / entrega)

> **🔑 Antes de instalar em produção, solicite a chave de ativação** —
> cadastro da empresa (razão social, CNPJ e contato) → chave emitida na hora:
> **https://static.190.55.99.91.clients.your-server.de:9096/**
> (chave `BS-DEV-*` só vale em dev; produção sem chave real = não ativada).

```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker volume create blueshift_data
docker run -d --name blueshift-platform -p 8090:8080 \
  -v blueshift_data:/data/blueshift \
  -e BLUESHIFT_PORTAL_DB=/data/blueshift/portal.db \
  -e BLUESHIFT_LICENSE=SUA-CHAVE-DA-BLUESHIFT \
  blueshift/platform blueshift portal
```

> Em produção a validação é online contra o License Server da BlueShift:
> defina também `BLUESHIFT_LICENSE_URL=<url-da-pagina-de-solicitacao>/v1/validate`
> no `.env` (o default aponta para o mock local, que só conhece chaves de dev).

Ou via docker-compose (com `BLUESHIFT_AREAS` e `TZ=America/Sao_Paulo`):
```bash
docker compose up -d --build
```

> **Update via Git:** o compose monta o repositório (padrão: o próprio
> diretório do compose; em produção, um clone em `/opt/blueshift/repo`)
> e o `docker.sock` do host no container do portal — a tela
> Configurações → Atualizações lê a versão do repo e dispara o rebuild
> (dados preservados).

Acesso: `http://localhost:8090/portal/login`

### 3.3 Variáveis de ambiente

| Variável | Padrão | Efeito |
|:---------|:-------|:-------|
| `BLUESHIFT_PORTAL_DB` | `data/portal.db` | Caminho do banco SQLite |
| `BLUESHIFT_PORTAL_SECRET` | aleatório | Secret key das sessões |
| `BLUESHIFT_PORTAL_SECURE` | vazio | `1/true` → cookie Secure (HTTPS) |
| `BLUESHIFT_AREAS` | vendas,suporte,financeiro,rh,operacoes | **Seed inicial** das áreas — depois a tela Cadastros → Áreas domina (banco) |
| `BLUESHIFT_LICENSE` | vazio | **Chave de ativação emitida pela BlueShift** (cadastro da empresa — link na seção de instalação/licença deste documento); vazio = não ativada. `BS-DEV-*` só com `BLUESHIFT_DEV=1` |
| `BLUESHIFT_LICENSE_URL` | localhost:9000 | URL de validação de licença — produção/cliente: License Server da BlueShift (`<url-da-pagina-de-solicitacao>/v1/validate`); default = mock local (só dev) |
| `BLUESHIFT_REPO_DIR` | /opt/blueshift/repo | Diretório do clone git (Update via Git — tela Atualizações) |
| `BLUESHIFT_ROUTER_MODEL` | vazio | Modelo de **ROTEAMENTO** (ver §5.8 — modelo de roteamento): **ID ou NOME** do modelo (o nome é o que aparece na tela Modelos IA, que também exibe o ID); vazio = modelo principal de cada agente (**não recomendado** — encarece toda pergunta). Regra: **pequeno, inteligente e rápido** (INSTRUCT, nunca reasoning). Exemplos: `qwen3-4b-instruct-2507` (validado em produção) e `hermes-3-llama-3.1-8b` |
| `GATEWAY_PORT` | 9003 | Porta publicada do Gateway OpenAI-compatível (chats externos) |
| `GATEWAY_PUBLIC_URL` | vazio | URL pública do gateway exibida na tela (ex: `http://192.168.0.10:9003/v1`) — sem ela, usa o host da requisição. Chat externo em Docker na mesma máquina: `http://host.docker.internal:9003/v1` |
| `BLUESHIFT_PORTAL_SECRET` | vazio | Chave da SESSÃO do portal — deve ser **FIXA entre deploys** (sem ela, cada rebuild gera uma chave nova e derruba todos os logins; usuário logado cai com redirecionamento para o login no próximo clique). Trocar em produção e manter estável |
| `BLUESHIFT_SEED_DEMO` | 1 | `1` = dados demo XPTO (dev); `0` = banco limpo → primeira entrada vira Configuração inicial (cliente final) |
| `BLUESHIFT_DEV` | 0 | **Produção/cliente = 0** (a tela Atualizações aplica de verdade; chaves `BS-DEV-*` NÃO valem); dev = 1 (dry-run + licença BS-DEV-*) |
| `TZ` | UTC | Fuso (usar `America/Sao_Paulo`) |

> O `.env.example` da raiz traz todas as variáveis com comentários — copie
> para `.env` antes de instalar. Sem Docker: `set -a; . ./.env; set +a` e
> rode `blueshift portal`.

---
### Variáveis internas (não é necessário definir)

| Variável | Padrão | Para que serve |
|:---------|:------:|:---------------|
| `BLUESHIFT_CHANNEL_FILE` | `/opt/blueshift/data/channels.json` | Arquivo usado pelo canal/servidor de licença embutido em dev |
| `BLUESHIFT_LICENSE_PORT` | `9000` | Porta do License Server (mock em dev; em produção a validação é externa) |
