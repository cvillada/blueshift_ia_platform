#!/usr/bin/env bash
# BlueShift IA Platform — Update a partir do Git (A4)
#
# Faz o update da plataforma: puxa a tag aprovada do repositório e
# recria os containers (dados preservados — volumes intactos).
#
# Uso:
#   ./update.sh v0.9.4            # atualiza para a tag v0.9.4
#   REPO_DIR=/caminho ./update.sh # repo em outro lugar (dev)
#
# Seguranca:
#   - Aborta se o repo tiver alteracoes locais (nunca sobrescreve trabalho)
#   - Log completo em /opt/blueshift/update.log (quando gravavel)
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/blueshift/repo}"
TAG="${1:-}"
LOG_FILE="${BLUESHIFT_UPDATE_LOG:-/opt/blueshift/update.log}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if [ -z "$TAG" ]; then
  log "ERRO: informe a tag (ex: ./update.sh v0.9.4)"
  exit 1
fi

if [ ! -d "$REPO_DIR/.git" ]; then
  log "ERRO: repo nao encontrado em $REPO_DIR (git clone necessario)"
  exit 1
fi

log "Update BlueShift -> tag $TAG (repo: $REPO_DIR)"
cd "$REPO_DIR"

log "git fetch origin --tags"
git fetch origin --tags

# Aborta se houver alteracoes locais (nao sobrescreve trabalho)
if ! git diff --quiet HEAD; then
  log "ERRO: repo com alteracoes locais — faça commit/stash antes do update"
  exit 1
fi

log "git checkout $TAG"
git checkout "$TAG"

log "docker compose up -d --build"
# Projeto do compose: o update roda DENTRO do container (docker.sock). Se o
# compose rodar daqui, deriva o projeto do nome do diretorio (/opt/blueshift/
# repo -> "repo") e NAO reconhece os containers criados pelo host (projeto
# "blueshift_ia_platform") -> conflito de nome e o update aborta sem trocar
# os containers. Deriva o projeto do container em execucao (label real).
PROJ="$(docker inspect blueshift-platform \
  --format '{{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null)"
PROJ="${PROJ:-blueshift_ia_platform}"
docker compose -p "$PROJ" up -d --build

log "Update concluido: $TAG"
