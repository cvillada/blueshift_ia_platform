#!/usr/bin/env bash
# BlueShift IA Platform — installer de cliente (on-premise).
#
# Faz o bootstrap completo em um comando:
#   1. valida que o Docker esta disponivel
#   2. cria o .env a partir de .env.example (se ainda nao existir)
#   3. sobe a plataforma com docker compose (build + up -d)
#   4. aguarda o health e imprime a URL de acesso + proximos passos
#
# Modelos de IA: a plataforma NAO embute modelo. Depois de subir, va em
# "Modelos IA" no Portal e cadastre os seus (local vLLM/LM Studio ou externo
# DeepSeek/OpenRouter/OpenAI/Claude). Cada agente usa o modelo que voce definir.
set -e

cd "$(dirname "$0")"

echo "=== BlueShift IA Platform — installer ==="

# 1. Docker disponivel?
if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: Docker nao encontrado. Instale o Docker antes de continuar."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERRO: 'docker compose' nao disponivel. Use Docker Desktop ou instale o plugin."
  exit 1
fi

# 2. .env
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "[installer] .env criado a partir de .env.example — edite BLUESHIFT_LICENSE se necessario."
  else
    echo "ERRO: .env.example ausente."
    exit 1
  fi
else
  echo "[installer] .env ja existe — usando configuracoes atuais."
fi

# carrega variaveis do .env para o script (docker compose ja as usa nativamente)
set -a; [ -f .env ] && . ./.env; set +a

# 3. Sobe a plataforma
echo "[installer] subindo a plataforma (build + up -d)..."
docker compose up -d --build

# 4. Aguarda o Portal responder
PORTAL_PORT="${PORTAL_PORT:-8080}"
echo "[installer] aguardando o Portal ficar pronto em porta ${PORTAL_PORT}..."
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORTAL_PORT}/portal/" 2>/dev/null | grep -q "200\|302"; then
    break
  fi
  sleep 2
done

echo ""
echo "=== BlueShift instalado ==="
echo "Acesse o Portal: http://localhost:${PORTAL_PORT}/portal"
echo "Login demo: admin / admin123  (troque em producao!)"
echo ""
echo "Proximos passos:"
echo "  1. Vá em 'Modelos IA' e cadastre SEUS modelos de IA:"
echo "       - Local/servidor interno: vLLM, LM Studio, Ollama (base_url interna, sem api_key)"
echo "       - Externo: DeepSeek, OpenRouter, OpenAI, Claude (base_url + api_key)"
echo "  2. Crie agentes em 'Agentes' e defina qual modelo cada um usa."
echo "  3. (Opcional) crie um 'Canal' em 'Canais' para expor o agente via API/webhook."
echo ""
echo "Logs: docker compose logs -f"
echo "Parar: docker compose down"
