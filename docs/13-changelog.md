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

**v0.11.6 (2026-09-29) — skills sem falha silenciosa (uma skill por agente + integridade da referência)**
- **uma skill por agente**: o campo vira **radio** (era checkbox), com a opção
  **nenhuma** — dois itens marcados gravavam, por exemplo, `vendas,suporte` e
  as duas skills entravam no prompt marcadas como obrigatórias (regras
  potencialmente conflitantes no mesmo agente); e sem a opção "nenhuma" não
  havia como **limpar** a skill de um agente já salvo;
- **corpo da skill sem corte**: o limite sobe de 4.000 para **8.000
  caracteres** por skill e passa a ser ajustável pela env
  `BLUESHIFT_SKILL_BODY_MAX` (sem rebuild da imagem). Com 4.000 o `rh`
  (5.259 chars) e o `operacoes` (4.826 chars) eram truncados **em silêncio** —
  e o trecho perdido é justamente o fim do SKILL.md, onde ficam as regras de
  formato e comportamento;
- **excluir skill em uso é bloqueado**, com a lista dos agentes afetados
  ("Desvincule antes de excluir") — o vínculo `agentes.skills` é uma lista de
  nomes sem chave estrangeira, então apagar uma skill em uso deixava o agente
  com referência pendurada (as instruções sumiam do prompt sem erro, ou o
  agente caía na cópia do arquivo embarcado e mudava de conteúdo sem aviso);
- **nome de skill que não existe não é gravado**: cadastro e edição recusam
  com mensagem na tela (referência inválida não entra no banco);
- **referência pendurada fica visível**: a lista de Agentes marca
  `⚠️ não aplicada`, a tela de edição mostra o nome que não resolve e o
  **Rastreio** passa a registrar o campo `skills_ausentes` por execução;
- cobertura nova: `tests/test_skills_fase1.py` (limite/env, nome inválido
  recusado, opção "nenhuma", exclusão bloqueada por token de CSV, aviso na
  tela e `skills_ausentes` no trace ponta a ponta).

**v0.11.5 (2026-09-27) — tool calling no gateway (ferramentas do cliente)**
- O gateway OpenAI-compatível passa a **repassar as ferramentas do cliente**:
  com o campo `permitir tool calling` ligado na tela Gateway (`permite_tools`,
  por gateway, **padrão desligado**), os `tools` do corpo vão ao modelo do
  agente e a chamada volta no contrato OpenAI — `finish_reason: "tool_calls"`
  com `message.tool_calls` em JSON ou `delta.tool_calls` em SSE (`stream: true`);
- **quem executa a ferramenta é o cliente** — a plataforma não roda nada. O
  resultado volta na chamada seguinte como mensagem `role: "tool"`, é entregue
  ao modelo com o **nome da ferramenta** (resolvido pelo `tool_call_id`) e o
  agente conclui a resposta em texto. Vale para **qualquer ferramenta** que o
  cliente declarar: não há lista fixa na plataforma;
- **teto de 8 rodadas** de ferramenta por conversa (`MAX_RODADAS_TOOLS`): ao
  estourar, o gateway responde em texto (`finish_reason: "stop"`) para encerrar
  o laço, sem chamar o agente;
- exige **modelo que emita tool call** — modelos pequenos "instruct" respondem
  texto e nunca chamam a ferramenta (a doc do gateway registra o aviso);
- a chamada de ferramenta **não é resposta vazia**: o agente não cai mais no
  fallback de `content` vazio nem na mensagem de "não consegui responder"
  quando o modelo pede uma ferramenta;
- desligado (padrão), o comportamento é o de antes: `tools` ignorado, resposta
  em texto com `finish_reason: "stop"`;
- cobertura nova: 6 casos de tool calling no teste do gateway (repasse só com a
  permissão, JSON, SSE, resultados do cliente, teto de rodadas) e 4 no cliente
  de LLM (`tools` no payload, `tool_calls` na volta).

**v0.11.4 (2026-09-27) — update não deixa mais o repositório com dono `root`**
- O update pela tela roda o `git checkout` num **container irmão** — e esse irmão
  rodava como `root`, então **todo update deixava os arquivos do clone com dono
  `root`** no servidor do cliente. Efeito em cadeia: o update seguinte, rodado
  pelo dono do repo (host ou o próprio `git` da tela), falha com *"Your local
  changes to the following files would be overwritten"* — parece alteração local
  do operador, e não é; e o cliente fica dependente de `sudo` para mexer no
  próprio clone;
