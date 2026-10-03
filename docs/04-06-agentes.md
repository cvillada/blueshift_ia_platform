### 5.6 Agentes (/portal/agentes)

**Onde:** Cadastros → Agentes.

**Propósito:** criar e gerenciar os agentes de IA por área.

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Cliente | ✅ | XPTO Seguros (Piloto) | Já vem selecionado (primeira empresa) |
| Nome do agente | ✅ | `Agente Vendas` | |
| Área | ✅ | `vendas` | Define quais conectores o agente enxerga |
| Modelo de IA (principal) | ✅ | `bonsai-8b` | Modelo cadastrado em Modelos IA |
| Modelo de IA (fallback) | ❌ | `hermes-3-llama-3.1-8b` | Usado se o principal falhar |
| Skill do agente | ❌ | `vendas` | **Radio — uma só** (ou "nenhuma"); ver §5.7 |
| Workers | ❌ | `Agente Vendas`, `Agente Suporte` | Lista ordenada de agentes que o mestre orquestra; vazio = só o mestre |
| Status | ❌ | `ativo` | ativo / pausado |
| 🔒 Aplicar LGPD | checkbox | ativo por padrão | Anonimiza a resposta na saída |

Ações: **testar** (chat de teste com o pipeline completo: conectores → RAG →
LLM, com 👍/👎 feedback e 🔍 rastreio), **editar**, **excluir**.

**Skill do agente (uma por agente):** o campo é **radio** — uma skill, com a
opção **nenhuma** (sem ela não haveria como limpar a skill de um agente já
salvo). Gravar um nome que **não existe no catálogo é recusado** no cadastro e
na edição (erro visível, nada é salvo); se a referência já estiver pendurada, a
listagem mostra `⚠️ não aplicada` e o **Rastreio** registra `skills_ausentes`.
Detalhes em `04-07-skills.md`.

**Checklist contextual (topo da página Agentes):** a plataforma mostra o que
o agente precisa, na ordem de configuração — `✓ Modelo IA (N)` · `Skills: N` ·
`Conectores: N`. Sem nenhum modelo cadastrado, aparece o aviso **"Comece por
aqui: cadastre um modelo em Modelos IA"** (com link) e o item vira
`✗ Modelo IA — cadastre aqui`.

**Ordem de configuração (menu Cadastros):** Clientes → Usuários → Modelos IA →
Skills → Agentes → Conectores → Canais — o menu segue a sequência de
montagem (base → modelo/skills → agente → entrega).

**Roteamento inteligente de conectores:** antes de executar os conectores
da área, uma IA curta (a mesma do agente, ou a apontada por
`BLUESHIFT_ROUTER_MODEL` — ver §5.8, "Modelo de roteamento") decide QUAL
conector é relevante para a pergunta
— ou nenhum. Pergunta de norma/política → responde só com a Base de
Conhecimento (RAG), sem tocar nos conectores. Pergunta que cita um
conector (ex: "CEP", "hospedagem") → executa só ele. Voto majoritário de
3 tentativas; se a seleção falhar ou for ambígua, executa todos os
conectores da área (comportamento seguro — nunca deixa o agente sem
dados). A tela Atualizações mostra o modelo de roteamento e as áreas
configuradas (card "Configuração de ambiente").

**Extração de parâmetros por IA:** além do reconhecimento automático de
padrões (códigos como `C001`, `id_cliente=58`, e-mails, datas), a IA
também extrai os parâmetros da pergunta em linguagem natural (ex:
"id cliente igual a 58" → `customer_id='58'`). Vale para **todos os tipos
de conector** (API — URL/headers/body, MCP — args, SQL — WHERE), que
usam o mesmo mecanismo de placeholders `{param}`.

**Anti-alucinação:** quando os conectores retornam sem dados vivos, o
agente é instruído a NÃO inventar valores (datas, nomes, números, IDs) —
responde "não encontrei" e sugere reformular a pergunta (ex: informar
`id_cliente=58`).

