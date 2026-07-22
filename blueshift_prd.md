# BlueShift IA Platform — Product Requirements Document (PRD)

**Versão:** 0.2  
**Data:** 2026-07-21  
**Autor:** Nei  
**Base tecnológica:** Flask standalone, Python puro (sem dependência de motor externo)

---

## 1. Resumo Executivo

O **BlueShift IA Platform** é um produto de inteligência artificial **on-premise** entregue como **container Docker** que o cliente sobe em sua própria infraestrutura. Ele instala, dentro do ambiente do cliente, uma plataforma de agentes de IA com modelos de linguagem **cadastrados pelo cliente**, memória **persistente por usuário**, controle de acesso por usuário e por sistema (MCP/API), e conectores para sistemas internos (ERP, CRM, RH).

**Nome do produto (canônico):** **BlueShift IA Platform**. "BlueShift Agents" refere-se apenas ao subsistema de agentes/skills, não ao produto como um todo.

**Modelo de entrega:** Container Docker ativado por **chave de licença** (license key) emitida pela BlueShift.

**Modelo de cobrança:** **Licença anual por empresa** (valor definido por cliente/tamanho), não por token nem mensalidade.

**Público-alvo:** qualquer segmento de negócio — a plataforma é genérica e parametrizável por área da empresa, sem vertical inicial obrigatória.

---

## 2. Licença e Conformidade Legal

| Item | Decisão |
|:-----|:--------|
| Licença | **MIT** — código próprio BlueShift |
| Uso comercial | ✅ Permitido (sublicenciar e vender) |
| Aviso obrigatório | Manter texto MIT no pacote BlueShift |
| Responsabilidade | BlueShift assume suporte e garantia (MIT is "AS IS") |

---

## 3. Arquitetura do Produto (4 camadas)

```
CAMADA 4 — Experiência      → Portal do cliente (marca BlueShift): gerenciar, cadastrar, monitorar
CAMADA 3 — Operação         → Installer Docker, License Server, Update Channel, Monitoring
CAMADA 2 — Domínio          → Template Skills por área da empresa, Connector Pack (MCP)
CAMADA 1 — Motor/Núcleo     → Flask + SQLite + urllib (tudo Python puro, sem libs externas pesadas)
```

---

## 4. Modelo de Entrega — Container Docker + License Key

### 4.1 Fluxo de ativação
```
1. Cliente recebe imagem Docker BlueShift (ou puxa do registry privado)
2. Sobe o container:  docker run -e BLUESHIFT_LICENSE=XXXX blueshift/platform
3. Container valida a chave no License Server BlueShift (online)
4. Se válida → ativa perfil do cliente
5. Se inválida/expirada → container sobe em modo "bloqueado" (mostra tela de ativação)
```

### 4.2 Componentes do container
```
blueshift/platform
├── blueshift-layer/          → código da plataforma
│   ├── license_client.py     (valida chave no License Server)
│   ├── installer.py          (cria perfil do cliente no 1º boot)
│   ├── update_client.py      (checa Update Channel aprovado)
│   ├── connector_pack/       (servidores MCP prontos: erp, crm, rh)
│   └── template_skills/      (skills por área da empresa)
├── data/                     (banco SQLite, memória, vetores — volume persistente)
```

### 4.3 Isolamento por cliente
Cada cliente = registros isolados por `cliente_id` no SQLite + RBAC.
Perfis são pastas isoladas: skills, config.
Zero vazamento de dados entre clientes.

---

## 5. Funcionalidades do Produto

| Capacidade | Produto BlueShift |
|:-----------|:------------------|
| Perfil isolado | **Instalador 1-comando** gera perfil isolado do cliente |
| Tools | Agente executa ferramentas MCP reais (ERP/CRM/RH) e injeta no contexto |
| MCP servers | **Connector Pack** pré-pronto (ERP/CRM/RH) exposto via stdio JSON-RPC |
| Memória | **Memória persistente por usuário logado** (TF-IDF + cosseno, Python puro) |
| Skills reutilizáveis | **Template Skills por área da empresa** |
| Relatórios | **Uso de Tokens** e dashboard de monitoramento |
| Modelos | **Qualquer OpenAI-compatible**: local (vLLM/LM Studio/Ollama) ou externo (OpenAI/DeepSeek/Claude) |

---

## 6. Controle de Acesso

### 6.1 Hierarquia
```
Admin → cria usuários e sistemas
  ├── Usuário (login/senha ou SSO) → memória individual, escopo por departamento
  └── Sistema (API key do canal) → escopo limitado, rate limit, auditável
```

### 6.2 Permissões
- O que o usuário vê (departamento)
- O que o usuário faz (agentes/skills liberados)
- O que o sistema conecta (MCP escopo mínimo)

---

## 7. Modelos de IA (híbrido)

| Tipo | Onde roda | Quando usar |
|:-----|:---------|:-----------|
| **Local** | GPU do cliente (vLLM/LM Studio/Ollama) | Dados sensíveis, rotinas |
| **Externo opcional** | OpenAI/Claude/DeepSeek via API | Capacidade extra sob controle do cliente |

Cliente decide quais tarefas usam local vs externo. Dados sensíveis nunca saem.

### 7-A. RAG (Retrieval-Augmented Generation)

RAG é a fonte de contexto externa ao modelo (ver §8-C "Contexto Dinâmico"). O BlueShift mantém um **banco vetorial local** com documentos do cliente:

