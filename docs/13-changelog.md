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

**v0.11.11 (2026-10-03) — Mestre + Workers: um agente orquestra vários agentes**

### Novo
- **Agente mestre com workers**: na tela do agente, o card **Workers** monta a
  orquestração — a lista mostra os workers do mestre, com **↑ ↓** (ordem de
  execução), **editar** e **excluir** por linha, e **➕ Cadastrar worker** cria o
  agente já vinculado (Nome, Área, Modelo) sem sair da tela. Cada worker roda
  **só os conectores da área dele** e devolve dados; o mestre recebe os blocos
  rotulados (`[WORKER 1: Agente Vendas (vendas) | consulta.tool]`) e consolida a
  resposta final. Sem workers, o comportamento é exatamente o de antes.
- **Execução em paralelo** (até 3 simultâneos): o tempo do mestre é o do worker
  mais lento + a consolidação, e não a soma dos workers. Sem workers no caminho,
  o custo por chamada é o mesmo de sempre.
- **Custo visível**: as chamadas de **consulta inteligente** (text-to-SQL) —
  que antes não apareciam em relatório nenhum — passam a ser contabilizadas em
  Uso de Tokens com a origem **`sql`**, **na chamada do mestre** (inclui as
  consultas feitas por cada worker, que não têm relatório próprio).
- **Lista de Agentes e Workspace** mostram só o **mestre** (com a etiqueta
  **🧩 mestre de N workers** e os nomes dos workers no card); worker não tem linha
  na tela de Agentes nem card no Workspace — os avisos lembram onde eles se
  cadastram. `↑`/`↓` no card Workers mudam a ordem **sem** jogar a tela para o
  topo; editar um worker e desistir (ou salvar) **volta para o mestre**, no ponto
  do card.
- **Worker não escolhe modelo**: ele **herda o modelo do mestre** (inclusive na
  consulta inteligente de cada worker). O cadastro de worker no card do mestre
  pede só **Nome** e **Área**, e na tela do worker o campo de modelo aparece como
  *herda do mestre* — antes havia um select ali que a cadeia ignorava
  (configuração morta na tela).
