### 5.8 Modelos IA (/portal/modelos) — cadastro de LLMs (locais e externos)

**Propósito:** cadastro dos modelos de IA (endpoints **OpenAI-compatíveis**)
que os agentes usam para responder — servidores **locais** (LM Studio,
vLLM, servidor do cliente) ou **externos** (OpenRouter, DeepSeek, OpenAI).
A plataforma é **agnóstica a provedor**: qualquer endpoint que fale o
protocolo OpenAI entra aqui.

**Como cadastrar um modelo de IA (resumo):** em Cadastros → Modelos IA →
"+ Novo modelo", preencha Nome, Endpoint (base_url), Modelo, Tipo e — se
externo — a API Key, e salve. O badge de status indica se o endpoint
respondeu (online) ou não (offline). Detalhe de cada campo abaixo.

**O que preencher em cada campo (passo a passo):**

| Campo | Obrigatório? | O que é | Exemplo |
|:------|:-----------:|:--------|:--------|
| Cliente | ✅ | Empresa dona do modelo (primeira já vem selecionada) | XPTO Seguros (Piloto) |
| Nome | ✅ | Nome de exibição — como aparece nas telas e no `BLUESHIFT_ROUTER_MODEL` | `bonsai-8b` |
| Endpoint (base_url) | ✅ | A **base** do servidor do modelo — o sistema acrescenta `/v1/chat/completions` na chamada e `/v1/models` no teste de status. ⚠️ NÃO colocar o `/chat/completions` no final (ver regra de ouro abaixo) | `http://127.0.0.1:1234` |
| Modelo | ✅ | O NOME exato do modelo dentro do servidor (o que o provedor documenta) | `bonsai-8b` ou `qwen/qwen3.7-flash` |
| Tipo | ✅ | `local` = servidor interno (sem chave) · `hibrido` = externo na nuvem (com chave) | `local` / `hibrido` |
| Modo da API | ✅ | `openai_chat` (padrão — o sistema acrescenta `/v1/chat/completions`) · `responses` (OpenAI Responses: posta **direto** na base_url cadastrada — para agentes externos como Oracle AIDP `/chat`) | `openai_chat` |
| API Key | ❌ | Chave de autenticação — **obrigatória para externo** (OpenRouter/DeepSeek/OpenAI); deixe VAZIA para local | `sk-or-v1-...` |
| Max tokens | ❌ | Limite máximo de tokens da resposta (padrão 4096) | `4096` |
| Temperatura | ❌ | Criatividade da resposta (0.0 = determinístico, 1.0 = criativo; padrão 0.3). O roteador de conectores e o extrator de parâmetros usam 0.0 sempre | `0.3` |
| Preço input (R$/1M tokens) | ❌ | Custo de entrada — alimenta o Cost Intelligence | `0.15` |
| Preço output (R$/1M tokens) | ❌ | Custo de saída — alimenta o Cost Intelligence | `0.60` |

**Exemplo 1 — modelo LOCAL (LM Studio no servidor do cliente):**

| Campo | Valor |
|:------|:------|
| Nome | `bonsai-8b` |
| Endpoint (base_url) | `http://127.0.0.1:1234` |
| Modelo | `bonsai-8b` |
| Tipo | `local` |
| API Key | (vazio) |

**Exemplo 2 — modelo EXTERNO (OpenRouter na nuvem):**

| Campo | Valor |
|:------|:------|
| Nome | `qwen3.7-flash` |
| Endpoint (base_url) | `https://openrouter.ai/api` |
| Modelo | `qwen/qwen3.7-flash` |
| Tipo | `hibrido` |
| API Key | `sk-or-v1-...` (a chave do OpenRouter) |

**Para que servem os modelos cadastrados:**
- Cada **Agente** escolhe o modelo via `modelo_id` (tela Montar/Editar
  agente) — pode mesclar local e externo entre agentes;
- **Roteamento** (`BLUESHIFT_ROUTER_MODEL`) — ver o bloco abaixo;
- **Ajuda IA** e **geração de skills** usam o modelo selecionado.

#### Modelo de roteamento (`BLUESHIFT_ROUTER_MODEL`) — o que ele faz e qual usar

