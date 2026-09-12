## 13. Changelog (histórico de versões)

**O que é:** histórico das versões entregues do CL Agents. A versão instalada
aparece em **Atualizações → Configuração de ambiente**; atualização disponível e
o botão de atualizar ficam na mesma tela.

**Convenção:** toda release nova entra **no topo** desta página, com os
destaques que o usuário percebe. A checagem automática
(`tools/doc_check.py`) exige que toda tag `vX.Y.Z` do repositório exista aqui —
então esta página não fica para trás. Versões sem destaques registrados no
momento do release aparecem como `—`.

### Últimas versões — destaques

**v0.11.1 (2026-09-12) — documentação navegável dentro do produto**
- **Docs do portal** reorganizado em páginas: sidebar agrupada (Começando · Telas do
  Portal · Como funciona · Referência), **busca** na documentação, uma página por
  tela/assunto, índice "Nesta página", botão de copiar nos blocos de código,
  impressão limpa e links antigos (`#5-9-conectores`) continuando válidos;
- páginas novas: **API Reference** (integração do TI do cliente: API do portal e
  Gateway OpenAI, autenticação, erros e limites) e **Changelog** por versão;
- **rotina de documentação**: template de página, mapa nome-técnico ↔ rótulo da
  tela e checagem automática (`tools/doc_check.py`) que barra alteração de código
  sem documentação — cobre rotas, campos de formulário, variáveis de ambiente,
  tabelas do banco e versões entregues;
- a **Ajuda IA** continua respondendo a partir das mesmas páginas (uma fonte só);
- **gerador de site de documentação** para uso interno (apresentar/imprimir/levar
  offline na demo), com curadoria do que entra — **sem publicação pública**.

**v0.11.0 (2026-09-12) — Connector Pack: integrações corporativas**
- Conector **API**: autenticação `none` / `bearer` / `oauth2` (client_credentials
  com cache e renovação automática), timeout configurável, **job assíncrono
  (polling)** com status de conclusão/erro e **mapeamento da resposta** (envia ao
  modelo só o pedaço útil do JSON);
- novo tipo de conector **A2A (agente remoto)** — conversa com agentes
  publicados no padrão Agent2Agent (Oracle Autonomous AI Database e AIDP `/a2a`);
- conector **SQL**: **SSL mode** (PostgreSQL/Databricks SQL Warehouse) e
  **wallet** do Oracle Autonomous (mTLS); o botão 🔌 Testar Conexão valida os dois;
- **Modelos IA** com o campo **Modo da API** (`openai_chat` padrão ou
  `responses` — agentes externos como o AIDP `/chat`);
- documentação de conectores reescrita (guia por tipo, receitas Databricks /
  Autonomous / AIDP, problemas comuns) e, na sequência, a documentação passou a
  ser publicada em páginas navegáveis com busca dentro do portal.

**v0.10.16 (2026-09-09) — corpo das skills no prompt**
- As instruções escritas no **corpo** da skill passam a ser enviadas ao modelo
  (antes só a descrição ia) — regras de formato, tom e limites definidos na skill
  são obedecidos.

**v0.10.15 (2026-09-08) — respostas sempre limpas**
- Bloqueio de vazamentos de `<tool_call>` / `<think>` crus na resposta: se o dado
  pedido não veio, o agente pede a informação em texto, nunca despeja o protocolo.

**v0.10.14 (2026-09-08) — desempenho e base de conhecimento**
- Instrumentação de latência **por fase** (roteador, conectores, RAG, modelo) no
  rastreio de cada resposta;
- a base de conhecimento deixou de receber gravação automática de conversas
  (cresce só por cadastro, import CSV/PDF e indexação de skills);
- **export JSONL das memórias** na tela Memória (com máscara LGPD), como já
  existia no Conhecimento;
- comandos de **atualização manual** documentados na tela Atualizações (para
  quando o botão falhar) e correção do update que recriava o portal sem a
  configuração da instalação (licença aparecia inválida).

### Histórico completo

