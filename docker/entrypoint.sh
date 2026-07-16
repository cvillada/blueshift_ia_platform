#!/usr/bin/env bash
# BlueShift container entrypoint.
#
# Sobe o License Server mock (Flask) em background e, em seguida, executa o
# comando principal (CMD) em foreground. Assim o container ja nasce com o
# License Server de pe, e o license_client.py valida a chave 100% offline
# (sem dependencia de rede externa).
#
# O License Server escuta na porta 9000 dentro do container. O client ja
# aponta para http://localhost:9000/v1/validate via BLUESHIFT_LICENSE_URL.
set -e

LICENSE_PORT="${BLUESHIFT_LICENSE_PORT:-9000}"

echo "[entrypoint] iniciando License Server mock na porta ${LICENSE_PORT}..."
python -m blueshift_layer.license_server_mock &
LICENSE_PID=$!

# health check: aguarda o /healthz do mock responder antes de proseguir
for i in $(seq 1 30); do
  if python - <<'PY' "${LICENSE_PORT}" 2>/dev/null
import sys, urllib.request
port = sys.argv[1]
try:
    urllib.request.urlopen(f"http://localhost:{port}/healthz", timeout=1)
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
  then
    echo "[entrypoint] License Server pronto (porta ${LICENSE_PORT})."
    break
  fi
  sleep 1
done

# encerra o License Server de forma limpa se o container receber sinal
trap 'kill -TERM "$LICENSE_PID" 2>/dev/null || true' EXIT TERM INT

# executa o comando principal (ex: blueshift status | blueshift portal)
exec "$@"