- o irmão agora roda com o **uid:gid do dono do repositório** (lido do bind
  mount), com `--group-add` do grupo do `docker.sock` (o CLI do docker precisa
  falar com o daemon) e `HOME` gravável (git/docker config);
- a correção vale para o update disparado por um portal **já nessa versão** — o
  `update_client` que monta o comando é o da imagem em execução. Instalação que
  já tem arquivo de dono `root` no repo precisa de `sudo chown -R <dono> <repo>`
  uma única vez (documentado na página Atualizações);
- testes do comando do irmão passam a cobrir `--user` (dono do repo),
  `--group-add` (grupo do socket) e `HOME`.

**v0.11.3 (2026-09-27) — gateway: `/v1/models` autenticado + `stream` do cliente respeitado**
- **`/v1/models` agora exige o token do canal** (mesmo contrato do chat): a lista
  devolvia os **nomes dos agentes publicados** para qualquer requisição anônima —
  inventário da empresa exposto a quem alcançasse a porta do gateway. Token
  ausente/inválido → **401**; `/healthz` continua público;
- **o campo `stream` da requisição passa a decidir SSE × JSON**: antes quem decidia
  era só o *Modo de resposta* da tela Gateway — então um cliente que pedia
  `stream: false` recebia `text/event-stream` (e o inverso também acontecia), o
  que fazia a requisição parecer **pendurada** em clientes que esperam JSON do
  gateway (caso real de integração de agente externo). Sem o campo, vale o *Modo
  de resposta* (comportamento anterior preservado para Open WebUI);
- **documentado o que o gateway NÃO faz**: sem tool calling — `tools` no corpo é
  ignorado e a resposta sai em texto com `finish_reason: "stop"`. Para um cliente
  que executa ferramentas, o caminho é a **API do portal** (agente como ferramenta
  do cliente); a doc do gateway e a *API Reference* (pt/en/es) registram isso;
- teste novo `tests/test_gateway_openai.py` (rota de modelos com e sem token,
  `stream` nos dois sentidos, caminho de título e `tools` ignorado).

**v0.11.2 (2026-09-14) — roteamento do SQL por intenção + conector ativo/desligado**
- **Conector Ativo/Desligado ganhou interface**: caixa *Ativo* no cadastro e na
  edição, ação **ativar/desativar** na lista (auditada) e badge **inativo**;
  conector inativo não é executado, **não entra no roteamento** (não gasta voto do
  modelo pequeno) e o heartbeat aparece como *(parado)* em vez de "online";
- **Roteamento do conector SQL decidido por INTENÇÃO** (classificada pela IA no
  mesmo voto do roteador, sem custo extra de latência): conector **sem query
  fixa** passa a usar sempre a Consulta inteligente — "listar", "liste", "lista"
  ou "mostre" dão no mesmo (antes a variação do verbo caía em "SQL query nao
  configurada" e o modelo improvisava); pergunta de **análise** usa o SELECT
  montado sobre o schema; pergunta de **dado** usa a query fixa (rápida e exata);
- **Diagnóstico honesto**: quando a consulta não é feita (ou a query fixa é
  dispensada), o motivo real vai para o trace **e** para o prompt — o agente passa
  a explicar a lacuna em vez de inventar dados;
- **Limite de linhas**: teto único de **50 linhas** por consulta com aviso de
  truncamento (o agente não afirma mais "existem exatamente esses registros");
- testes novos de roteamento SQL e de **compatibilidade** (provam que o
  comportamento anterior continua igual), além do teste do campo ativo.

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
  offline na demo), com curadoria do que entra — **sem publicação pública**;
- **README e PRD alinhados ao produto**: README com a seção de Documentação,
  estrutura atualizada e o modelo de roteamento validado; PRD revisado para a
  **versão 0.3** — licença source-available (não mais MIT), marca **CL Agents**,
  conectores corporativos (API/A2A/MCP/SQL), Modo da API `responses`, roteamento
  por IA e pendências de 0.9 a 0.11.1.

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
| v0.11.2 | 2026-09-14 | roteamento do SQL por intenção (fim do "liste"/"lista" quebrado), conector ativo/desligado com interface, diagnóstico honesto do motivo e teto de 50 linhas com aviso |
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
