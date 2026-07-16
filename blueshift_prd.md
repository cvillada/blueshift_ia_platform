# BlueShift IA Platform — Product Requirements Document (PRD)

**Versão:** 0.1 (rascunho inicial)  
**Data:** 2026-07-13  
**Autor:** Nei  
**Base tecnológica:** Hermes-Agent v0.18.2 (licença MIT, Nous Research)

---

## 1. Resumo Executivo

O **BlueShift IA Platform** é um produto de inteligência artificial **on-premise** entregue como **container Docker** que o cliente sobe em sua própria infraestrutura. Ele instala, dentro do ambiente do cliente, uma plataforma de agentes de IA com modelos de linguagem **fine-tuned para o negócio**, memória **persistente por usuário**, controle de acesso por usuário e por sistema (MCP/API), e conectores para sistemas internos (ERP, CRM, RH).

A base tecnológica é o **Hermes-Agent v0.18.2** (licença MIT — permite uso comercial, modificação e sublicenciamento mediante preservação do aviso de copyright).

**Decisão arquitetural:** BlueShift é uma **camada empacotada sobre o Hermes-Agent**, NÃO um fork do código. Isso garante herança de atualizações (v0.18.3, v0.19…) assim que aprovadas, sem retrabalho de merge.

**Nome do produto (canônico):** **BlueShift IA Platform**. "BlueShift Agents" refere-se apenas ao subsistema de agentes/skills (Camada 2), não ao produto como um todo.

**Modelo de entrega:** Container Docker ativado por **chave de licença** (license key) emitida pela BlueShift.

**Modelo de cobrança:** **Licença anual por empresa** (valor definido por cliente/tamanho), não por token nem mensalidade.

**Público-alvo:** qualquer segmento de negócio — a plataforma é genérica e parametrizável por área da empresa, sem vertical inicial obrigatória.

---

## 2. Licença e Conformidade Legal

| Item | Decisão |
|:-----|:--------|
| Licença do Hermes | **MIT** (verificada em `/usr/local/lib/hermes-agent/LICENSE`) |
| Uso comercial | ✅ Permitido (sublicenciar e vender) |
| Estratégia de código | **Layer sobre Hermes** (não fork) |
| Aviso obrigatório | Manter `Copyright (c) 2025 Nous Research` + texto MIT no pacote BlueShift |
| Responsabilidade | BlueShift assume suporte e garantia (MIT is "AS IS") |

**Ação:** O container BlueShift inclui o Hermes como dependência declarada (não modificada). O `LICENSE` do BlueShift cita o Hermes MIT.

---

## 3. Arquitetura do Produto (4 camadas)

```
CAMADA 4 — Experiência      → Portal do cliente (marca BlueShift): gerenciar, cadastrar, monitorar, billing, suporte
CAMADA 3 — Operação         → Installer Docker, License Server, Update Channel, Monitoring
CAMADA 2 — Domínio          → Template Skills por área da empresa, Connector Pack (MCP)
CAMADA 1 — Motor (Hermes)   → Agent loop, tools (terminal/browser/código), MCP, memory, profiles
```

- **Camada 1** é herdada do Hermes v0.18.2 (sem modificação).
- **Camadas 2-4** são propriedade BlueShift e onde reside o valor comercializável.

---

## 4. Modelo de Entrega — Container Docker + License Key

### 4.1 Fluxo de ativação
```
1. Cliente recebe imagem Docker BlueShift (ou puxa do registry privado)
2. Sobe o container:  docker run -e BLUESHIFT_LICENSE=XXXX blueshift/platform
3. Container valida a chave no License Server BlueShift (online)
4. Se válida → ativa perfil do cliente, baixa modelo fine-tuned autorizado
5. Se inválida/expirada → container sobe em modo "bloqueado" (mostra tela de ativação)
```

### 4.2 Componentes do container
```
blueshift/platform
├── hermes-agent/          (v0.18.2, dependência, não modificado)
├── blueshift-layer/
│   ├── license_client.py  (valida chave no License Server)
│   ├── installer.py       (cria profile do cliente no 1º boot)
│   ├── update_client.py   (checa Update Channel aprovado)
│   ├── connector_pack/    (servidores MCP prontos: erp, crm, rh)
│   └── template_skills/   (skills por área da empresa)
├── models/                (modelo fine-tuned do cliente, montado via volume)
└── data/                  (memória, banco vetorial — volume persistente)
```

### 4.3 Isolamento por cliente
Cada cliente = 1 **profile Hermes** (`hermes profile create <cliente>`).  
Perfis são pastas isoladas: config, skills, cron, memory, .env.  
Zero vazamento de dados entre clientes.

---

## 5. Funcionalidades do Produto (mapa Hermes → BlueShift)

