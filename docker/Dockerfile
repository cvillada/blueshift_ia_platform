# BlueShift IA Platform - imagem Docker (Fase 2)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /opt/blueshift

COPY . /opt/blueshift
RUN pip install --no-cache-dir -e .

# Node.js para servidores MCP via stdio (ex: airbnb mcp-server)
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# git + docker CLI p/ Update via Git (A4): o portal le a versao do repo
# e dispara o rebuild pelo docker.sock do host (montado no compose)
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Entrypoint sobe o License Server mock junto com o comando principal
COPY docker/entrypoint.sh /opt/blueshift/docker/entrypoint.sh
RUN chmod +x /opt/blueshift/docker/entrypoint.sh

# Volume persistente: dados do portal + memoria do cliente
VOLUME ["/opt/blueshift/data"]

# License Server (mock) na 9000 + Update Channel (mock) na 9001 + app/portal na 8080.
# BLUESHIFT_LICENSE_URL aponta para o mock dentro do container (validacao offline).
ENV BLUESHIFT_LICENSE_URL="http://localhost:9000/v1/validate"
ENV BLUESHIFT_LICENSE_PORT="9000"
ENV BLUESHIFT_UPDATE_URL="http://localhost:9001/v1/channel"
ENV BLUESHIFT_UPDATE_PORT="9001"
# Ambiente de dev/demo: aplica update em dry-run e usa chaves BS-DEV-*
# CLIENTE/PRODUCAO = 0 (a tela Atualizacoes aplica de verdade). Dev local = 1.
ENV BLUESHIFT_DEV="0"
EXPOSE 8080 9000 9001

ENTRYPOINT ["/opt/blueshift/docker/entrypoint.sh"]
CMD ["blueshift", "status"]
