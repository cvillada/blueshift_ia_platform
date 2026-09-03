#!/usr/bin/env bash
# BlueShift container entrypoint.
#
# Sobe o License Server mock (Flask, porta 9000) e o Update Channel Server
# mock (Flask, porta 9001) SOMENTE em desenvolvimento:
#   - BLUESHIFT_DEV=1, OU
#   - BLUESHIFT_LICENSE_URL apontando para o proprio localhost (default,
#     instancia sem .env customizado).
# Em producao/cliente com BLUESHIFT_LICENSE_URL real (License Server da
# BlueShift), os mocks NAO sobem: a validacao vai ao servidor da BlueShift
# (pagina de solicitacao de chave). Mock de licenca dentro do container de
# producao do cliente so esconderia o estado real da chave.
set -e

# git safe.directory: o repo montado (/opt/blueshift/repo) tem dono 1000:1000
# e o git (CVE-2022-24765) recusa operar nele ("dubious ownership") — sem isso
# o update_client (ls-remote/describe/fetch) falha e a tela Atualizacoes nunca
# lista uma versao nova. Configura para o REPO_DIR efetivo (default ou env).
REPO_DIR_GIT="${BLUESHIFT_REPO_DIR:-/opt/blueshift/repo}"
git config --global --add safe.directory "$REPO_DIR_GIT" 2>/dev/null || true

LICENSE_PORT="${BLUESHIFT_LICENSE_PORT:-9000}"
UPDATE_PORT="${BLUESHIFT_UPDATE_PORT:-9001}"
BLUESHIFT_DEV="${BLUESHIFT_DEV:-0}"
LICENSE_URL="${BLUESHIFT_LICENSE_URL:-http://localhost:9000/v1/validate}"

SOBE_MOCKS=0
if [ "$BLUESHIFT_DEV" = "1" ]; then
  SOBE_MOCKS=1
else
  case "$LICENSE_URL" in
    http://localhost:*|http://127.0.0.1:*) SOBE_MOCKS=1 ;;
  esac
fi

LICENSE_PID=""
UPDATE_PID=""
if [ "$SOBE_MOCKS" = "1" ]; then
  echo "[entrypoint] dev: iniciando License Server mock na porta ${LICENSE_PORT}..."
  python -m blueshift_layer.license_server_mock &
  LICENSE_PID=$!

  echo "[entrypoint] dev: iniciando Update Channel Server mock na porta ${UPDATE_PORT}..."
  python -m blueshift_layer.update_server &
  UPDATE_PID=$!

  # health check: aguarda o /healthz de ambos os mocks responderem
  for i in $(seq 1 30); do
    READY=1
    for port in "${LICENSE_PORT}" "${UPDATE_PORT}"; do
      if ! python - "$port" <<'PY' 2>/dev/null
import sys, urllib.request
port = sys.argv[1]
try:
    urllib.request.urlopen(f"http://localhost:{port}/healthz", timeout=1)
except Exception:
    sys.exit(1)
PY
      then
        READY=0
        break
      fi
    done
    if [ "$READY" = "1" ]; then
      echo "[entrypoint] License Server pronto (porta ${LICENSE_PORT})."
      echo "[entrypoint] Update Channel pronto (porta ${UPDATE_PORT})."
      break
    fi
    sleep 1
  done
else
  echo "[entrypoint] producao: mocks desligados (licenca via ${LICENSE_URL})"
fi

# encerra os mocks de forma limpa se o container receber sinal
trap '[ -n "$LICENSE_PID" ] && kill -TERM "$LICENSE_PID" "$UPDATE_PID" 2>/dev/null || true' EXIT TERM INT

# executa o comando principal (ex: blueshift status | blueshift portal)
exec "$@"