| Capacidade Hermes (base) | Produto BlueShift |
|:------------------------|:------------------|
| `profile create` | **Instalador 1-comando** gera profile isolado do cliente |
| Tools: terminal, browser, código, arquivos | Acesso ao SO do cliente (on-premise) |
| MCP servers | **Connector Pack** pré-pronto (ERP/CRM/RH) |
| Memory por sessão/perfil | **Memória persistente por usuário logado** |
| Skills reutilizáveis | **Template Skills por área da empresa** |
| Cron jobs nativos | **Relatórios automáticos** por cliente |
| Qualquer modelo (OpenRouter, local) | **Modelos fine-tuned locais** + externos opcionais |

---

## 6. Controle de Acesso

### 6.1 Hierarquia
```
Admin (chave mestra) → cria usuários e sistemas
  ├── Usuário (login/senha ou SSO) → memória individual, escopo por departamento
  └── Sistema (MCP key / API key) → escopo limitado, rate limit, auditável
```

### 6.2 Permissões
- O que o usuário vê (departamento)
- O que o usuário faz (agentes/skills liberados)
- O que o sistema conecta (MCP escopo mínimo)

---

## 7. Modelos de IA (híbrido)

| Tipo | Onde roda | Quando usar |
|:-----|:---------|:-----------|
| **Fine-tuned local** | GPU do cliente (vLLM/MLX) | Dados sensíveis, rotinas, tom do negócio |
| **Externo opcional** | OpenAI/Claude/Gemini via API | Capacidade extra sob controle do cliente |

Cliente decide quais tarefas usam local vs externo. Dados sensíveis nunca saem.

### 7-A. RAG (Retrieval-Augmented Generation)

RAG é a fonte de contexto externa ao modelo (ver §8-C "Contexto Dinâmico"). O BlueShift mantém um **banco vetorial local** (volume `data/` do container) com documentos do cliente:

- Manual de produto, políticas internas, base de conhecimento, contratos.
- Em tempo de inferência, o orquestrador recupera os chunks relevantes e injeta no contexto do modelo.
- **Sem RAG:** o modelo responde só com parâmetros (sem dados variáveis do cliente).
- **Com RAG:** o modelo responde com os dados atuais do cliente, sem retreinamento.

RAG é a **porta de entrada de dados variáveis**; Fine-Tuning é para o "tom/comportamento". Os dois são complementares (decisão prévia do projeto).

---

## 8. Template Skills e Connector Pack (Camada 2)

### 8.1 Template Skills (genéricos por área da empresa, parametrizáveis)

Os agentes/skills são **genéricos e parametrizáveis por área da empresa** — a plataforma é prática em qualquer segmento de negócio, sem vertical inicial obrigatória.

- `vendas` — consulta ERP, propõe produtos, follow-up
- `suporte` — abre chamado, consulta base
- `financeiro` — fecha caixa, gera relatório
- `rh` — consulta folha, responde colaborador
- `operacoes` — alertas de processo, relatórios automáticos

Cada skill é um `SKILL.md` + referências. Parametrizável por cliente e por área. O mesmo template serve a qualquer cliente; o comportamento é ajustado pelos dados e pelo escopo de área.

### 8.2 Connector Pack (MCP servers)
- `mcp_erp` — buscar cliente, pedidos, criar oportunidade
- `mcp_crm` — histórico de contato, próximos passos
- `mcp_rh` — folha, colaboradores

> **Genérico por design:** sem vertical inicial (decisão do produto). Os templates acima são genéricos; o 1º cliente parametriza por área, não por indústria.

---

## 8-B. Feature Matrix (visão de produto)

Matriz de capacidades do BlueShift (origem: slide "Blueshift-agents"). Serve como resumo product-facing e guia de cobertura da documentação.

| Modelos & IA | Agentes & Contexto | Operações & Segurança |
|:-------------|:-------------------|:----------------------|
| Gerenciamento de Modelos de IA com fallback | Contexto Atualizados | Acesso a Modelos Internos e Externos |
| RAG | Criação de Agentes e Reaproveitamento | Segurança |
| Fine-Tuning | Criação de Skills e Reaproveitamento | MCP ou API |
| Memória por Utilizador | Controle de Acesso | Observabilidade |
| Segmentação | Rastreabilidade | Monitoramento |

**Status de cobertura na doc (mapeado):**

