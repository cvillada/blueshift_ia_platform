<!-- sync: 00-visao-geral.md@69b7e780ab31 | checar: python tools/readme_check.py -->
🌐 [Português](../00-visao-geral.md) · [English](../en/00-visao-geral.md) · **Español**

# 📘 CL Agents — Documentación

*(BlueShift IA Platform)*

> Documentación funcional completa del sistema — pantallas, campos, flujos y API.
> Fuente: código real (blueshift_layer/). Versión: {{versao}} — actualizado en {{data}}.
> Los ejemplos de llenado son FICTICIOS (nunca datos reales de cliente).

---

## 1. Visión general

La BlueShift IA Platform es una plataforma de IA **on-premise** (instalada dentro
de la infraestructura del cliente): los datos, los agentes, la memoria y el
historial quedan 100% en el entorno del cliente. Aplicación Python pura (Flask +
SQLite), sin dependencia externa de motor de IA — los modelos pueden ser locales
(vLLM, LM Studio, Ollama) o externos (OpenAI, DeepSeek, OpenRouter) vía API
compatible con OpenAI.

Componentes principales:

| Componente | Función |
|:-----------|:--------|
| **Portal del Cliente (Portal do Cliente)** | Interfaz web (Capa 4) para administrar y monitorear la plataforma |
| **Agentes** | Orquestadores por área (ventas, soporte, financiero, Recursos Humanos, operaciones) |
| **Conectores** | Fuentes externas: API REST, servidores MCP (stdio/SSE), SQL (PG/MySQL/SQL Server/Oracle) |
| **RAG / Memoria (RAG / Memória)** | Base de conocimiento vectorial local (TF-IDF + similitud de coseno) |
| **Skills** | Instrucciones de comportamiento (SKILL.md) que guían a los agentes |
| **Canales (Canais)** | Integración máquina a máquina con token propio (API/webhook) |
| **Gateway** | Compatible con OpenAI para chats externos (Open WebUI, apps) — puerto 9003 |
| **Licencia** | Anual por empresa — clave de activación emitida por BlueShift (registro de la empresa); validación online contra el License Server de BlueShift en producción |

---
