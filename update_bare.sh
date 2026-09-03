#!/usr/bin/env bash
# BlueShift — update SEM Docker (bare-metal: portal roda como processo
# Python direto no Linux, sem containers).
#
# Faz git fetch + checkout da tag no repo e reinicia o servico do portal
# (systemd). O update_client dispara este script DESACOPLADO
# (start_new_session) — ele sobrevive ao restart do proprio servico e
# termina sozinho (mesma ideia do container irmao no modo Docker).
#
# Requisitos (instalacao bare-metal):
#   - clone do repo em $REPO_DIR (default /opt/blueshift/repo)
#   - portal rodando como servico systemd (BLUESHIFT_SERVICE_NAME,
#     default "blueshift") — para o restart automatico
# Sem systemd, o script faz o checkout e orienta o restart manual.
set -euo pipefail

REPO_DIR="${BLUESHIFT_REPO_DIR:-/opt/blueshift/repo}"
TAG="${1:-}"
LOG_FILE="${BLUESHIFT_UPDATE_LOG:-/opt/blueshift/update.log}"
SERVICE="${BLUESHIFT_SERVICE_NAME:-blueshift}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if [ -z "$TAG" ]; then
  log "uso: update_bare.sh <tag>"
  exit 1
fi
if [ ! -d "${REPO_DIR}/.git" ]; then
  log "ERRO: ${REPO_DIR} nao e um clone git valido"
  exit 1
fi

cd "$REPO_DIR"

# O processo roda como o usuario do servico; o repo pode ser de outro dono —
# defensivo (mesmo caso do container, CVE-2022-24765).
git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true

log "update ${TAG} iniciado (bare-metal, repo ${REPO_DIR})"
git fetch origin --tags
git checkout "${TAG}"
log "checkout concluido: $(git describe --tags --abbrev=0)"

if command -v systemctl >/dev/null 2>&1; then
  log "reiniciando servico ${SERVICE}..."
  systemctl restart "${SERVICE}"
  log "Update concluido: ${TAG}"
else
  log "Update concluido: ${TAG} (checkout feito — reinicie o servico manualmente:"
  log "  systemctl restart ${SERVICE}   ou reinicie o processo do portal)"
fi