| Item da matriz | Onde está coberto | Gap |
|:--------------|:------------------|:-----|
| Gerenciamento de Modelos c/ fallback | §7 (híbrido) | ✅ |
| RAG | Discussão prévia (não seção própria) | ⚠️ criar §7-A |
| Fine-Tuning | Discussão prévia | ✅ |
| Memória por Utilizador | §6 / §4.3 | ✅ |
| Segmentação | §4.3 (isolamento) — sem nome | 🔧 tornar explícito (§8-D) |
| Contexto Atualizados | Ausente como feature | 🔴 criar §8-C |
| Criação de Agentes e Reaproveitamento | §8.1 (skills) — implícito | 🔧 criar §8-E (Agent Factory) |
| Criação de Skills e Reaproveitamento | §8.1 | ✅ |
| Controle de Acesso | §6 | ✅ |
| Rastreabilidade | Implícita no audit MCP | 🔧 consolidar (§8-F) |
| Acesso Interno/Externo | §7 | ✅ |
| Segurança | Isolamento por profile | ✅ |
| MCP ou API | §6 | ✅ |
| Observabilidade | Fase 4 (GTM) | 🔧 consolidar (§8-F) |
| Monitoramento | Fase 4 (GTM) | 🔧 consolidar (§8-F) |

> **Naming:** nome canônico do produto = **BlueShift IA Platform**. "Blueshift-agents" (slide) refere-se à **camada de agentes** do produto. "BlueShift Agents" = subsistema de agentes/skills (Camada 2).

---

## 8-C. Contexto Dinâmico (Contexto Atualizados)

A matriz lista "Contexto Atualizados" como feature central. No BlueShift, contexto dinâmico = combinação de 3 fontes, sempre frescas:

1. **Memória por usuário** (§6) — histórico persistente do usuário logado (banco vetorial local).
2. **RAG** — recuperação de documentos atuais do cliente (manual, política, base de conhecimento) em tempo de inferência.
3. **Janela de sessão + estado do agente** — o agente mantém o contexto da conversa ativa e o estado entre passos de tool calling.

**Princípio:** o agente nunca responde "de cabeça" quando há dado atualizado disponível. Contexto é composto em runtime, não congelado em prompt estático.

**Implementação (camada BlueShift):** orquestrador decide, por tarefa, quais das 3 fontes consultar antes de gerar resposta. RAG opcional por cliente (volume `data/` montado no container).

---

## 8-D. Segmentação

A matriz lista "Segmentação" (do original "Seguimentação"). No BlueShift, **segmentação é voltada a ÁREAS da empresa** (ex: vendas, suporte, financeiro, RH), não a setores de mercado/vertical.

**Decisão:** a plataforma é **genérica e prática em qualquer segmento de negócio** (sem vertical inicial obrigatória). Os agentes/skills são parametrizáveis por área da empresa, não por indústria.

**Eixo definido:** segmentação por **área da empresa** (departamento).
**Conteúdo a segmentar:** AINDA NÃO DEFINIDO pelo produto — candidatos em avaliação:

| Dimensão | Exemplo de segmentação por área |
|:---------|:--------------------------------|
| Dados | Cada área vê só os dados do seu domínio |
| Acesso | Permissões liberadas por área |
| Usuários | Usuários vinculados à(s) sua(s) área(s) |
| Memória | Memória compartilhada ou isolada por área |

> **Pendência:** definir quais das dimensões acima (dados, acesso, usuários, memória, outras) são efetivamente segmentadas por área. Por ora, o mecanismo de isolamento (1 profile Hermes por cliente, §4.3) já suporta qualquer uma delas — falta only decidir o escopo de produto.

Implementação atual: `template_skills/` já separa por área (vendas/suporte/financeiro/rh — §8.1); o installer copia os templates por cliente.

---

## 8-E. Agent Factory e Reaproveitamento

A matriz separa "Criação de Agentes" de "Criação de Skills". No BlueShift:

- **Agente** = instância operacional composta por: 1+ skills + 1 modelo + 1 escopo de acesso + 1 conjunto de conectores MCP.
- **Skill** = unidade reutilizável de comportamento (`SKILL.md` + referências), parametrizável por cliente/área da empresa.

**Reaproveitamento:**
- Skill criada para o Cliente A pode ser copiada para o Cliente B (mesma pasta `template_skills/`), com parâmetros ajustados.
- Agentes são "montados" a partir do catálogo de skills + conectores, não escritos do zero por cliente.
- Isso é o que transforma BlueShift de "consultoria" em "produto" (PRD §intro): o mesmo pacote serve a N clientes.

**Implementação:** `blueshift init <cliente>` popula o profile com os templates; o installer copia `template_skills/` (§8.1) e conecta o Connector Pack (§8.2).

---

## 8-F. Observabilidade, Rastreabilidade e Monitoramento

A matriz lista os 3 separadamente. No BlueShift eles formam o subsistema de confiança (Camada 3/4):

| Capacidade | O que entrega | Status na doc |
|:-----------|:-------------|:-------------|
| **Rastreabilidade** | Todo agente deixa rastro: quem perguntou, qual skill, qual tool MCP, qual dado consultado, qual resposta. Auditoria completa por usuário/sistema. | Implícita no escopo mínimo MCP (§6.2); consolidada aqui |
| **Observabilidade** | Métricas de execução (latência, tokens, taxa de erro de tool, uso por departamento). | Fase 4 (GTM) — antecipada nesta seção |
| **Monitoramento** | Health do container, do modelo local (GPU), e dos conectores MCP (online/offline). Alertas pro admin. | Fase 4 (GTM) — antecipada nesta seção |

