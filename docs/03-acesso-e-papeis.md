## 4. Acesso e Papéis (RBAC)

| Papel | O que pode |
|:------|:-----------|
| **admin** | Tudo: CRUD completo, auditoria, observabilidade, canais, LGPD, SSO |
| **gestor** | Telas operacionais (monitorar, workspace, agentes, teste A/B) |
| **usuario** | Telas do dia a dia (workspace, chat, memória, conhecimento) |
| **sistema** | Ações via API (registrado em auditoria) |

Hierarquia: `admin > gestor > usuario > sistema`.

Tabela de permissões por rota (resumo):

| Tela | Acesso |
|:-----|:-------|
| Monitorar, Workspace, Docs, Usuários, Agentes, Skills, Uso de Tokens, Memória, Conhecimento, Chat, Teste A/B, Fine-Tuning | login_required |
| Clientes (novo/editar/suspender), Usuários (novo/editar/suspender), Áreas (tudo), Agentes (novo/editar/excluir), Skills (novo/editar/excluir/gerar-ia/indexar-rag), Conectores (tudo), Modelos (tudo), Canais (tudo), Auditoria, Observabilidade, Alertas, LGPD, SSO config, Atualizações, Rastreio, Exportar JSONL | admin_required |
| API `/api/v1/agente`, `/api/v1/feedback/<id>` | token do canal (Bearer) |

---