| Versão | Data | Destaques registrados |
|:-------|:-----|:----------------------|
| v0.11.1 | 2026-09-12 | documentação navegável no produto (páginas, busca, API Reference, Changelog) + checagem automática doc × código e gerador de site interno |
| v0.11.0 | 2026-09-12 | Connector Pack (auth OAuth2/bearer, polling + mapeamento, tipo A2A, SSL/wallet, modelo Modo=responses) e guia completo de conectores |
| v0.10.16 | 2026-09-09 | corpo das skills vai ao prompt (regras de formato valem) |
| v0.10.15 | 2026-09-08 | guard de resposta (tool_call/think nunca chegam ao usuario) |
| v0.10.14 | 2026-09-08 | instrumentação de latência por fases, RAG sem auto-alimentação, export JSONL de memórias (+ correção do update que perdia a config da instalação) |
| v0.10.13 | 2026-09-04 | — |
| v0.10.12 | 2026-09-03 | Update LICENSE |
| v0.10.11 | 2026-09-03 | — |
| v0.10.10 | 2026-09-01 | — |
| v0.10.9 | 2026-09-01 | — |
| v0.10.8 | 2026-09-01 | — |
| v0.10.7 | 2026-09-01 | update — safe.directory no container irmao (dubious ownership) |
| v0.10.6 | 2026-09-01 | update — safe.directory no container irmao (dubious ownership) |
| v0.10.5 | 2026-09-01 | remove 'BlueShift' dos prompts dos agentes/chats (identificacao neutra) |
| v0.10.4 | 2026-09-01 | — |
| v0.10.3 | 2026-09-01 | combos de Area com areas HARDCODED (agentes novo/editar + usuario novo) |
| v0.10.2 | 2026-09-01 | — |
| v0.10.1 | 2026-09-01 | — |
| v0.10.0 | 2026-09-01 | — |
| v0.9.9 | 2026-09-01 | — |
| v0.9.8 | 2026-09-01 | — |
| v0.9.7 | 2026-09-01 | — |
| v0.9.6 | 2026-08-31 | — |
| v0.9.5 | 2026-08-31 | — |
| v0.9.4 | 2026-08-31 | — |
| v0.9.3 | 2026-08-10 | tokens por agente nos cards do Workspace (periodo 1d/7d/30d/90d) |
| v0.9.2 | 2026-08-06 | endpoint do Gateway nao usa host de tunel publico (ngrok) |
| v0.9.1 | 2026-08-02 | popup de Ajuda com IA baseado no DOCUMENTACAO_PB.md |
| v0.9.0 | 2026-07-30 | README e PRD atualizados (MCP SSE, AREAS env, editar usuarios) |
| v0.8.1 | 2026-07-29 | Melhorias: Teste A/B, Hamburger, Oracle, Fine-Tuning |
| v0.8.0 | 2026-07-27 | Conformidade LGPD na saida |
| v0.7.1 | 2026-07-25 | Remove docs obsoletos: blueshift_passo_a_passo, blueshift_dev_guide, CONFORMIDADE |
| v0.7.0 | 2026-07-24 | Docs: observabilidade na tabela de funcionalidades |
| v0.6.1 | 2026-07-24 | Saude: indices SQLite + funcao limpar_auditoria_antiga (90 dias) |
| v0.6.0 | 2026-07-24 | Docs: rastreio documentado na tabela de funcionalidades |
| v0.5.0 | 2026-07-23 | Extrator inteligente: qualquer codigo vira placeholder, sem C001 fixo |
| v0.4.0 | 2026-07-23 | Docs: fluxo atualizado (conectores primeiro, RAG complementar) |
| v0.3.0 | 2026-07-22 | Docs: skills persistentes no banco documentadas |
| v0.2.0 | 2026-07-22 | README: secao Hardware Recomendado com 4 tiers (CPU/RAM/Disco/SO) |
| v0.1.0 | 2026-07-22 | Fix: chave removida do docstring (exemplo generico) |

> Versões mais antigas (antes da v0.9.x) estão nas *Releases* do repositório;
> o histórico aqui é o que ficou registrado no momento de cada entrega.