**Princípio de segurança:** todo acesso a dado do cliente via MCP é **auditável** (quem + quando + o quê). Isso é pré-requisito para LGPD/ compliance enterprise.

---



| Fase | Escopo | Gatilho |
|:-----|:-------|:--------|
| **0. Legal** | ✅ Licença MIT confirmada | Concluída |
| **1. Núcleo** | Decidir arquitetura (layer sobre Hermes) | ✅ Decidido: layer |
| **2. Empacotar** | Docker + License Server + Update Channel | Quando houver 1 cliente piloto |
| **3. Domínio** | Template skills + connectors por área da empresa | Quando repetir para 2º cliente |
| **4. GTM** | **Portal do cliente (core): gerenciar, cadastrar, monitorar + billing + suporte** | Após Fase 2 (já é obrigatório na arquitetura) |

---

## 8-G. Setup de Desenvolvimento (modelo de 2 pastas + Git)

O desenvolvimento do BlueShift segue o modelo **camada sobre Hermes** decidido no PRD:

- **Hermes (motor):** já instalado na máquina de dev; fork baixado em `~/Dev/_ref/hermes-ref` **apenas para consulta** (read-only). Nunca editado nem copiado para o projeto.
- **BlueShift (camada):** projeto em `~/Dev/blueshift-ia-platform` com venv próprio. O Hermes entra como **dependência** (`hermes-agent==0.18.2` no Dockerfile), não como código do projeto.
- **Git:** repo único `blueshift-ia-platform` contendo só a camada. O fork do Hermes no GitHub é espelho read-only.
- **Quem constrói:** o próprio Hermes-Agent (rodando na máquina) escreve os arquivos do BlueShift a pedido do desenvolvedor.

Passo-a-passo completo: ver **`blueshift_passo_a_passo.md`** (mesmo diretório).

> **Regra de ouro:** desenvolvimento e Git são da camada; Hermes é motor/referência. Isso garante herança de updates (v0.18.3…) ao subir o pin de versão, sem merge de fork.

---

## 10. Pendências / Decisões em aberto

| Item | Status | Próximo passo |
|:-----|:------|:--------------|
| Licença | ✅ MIT OK | Incluir aviso no pacote |
| Fork vs Layer | ✅ Layer | Documentar padrão de integração |
| Entrega | ✅ Docker + License Key | Construir installer + license server |
| **RAG** | ✅ §7-A criado | Implementar banco vetorial local no container |
| **Contexto Dinâmico** | ✅ §8-C criado | Orquestrador de contexto (Camada 2) |
| **Segmentação** | 🟡 §8-D (áreas da empresa; conteúdo em aberto) | Definir o que segmentar (dados/acesso/usuários/memória) |
| **Agent Factory** | ✅ §8-E criado | Catálogo de skills reaproveitáveis |
| **Observab./Rastreab./Monitor.** | ✅ §8-F criado | Implementar na Fase 4 (GTM) |
| **Vertical inicial** | ✅ Resolvido: SEM vertical — plataforma genérica p/ qlq segmento | Templates parametrizáveis por área |
| **Cobrança** | ✅ Anual por empresa (não mensal) | Definir faixas de preço por tamanho |
| **Portal do cliente** | ✅ OBRIGATÓRIO (core) — gerenciar, cadastrar, monitorar | Construir na Fase 4; antecipar na arquitetura (Camada 4) |
| **Naming** | ✅ "BlueShift IA Platform" (canônico) | "BlueShift Agents" = subsistema apenas |

---

## 11. Posicionamento vs Concorrência (análise prévia)

| Sistema | Tipo | Veredito vs BlueShift |
|:--------|:-----|:---------------------|
| MS Foundry | Cloud Azure | BlueShift ganha em on-premise/lock-in |
| Databricks Genie | Cloud + SQL | BlueShift ganha em generalismo e custo |
| Google ADK | Cloud + OSS | BlueShift = ADK + deploy on-premise real |
| **Hermes (base)** | Local/self-host | BlueShift = Hermes empacotado como produto |

**Diferencial BlueShift:** on-premise real (dados não saem), custo zero de plataforma (modelo roda na GPU do cliente), zero lock-in (MIT), entrega Docker com chave.

---

## 12. Resumo para investidor/cliente (one-liner)

> "BlueShift IA Platform é uma plataforma de IA que você instala DENTRO da sua empresa — funciona em qualquer segmento de negócio. Seus dados não saem. Modelos treinados no seu negócio. Licença anual por empresa, não por token. Sobe em 1 comando com sua chave de ativação."
