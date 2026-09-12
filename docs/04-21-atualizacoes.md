### 5.21 Atualizações (/portal/atualizacoes) — versão e configuração de ambiente

**Onde:** Configurações → Atualizações.

**Propósito:** update da plataforma a partir do **Git** (tags de versão).
Mostra a versão instalada (tag do repo) e se há tag nova disponível no
remoto. Admin-only.

**Como funciona:**
- O servidor mantém um **clone fixo** do repositório (padrão
  `/opt/blueshift/repo` — variável `BLUESHIFT_REPO_DIR`; no compose o repo
  é montado no container junto com o `docker.sock` do host)
- Versão instalada = `git describe --tags` do repo (ex: `v0.9.3`)
- Versão disponível = tags do remoto (`git ls-remote`), ordenadas por
  versão; a mais recente diferente da instalada aparece como atualização
- **Aplicar atualização** roda `update.sh <tag>` em background:
  `git fetch` + `git checkout <tag>` + `docker compose up -d --build`
  (dados preservados — volumes intactos). O portal reinicia ao concluir;
  log em `/opt/blueshift/update.log`
- A configuração da instalação (ex.: `BLUESHIFT_LICENSE_URL`, chave de
  licença, roteador) é **repassada ao portal recriado** via env do próprio
  container em execução — o update não depende do compose ler o `.env` do
  host (que falhava de dentro do container irmão e fazia a licença cair no
  mock `localhost:9000`, exibindo "inválida" após todo update)
- Em dev (`BLUESHIFT_DEV=1`) o botão faz **dry-run** (mostra o comando,
  não derruba o ambiente); se o remoto for inacessível (repo privado sem
  credencial), usa as tags locais como referência
- Se o repo não existir, a tela avisa "repo não encontrado" (sem quebrar)

**Card "Configuração de ambiente":** exibe as configurações ativas da
instalação:
- **Modelo de roteamento configurado** — o `BLUESHIFT_ROUTER_MODEL`
  resolvido (nome + ID, ou "(não encontrado)" se a env apontar um modelo
  inexistente; vazio = modelo principal de cada agente);
- **Áreas configuradas** — a lista do cadastro Cadastros → Áreas (banco;
  a env `BLUESHIFT_AREAS` serve só como seed inicial do primeiro boot).

**Card "Atualização manual (se o botão falhar)":** traz os comandos para
atualizar na mão a partir do **host** do servidor (útil quando o botão
erra por rede, repo sujo ou imagem que não troca):
1. descobrir a pasta do repo no host (`docker inspect` do mount
   `/opt/blueshift/repo`);
2. `git fetch origin --tags && git checkout vX.Y.Z && docker compose up -d --build`;
3. conferir com `docker ps` + `git describe --tags`.
Inclui também o caminho **sem Docker** (`bash update_bare.sh vX.Y.Z`, Linux
direto) e o aviso de nunca rodar `docker compose down -v` (apaga o volume
de dados). O diagnóstico de "repo não encontrado" (dubious ownership) é o
`safe.directory` do git no container — o entrypoint já configura; o
container irmão do update pula o entrypoint, então o fix pode ser aplicado
à mão com `docker exec` quando necessário.
**Variáveis internas do canal de atualização:** `BLUESHIFT_UPDATE_PORT`
(porta do servidor de atualização embutido), `BLUESHIFT_UPDATE_SCRIPT` e
`BLUESHIFT_UPDATE_BARE_SCRIPT` (scripts de atualização — o `bare` é o usado
quando o repositório está montado) e `BLUESHIFT_UPDATE_LOG` (arquivo de log do
processo de atualização). Não é necessário defini-las no uso normal.
**Licença:** a tela mostra a chave ativa (mascarada) e o status da validação. O
campo técnico `licenca` corresponde à chave de ativação definida na instalação
(`BLUESHIFT_LICENSE`); para trocar, reinicie o container com a nova chave.