A plataforma tem uma etapa de **roteamento** antes de chamar o modelo que
escreve a resposta. Configure um modelo **dedicado, pequeno e rápido** para
ela — de preferência local. Sem essa variável, o roteamento cai no **modelo
principal de cada agente**, o que encarece e atrasa TODA pergunta.

**As quatro tarefas que usam esse modelo** (é o mesmo modelo nas quatro):

| # | Tarefa | Onde | Tipo de saída | Peso |
|:-:|:-------|:-----|:--------------|:-----|
| 1 | **Escolher os conectores** relevantes da área (ou nenhum) | `agente.py` (`_selecionar_conectores`) — voto majoritário de 3 tentativas | um número | classificação, 1 token |
| 2 | **Extrair os parâmetros** da pergunta (`{id_cliente}`, `{email}`, `{data}`…) | `agente.py` (`_extrair_parametros_ia`) | JSON minúsculo | extração |
| 3 | **Montar o spec do gráfico** (tipo, título, dados) | `agente.py` (`_especificar_grafico`) | JSON pequeno (≤20 pontos) | geração curta |
| 4 | **Gerar o SELECT da Consulta inteligente** (text-to-SQL sobre o schema real) | `connector_pack/registry.py` (`_gerar_sql_ia`) | SQL, ~300 tokens | **geração de verdade** |

**Perfil obrigatório do modelo de roteamento — pequeno, inteligente e rápido:**
> O roteador precisa ser **pequeno** (cabe no servidor do cliente, sem GPU dedicada),
> **inteligente** (entende a pergunta e acerta escolher — ou não escolher — o
> conector certo, mesmo com sinônimos) e **rápido** (a latência dele é a latência
> de TODA pergunta). Se faltar qualquer um dos três, o roteamento vira gargalo.

- **Pequeno** — roda em quase toda pergunta, no mesmo servidor da plataforma, sem exigir GPU dedicada (4B–8B quantizado já é "pequeno" para esse papel; 0,5B é o piso);
- **Inteligente** — entende a pergunta e acerta **escolher, não escolher, ou escolher mais de um** conector, inclusive com sinônimos ("faturamento" → conector de vendas). É aqui que o 0,5B tropeça; 3B–8B instruct acerta bem;
- **Rápido** — a latência do roteador é a latência de TODA pergunta. Referência: ~0,3–0,5 s por voto no 4B em GPU;
- **INSTRUCT, nunca reasoning** — modelo de raciocínio gasta os tokens "pensando" e, com o limite cortado, devolve **vazio**; o roteador então repete a chamada (256→512) e a conta explode: medimos **16 s de 17 s** de uma resposta só por causa disso (modelo 9B reasoning);
- **Temperatura 0 / determinístico** — a plataforma já chama com temperatura 0.0; o prompt pede resposta curta e objetiva;
- **Contexto modesto basta** (o prompt é a pergunta + uma lista curta de conectores), mas para a **tarefa 4** (SQL) o modelo precisa ter alguma competência de geração — um 0,5B dá conta de 1–3, **não** da 4. Se o roteador for muito pequeno, a Consulta inteligente tende a falhar (e o agente cai no comportamento seguro de responder sem o dado).

> Regra prática de escolha: **menor modelo que ainda acerta a seleção**. Comece
> com 3B–4B instruct; suba para 8B (`hermes-3-llama-3.1-8b`) se o entendimento
> ficar fraco; só desça para 0,5B em instalação muito modesta, ciente de que a
> Consulta inteligente (tarefa 4) pode falhar.

**Validado em produção:** `qwen3-4b-instruct-2507` em LM Studio (aprox. 2,6 GB,
Q4) — resultado medido: pergunta simples **1,6 s** no total (era 6–17 s) e
pergunta com conector **3,4 s** (era 22,5 s); os votos do roteador caem para
~0,3–0,5 s.

**Outros modelos que atendem** (todos INSTRUCT, temperatura 0):
- `hermes-3-llama-3.1-8b` — 8B instruct, já usado como referência da plataforma;
  excelente em seguir formato/JSON. Roda bem quando o servidor tem GPU (você já
  tem 2× RTX 5070 Ti): é mais "inteligente" no entendimento, um pouco mais lento
  que o 4B no primeiro token;