- Manual de produto, políticas internas, base de conhecimento, contratos.
- Em tempo de inferência, o orquestrador recupera os chunks relevantes e injeta no contexto do modelo.
- **Sem RAG:** o modelo responde só com parâmetros (sem dados variáveis do cliente).
- **Com RAG:** o modelo responde com os dados atuais do cliente, sem retreinamento.

RAG é implementado em Python puro (TF-IDF + cosseno), sem libs externas — 100% on-premise.

---

## 8. Template Skills e Connector Pack (Camada 2)

### 8.1 Template Skills (genéricos por área da empresa, parametrizáveis)

- `vendas` — consulta ERP, propõe produtos, follow-up
- `suporte` — consulta base de conhecimento
- `financeiro` — análise de gastos
- `rh` — consulta folha, dados de colaborador
- `operacoes` — alertas de processo, relatórios automáticos

### 8.2 Connector Pack (MCP servers)
- `mcp_erp` — buscar cliente, pedidos, criar oportunidade
- `mcp_crm` — histórico de contato, próximos passos
- `mcp_rh` — folha, colaboradores

> **Genérico por design:** sem vertical inicial (decisão do produto).

---

## 8-B. Feature Matrix (visão de produto)

| Modelos & IA | Agentes & Contexto | Operações & Segurança |
|:-------------|:-------------------|:----------------------|
| Gerenciamento de Modelos de IA com fallback | Contexto Atualizados | Acesso a Modelos Internos e Externos |
| RAG | Criação de Agentes e Reaproveitamento | Segurança |
| Fine-Tuning | Criação de Skills e Reaproveitamento | MCP ou API |
| Memória por Utilizador | Controle de Acesso | Observabilidade |
| Segmentação | Rastreabilidade | Monitoramento |

---

## 8-C. Contexto Dinâmico (Contexto Atualizados)

Contexto dinâmico = combinação de 3 fontes, sempre frescas:

1. **Memória por usuário** (§6) — histórico persistente do usuário logado (banco vetorial local).
2. **RAG** — recuperação de documentos atuais do cliente em tempo de inferência.
3. **Conectores MCP** — dados de sistemas internos (ERP/CRM/RH) executados em tempo real.

**Princípio:** o agente nunca responde "de cabeça" quando há dado atualizado disponível.

---

## 8-D. Segmentação

Segmentação por **área da empresa** (departamento).

| Dimensão | Implementação |
|:---------|:--------------|
| Dados | Cada área vê só os dados do seu domínio |
| Acesso | Permissões liberadas por área |
| Usuários | Usuários vinculados à(s) sua(s) área(s) |

---

## 8-E. Agent Factory e Reaproveitamento

- **Agente** = instância operacional composta por: modelo (principal + fallback) + skills + conectores MCP.
- **Skill** = unidade reutilizável de comportamento (`SKILL.md` + referências), parametrizável por cliente/área.
- **Reaproveitamento:** agente é montado a partir do catálogo, não escrito do zero por cliente.

---

## 8-F. Observabilidade, Rastreabilidade e Monitoramento

| Capacidade | O que entrega |
|:-----------|:-------------|
| **Rastreabilidade** | Auditoria completa: quem perguntou, qual agente, qual conector, qual resposta |
| **Observabilidade** | Métricas de execução (latência, tokens, taxa de erro) |
| **Monitoramento** | Health do container, do modelo local, e dos conectores MCP (online/offline) |

**Princípio de segurança:** todo acesso a dado do cliente é **auditável** (quem + quando + o quê).

---

## 8-G. Setup de Desenvolvimento

O desenvolvimento do BlueShift segue o modelo **Flask standalone**:

- **BlueShift (plataforma):** projeto em `~/bp-proj` com venv próprio (`bp-venv`), instalado via `pip install -e .`
- **Git:** repo único no GitHub contendo toda a plataforma.
- **Quem constrói:** o desenvolvedor, utilizando ferramentas de IA auxiliares, escreve os arquivos do BlueShift.

Passo-a-passo completo: ver **`blueshift_passo_a_passo.md`** (mesmo diretório).

---

## 10. Pendências / Decisões em aberto

| Item | Status | Próximo passo |
|:-----|:------|:--------------|
| Licença | ✅ MIT OK | Incluir aviso no pacote |
| Entrega | ✅ Docker + License Key | Construir installer + license server |
| RAG | ✅ §7-A criado | Implementado (TF-IDF + cosseno, Python puro) |
| Contexto Dinâmico | ✅ §8-C criado | Orquestrador de contexto implementado |
| Segmentação | ✅ §8-D (áreas da empresa) | Implementado no Portal |
| Agent Factory | ✅ §8-E criado | Implementado com fallback de modelo |
| Observab./Rastreab./Monitor. | ✅ §8-F criado | Implementado no Portal |
| Vertical inicial | ✅ Resolvido: SEM vertical | Templates parametrizáveis por área |
| Cobrança | ✅ Anual por empresa | Tela de Uso de Tokens + contratos |
| Portal do cliente | ✅ OBRIGATÓRIO (core) | Implementado e rodando |

---

## 12. Resumo para investidor/cliente (one-liner)

> "BlueShift IA Platform é uma plataforma de IA que você instala DENTRO da sua empresa — funciona em qualquer segmento de negócio. Seus dados não saem. Modelos cadastrados pelo cliente. Licença anual por empresa, não por token. Sobe em 1 comando com sua chave de ativação."
