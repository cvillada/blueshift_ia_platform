<div align="center">

<!-- sync: README.md@afb44662ecea | checar: python tools/readme_check.py -->
🌐 [Português](README.md) · [English](README.en.md) · **Español**

# 🔷 CL Agents - BlueShift IA Platform

**Plataforma propia de Inteligencia Artificial on-premise — 100% Python, Flask standalone.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-Commercial-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docker.com)

**Despliegue on-premise · Datos 100% en el cliente · Modelos híbridos (local/externo) · Agentes por área · Licencia anual**

</div>

---

## 📋 Índice

- [Visión General](#-visión-general)
- [Arquitectura](#-arquitectura)
- [Funcionalidades](#-funcionalidades)
- [Empezando](#-empezando)
- [Comandos CLI](#-comandos-cli)
- [Modelos Locales de IA](#-modelos-locales-de-ia)
- [Docker](#-docker)
- [Instalación sin Docker (Linux directo)](#-instalación-sin-docker-linux-directo)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Stack Tecnológico](#-stack-tecnológico)
- [Hardware Recomendado](#-hardware-recomendado)
- [Documentación](#-documentación)
- [Licencia](#-licencia)

---

## 🚀 Visión General

La **BlueShift IA Platform** es una plataforma de inteligencia artificial diseñada para instalarse **dentro de la infraestructura del cliente** — datacenter, servidor dedicado o nube privada. A diferencia del SaaS, donde los datos salen de la empresa, aquí **todo permanece dentro del entorno del cliente**: datos, agentes, memoria de los usuarios e historial.

### 🎯 Diferenciales

| Característica | BlueShift |
|:---------------|:----------|
| **Datos** | 100% on-premise — nunca salen del cliente |
| **Modelos** | Híbrido: local (llama.cpp/LM Studio/vLLM/Ollama) o externo (OpenRouter/DeepSeek/OpenAI); **Modo de API** `openai_chat` o `responses` (agentes externos, ej.: AIDP `/chat`) |
| **Agentes** | Por área de la empresa (ventas, soporte, financiero, RR. HH., operaciones) |
| **Memoria** | Persistente por usuario — índice local en TF-IDF + coseno (sin base vectorial externa) |
| **RAG** | Conocimiento curado: importación CSV/PDF + alta manual (sin autoguardado de conversaciones desde la v0.10.14) |
| **Conectores** | Configurables: API REST (con OAuth2/bearer y job asíncrono), agentes A2A, servidores MCP y consultas SQL (TLS/wallet) |
| **Gateway OpenAI** | Chats externos (Open WebUI, LibreChat, apps) en el protocolo estándar — puerto 9003 |
| **Skills IA** | Generación de skills con el propio modelo registrado |
| **Documentación** | Docs navegable dentro del producto (búsqueda, una página por pantalla) + Ayuda IA sobre la misma fuente + API Reference y Changelog |
| **Licenciamiento** | Anual por empresa (no por token) |
| **Stack** | Python puro, Flask, SQLite — sin dependencias pesadas |

---

## 🏗️ Arquitectura

```
                    ┌─────────────────────┐
                    │   CLI (blueshift)    │
                    │  init · portal ·     │
                    │  mcp · gateway       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  🌐 PORTAL (Flask)   │
                    │  create_app() :8080  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  🔀 GATEWAY         │
                    │  /v1/chat/completions│
                    │  :9003 (OpenAI)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  💬 CHATS EXTERNOS  │
                    │  Open WebUI, apps   │
                    └────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌──────────┐         ┌──────────┐         ┌──────────┐
   │   AUTH   │         │  VIEWS   │         │   SSO    │
   │  auth.py │         │ views.py │         │  sso.py  │
   │   RBAC   │         │          │         │  OIDC    │
   └────┬─────┘         └────┬─────┘         └────┬─────┘
        │                   │                    │
        └───────────┬───────┴────────┬───────────┘
                    ▼                ▼
             ┌──────────┐     ┌──────────┐
             │  DB      │     │TEMPLATES │
             │  db.py   │     │templates │
             │ (SQLite) │     │   .py    │
             └────┬─────┘     └──────────┘
                  │
        ┌─────────┼──────────┐
        ▼         ▼          ▼
 ┌──────────┐ ┌──────┐ ┌──────────┐
 │ MEMORIA  │ │ LLM  │ │  AGENTE  │
 │ memory.py│ │client│ │ agente.py│
 │ (TF-IDF) │ │ .py  │ │Orq. Final│
 └──────────┘ └──────┘ └─────┬────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  PACK DE       │
                    │  CONECTORES    │
                    │  registry.py   │
                    └───┬────┬────┬──┘
                        │    │    │
                 ┌──────┘    │    └──────┐
                 ▼           ▼           ▼
           ┌─────────┐ ┌────────┐ ┌────────┐
           │ 🌐 API  │ │ 🔌 MCP │ │ 🗄️ SQL │
           │ urllib  │ │ stdio  │ │psycopg │
           │ REST    │ │ JSON-  │ │SELECT  │
           │         │ │ RPC    │ │        │
           └─────────┘ └────────┘ └────────┘
```

### Flujo de Ejecución del Agente

```
1   El usuario pregunta
    │
2   ▼
    Conectores del área  →  SQL / API REST / A2A / MCP
    │   Parámetros (id_cliente, email, fechas) extraídos de la pregunta
    │   * Placeholder {id_cliente} sustituido por los valores extraídos
    │
    ▼
3   RAG (TF-IDF)  ← siempre busca, top_k=2 si los conectores responden, 4 si están vacíos
    │   * Las skills indexadas también se encuentran aquí
    │
    ▼
4   LLM + Skills + Datos + Contexto  →  Respuesta (JSON)
    │   * Datos del sistema = FUENTE PRIMARIA
    │   * Contexto RAG = FUENTE SECUNDARIA
    │   * Modelo principal + fallback automático
    │
    ▼ (post-respuesta)
5   Post-respuesta  →  Graba pregunta + respuesta en el histórico (memoria de conversación)
    │   Base de conocimiento: solo importación/alta manual (sin auto-feed — v0.10.14)
    │
    ▼
6   Webhook (opcional)  →  POST de la respuesta a una URL externa (con retry 3x)
```

---

## ✨ Funcionalidades

### 🖥️ Portal del Cliente

| Pantalla | Descripción | Acceso |
|:-----|:----------|:-------|
| **Monitorear (Monitorar)** | Dashboard de salud: clientes, agentes, modelos, tokens, conectores | Login |
| **Workspace** | Panel por departamento con agentes y documentos del área; cards con **tokens por agente** (1d/7d/30d/90d) | Login |
| **Clientes** | Gestionar y registrar clientes | Admin |
| **Usuarios (Usuários)** | CRUD de usuarios con roles (admin/gestor/usuario/sistema) y área | Admin |
| **Áreas** | Alta de departamentos (base de datos; variable `BLUESHIFT_AREAS` solo seed inicial) | Admin |
| **Agentes** | Agent Factory: montar un agente con modelo + skills + conectores | Admin |
| **Skills** | Catálogo de skills por área (SKILL.md) | Login |
| **Memoria (Memória)** | Memoria persistente por usuario (base vectorial local) | Login |
| **Conocimiento (Conhecimento)** | Base de conocimiento RAG (manual, política, contratos + CSV + PDF) | Login |
| **Docs** | Documentación completa (carpeta `docs/`) en el menú lateral — las mismas páginas del popup Ayuda; convención de escritura en `docs/README.md` | Login |
| Modelos IA | Alta de LLMs OpenAI-compatible (local y externo) | Admin |
| **Conectores** | Alta de fuentes externas (API, A2A, MCP, SQL) + autenticación OAuth2/bearer, SSL/wallet, polling de jobs + finalidad (Art. 26 LGPD) | Admin |
| **Canales (Canais)** | API de integración con token + webhook de salida | Admin |
| **Gateway** | Activación del gateway OpenAI-compatible (canal + modo streaming/completa + límites de contexto) | Admin |
| **LGPD** | Conformidad en la salida: anonimizar LLM/RAG, aviso de privacidad, finalidad por conector, retención de logs | Admin |
| **Uso de Tokens** | Análisis de consumo por cliente/modelo/origen | Admin |
| **Observabilidad (Observabilidade)** | Dashboard IA: KPI, drift, costos, feedback, alertas | Admin |
| **Test A/B (Teste A/B)** | Reejecuta preguntas del feedback contra otro modelo y compara resultados con modelo juez | Admin/Gestor |
| **Auditoría** | Trazabilidad LGPD + 🔍 Rastreo paso a paso | Admin |
| **Archivo Muerto (Arquivo Morto)** | Snapshot sellado de la base de datos + corte manual (D-1 máx.) — controla el crecimiento sin perder histórico (detalles en [Limpieza y archivo muerto](#limpieza-y-archivo-muerto)) | Admin |
| **Fine-Tuning** | Documentación sobre formatos (GGUF/MLX), hardware y paso a paso | Login |
| **SSO (OIDC)** | Login federado (Azure AD, Okta, Keycloak, Google) | Admin |
| **Actualizaciones (Atualizações)** | Update vía Git (tags) — versión del repo + rebuild con datos preservados | Admin |

### 🤖 Agentes (Agent Factory)

- **Modelo principal + fallback automático** — si el endpoint principal falla, intenta el secundario
- **Skills del catálogo** — skills reutilizables por área
- **Conectores del área con ENRUTAMIENTO inteligente** — una IA corta decide
  qué conector es relevante para cada pregunta (o ninguno): una pregunta de
  norma/política responde solo con la Base de Conocimiento; una pregunta que cita
  un conector (ej: "CEP") ejecuta solo ese. Configurable vía
   `BLUESHIFT_ROUTER_MODEL` — use un modelo **pequeño, inteligente y rápido**
   (instruct, nunca reasoning); validado en producción: `qwen3-4b-instruct-2507`
   (otro ejemplo: `hermes-3-llama-3.1-8b`).
   El mismo modelo atiende 4 tareas internas (elegir conectores, extraer
   parámetros, spec del gráfico y el SELECT de la Consulta inteligente)
- **Extracción de parámetros por IA** — la IA extrae las claves de la pregunta en
  lenguaje natural ("id cliente igual a 58" → `customer_id='58'`), para
  todos los tipos de conector (API/MCP/SQL) + anti-alucinación: sin datos,
  el agente dice "no encontré" en lugar de inventar
- **Contexto dinámico** — RAG (memoria + knowledge) + datos de conectores inyectados en el prompt
- **Prueba en tiempo real** — pantalla de prueba con RAG + LLM real

### 🔌 Conectores Externos

Los conectores son fuentes de datos configurables por **área** (ventas, soporte, etc.):

| Tipo | Descripción | Ejemplo |
|:-----|:----------|:--------|
| 🌐 **API REST** | Llamada HTTP vía `urllib`, con autenticación (bearer/OAuth2 client_credentials), timeout configurable, **polling de jobs asíncronos** y mapeo de la respuesta | `GET https://api.externa.com/dados` |
| 🤝 **A2A** | Agente remoto en el protocolo Agent2Agent (ej.: Oracle Autonomous/AIDP `/a2a`) | `message/send` + agent card |
| 🔌 **MCP** | Servidor MCP vía stdio (local) o SSE (remoto, JSON-RPC 2.0) | `python mcp_server.py` / URL SSE + tool call |
| 🗄️ **SQL** | PostgreSQL, MySQL, SQL Server, **Oracle** vía `oracledb`, con SSL mode y wallet (Autonomous) | `SELECT * FROM vw_clientes WHERE id = %s` |

Los parámetros (`{id_cliente}`, `{email}`, `{data}`, `{pergunta}`) se extraen automáticamente de la pregunta del usuario. Configuración detallada de cada tipo: `docs/04-09-conectores.md`.

**Consulta inteligente (SQL):** cuando la query fija vuelve vacía y la pregunta pide
análisis ("quién alquiló más y menos", "cuántos por categoría"), el agente arma el
SELECT solo a partir del **schema real de la fuente** (tablas/views + columnas),
genérico por driver (MySQL/PostgreSQL/SQL Server/Oracle), con validación de
seguridad (solo SELECT de lectura + LIMIT) y checkbox por conector en la pantalla.

**Gráficos:** los pedidos de gráfico (torta/barras/línea) generan la imagen
automáticamente a partir de los datos de los conectores (matplotlib embutido), adjunta
a la respuesta — renderiza en Open WebUI y en el portal, con rótulos enmascarados por la
LGPD.

### 🧠 Base de Conocimiento (RAG)

| Mecanismo | Descripción |
|:----------|:----------|
| **Manual** | Agregar documentos vía formulario en el portal |
| **CSV Import** | Upload de `.csv` con columnas `titulo,conteudo,fonte,area` |
| **PDF Import** | Upload de `.pdf` con extracción automática de texto (PyMuPDF) |
| **Sin auto-save** | El RAG no recibe grabación automática de conversaciones/conectores (desde la v0.10.14) — crece por alta manual, CSV/PDF y skills |
| **Skills en el RAG** | Las skills del catálogo pueden indexarse en el knowledge |
| **Monitor** | KPI cards: total docs, áreas, accesos, tamaño promedio |
| **Export Fine-Tuning** | Exporta el RAG como JSONL (formato `messages`) para MLX, HuggingFace, Unsloth, OpenAI |

### ⚙️ Skills

- **Catálogo por área**: skills reutilizables (ventas, soporte, financiero, RR. HH., operaciones)
- **Edición persistente**: las skills editadas se guardan en la base de datos (volumen Docker),
  sobrevivendo a rebuilds del container. El archivo SKILL.md funciona como fallback.
- **Generación con IA**: cree el contenido de la skill describiendo en portugués lo que el agente debe hacer
- **Indexación en el RAG**: las skills pueden importarse a la base de conocimiento (buscables por TF-IDF)

### 🔐 Seguridad y Control de Acceso

- **Contraseñas con hash**: scrypt (salt 16 bytes, N=16384) — sin plaintext en la base de datos; **mínimo 8 caracteres** (crear/editar usuario y setup inicial)
- **RBAC**: jerarquía `admin > gestor > usuario > sistema`
- **Rate limit**: login 5 intentos/IP/min (bloqueo 15min) + API 100 req/token/min
- **Login fallido**: registrado en auditoría (usuario intentado + IP) — detecta brute-force
- **CSRF**: token en todos los formularios del portal
- **XSS**: escape (html.escape) en toda renderización de datos — nombres, descripciones, contexto RAG y resultados de conectores
- **Session hardening**: cookie HttpOnly + SameSite=Lax + timeout 30min + Secure (HTTPS)
- **SQL injection**: whitelist de columnas + queries parametrizadas
- **Path traversal**: nombres de skills validados como `isidentifier()`
- **Webhook URL (anti-SSRF)**: validación con `ipaddress` (bloquea privado, CGNAT, link-local/metadata de nube, loopback, IPv6 interno) + resolución de DNS (DNS rebinding); vale al crear, editar y en el momento del envío
- **Headers HTTP**: X-Content-Type-Options, X-Frame-Options: DENY, Referrer-Policy y Content-Security-Policy en todas las respuestas
- **API Key de modelo**: nunca renderizada en el HTML (máscara al editar)
- **SSO (OIDC)**: login federado opcional (mantiene el login local)
- **CORS**: headers configurados (Allow-Origin: \\*) — **solo en las rutas `/portal/api/*`** (las páginas web no lo necesitan)
- **Health check**: ruta pública `/portal/healthz` para load balancer / HEALTHCHECK
- **Auditoría LGPD**: toda acción sensible queda registrada
- **Canales con token**: cada canal de integración tiene su propia clave (regenerable)
- **Debug mode apagado**: sin tracebacks en producción
- **Aislamiento**: datos separados por `cliente_id` + área

### 🔒 Conformidad LGPD

| Funcionalidad | Artículos | Descripción |
|:---------------|:--------|:----------|
| **Anonimizar respuesta del LLM** | 12, 13 | Enmascara CPF, CNPJ, email, teléfono, nombre y dirección en la respuesta del agente (chat, API, webhook) |
| **Anonimizar exportación RAG** | 12, 13 | Datos personales enmascarados en la exportación JSONL de la base de conocimiento |
| **Aviso de privacidad en el login** | 9, 10 | Texto personalizable mostrado en el pie de la pantalla de login |
| **Finalidad del tratamiento** | 26 | Campo obligatorio por conector cuando está activado |
| **Retención automática de logs** | 15 | Limpieza periódica de auditoría (90d), tracing/uso_tokens (180d) y memorias (365d) vía thread daemon — o **Archivo Muerto** (snapshot + corte manual, sin perder histórico) |
| **Test A/B entre modelos** | — | Reejecuta preguntas del feedback con otro modelo y evalúa vía modelo juez |

Configuración en **Registros (Cadastros) > 🛡️ LGPD** y **Test A/B** en el menú principal.

---

## 🚀 Empezando

### Requisitos previos

- Python 3.11+
- Git
- Docker (opcional, para despliegue en container)

### Setup Local

```bash
# 1. Clone el repositorio
git clone https://github.com/cvillada/blueshift_ia_platform.git
cd blueshift_ia_platform

# 2. Cree y active el entorno virtual
python3 -m venv bp-venv && source bp-venv/bin/activate

# 3. Instale la plataforma
pip install --upgrade pip
pip install -e .

# 4. Pruebe la instalación
blueshift --help
# Dev local (BLUESHIFT_DEV=1): cualquier clave BS-DEV-* activa. Producción:
# la clave es emitida por BlueShift mediante el registro de la empresa
# (solicítela en el canal oficial — vea la sección Licencia).
blueshift activate BS-DEV-local

# 5. Levante el Portal
blueshift portal --port 8080
# Acceda a: http://localhost:8080/portal
# Modo desarrollo (BLUESHIFT_SEED_DEMO=1): Login: admin / admin123
# Cliente final (BLUESHIFT_SEED_DEMO=0): vea "Primera instalación" abajo
```

### Primera instalación (cliente final)

La plataforma nace con **base de datos limpia**: ninguna empresa, ningún usuario,
ningún dato demo. Quien instala lo controla mediante la variable
`BLUESHIFT_SEED_DEMO` (default `1` para desarrollo — crea datos de
ejemplo XPTO; defina `0` para que el cliente final no reciba nada).

Con la base limpia, el primer acceso ocurre así:

1. Abra `http://localhost:8080/portal` (o el puerto/URL del despliegue)
2. La pantalla de login se convierte en un formulario de **Configuración inicial**
3. El cliente registra:
   - su propia **empresa** (nombre, código, razón social, e-mail)
   - el **administrador inicial** (nombre, login, contraseña — mínimo 6 caracteres)
4. Al guardar, el portal autentica automáticamente y entra en Monitorear (Monitorar)

Después de eso, el formulario de Configuración inicial **desaparece para siempre** —
nadie más consigue reabrir el setup (solo existe un admin). El login normal
vuelve a valer.

> ⚠️ Por seguridad, en instalación de cliente final use siempre
> `BLUESHIFT_SEED_DEMO=0` y cambie la contraseña del admin periódicamente.

```bash
# Ejemplo: levantar el portal limpio para un cliente
BLUESHIFT_SEED_DEMO=0 blueshift portal --port 8080
```

### Variables de entorno

La configuración de la instalación vive en variables de entorno. El archivo
[`.env.example`](.env.example) trae todas con comentarios — cópielo a
`.env` antes de instalar. El `docker-compose.yml` usa las mismas variables
(con defaults), y la pantalla **Actualizaciones** del portal muestra las principales
(card "Configuración de ambiente").

| Variable | Por defecto | Efecto |
|:---------|:-------|:-------|
| `BLUESHIFT_LICENSE` | vacío | **Clave de activación emitida por BlueShift** — obtenida en el registro de la empresa (vea la sección [Licencia](#-licencia)); vacío = plataforma no activada. `BS-DEV-*` vale solo en dev (`BLUESHIFT_DEV=1`) |
| `BLUESHIFT_AREAS` | vendas,suporte,financeiro,rh,operacoes | **Seed inicial** de las áreas — después domina la pantalla Registros → Áreas (base de datos) |
| `BLUESHIFT_SEED_DEMO` | 1 | `1` = datos demo XPTO (dev); `0` = base limpia (setup inicial) |
| `BLUESHIFT_ROUTER_MODEL` | vacío | Modelo de **ENRUTAMIENTO** — **ID o NOMBRE** (el nombre aparece en la pantalla Modelos IA); vacío = principal del agente (no recomendado). Regla: **pequeño, inteligente y rápido** (instruct, nunca reasoning). Ejemplos: `qwen3-4b-instruct-2507` (validado) y `hermes-3-llama-3.1-8b` |
| `BLUESHIFT_LICENSE_URL` | localhost:9000 | URL de validación de licencia — **producción/cliente: apunte al License Server de BlueShift** (la misma base de la página de solicitud, ej: `<url>/v1/validate`); default = mock local (solo dev) |
| `BLUESHIFT_REPO_DIR` | /opt/blueshift/repo | Clone git del repo (Update vía Git — pantalla Actualizaciones) |
| `GATEWAY_PORT` | 9003 | Puerto publicado del Gateway OpenAI-compatible |
| `GATEWAY_PUBLIC_URL` | vacío | URL pública del gateway mostrada en la pantalla (ej: `http://192.168.0.10:9003/v1`); sin ella, usa el host de la petición |
| `BLUESHIFT_DEV` | 0 | **Producción/cliente = 0** (la pantalla Actualizaciones aplica la actualización de verdad); **dev = 1** (dry-run + licencia BS-DEV-*) |
| `TZ` | UTC | Zona horaria (usar `America/Sao_Paulo`) |

Sin Docker (CLI directa), cargue el `.env` y levante:

```bash
cd blueshift_ia_platform
set -a; . ./.env; set +a
blueshift portal --port 8080
```

---

## 📟 Comandos CLI

| Comando | Descripción |
|:--------|:----------|
| `blueshift init <cliente>` | Crea el perfil del cliente |
| `blueshift activate <chave>` | Valida la license key |
| `blueshift status` | Muestra el estado del container |
| `blueshift update` | Revisa las actualizaciones aprobadas |
| `blueshift portal [--port 8080]` | Levanta el Portal del Cliente |
| `blueshift mcp` | Levanta el servidor MCP stdio (conectores) |
| `blueshift gateway [--port 9003]` | Levanta el Gateway OpenAI-compatible (chats externos) |

### Ejemplo de Uso de la API de Canal

```bash
curl -X POST http://localhost:8080/portal/api/v1/agente \
  -H "Authorization: Bearer bs_chan_seu_token_aqui" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "¿Cuál es el historial del cliente C001?"}'
```

Respuesta:
```json
{
  "ok": true,
  "resposta": "El cliente C001 tiene 3 interacciones...",
  "pergunta": "¿Cuál es el historial del cliente C001?",
  "agente": "Agente Vendas",
  "modelo": "qwen3-4b-instruct-2507",
  "feedback_url": "http://localhost:8080/portal/api/v1/feedback/123",
  "erro": null,
  "tokens": {"total_tokens": 345, "prompt_tokens": 200, "completion_tokens": 145},
  "tempo_ms": 2340
}
```

### Feedback de la Respuesta (opcional)

La respuesta de la API incluye `feedback_url` — una URL para registrar si la respuesta fue útil.

**Endpoint:** `POST /portal/api/v1/feedback/<trace_id>`

**Body (JSON):**
```json
{"util": true}   // o false
```

**Ejemplo:**
```bash
curl -X POST http://localhost:8080/portal/api/v1/feedback/123 \
  -H "Authorization: Bearer <TOKEN_DO_CANAL>" \
  -H "Content-Type: application/json" \
  -d '{"util": true}'
```

**Respuesta:**
```json
{"ok": true, "feedback_id": 1}
```

> El campo `tipo` en la base de datos será `"api"` (vía curl) o `"manual"` (vía los botones 👍/👎 en la pantalla Agentes → Probar (Testar)). El uso es **opcional** — la API funciona sin el feedback. Los datos aparecen en el Dashboard de Observabilidad.

### Programación de la Agregación de Métricas

El dashboard de observabilidad consolida datos de las tablas `tracing` y `feedback` en la tabla `metricas_diarias`. La agregación se hace manualmente con el botón **"Procesar métricas"** del propio dashboard.

Para automatizar (ej: correr todos los días a las 2 de la mañana), agregue en el crontab del servidor:

```cron
0 2 * * * cd /opt/blueshift && python3 -c "from blueshift_layer.portal import db; db.agregar_metricas_diarias()"
```

O dentro de Docker:

```bash
docker exec blueshift-platform python3 -c "from blueshift_layer.portal import db; db.agregar_metricas_diarias()"
```

---

## 🤖 Modelos Locales de IA

BlueShift es 100% compatible con cualquier servidor **OpenAI-compatible**. Puede usar modelos locales (recomendado para on-premise) o externos.

### Opciones de Servidor Local

| Servidor | Descripción | Puerto por defecto |
|:---------|:----------|:-------------|
| **[LM Studio](https://lmstudio.ai)** | GUI para descargar y correr modelos GGUF | `http://127.0.0.1:1234` |
| **[Ollama](https://ollama.com)** | CLI simple para correr modelos locales | `http://127.0.0.1:11434` |
| **[llama.cpp](https://github.com/ggerganov/llama.cpp)** | Engine C++ ligero, vía `llama-server` | `http://127.0.0.1:8080` |
| **[vLLM](https://github.com/vllm-project/vllm)** | Alto throughput, ideal para GPU | `http://127.0.0.1:8000` |
| **[SGL](https://docs.sglang.io/)** | Alto throughput, ideal para GPU | `http://127.0.0.1:8000` |

### Setup con LM Studio (recomendado para dev)

```bash
# 1. Descargue LM Studio en https://lmstudio.ai
# 2. En la pestaña "Discover", busque y descargue un modelo GGUF

# Modelo de ENRUTAMIENTO (recomendado, validado en producción):
#   Qwen3-4B-Instruct-2507 (Q4, ~2,6 GB)
#   → Buscar en LM Studio: "qwen3-4b-instruct-2507"
#
# Ejemplos alternativos (instruct, NUNCA reasoning):
#   - hermes-3-llama-3.1-8b (8B instruct, excelente en formato/JSON)
#   - Qwen2.5-3B-Instruct (término medio)
#   - Qwen2.5-0.5B-Instruct (instalación modesta; no hace el text-to-SQL)
#
# Para el modelo PRINCIPAL (el que escribe la respuesta) use lo mejor que tenga:
# Llama 3.1 8B Instruct, Qwen 2.5 7B/14B, Mistral, etc.

# 3. En la pestaña "Local Server":
#    - Seleccione el modelo descargado
#    - Active "Cross-Origin-Resource-Sharing (CORS)"
#    - Active "Start Server"
#    - Puerto: 1234 (por defecto)

# 4. En el Portal BlueShift, vaya a Modelos IA y registre:
#    - Nombre: qwen3-4b-instruct-2507
#    - Endpoint: http://host.docker.internal:1234 (si está en Docker)
#               o http://127.0.0.1:1234 (si está corriendo local)
#    - Modelo: qwen3-4b-instruct-2507 (o el nombre exacto que el servidor espera)
#    - Tipo: Local
```

> ⚠️ **En Docker:** el container necesita acceder a LM Studio en el host. Use `host.docker.internal` en lugar de `127.0.0.1`. En Linux, use `--add-host=host.docker.internal:host-gateway`.

### Setup con Ollama

```bash
# 1. Instale Ollama: https://ollama.com
# 2. Descargue un modelo:
ollama pull llama3.2:3b
ollama pull phi4:14b
# 3. Inicie el servidor (ya arranca automático en macOS):
ollama serve
# 4. En el Portal, registre:
#    - Nombre: llama3.2
#    - Endpoint: http://host.docker.internal:11434
#    - Modelo: llama3.2:3b
#    - Tipo: Local
```

### Modelos Externos (OpenAI-compatible)

Si prefiere usar APIs externas en lugar de modelos locales:

| Proveedor | Endpoint | API Key |
|:---------|:---------|:--------|
| **DeepSeek** | `https://api.deepseek.com` | ✅ Necesaria |
| **OpenRouter** | `https://openrouter.ai/api/v1` | ✅ Necesaria |
| **OpenAI** | `https://api.openai.com/v1` | ✅ Necesaria |
| **NVIDIA NIM** | `https://integrate.api.nvidia.com/v1` | ✅ Necesaria |

En el Portal, registre como **Tipo: Híbrido** y complete la API Key.

---

## 🐳 Docker

### Instalación vía Installer (recomendado)

```bash
cp .env.example .env          # ajuste BLUESHIFT_LICENSE
./install.sh                  # docker compose up -d --build
```

Acceda a `http://localhost:8080/portal`.

> **Instalación del cliente (base de datos limpia):** con `BLUESHIFT_SEED_DEMO=0` la primera
> entrada abre la pantalla **Configuración inicial**, que crea la empresa y el primer
> admin (no existen datos de demostración). El `admin` / `admin123` es solo el
> usuario de demostración del modo dev (`BLUESHIFT_SEED_DEMO=1`).

> **Los modelos de IA no vienen embutidos.** Después de levantar la plataforma, registre los modelos en la pantalla **Modelos IA** — local (vLLM/LM Studio/Ollama) o externo (DeepSeek/OpenRouter/OpenAI).
>
> **Áreas personalizadas:** registre las áreas en la pantalla **Registros → Áreas**
> (base de datos). La variable `BLUESHIFT_AREAS` en el `docker-compose.yml` sirve apenas
> como seed inicial del primer boot.
>
> **MCP con Node.js:** para servidores MCP locales que dependen de Node.js (npm/npx), el container ya incluye Node 20 y npm.
>
> **Update vía Git:** el compose monta el repositorio (por defecto: el propio
> directorio; producción: clone en `/opt/blueshift/repo`) y el `docker.sock`
> del host en el portal. La pantalla **Actualizaciones** muestra la versión del repo y
> aplica la tag nueva con `docker compose up -d --build` (datos preservados).

### Manual

```bash
# 1. Build de la imagen
docker build -t blueshift/platform -f docker/Dockerfile .

# 2. Cree un volumen para la persistencia de los datos
docker volume create blueshift_data

# 3. Levante el container con el volumen montado
docker run -d --name blueshift-platform \
  -p 8080:8080 \
  -v blueshift_data:/data/blueshift \
  -e BLUESHIFT_PORTAL_DB=/data/blueshift/portal.db \
  -e BLUESHIFT_LICENSE=TU-CLAVE-DE-BLUESHIFT \
  blueshift/platform blueshift portal
```

> **Persistencia de datos:** la base SQLite y los demás datos quedan en el volumen `blueshift_data`.
> Puede rebuildear el container (`docker build` + `docker stop` + `docker rm` + `docker run`)
> que los datos (clientes, usuarios, agentes, conectores, skills editadas, documentos RAG) se preservan.
> Para backup: `docker run --rm -v blueshift_data:/data -v $(pwd):/backup alpine tar czf /backup/blueshift_backup.tar.gz -C /data .`

> **El compose levanta DOS containers:** `blueshift-platform` (portal, :8090→8080)
> y `blueshift-gateway` (gateway OpenAI-compatible, :9003) — el gateway
> depende del portal y lee la configuración en el mismo volumen `blueshift-data`.

### 🔀 Gateway OpenAI-compatible (chats externos)

El gateway expone el protocolo estándar de OpenAI (`/v1/chat/completions` +
`/v1/models`) para chats externos — **Open WebUI**, LibreChat, apps
custom, OpenAI SDK/LangChain — y lo reenvía al agente vía API del canal
(token `bs_chan_*`).

Para conectar **Open WebUI** (container en la misma máquina):

```bash
# 1. En el portal: Registros → Canales → cree el canal (ej: "API Vendas")
#    apuntando al agente deseado (el token bs_chan_* es la API Key)
# 2. En el portal: Registros → Gateway → "Activar gateway" (canal + modo:
#    Respuesta completa JSON o Streaming SSE) — el gateway debe estar
#    ACTIVO para responder
# 3. En Open WebUI (Admin → Connections → OpenAI API):
#      API URL: http://host.docker.internal:9003/v1
#      API Key: el token del canal (cualquier gateway activo autentica)
#      Model:  agente:Agente Vendas  (el nombre del agente)
```

- El `model` elige el agente; el token solo valida la autenticación (cualquier
  clave de canal con gateway activo funciona — Open WebUI usa una
  conexión = una clave para varios modelos)
- **Contexto de la conversación:** el gateway reenvía los mensajes anteriores
  (límites configurables en la pantalla: máx. mensajes + presupuesto en tokens);
  la memoria/RAG graban siempre la última pregunta/respuesta real
- Chat en otra máquina de la red: `http://IP_DO_SERVIDOR:9003/v1`
- Sin Docker: `set -a; . ./.env; set +a` + `blueshift gateway --port 9003`

---

## 🖥️ Instalación sin Docker (Linux directo)

El producto corre **100% sin Docker**: es Python puro (Flask standalone). Para
clientes que prefieren correr directo en el servidor Linux (sin containers):

```bash
# 1. Clone del repo (el MISMO clone usado por el Update)
sudo mkdir -p /opt/blueshift/repo && sudo chown $USER /opt/blueshift/repo
git clone https://github.com/cvillada/blueshift_ia_platform.git /opt/blueshift/repo
cd /opt/blueshift/repo

# 2. Entorno virtual + dependencias
python3 -m venv .venv
.venv/bin/pip install -e .

# 3. Servicio systemd (/etc/systemd/system/blueshift.service)
#    [Unit]
#    Description=CL Agents — BlueShift IA Platform
#    After=network.target
#
#    [Service]
#    WorkingDirectory=/opt/blueshift/repo
#    Environment=BLUESHIFT_PORTAL_DB=/opt/blueshift/data/portal.db
#    Environment=BLUESHIFT_LICENSE=TU-CLAVE
#    Environment=BLUESHIFT_LICENSE_URL=<url-de-la-pagina-de-solicitud>/v1/validate
#    Environment=BLUESHIFT_REPO_DIR=/opt/blueshift/repo
#    ExecStart=/opt/blueshift/repo/.venv/bin/blueshift portal --port 8080
#    Restart=always
#
#    [Install]
#    WantedBy=multi-user.target

sudo systemctl daemon-reload && sudo systemctl enable --now blueshift
# Acceda a: http://<servidor>:8080/portal
```

**La actualización por el botón (pantalla Actualizaciones) funciona sin Docker:** el portal
detecta que corre fuera de container (`/.dockerenv` ausente) y el botón
**Aplicar** hace `git fetch + checkout` de la tag en el repo y reinicia el servicio
vía `systemctl restart blueshift` — con el mismo aviso de "descargado pero no
aplicado" y log en `/opt/blueshift/update.log`.

Variables específicas del modo bare:
- `BLUESHIFT_REPO_DIR=/opt/blueshift/repo` — clone del repo (el default ya es ese)
- `BLUESHIFT_SERVICE_NAME=blueshift` — nombre del servicio systemd (default
  `blueshift`); si el servicio tiene otro nombre, defínalo aquí

> **Nota:** sin systemd en el host, el botón hace el checkout y el log orienta el
> reinicio manual — la pantalla muestra "descargado pero NO aplicado" hasta que el servicio
> reinicie. Docker sigue siendo el modo recomendado de entrega; el bare es
> para servidores Linux sin containers.

## 📁 Estructura del Proyecto

```
blueshift_layer/                    ← Código principal de la plataforma
├── cli.py                          ← Entry point CLI (blueshift)
├── gateway.py                      ← Gateway OpenAI-compatible (:9003, /v1)
├── license_client.py               ← Validación de license key
├── license_server_mock.py          ← License Server mock (Flask, :9000)
├── installer.py                    ← Crea el perfil del cliente
├── update_client.py                ← Update vía Git (tags) — versión + apply
├── update_server.py                ← Update Channel mock legado (Flask, :9001)
├── config/
│   └── default_config.yaml         ← Config por defecto del container
├── portal/                         ← 🌐 Portal del Cliente (Flask)
│   ├── __init__.py                 ← Factory create_app()
│   ├── db.py                       ← SQLite (punto único de datos)
│   ├── views.py                    ← Rutas y pantallas
│   ├── auth.py                     ← Autenticación + RBAC
│   ├── templates.py                ← Layout HTML/CSS/JS
│   ├── memory.py                   ← RAG (TF-IDF + coseno, Python puro)
│   ├── llm_client.py               ← Client LLM OpenAI-compatible (urllib)
│   ├── agente.py                   ← Orquestador del agente
│   ├── mask.py                     ← Enmascaramiento LGPD (CPF, email, nombre, etc.)
│   └── sso.py                      ← Login federado OIDC
├── connector_pack/                 ← 🔌 Conectores externos
│   ├── registry.py                 ← Engine API/MCP/SQL
│   ├── mcp_server.py               ← MCP stdio (JSON-RPC 2.0)
│   ├── mcp_erp.py                  ← ERP (Postgres)
│   ├── mcp_crm.py                  ← CRM (datos de ejemplo)
│   └── mcp_rh.py                   ← RR. HH. (datos de ejemplo)
└── template_skills/                ← ⚙️ Skills por área (fallback; guardadas en la base de datos p/ persistencia)
    ├── vendas/SKILL.md
    ├── suporte/SKILL.md
    ├── financeiro/SKILL.md
    ├── rh/SKILL.md
    └── operacoes/SKILL.md

docs/                               ← 📚 Documentación (páginas navegables — Docs + Ayuda IA)
├── README.md                       ← Convención de escritura (dónde documentar cada cambio)
├── 00-…13-*.md                     ← Contenido (una página por asunto/pantalla) + API Reference + Changelog
├── _TEMPLATE.md                    ← Plantilla para página nueva
├── _mapa_apelidos.json             ← Campo técnico ↔ rótulo de la pantalla (chequeo automático)
├── _pendentes.json                 ← Deuda conocida del chequeo
└── _publico.txt                    ← Curaduría del sitio interno de documentación

tools/
├── doc_check.py                    ← Gate doc × código (rutas, campos, variables, tablas, versiones)
└── docs_site.py                    ← Genera el sitio de documentación para uso interno (no publicado)

docker/
├── Dockerfile                      ← Imagen del container
└── entrypoint.sh                   ← Levanta License + Update + Portal
```

---

## 🛠️ Stack Tecnológico

| Categoría | Tecnología |
|:----------|:-----------|
| **Lenguaje** | Python 3.11+ |
| **Framework** | Flask 3.1 |
| **Base de Datos** | SQLite (on-premise, sin dependencia de red) |
| **LLM Client** | urllib puro (OpenAI-compatible) |
| **RAG** | TF-IDF + similitud de coseno (Python puro, sin numpy) |
| **PDF Extraction** | PyMuPDF (extracción de texto para RAG) |
| **MCP** | JSON-RPC 2.0 sobre stdio (Python puro) |
| **SSO** | OIDC vía urllib + HMAC (sin libs OAuth) |
| **Autenticación** | Login/contraseña local + SSO federado |
| **Container** | Docker (Python 3.11-slim) |
| **Postgres** | Opcional (vía `psycopg` para conector ERP) |

### Dependencias Python

```
flask>=3.1          # Framework web
requests>=2.31      # HTTP client (license_client)
pyyaml>=6.0         # YAML config
mcp>=1.0            # FastMCP (conectores)
psycopg[binary]>=3.1 # Postgres (conector ERP, opcional)
PyMuPDF>=1.28       # Extracción de texto PDF (RAG)
```

---

## 💻 Hardware Recomendado

### Cuellos de botella de la plataforma

| Componente | Límite real | Causa |
|:-----------|:------------|:------|
| **LLM local** | 2-60s por llamada | Modelo/hardware — **el cuello de botella principal** (GPU vía vLLM lo resuelve) |
| **SQLite (WAL)** | 1 escritura a la vez; lecturas concurrentes liberadas | Single-writer — irrelevante en la práctica: ~3 escrituras minúsculas por llamada de agente |
| **Portal (Werkzeug, threaded)** | Peticiones concurrentes (el I/O del LLM libera el GIL) | Servidor dev; para carga extrema, waitress/gunicorn (ver Tier 3) |
| **TF-IDF** (memoria) | ~100k docs / ~500MB RAM | Índice cargado en RAM |
| **Búsqueda vectorial** | O(n) = 50-200ms p/ 10k docs | Fuerza bruta (coseno), sin índice |

### Tiers

Los tiers son **orientativos para dimensionar la instalación del cliente**. "Accesos simultáneos" es la capacidad de **KV cache** del servidor LLM (vLLM) con el modelo indicado en Q4 y contexto medio de referencia — quien pasa el límite **entra en la cola nativa del vLLM** (espera, no falla). Fórmula y tabla completa en la sección [Capacidad de accesos simultáneos](#capacidad-de-accesos-simultáneos-kv-cache).

#### 🟢 TIER 1 — Pequeño (hasta 10 usuarios, 1k docs, 500 queries/día)

| Recurso | Especificación |
|:--------|:--------------|
| **CPU** | 2 vCPU |
| **RAM** | 8 GB |
| **Disco** | 50 GB SSD |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | No (opcional: RTX 4060 8GB) |
| **Modelo LLM** | hasta 3B params (Q4, ~2GB RAM, CPU) |
| **Accesos simultáneos** | 1-2 (CPU; con GPU 8GB: 1-2 @ 8K ctx) |
| **Registros/día** | ~1,5k (3 por query) — SQLite WAL + retención LGPD: holgura total |
| **Costo estimado** | ~R$ 80/mes (VPS) |

#### 🟡 TIER 2 — Medio (hasta 50 usuarios, 10k docs, 5k queries/día)

| Recurso | Especificación |
|:--------|:--------------|
| **CPU** | 4 vCPU |
| **RAM** | 16 GB |
| **Disco** | 200 GB SSD |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | RTX 4060 8GB (opcional, p/ vLLM) |
| **Modelo LLM** | hasta 8B params (Q4_K_M, ~5GB VRAM) |
| **Accesos simultáneos** | ~1-2 @ 8K ctx (8B Q4 en GPU 8GB); CPU: 1 |
| **Registros/día** | ~15k — SQLite WAL + índices + retención: holgura |
| **Costo estimado** | ~R$ 250/mes (VPS) |

#### 🟠 TIER 3 — Grande (hasta 200 usuarios, 50k docs, 20k queries/día)

| Recurso | Especificación |
|:--------|:--------------|
| **CPU** | 8 vCPU |
| **RAM** | 32 GB |
| **Disco** | 500 GB SSD NVMe |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | NVIDIA RTX 4080/3090 24GB (recomendado, p/ vLLM) |
| **Modelo LLM** | hasta 14B params (Q4, ~9GB VRAM) |
| **Accesos simultáneos** | ~3 @ 32K ctx (8B Q4); ~1 @ 32K (14B Q4) — el excedente en la cola del vLLM |
| **Registros/día** | ~60k — SQLite WAL + índices + retención: aguanta |
| **Costo estimado** | ~R$ 800/mes (dedicated server) |

**Lo que necesita cambiar en este tier:**
- **Nada en la plataforma** — el salto es que el modelo pase de CPU a **vLLM en GPU** (24GB+). SQLite ya opera en WAL con índices de retención.
- Opcional: servidor **waitress/gunicorn** para throughput HTTP por encima del Werkzeug dev (1 proceso threaded).

#### 🔴 TIER 4 — Enterprise (500+ usuarios, 200k docs, 100k queries/día)

| Recurso | Especificación |
|:--------|:--------------|
| **CPU** | 16 vCPU |
| **RAM** | 64 GB |
| **Disco** | 1 TB NVMe |
| **SO** | Linux (Ubuntu 22.04 / Debian 12) |
| **GPU** | NVIDIA RTX Pro 6000 128GB (o 2x 24GB) |
| **Modelo LLM** | hasta 70B params (Q4, ~41GB VRAM, vía vLLM) |
| **Accesos simultáneos** | ~25 @ 32K (8B Q4) / ~6 @ 32K (70B Q4); ~6 @ 128K (8B) — el excedente en la cola del vLLM |
| **Registros/día** | ~300k — techo del diseño actual: ~18M líneas de tracing (180d) indexadas; SQLite WAL aguanta |
| **Costo estimado** | ~R$ 3.000+/mes (servidor dedicado) |

**Lo que necesita cambiar en este tier:**
- **El único escenario que justifica PostgreSQL**: 2+ réplicas del portal escribiendo en la misma base de datos (multi-writer). El diseño actual (1 portal + gateway stateless de lectura) no cruza ese límite — si el TI del cliente lo exige, es un estudio de migración con alcance definido, no una reescritura de la capa de datos.
- Cola de tareas async (Celery/RQ) solo si hay webhook de salida en volumen con retry persistente — hoy la entrega es síncrona con retry (3x, backoff) y la alternativa ligera es un thread en background.

### Resumen

| Tier | CPU | RAM | Disco | GPU (VRAM) | Accesos simultáneos* | Usuarios | Registros/día | Costo/mes |
|:----:|:---:|:---:|:-----:|:----------:|:--------------------:|:--------:|:-------------:|:---------:|
| 🟢 1 | 2 vCPU | 8 GB | 50 GB | No | 1-2 (CPU) | 10 | ~1,5k | ~R$ 80 |
| 🟡 2 | 4 vCPU | 16 GB | 200 GB | RTX 4060 (8GB, opc.) | 1-2 @ 8K | 50 | ~15k | ~R$ 250 |
| 🟠 3 | 8 vCPU | 32 GB | 500 GB | RTX 4080/3090 (24GB) | ~3 @ 32K | 200 | ~60k | ~R$ 800 |
| 🔴 4 | 16 vCPU | 64 GB | 1 TB | RTX Pro 6000 (128GB) | ~25 @ 32K | 500+ | ~300k | ~R$ 3.000+ |

\* Accesos simultáneos = peticiones que la GPU atiende **al mismo tiempo** (KV cache, modelo 8B Q4, fp16). El excedente **espera en la cola del vLLM** — no falla.

> **Nota:** el mayor cuello de botella no es el hardware — es el **LLM local** sin GPU. Un modelo 8B en CPU genera 5-15 tok/s. Una respuesta de 300 tokens tarda 20-60 segundos. Para producción con muchos usuarios, **la GPU es esencial** (vía vLLM).

### Capacidad de accesos simultáneos (KV cache)

Cada conversación activa consume memoria de **KV cache** en la GPU. La cuenta (fp16):

```
KV por token = 2 × capas × KV heads × head_dim × 2 bytes
Slots        = (VRAM − pesos − overhead) / (KV por token × contexto medio)
```

Costo de contexto por modelo (fp16):

| Modelo | KV/token | 8K ctx | 32K ctx | 128K ctx |
|:-------|:---------|:-------|:--------|:---------|
| 8B (Llama 3.1) | 128 KB | 1,0 GB | 4,2 GB | 16,8 GB |
| 14B (Qwen 2.5) | 192 KB | 1,5 GB | 6,3 GB | 25,2 GB |
| 32B (Qwen 2.5) | 256 KB | 2,1 GB | 8,4 GB | 33,6 GB |
| 70B (Llama 3.3) | 320 KB | 2,6 GB | 10,5 GB | 42,0 GB |

Slots simultáneos por GPU (modelo Q4, KV en fp16, overhead ~10% VRAM + 2GB, valores redondeados):

| GPU (VRAM) | 8B | 14B | 32B | 70B |
|:-----------|:---|:----|:----|:----|
| RTX 4060 (8GB) | 1 @ 8K | — | — | — |
| RTX 4060 Ti (16GB) | 7 @ 8K / 1 @ 32K | 2 @ 8K | — | — |
| RTX 4080/3090 (24GB) | 13 @ 8K / 3 @ 32K | 6 @ 8K / 1 @ 32K | — | — |
| RTX Pro 6000 (128GB) | 103 @ 8K / 25 @ 32K / 6 @ 128K | 66 @ 8K / 16 @ 32K / 4 @ 128K | 44 @ 8K / 11 @ 32K / 2 @ 128K | 27 @ 8K / 6 @ 32K / 1 @ 128K |

Ejemplo (RTX Pro 6000 128GB): 100 peticiones llegando juntas, modelo 8B Q4 — ~25 atienden en paralelo con contexto medio 32K y ~75 esperan en la cola del vLLM; con contexto 128K lleno, ~6 atienden. El vLLM **no rechaza** — encola y atiende conforme se liberan los slots (límite de cola configurable).

Multiplicadores: KV cache en **FP8 duplica los slots**; contexto 32K (típico de RAG) rinde 4-5x más que 128K lleno. El modelo 70B Q4 **no cabe** en una GPU de 24GB — solo los pesos usan ~41GB.

### Capacidad de registros (SQLite)

Cada llamada de agente graba ~3 líneas: `tracing` + `uso_tokens` + `auditoria`. Con la retención LGPD activa (Configuraciones (Configurações) → LGPD; desactivada por defecto), las tablas son estables:

| Tabla | Retención por defecto | Tier 4 (100k queries/día) |
|:-------|:----------------|:--------------------------|
| auditoria | 90 días | ~9M líneas máx |
| tracing | 180 días | ~18M líneas máx |
| uso_tokens | 180 días (sigue tracing) | ~18M líneas máx |
| metricas_diarias | sin retención (agregado diario) | ~365 líneas/año por agente+modelo |
| memories | 365 días | conforme al uso |

SQLite en modo **WAL** con índices en `criado_em` (tracing/feedback/auditoria) lee y filtra ese volumen sin problema — point lookup + range por fecha. El límite real de SQLite **no es tamaño, es multi-writer**: 2+ procesos grabando el mismo archivo. El diseño actual (1 portal + gateway stateless de lectura) no cruza ese límite. Si algún día hay 2+ réplicas del portal, **ahí sí** PostgreSQL pasa a tener sentido — estudio de migración con alcance definido, no reescritura.

### Limpieza y archivo muerto

Existen dos formas de controlar el crecimiento — manuales y con criterios diferentes:

**1. Archivo muerto (pantalla Archivo Muerto (Arquivo Morto), menú Operación — solo admin):** genera un snapshot sellado de la base de datos (`data/arquivo_morto/arquivo_morto_<execução>_<corte>.db` — la primera fecha = ejecución, la segunda = corte) y elimina de la base caliente los registros con `criado_em <= corte`. Corte máximo = **ayer a medianoche** (el día corriente nunca se ve afectado). El flujo pide confirmación mostrando los conteos antes de ejecutar — **incluida la confirmación de que se hizo el backup físico del portal.db** (el snapshot no sustituye al backup); la copia se hace antes del DELETE (falla en la copia = nada se borra). El backup físico de la base principal es responsabilidad del cliente (volumen).

| Tabla | Campo del corte | Criterio |
|:-------|:---------------|:---------|
| tracing | criado_em | antigüedad (≤ corte) |
| uso_tokens | criado_em | antigüedad (≤ corte) |
| auditoria | criado_em | antigüedad (≤ corte) |
| memories | criado_em | antigüedad (≤ corte) |
| feedback | criado_em | antigüedad (≤ corte) |
| teste_ab | criado_em | antigüedad (≤ corte) |
| knowledge | acessos / ultimo_acesso | fuente importada (csv/pdf/...) **y** sin uso reciente (`acessos = 0` o `ultimo_acesso ≤ corte`) — las fuentes `manual` y `skill` (reglas) nunca se ven afectadas |

Nunca entran: `metricas_diarias` (agregado perpetuo) y datos maestros (clientes, usuarios, agentes, modelos, skills, conectores, canales, áreas, api_keys, configs). Cada ejecución — éxito **o falla** — queda en el histórico de la pantalla (ejecución, corte, archivo, movidos) **y en la Auditoría** (menú Operación, `acao=arquivo_morto`: usuario, corte, archivo, total movido). Un snapshot duplicado en el mismo día/corte es rechazado (nada se sobrescribe).

**2. Limpieza automática (pantalla LGPD):** opcional (`retencao_auto`), corre cada hora y hace **DELETE físico** con retenciones configurables (auditoria 90d, tracing/uso_tokens 180d, memorias 365d). Desactivada por defecto — solo se activa si el cliente quiere descartar sin snapshot.

---

## 📚 Documentación

La documentación vive en **`docs/`** (una página por asunto/pantalla) y es la **fuente
única** de tres lugares: el menú **Docs** del portal, el popup **Ayuda IA** y el sitio
interno de documentación.

| Página | Para quién | Contenido |
|:-------|:----------|:---------|
| `docs/00-…03-*.md` | operador | visión general, arquitectura, cómo ejecutar, acceso y roles |
| `docs/04-*.md` | operador | **una página por pantalla** del portal (campos, paso a paso, ejemplos, pitfalls) |
| `docs/05-…07-*.md` | operador/TI | API de canal, conectores y flujo del agente/RAG |
| `docs/12-api-reference.md` (ES: `docs/es/12-api-reference.md`) | **TI del cliente** | referencia de integración: API del portal, Gateway OpenAI, autenticación, errores y límites |
| `docs/13-changelog.md` | todos | histórico de versiones (toda release entra en la parte superior) |

**Al tocar el producto, documente en el mismo commit:**

```bash
python tools/doc_check.py            # falla si algo del código queda sin documentación
python tools/doc_check.py --lista    # deuda conocida
```

El chequeo compara **rutas, campos de formulario, variables de entorno, tablas
de la base de datos y tags de versión** con las páginas — hoy con cobertura total. Convención
de escritura, plantilla de página y "dónde documentar cada tipo de cambio":
**`docs/README.md`**.

**Sitio interno de documentación** (presentar/imprimir/llevar offline en demo):

```bash
./bp-venv/bin/python tools/docs_site.py       # genera dist/docs_site/ (autocontenido, con búsqueda)
./bp-venv/bin/python tests/test_docs_site.py  # valida curaduría, links y JS
```

La curaduría de lo que entra en el sitio es explícita en `docs/_publico.txt`. **El sitio no
se publica** — uso interno.

La documentación completa vive en `docs/` (portugués, fuente única). Traducciones EN/ES: `docs/en/` y `docs/es/` (páginas 00, 01, 02 y 12).

---

## 📄 Licencia

Este proyecto es **código-fuente disponible (source-available)**: el repositorio es
público a fines de transparencia, auditoría y actualización automática de las
instalaciones licenciadas — la publicación NO concede derecho de uso.

> ### 🔑 Obtenga su clave de activación
>
> **https://static.190.55.99.91.clients.your-server.de:9096/**
>
> Registro de la empresa (razón social, CNPJ y contacto) → la clave se emite en
> el acto. BlueShift entra en contacto con la propuesta comercial. *(URL actual de
> la página de solicitud — la URL definitiva será divulgada en el sitio de
> BlueShift.)*

**Uso e instalación** exigen:
1. Contrato de licenciamiento válido firmado con BlueShift; y
2. **Clave de activación emitida por BlueShift** para la empresa contratante
   (obtenida por el registro en el link de arriba).

No existen claves de uso general: la instalación sin clave válida no está
licenciada (la pantalla **Actualizaciones** muestra el estado de la licencia). Las
claves `BS-DEV-*` se aceptan **solamente en ambiente de desarrollo**
(`BLUESHIFT_DEV=1`) — nunca en producción.

**Validación en producción:** la instalación valida la clave contra el License
Server de BlueShift — configure en el `.env`:
```
BLUESHIFT_LICENSE=TU-CLAVE
BLUESHIFT_LICENSE_URL=<url-de-la-pagina-de-solicitud>/v1/validate
```

**Servicios adicionales** (fine-tuning de modelos, reentrenamiento, soporte
extendido, capacitación) no están incluidos en la licencia: se contratan
por separado con BlueShift, mediante propuesta de servicio.

Vea el archivo [LICENSE](LICENSE) para los términos completos.

Para obtener una licencia comercial o solicitar su clave de activación,
entre en contacto: https://www.blueshift.com.br/FaleComBlueShift

---

<div align="center">
  <sub>Desarrollado por Nei · BlueShift IA Platform</sub>
</div>