- `Qwen2.5-3B-Instruct` — meio-termo entre tamanho e acerto;
- `Qwen3-4B` **com o "pensamento" desligado** (`/no_think`) — mesma família, mas
  obrigatoriamente sem reasoning;
- `Qwen2.5-0.5B-Instruct` — para instalações muito modestas (CPU fraca), aceitando
  as limitações: pode errar o caso "nenhum", escorregar no formato e não dá conta
  do text-to-SQL (tarefa 4).

**O que NÃO usar como roteador:** modelo de resposta do agente (grande/ reasoning),
modelo de 7B+ reasoning e qualquer coisa com "thinking" ligado por padrão.

**Como configurar:**
1. Cadastre o modelo na tela **Modelos IA** (ex.: `qwen3-4b-instruct-2507`, endpoint do LM Studio/vLLM, tipo **local**);
2. Na instalação, defina `BLUESHIFT_ROUTER_MODEL` com o **ID ou o NOME** desse modelo (o nome é o que aparece na tela Modelos IA);
3. Confira em **Atualizações → Configuração de ambiente** qual modelo de roteamento está em uso (mostra o nome e o ID);
4. Se deixar vazio, o roteamento usa o modelo principal do agente — funciona, mas não é o recomendado.

**Pitfalls operacionais (aprendidos em produção):**
- **LM Studio é aplicativo com interface** — se o servidor reiniciar e o LM Studio não subir, o roteamento volta para o modelo principal **sem erro visível** (o sintoma é só lentidão). Em cliente/produção, hospede o modelo de roteamento como **serviço** (llama-server via systemd) ou garanta o autostart;
- **Nunca use o modelo grande/resposta como roteador** — além do custo, é onde o reasoning cortado gera respostas vazias e o famoso retry;
- Se o roteamento **falhar ou for ambíguo, a plataforma executa todos os conectores da área** (comportamento seguro — o agente nunca fica sem dados);
- Catálogo de conectores grande aumenta o prompt do roteamento: mantenha **descrições curtas e distintas** por conector (é a descrição que o roteador lê).

**Dica:** no Docker, `127.0.0.1`/`localhost` é traduzido automaticamente para
`host.docker.internal` (o modelo roda no HOST, fora do container).

**Regra de ouro da `base_url`:** cadastre apenas a BASE — **sem** o
`/v1` e **sem** o `/chat/completions` no final. O sistema monta sozinho:

- Chamada: `{base}/v1/chat/completions`
- Teste de status: `{base}/v1/models`

Exemplos corretos por provedor:

| Provedor | base_url correta |
|:---------|:-----------------|
| OpenRouter | `https://openrouter.ai/api` |
| DeepSeek | `https://api.deepseek.com` |
| OpenAI | `https://api.openai.com` |
| LM Studio / vLLM local | `http://127.0.0.1:1234` |

⚠️ Se a URL for cadastrada com o endpoint completo (ex:
`https://openrouter.ai/api/v1/chat/completions`), o teste de status monta
`.../chat/completions/v1/models` → 404 e o modelo aparece **offline** —
mesmo com o nome e a chave corretos. Nesse caso, edite o modelo e remova
o `/v1/chat/completions` do final.

**Status online/offline:** o badge na lista testa `{base}/v1/models` a
cada carregamento. Offline geralmente significa: (a) URL errada (regra de
ouro acima); (b) servidor local desligado; (c) chave inválida ou sem
acesso ao provedor externo.

**Perguntas frequentes (FAQ):**

- **O que devo preencher no cadastro de modelos de IA?** Nome (exibição),
  Endpoint (a base do servidor, sem `/chat/completions`), Modelo (nome
  exato no provedor), Tipo (local ou híbrido) e, para externo, a API Key.
  O resto é opcional (max tokens, preços).
- **Preciso de chave de API para modelo local?** Não — local (LM Studio,
  vLLM, servidor do cliente) roda sem chave; a chave é obrigatória só
  para modelos externos (OpenRouter, DeepSeek, OpenAI).
- **Onde acho o nome exato do modelo?** Na documentação do provedor
  (ex: `qwen/qwen3.7-flash` no OpenRouter) ou na lista do servidor local.
- **Por que o modelo aparece offline?** URL errada (regra de ouro),
  servidor local desligado, ou chave inválida/sem acesso. O teste de
  status usa `{base}/v1/models`.