- **Skill própria do worker:** o agente sozinho continua igual (a skill dele
  responde ao usuário). No mestre+workers o worker usa a **skill dele** para
  organizar o dado da área antes de entregar, e o mestre responde com a skill
  dele; o dado bruto segue junto e o Rastreio mostra os dois. O cadastro de worker
  no card do mestre passou a ter **Skill do worker (opcional)** — worker sem skill
  devolve só o dado, como antes (+0 chamada de LLM). Com skill: **+1 chamada de
  LLM** por worker, com retry automático (teto maior + espera) quando o modelo
  devolve vazio ou o servidor está ocupado. As leituras rodam na **fase 2** —
  depois que **todos** os workers terminaram os conectores e **uma por vez**: foi
  essa sobreposição (leitura de um worker x geração de SQL do outro) que devolvia
  **HTTP 500** num servidor de IA de um slot e deixava o worker sem leitura
  (traces #357/#359). O dado bruto continua indo em paralelo.
- **Rastreio — conectores:** a linha de cada conector contava registros por
  `resultado.length`; quando o retorno é **objeto** (conector de API e o bloco de
  leitura do worker) o JavaScript mostrava **`undefined registros`**. Agora
  `bsConector()` (JS global) mostra registros para lista, **campos** para objeto,
  o texto da **leitura organizada pela skill** e o motivo no caso de erro.
- **Rastreio — valor do parâmetro ligado:** o SQL executado aparece com o
  marcador (`WHERE r.customer_id = %s`) porque, desde a v0.11.9, o valor do
  `{id_cliente}` viaja como **parâmetro do driver** e nunca é escrito no texto do
  SQL (é o que fecha a injeção). Faltava mostrar o valor: agora a linha do
  conector traz também **`valores ligados (vão como PARÂMETRO do driver, FORA do
  texto do SQL): ["22"]`**, ao lado do SQL — dá para conferir o filtro sem
  adivinhar (dúvida levantada no Rastreio #364).
- **Prompt — bloco de dados legível:** o bloco ia para o modelo como dump Python
  (`args=[...] -> [{'sql': ...}]`). Medido: o modelo **recitava o SQL** na resposta
  e o worker com skill **ecoava** o bloco em vez de organizar. Agora o bloco é
  texto legível (`1 linha(s): coluna=valor`), com o SQL **fora** do prompt (o
  Rastreio continua guardando o SQL gerado).
- **Prompt do text-to-SQL — critério explícito:** o prompt de geração ganhou três
  regras, todas vindas de Rastreio real (`#368`, `#369`, `#370` e o E2E do
  cliente 22): (1) **`LIMIT`/`TOP` nunca sem `ORDER BY`** e nunca com direção
  implícita — "maior/mais recente/último/top" pede `DESC`, "menor/mais
  antigo/primeiro" pede `ASC` (o `#369` saiu `ORDER BY r.rental_date` sem
  direção, o MySQL resolveu como `ASC` e devolveu o mais **antigo**); (2) a
  **coluna do critério** e as **colunas do filtro** têm de vir **no `SELECT`**
  (`SELECT c.customer_id, f.title, r.rental_date …`) para o resultado provar a
  ordem e a quem o dado pertence; (3) **contagem sem join 1:N** — `COUNT(*)`
  com `GROUP BY`/`ORDER BY`, `COUNT(DISTINCT chave_do_evento)` quando o nome vem
  de outra tabela (medido: `JOIN film_actor` para contar aluguel devolvia o
  número de **atores** — "DROP WATERFRONT = 8" em vez de 1, e 122 aluguéis em vez
  de 22). Empate no topo é reportado com a contagem; o modelo não escolhe um
  registro como se fosse o único.
- **Prompt do text-to-SQL — regras repetidas no pedido e topo com contagem:** as
  mesmas regras passaram a ser **repetidas na mensagem do usuário** (bloco
  `LEMBRETES`, colado na pergunta, antes do `SQL:`) — no E2E do cliente 22 o
  modelo seguiu a regra numa pergunta e ignorou na seguinte quando ela estava só
  no *system*. E o topo agora vem **com a contagem** (`LIMIT 5`) em vez de
  `LIMIT 1` quando a pergunta não pede uma linha só: o `LIMIT 1` cortava o
  empate e o modelo respondia "não é possível confirmar" sem mostrar os pares.
- **B3 — ordem e empate (fase da resposta):** o bloco de dados passou a trazer o
  **critério da consulta** em vez do texto do SQL — `(consulta: ordenado por
  rental_date (maior/mais recente primeiro); no máximo 1 linha(s))`, extraído da
  query executada (`registry._criterio_da_consulta`). Causa medida no E2E do
  cliente 22: o modelo de resposta **não via a consulta** (o SQL sai do prompt
  desde a v0.11.9, para não ser recitado), então recebia uma linha de uma
  consulta `ORDER BY … DESC LIMIT 1` e respondia com ressalva ("não veio
  classificada"). Com o critério, a diretiva `ORDEM E ATUALIDADE` **autoriza
  afirmar**: a primeira linha é o maior/mais recente — e continua proibindo
  afirmar quando o bloco não traz ordenação. No mesmo guard, **empate**: quando o
  topo vem com contagens iguais (ou contagem 1), a resposta diz o empate e nunca
  apresenta um registro como único vencedor (era o caso do "top 1" respondendo
  `BARBARELLA STREETCAR` num empate de 22 títulos com 1 locação cada).
- **Repetição quando o SQL gerado não existe no banco:** no E2E do cliente 22 a
  pergunta "filme mais alugado" falhou com `(1054, "Unknown column 'f.title'")` —
  o modelo escreveu `f.title` sem juntar `film`, e a resposta virava "não há dado"
  existindo dado. Agora, quando o erro é do **SQL gerado** (coluna/tabela
  inexistente, sintaxe — `registry._erro_sql_invalido`), a consulta inteligente
  repete **uma vez com o mesmo modelo**: escalar para o principal não funcionava
  aqui porque `BLUESHIFT_SQL_MODEL` e o modelo do agente apontavam para o mesmo
  alvo (a regra "não escalar para o mesmo modelo" barrava a segunda tentativa).
  Resultado **vazio** e **timeout** continuam fora da repetição. Nunca três
  chamadas: 1 tentativa + 1 repetição.

### Segurança / integridade
- Worker **não pode ter workers** (profundidade 1): a tela do worker não oferece o
  card e o servidor recusa, mesmo por chamada direta. Além disso, sem nome ou sem
  modelo o worker não é criado, e acima de 10 workers o cadastro é recusado.
- **Excluir o mestre leva os workers junto** (o `confirm` nomeia quais) — evita
  worker órfão respondendo sem se saber de quem ele era; pela listagem, excluir um
  worker em uso continua **recusado** (o caminho é o card do mestre).
- Toda ação da orquestração (cadastrar, subir, descer, excluir) é **POST com o
  token da sessão** e entra na auditoria.
- A lista de workers é **avisada** quando: o worker está pausado ou sem conector
  na área (a linha mostra "sem conector"), dois workers estão na mesma área
  (consulta repetida) ou a área do mestre tem conector ativo (o mestre também
  consulta).

### Correções
- **Consulta inteligente (text-to-SQL)**: quando o modelo devolvia **duas
  consultas coladas** (separadas por linha em branco em vez de `;`), o texto ia
  inteiro como uma só consulta e o banco recusava com erro de sintaxe — perdendo
  também a consulta que estava correta. Agora as consultas coladas são separadas
  (linha em branco ou logo após um `LIMIT`), validadas e executadas uma a uma.
- **Rastreio**: quando a consulta inteligente falha, o bloco passa a mostrar o
  **SQL que o modelo gerou** — antes só havia a mensagem do banco, e não dava
  para saber o que o modelo escreveu sem reproduzir a chamada.
- **Honestidade da resposta (ordem)**: o agente não afirma mais "o mais recente",
  "o último" ou "o maior" quando os dados recebidos não vieram ordenados
  (consulta sem `ORDER BY`) — nesse caso apresenta os itens sem o qualificador e
  diz que a consulta não trouxe essa ordenação.
- **JavaScript do portal**: uma linha inválida no script global (uma palavra do
  Python que entrou no JS) fazia o navegador **descartar o script inteiro** — menu,
  popup e botões paravam de responder sem erro visível na página. Corrigido, e
  agora existe checagem automática: `python tools/js_check.py` percorre as telas,
  valida cada `<script>` com `node --check` e confere se todo handler inline
  (`onclick`/`onsubmit`…) chama função que existe.

### Operação
- **Voz**: não usar workers em agente de telefonia/voz (a cadeia acrescenta
  segundos; a voz exige resposta abaixo de 1s). Regra de operação, avisada na
  própria tela.
- **Banco**: `PRAGMA busy_timeout` explícito no acesso ao `portal.db` (vários
  conectores gravando heartbeat em paralelo).

**v0.11.10 (2026-09-30) — ação destrutiva exige POST; campo inválido não derruba a tela**

### Segurança
- **Ações destrutivas saíram do `GET`** (13 rotas): excluir, suspender, revogar,
  regenerar chave, pausar/ativar e alternar conector agora são formulários `POST`
  com o token da sessão; `GET` nelas responde `405`. Link `GET` que muda estado é
  CSRF de verdade — o navegador prefetcha, um scanner de e-mail segue o link e o
  clique acidental executa a ação (foi assim que uma varredura de rotas suspendeu
  o próprio admin durante os testes).
- Os botões mantêm a aparência de link e a confirmação antes de executar; agora
  o nome do recurso aparece na confirmação (inclusive "nova chave", que avisa que
  a chave atual para de funcionar na hora).

### Robustez
- **Campo de formulário não numérico não gera mais erro interno:** o
  `int(request.form.get(...))` cru estourava `ValueError` → `500` em
  `/portal/usuarios/novo`, `/portal/modelos` e `/portal/agentes/novo` (provado
  antes e depois da correção). Agora o valor inválido cai no default, como já
  acontecia com parâmetro de URL.
- Correção de registro: a nota publicada da v0.11.9 anunciava essa correção por
  engano — o caminho de URL/GET já se comportava assim antes dela.

**v0.11.9 (2026-09-30) — segurança e robustez: o que a varredura encontrou**

Depois de o repositório virar público, o produto passou por uma varredura
funcional e de segurança de ponta a ponta. Esta versão entrega as correções.

**Segurança**
- **Injeção SQL no conector de banco (crítico):** a consulta passou a usar
  **binding de parâmetro** — o valor vindo da pergunta nunca é escrito dentro do
  SQL. Antes, `ano=1;DROP/**/TABLE/**/x;--` **apagava tabela** a partir da tela
  do agente (reproduzido em teste), e `UNION SELECT` lia catálogo e arquivos do
  servidor. Junto: a conexão roda em **sessão somente-leitura** e há **denylist**
  de funções perigosas;
- **RBAC nas telas:** cadastros e configuração (Clientes, Usuários, Áreas,
  Modelos IA, Skills, Agentes, Conectores, Canais, Gateway, Auditoria, LGPD, SSO,
  Atualizações, Teste A/B, Fine-tuning, Uso de tokens, Arquivo morto,
  Observabilidade, Alertas) exigem papel **admin**. Antes, um usuário comum
  conseguia **ler** essas telas. O **menu sai da mesma lista da rota** — o que
  aparece é o que pode ser aberto;
- **Rate limit de login:** conta apenas tentativa **falha**, e a tentativa
  bloqueada **não é processada**. Antes o aviso não interrompia: com a senha
  correta o login passava mesmo com o limite estourado. Entrar e sair várias
  vezes não bloqueia mais ninguém;
- **XSS em `onclick`:** nome de recurso com aspas não fecha mais a string do
  JavaScript (novo `templates.j()`, escape específico para string JS);
- **Segredo de sessão:** o instalador gera o segredo; o valor de exemplo saiu do
  compose (é público no repositório) e, sem a variável, o portal **gera e
  guarda** o segredo em `.portal_secret` (permissão 0600, dentro do volume) em
  vez de sortear um por processo — a sessão sobrevive ao restart e não oscila;
- **Query fixa do conector validada ao salvar** (uma instrução, começando em
  `SELECT`/`WITH`): configurar `DROP` na tela deixa de ser possível.

**Robustez**
- Resposta do provedor **sem `choices`** deixa de vazar o erro cru (`'choices'`)
  como HTTP 502 na tela — vem mensagem explicando o que o provedor devolveu;
- **URL base terminando em `/v1`** é normalizada (fim do `/v1/v1/chat/completions`);
- **Gateway OpenAI-compatible** autentica **antes** de validar o corpo (quem não
  tem token recebe 401, e não 400/404);
- **Erro interno** agora tem resposta apresentável: página em português no
  portal e JSON nas rotas de API — o traceback fica no log do container;
- **Resposta sobre dado vazio não inventa número:** quando o conector roda e
  volta sem valores (`{"sum": null}`, lista vazia), o resultado é marcado como
  *sem dados* no prompt e o agente responde que não há esse dado, em vez de
  completar por conta própria. Medido com o mesmo modelo: sem a correção, a
  pergunta *"quanto vendemos no total, em reais?"* sobre um resultado nulo
  devolveu **"1.380.000 reais"** (número inexistente); com a correção, as quatro
  execuções responderam que não há dado disponível.

**Risco residual conhecido (documentado):** as ações destrutivas do portal
(excluir, suspender, regenerar) ainda são disparadas por link `GET`. O
`SameSite=Lax` do cookie já bloqueia o vetor silencioso; o ajuste para
`POST` + token de formulário está previsto para a próxima versão.

**v0.11.8 (2026-09-29) — resposta objetiva: menos espera, mesmo conteúdo**
- **diretiva de formato no prompt do agente**: a medição na prod mostrou que a
  espera longa **não vinha do tamanho da resposta**, e sim do modelo
  **recapitulando os dados e narrando o raciocínio** — 4.471 tokens gerados
  para **121 caracteres** de resposta (41,8 s). A plataforma passa a instruir o
  formato padrão: responder direto o que foi perguntado, sem repetir o mesmo
  número em texto **e** em tabela, sem recapitular os dados recebidos e sem
  explicar o raciocínio;
- **~2,2x mais rápido no padrão** (medido contra o modelo principal da prod,
  mesmas perguntas e mesmos dados): 5.668 ms → 2.590 ms (*"top 5 produtos"*),
  4.965 ms → 2.283 ms (*"status do servidor"*) e 7.061 ms → 2.577 ms no caso
  que mais rampeava;
- **pedido explícito de texto longo continua atendido — e melhor**: sem a
  cláusula de exceção o modelo **se recusava** a escrever a "história de 1000
  palavras" (1.021 caracteres); com ela entrega 4.793;
- **`max_tokens` não foi tocado**: o teto **não é o instrumento** — medido,
  8.132 e 1.500 geram o **mesmo texto** (tokens e tempo idênticos), e baixá-lo
  só arriscaria **cortar** a resposta (resposta cortada chega **vazia** ao
  usuário);
- **a regra de formato da skill do cliente continua ganhando**: a diretiva entra
  **antes** do bloco de SKILLS;
- nota de rastreio: as respostas **vazias** observadas na prod (7 de 400 traces)
  traziam o erro `not enough values to unpack` — **o mesmo defeito corrigido na
  v0.11.7**. Nos traces com **ferramentas do cliente** (gateway), `content`
  vazio é o **contrato de tool-call**: o cliente recebe `tool_calls`, não texto.

**v0.11.7 (2026-09-29) — consulta inteligente: o SELECT não falha mais em silêncio (modelo do SQL + escalada)**
- **teto de saída do SELECT: 300 → 900 tokens** (1500 na escalada). Com 300 a
  consulta era cortada — e resposta cortada chega **vazia**, não truncada: o
  usuário via "não foi possível montar a consulta" sem nenhum sinal do motivo;
- **nova variável `BLUESHIFT_SQL_MODEL`** (ID ou nome; vazio = o mesmo modelo
  de roteamento, comportamento de sempre): a geração do SELECT passa a poder
  usar um modelo diferente das outras três tarefas do roteador;
- **escalada automática**: se o SELECT do modelo configurado **não rodar**
  (tipicamente coluna que não existe no schema — o erro mais comum do modelo
  pequeno) ou voltar vazio, a plataforma repete **uma única vez** com o
  **modelo principal do agente**. Medido com o SQL executado de verdade no
  banco: o pequeno acerta 6 de 8 perguntas (~0,6 s cada) e o principal acerta
  8 de 8 (~10,7 s) — a escalada mantém o caso comum rápido e só paga o modelo
  grande na falha. Não é cascata: no máximo duas tentativas por consulta;
- **Rastreio diz a verdade**: badge *"consulta montada pelo modelo de REFORÇO"*
  no popup e coluna `escalada_sql` no trace (dá para medir quantas consultas
  caem no reforço, por cliente);
- **correção adjacente**: `_selecionar_conectores` devolvia lista (em vez de
  tupla) quando a área não tinha conector ativo e o chamador estourava
  *"not enough values to unpack"* — o erro ia para o prompt como se fosse
  falha de conector, por um motivo que não era erro nenhum.

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
| v0.11.10 | 2026-09-30 | ações destrutivas exigem POST com token (13 rotas; GET responde 405) e campo de formulário inválido não gera mais 500 |
| v0.11.9 | 2026-09-30 | segurança: injeção SQL no conector fechada por binding de parâmetro (+ sessão somente-leitura + denylist + validação da query fixa ao salvar), RBAC nas telas de admin com menu na mesma fonte, rate limit de login conta só falha e interrompe, XSS em onclick (templates.j) e segredo de sessão gerado/persistido pelo portal; robustez: resposta sem `choices` sem vazar erro cru, base_url com /v1 normalizada, gateway autenticando antes do corpo e errorhandler 500 apresentável |
| v0.11.8 | 2026-09-29 | resposta objetiva: diretiva de formato no prompt do agente (~2,2x mais rápida, medido na prod); `max_tokens` mantido (teto é inerte) e pedido explícito de texto longo preservado |
| v0.11.7 | 2026-09-29 | consulta inteligente: teto do SELECT 300→900, modelo do SQL (`BLUESHIFT_SQL_MODEL`) e escalada ao modelo principal quando a execução falha; correção do `_selecionar_conectores` (lista em vez de tupla) |
| v0.11.6 | 2026-09-29 | skills sem falha silenciosa: uma skill por agente (radio, com "nenhuma"), corpo até 8.000 chars + `BLUESHIFT_SKILL_BODY_MAX`, skill em uso não pode ser excluída e skill que não resolve é reportada |
| v0.11.5 | 2026-09-27 | tool calling no gateway (ferramentas do cliente) |
| v0.11.4 | 2026-09-27 | atualização não deixa mais arquivos de dono `root` no repositório (container irmão roda como dono do repo) |
| v0.11.3 | 2026-09-27 | gateway: `/v1/models` autenticado + `stream` do cliente respeitado |
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
