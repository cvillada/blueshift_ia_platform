#!/usr/bin/env bash
# BlueShift container entrypoint.
#
# Sobe o License Server mock (Flask, porta 9000) e o Update Channel Server
# mock (Flask, porta 9001) em background, e em seguida executa o comando
# principal (CMD) em foreground. Assim o container ja nasce com ambos de pe:
#  - License Server: valida a chave 100% offline (sem rede externa)
#  - Update Channel: serve a versao aprovada da camada (BLUESHIFT_UPDATE_URL)
set -e

LICENSE_PORT="${BLUESHIFT_LICENSE_PORT:-9000}"
UPDATE_PORT="${BLUESHIFT_UPDATE_PORT:-9001}"

echo "[entrypoint] iniciando License Server mock na porta ${LICENSE_PORT}..."
python -m blueshift_layer.license_server_mock &
LICENSE_PID=$!

echo "[entrypoint] iniciando Update Channel Server mock na porta ${UPDATE_PORT}..."
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

# encerra os mocks de forma limpa se o container receber sinal
trap 'kill -TERM "$LICENSE_PID" "$UPDATE_PID" 2>/dev/null || true' EXIT TERM INT

# executa o comando principal (ex: blueshift status | blueshift portal)
exec "$@"
