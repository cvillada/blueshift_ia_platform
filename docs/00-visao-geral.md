# 📘 CL Agents — Documentação

*(BlueShift IA Platform)*

> Documentação funcional completa do sistema — telas, campos, fluxos e API.
> Fonte: código real (blueshift_layer/). Versão: {{versao}} — atualizado em {{data}}.
> Exemplos de preenchimento são FICTÍCIOS (nunca dados reais de cliente).

---

## 1. Visão Geral

A BlueShift IA Platform é uma plataforma de IA **on-premise** (instalada dentro
da infraestrutura do cliente): dados, agentes, memória e histórico ficam 100%
no ambiente do cliente. Aplicação Python pura (Flask + SQLite), sem dependência
externa de motor de IA — os modelos podem ser locais (vLLM, LM Studio, Ollama)
ou externos (OpenAI, DeepSeek, OpenRouter) via API compatível com OpenAI.

Componentes principais:

| Componente | Função |
|:-----------|:-------|
| **Portal do Cliente** | Interface web (Camada 4) para administrar e monitorar a plataforma |
| **Agentes** | Orquestradores por área (vendas, suporte, financeiro, RH, operações) |
| **Conectores** | Fontes externas: API REST, servidores MCP (stdio/SSE), SQL (PG/MySQL/SQL Server/Oracle) |
| **RAG / Memória** | Base de conhecimento vetorial local (TF-IDF + similaridade cosseno) |
| **Skills** | Instruções de comportamento (SKILL.md) que guiam os agentes |
| **Canais** | Integração máquina-a-máquina com token próprio (API/webhook) |
| **Gateway** | OpenAI-compatível para chats externos (Open WebUI, apps) — porta 9003 |
| **Licença** | Anual por empresa — chave de ativação emitida pela BlueShift (cadastro da empresa); validação online contra o License Server BlueShift em produção |

---
