# BlueShift IA Platform - imagem Docker (Fase 2)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /opt/blueshift

# Hermes-Agent como dependencia (MIT, nao modificado)
RUN pip install hermes-agent==0.18.2

COPY . /opt/blueshift
RUN pip install --no-cache-dir -e .

# Entrypoint sobe o License Server mock junto com o comando principal
COPY docker/entrypoint.sh /opt/blueshift/docker/entrypoint.sh
RUN chmod +x /opt/blueshift/docker/entrypoint.sh

# Volume persistente: modelo fine-tuned + memoria do cliente
VOLUME ["/opt/blueshift/models", "/opt/blueshift/data"]

# License Server (mock) na 9000 + Update Channel (mock) na 9001 + app/portal na 8080.
# BLUESHIFT_LICENSE_URL aponta para o mock dentro do container (validacao offline).
ENV BLUESHIFT_LICENSE_URL="http://localhost:9000/v1/validate"
ENV BLUESHIFT_LICENSE_PORT="9000"
ENV BLUESHIFT_UPDATE_URL="http://localhost:9001/v1/channel"
ENV BLUESHIFT_UPDATE_PORT="9001"
# Ambiente de dev/demo: aplica update em dry-run e usa chaves BS-DEV-*
ENV BLUESHIFT_DEV="1"
EXPOSE 8080 9000 9001

ENTRYPOINT ["/opt/blueshift/docker/entrypoint.sh"]
CMD ["blueshift", "status"]