**Formato da resposta (objetividade):** todo agente recebe no prompt a diretiva
de formato — responder direto o que foi perguntado, **sem repetir o mesmo número
em texto e em tabela**, sem recapitular os dados recebidos e sem narrar o
raciocínio. Medido contra o modelo principal da prod: **~2,2x mais rápido** com
o mesmo conteúdo (5.668 ms → 2.590 ms), porque a espera longa era o modelo
"pensando em voz alta" (4.471 tokens gerados para 121 caracteres de resposta).
**Pedido explícito de texto longo continua sendo atendido** ("conte uma história
de 1000 palavras", "relatório completo") — a objetividade vale para o padrão.
Detalhe importante para quem escreve skills: a diretiva entra **antes** do bloco
de SKILLS, então uma **skill do cliente com regra de formato própria tem
precedência** sobre ela.

**Importante:** os conectores do agente são herdados automaticamente da
**área** dele (não há mais checkboxes de ERP/CRM/RH no formulário).
**Modelo secundário (fallback):** o campo `modelo_secundario_id` define o modelo
usado quando o principal falha ou está indisponível. Sem ele, o agente responde
apenas com o modelo principal e devolve o erro quando ele não responde.

**Workers (mestre + workers):** dentro da tela do agente existe o card **Workers** —
é ali que a orquestração é montada. O agente que tem workers é o **mestre** (quem
consolida e responde ao usuário) e cada linha da lista é um **worker** (folha: só
consulta e devolve dados). A lista mostra **somente os workers deste mestre**, com
`↑` `↓` (ordem de execução), **editar** e **excluir** por linha; `➕ Cadastrar
worker` cria o agente **já vinculado** (Nome, Área) sem sair da tela — **o worker
não escolhe modelo: ele herda o modelo do mestre**. O
cadastro de agente **não** tem campo de workers: worker se cria dentro do mestre
(não há como vincular um agente existente nem transformar outra pessoa em worker).
Ao clicar em `↑`/`↓` a tela **não sobe para o topo**: ela volta para o card, na
mesma posição (a ordem reordenada é o próprio retorno visual — não há aviso
vermelho fora da vista).

- **Worker não aparece nas listas**: na tela **Agentes** (um aviso conta quantos
  estão ocultos e lembra que eles se cadastram no card do mestre) e no
  **Workspace** (onde só o mestre tem card — ele é quem responde ao usuário; o
  card mostra `🧩 mestre de N worker(s): nome, nome`). O botão **fluxo** desenha a
  cadeia na ordem gravada.

- **O que o worker faz:** roda **somente os conectores da área dele** (sem RAG,
  sem LLM final, sem memória e sem rastreio próprios) e devolve o **bloco de
  dados** — `[WORKER 1: Agente Vendas (vendas) | consulta]`. O mestre recebe
  todos os blocos rotulados e faz **uma** consolidação final. Os workers rodam
  **em paralelo** (até 3 ao mesmo tempo). O modelo usado por eles (inclusive na
  leitura e na consulta inteligente de cada um) é o **do mestre**: na tela do
  worker o campo de modelo aparece como *herda do mestre* (sem select), e salvar
  a tela do worker não altera modelo nem fallback.
- **Skill do worker (própria):** o agente **sozinho** não muda em nada — a skill
  dele é a que responde ao usuário. No mestre+workers, o **worker usa a skill
  DELE** para **organizar o dado da área** antes de entregar: o worker lê o
  resultado bruto dos conectores dele e devolve uma leitura organizada
  (`[WORKER 1: … | Agente Vendas · skill (worker)]`), e o **mestre responde com a
  skill dele**. O dado **bruto continua indo junto** (auditoria e honestidade: se
  a leitura divergir, vale o bruto). **Worker sem skill** devolve só o dado da
  área — comportamento igual ao de antes, sem chamada extra. Custo de um worker
  com skill: **+1 chamada de LLM** (com retry automático quando o modelo devolve
  vazio ou o servidor está ocupado). As leituras rodam **depois que todos os
  workers terminaram os conectores** e **uma por vez** — leitura sobreposta à
  geração de SQL de outro worker fazia o servidor de IA de um slot devolver
  **HTTP 500** e o worker entregava sem leitura (traces #357/#359). No Rastreio, o
  bloco de leitura aparece com o texto organizado e a skill usada; falha da
  leitura aparece como ERRO com o motivo, e o dado bruto continua indo para o
  mestre.
- **Latência e custo:** o tempo é o do **worker mais lento** + a consolidação
  (não é a soma), e cada worker gasta **1 consulta inteligente** (text-to-SQL). O
  limite de 3 simultâneos existe porque o gargalo real é o modelo de IA e as
  conexões do banco do cliente.
- **Ordem:** a numeração é a ordem em que o mestre recebe os blocos (e a ordem no
  Rastreio), não a ordem de conclusão — `↑`/`↓` é que mandam.
- **Editar um worker:** abre a tela do próprio agente, com o aviso **"este agente
  é worker de \<mestre\>"** e um botão **← voltar ao mestre** no lugar do
  "Cancelar" — e **salvar também volta para o mestre**, no ponto do card (antes
  caía na lista de Agentes, longe da cadeia). A tela do worker **não** tem card
  Workers (worker é folha; worker não pode ter workers — a recusa também vale no
  servidor, mesmo por chamada direta).
- **Excluir um worker:** tira da lista **e apaga o agente** (worker só existe
  dentro do mestre). Pela listagem de Agentes a exclusão de um worker em uso é
  recusada — o caminho é o card do mestre.
- **Excluir o mestre:** leva os workers junto (o `confirm` nomeia quais). Assim
  ninguém fica órfão: um worker solto continuaria respondendo sem que se soubesse
  de quem ele era.
- **Recusa no cadastro de worker:** sem nome ou sem modelo, nada é criado; acima
  de 10 workers o cadastro é recusado.
- **Avisos (não bloqueiam):** worker **pausado** ou **sem conector na área** volta
  sem dados (o mestre diz isso, não inventa — e a própria linha mostra
  "sem conector"); **dois workers na mesma área** consultam os mesmos conectores;
  e se a **área do mestre** tem conector ativo, o mestre também executa esses
  conectores — para um mestre que só despacha, use uma área sem conectores (ex.:
  `operacoes`).
- **Voz:** **não** use workers em agente que atende telefonia/voz — a cadeia
  acrescenta segundos e a voz exige resposta abaixo de 1s. Regra de operação,
  avisada na própria tela (a plataforma não marca "agente de voz").
- **Ordem sob controle, com a tela no lugar**: `↑`/`↓` por linha mudam a ordem de
  execução sem jogar a página para o topo (o card fica na mesma posição).

Rotas da orquestração (todas `POST` com o token da sessão, admin):
`/portal/agentes/<id>/workers/novo`, `/portal/agentes/<id>/workers/<wid>/subir`,
`/portal/agentes/<id>/workers/<wid>/descer` e
`/portal/agentes/<id>/workers/<wid>/excluir`.
