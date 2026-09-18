<!-- sync: 00-visao-geral.md@69b7e780ab31 | checar: python tools/readme_check.py -->
🌐 [Português](../00-visao-geral.md) · **English** · [Español](../es/00-visao-geral.md)

# 📘 CL Agents — Documentation

*(BlueShift IA Platform)*

> Complete functional documentation of the system — screens, fields, flows and API.
> Source: real code (blueshift_layer/). Version: {{versao}} — updated on {{data}}.
> Fill-in examples are FICTITIOUS (never real customer data).

---

## 1. Overview

The BlueShift IA Platform is an **on-premise** AI platform (installed inside the
customer's infrastructure): data, agents, memory and history stay 100% in the
customer's environment. Pure Python application (Flask + SQLite), with no external
dependency on an AI engine — models can be local (vLLM, LM Studio, Ollama) or
external (OpenAI, DeepSeek, OpenRouter) via an OpenAI-compatible API.

Main components:

| Component | Function |
|:-----------|:-------|
| **Client Portal (Portal do Cliente)** | Web interface (Layer 4) to administer and monitor the platform |
| **Agents (Agentes)** | Orchestrators per area (sales, support, finance, HR, operations) |
| **Connectors (Conectores)** | External sources: REST API, MCP servers (stdio/SSE), SQL (PG/MySQL/SQL Server/Oracle) |
| **RAG / Memory (Memória)** | Local vector knowledge base (TF-IDF + cosine similarity) |
| **Skills** | Behavior instructions (SKILL.md) that guide the agents |
| **Channels (Canais)** | Machine-to-machine integration with its own token (API/webhook) |
| **Gateway** | OpenAI-compatible for external chats (Open WebUI, apps) — port 9003 |
| **License** | Annual per company — activation key issued by BlueShift (company registration); online validation against the BlueShift License Server in production |

---
