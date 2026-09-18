<!-- sync: 02-como-executar.md@eb92964854ad | checar: python tools/readme_check.py -->
🌐 [Português](../02-como-executar.md) · [English](../en/02-como-executar.md) · **Español**

## 3. Cómo ejecutar

### 3.1 Local (desarrollo)

```bash
# entorno virtual
python -m venv bp-venv && source bp-venv/bin/activate
pip install -e .

# levanta el portal (predeterminado: 0.0.0.0:8080)
blueshift portal

# o con host/puerto personalizados
blueshift portal --host 0.0.0.0 --port 8080 --debug
```

El primer arranque crea la base `data/portal.db` y siembra el demo
(1 cliente, 5 usuarios, 5 agentes, modelos y conectores de ejemplo).

### 3.2 Docker (producción / entrega)

> **🔑 Antes de instalar en producción, solicite la clave de activación** —
> registro de la empresa (razón social, CNPJ y contacto) → clave emitida al instante:
> **https://static.190.55.99.91.clients.your-server.de:9096/**
> (la clave `BS-DEV-*` solo vale en dev; producción sin clave real = no activada).

```bash
docker build -t blueshift/platform -f docker/Dockerfile .
docker volume create blueshift_data
docker run -d --name blueshift-platform -p 8090:8080 \
  -v blueshift_data:/data/blueshift \
  -e BLUESHIFT_PORTAL_DB=/data/blueshift/portal.db \
  -e BLUESHIFT_LICENSE=SUA-CHAVE-DA-BLUESHIFT \
  blueshift/platform blueshift portal
```

> En producción la validación es online contra el License Server de BlueShift:
> defina también `BLUESHIFT_LICENSE_URL=<url-de-la-pagina-de-solicitud>/v1/validate`
> en el `.env` (el default apunta al mock local, que solo conoce claves de dev).

O mediante docker-compose (con `BLUESHIFT_AREAS` y `TZ=America/Sao_Paulo`):
```bash
docker compose up -d --build
```

> **Update vía Git:** el compose monta el repositorio (predeterminado: el propio
> directorio del compose; en producción, un clon en `/opt/blueshift/repo`)
> y el `docker.sock` del host en el contenedor del portal — la pantalla
> Configuración → Actualizaciones (Configurações → Atualizações) lee la versión
> del repo y dispara el rebuild (datos preservados).

Acceso: `http://localhost:8090/portal/login`

### 3.3 Variables de entorno

| Variable | Predeterminado | Efecto |
|:---------|:-------|:-------|
| `BLUESHIFT_PORTAL_DB` | `data/portal.db` | Ruta de la base SQLite |
| `BLUESHIFT_PORTAL_SECRET` | aleatorio | Secret key de las sesiones |
| `BLUESHIFT_PORTAL_SECURE` | vacío | `1/true` → cookie Secure (HTTPS) |
| `BLUESHIFT_AREAS` | vendas,suporte,financeiro,rh,operacoes | **Seed inicial** de las áreas — después manda la pantalla Registros → Áreas (Cadastros → Áreas) (base de datos) |
| `BLUESHIFT_LICENSE` | vacío | **Clave de activación emitida por BlueShift** (registro de la empresa — enlace en la sección de instalación/licencia de este documento); vacío = no activada. `BS-DEV-*` solo con `BLUESHIFT_DEV=1` |
| `BLUESHIFT_LICENSE_URL` | localhost:9000 | URL de validación de licencia — producción/cliente: License Server de BlueShift (`<url-de-la-pagina-de-solicitud>/v1/validate`); default = mock local (solo dev) |
| `BLUESHIFT_REPO_DIR` | /opt/blueshift/repo | Directorio del clon git (Update vía Git — pantalla Actualizaciones) |
| `BLUESHIFT_ROUTER_MODEL` | vacío | Modelo de **ENRUTAMIENTO** (ver §5.8 — modelo de enrutamiento): **ID o NOMBRE** del modelo (el nombre es el que aparece en la pantalla Modelos de IA (Modelos IA), que también muestra el ID); vacío = modelo principal de cada agente (**no recomendado** — encarece todas las preguntas). Regla: **pequeño, inteligente y rápido** (INSTRUCT, nunca reasoning). Ejemplos: `qwen3-4b-instruct-2507` (validado en producción) y `hermes-3-llama-3.1-8b` |
| `GATEWAY_PORT` | 9003 | Puerto publicado del Gateway compatible con OpenAI (chats externos) |
| `GATEWAY_PUBLIC_URL` | vacío | URL pública del gateway mostrada en la pantalla (ej.: `http://192.168.0.10:9003/v1`) — sin ella, se usa el host de la petición. Chat externo en Docker en la misma máquina: `http://host.docker.internal:9003/v1` |
| `BLUESHIFT_PORTAL_SECRET` | vacío | Clave de la SESIÓN del portal — debe ser **FIJA entre despliegues** (sin ella, cada rebuild genera una clave nueva y tumba todos los inicios de sesión; el usuario conectado se cae con redirección al login en el siguiente clic). Cambiar en producción y mantener estable |
| `BLUESHIFT_SEED_DEMO` | 1 | `1` = datos demo XPTO (dev); `0` = base limpia → la primera entrada pasa a ser la Configuración inicial (Configuração inicial) (cliente final) |
| `BLUESHIFT_DEV` | 0 | **Producción/cliente = 0** (la pantalla Actualizaciones aplica de verdad; las claves `BS-DEV-*` NO valen); dev = 1 (dry-run + licencia BS-DEV-*) |
| `TZ` | UTC | Zona horaria (usar `America/Sao_Paulo`) |

> El `.env.example` de la raíz trae todas las variables con comentarios — copie
> a `.env` antes de instalar. Sin Docker: `set -a; . ./.env; set +a` y
> ejecute `blueshift portal`.

---
### Variables internas (no es necesario definirlas)

| Variable | Predeterminado | Para qué sirve |
|:---------|:------:|:---------------|
| `BLUESHIFT_CHANNEL_FILE` | `/opt/blueshift/data/channels.json` | Archivo usado por el canal/servidor de licencia integrado en dev |
| `BLUESHIFT_LICENSE_PORT` | `9000` | Puerto del License Server (mock en dev; en producción la validación es externa) |
