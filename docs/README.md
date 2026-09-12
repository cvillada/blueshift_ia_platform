# Como escrever e manter a documentação do CL Agents

Esta pasta é a **fonte única** da documentação do produto. O portal (menu **Docs**)
e o popup **Ajuda** (que responde com IA) leem estes arquivos — não existe uma
segunda cópia para atualizar.

## Regra de ouro

> Toda alteração no produto é feita **no mesmo commit** que a documentação dela:
> código + página da doc + linha na tabela de campos + bloco na API (se criou rota)
> + registro no changelog. O `tools/doc_check.py` barra o esquecimento.

## Estrutura

- Arquivos `NN-nome.md` — o `NN` define a ordem de leitura (00, 01, 02…).
  A seção 5 (telas do portal) é `04-00-telas-do-portal.md` (índice) + `04-NN-tela.md`
  (uma tela por arquivo).
- Arquivos que começam com `_` e este `README.md` **não** entram na renderização
  (`_TEMPLATE.md`, `_mapa_apelidos.json`, `_pendentes.json`).
- `_TEMPLATE.md` — copie para criar uma página nova.
- `_mapa_apelidos.json` — liga o **nome técnico** do campo ao **rótulo da tela**
  (usado pela checagem automática).
- `_pendentes.json` — dívida conhecida da checagem (itens do código que ainda não
  estão documentados).

## Como documentar os casos mais comuns

| Você mudou… | Onde escrever |
|:------------|:--------------|
| Uma tela / um campo na tela | a página da tela (`04-NN-...md`): tabela de campos + passo a passo |
| Um comportamento do agente, RAG ou roteamento | `07-fluxo-do-agente-e-rag.md` (e `04-08-modelos-ia.md` se for o roteador) |
| Um conector (novo tipo, campo, exemplo) | `04-09-conectores.md` (+ `06-conectores.md` se mudar o funcionamento) |
| Uma rota de API / integração | `05-api-de-canal.md` (API de canal) e `04-23-gateway.md` (gateway OpenAI) |
| Uma variável de ambiente | `02-como-executar.md` (tabela de variáveis) |
| Uma tabela/coluna do banco | `09-banco-de-dados.md` |
| Uma tela nova | crie `04-NN-nome.md` a partir do `_TEMPLATE.md` e linke no índice `04-00-telas-do-portal.md` |
| Correção relevante ao usuário | `11-perguntas-frequentes.md` |

## Checagem automática (`tools/doc_check.py`)

```bash
python tools/doc_check.py            # falha se aparecer item NOVO sem documentação
python tools/doc_check.py --lista    # lista a dívida conhecida
python tools/doc_check.py --baseline # regrava _pendentes.json (use com consciência)
```

O que ele confere no código e procura na doc: **rotas** do portal, **campos** de
formulário, **variáveis de ambiente** (`BLUESHIFT_*`/`GATEWAY_*`) e **tabelas** do
banco. Um campo conta como documentado se aparecer pelo nome técnico **ou** pelo
rótulo cadastrado em `_mapa_apelidos.json`.

Interpretação: é um **alarme**, não uma prova. Ele garante que nada *novo* entre
sem documentação; a qualidade do texto continua sendo trabalho de quem escreve.
Quando `--lista` mostrar algo que passou a ser documentado, remova o item de
`_pendentes.json` para a dívida não crescer (a checagem já ignora o que está na doc).

## Convenções de escrita

- Rótulos **exatos** da interface (`Endpoint (base_url)`, `SSL mode`) — é o que o
  usuário vê e o que o operador procura.
- Toda configuração termina com um **exemplo pronto** (copiar e colar).
- Exemplos **fictícios** (`XPTO Seguros (Piloto)`) — nunca dado real de cliente.
- Nada de fornecedor/ferramenta de terceiro como recomendação nominal em material
  do cliente; cite o padrão (`API REST`, `MCP`, `OpenAI-compatível`).
- Pitfalls sempre com sintoma → causa → o que fazer.
- Páginas internas (rotas de admin, detalhes de licença/segurança) começam com
  `<!-- interno -->` — serão excluídas do site público.
