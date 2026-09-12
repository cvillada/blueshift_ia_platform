## 7. Conectores — como funcionam

1. O usuário faz uma pergunta ao agente.
2. **Roteamento inteligente**: uma IA curta (a do agente, ou a de
   `BLUESHIFT_ROUTER_MODEL`) decide QUAIS conectores da área executar —
   ou nenhum (pergunta de norma/política responde só com a base RAG).
   Voto majoritário de 3 tentativas; falha/ambiguidade → executa todos
   (seguro). Detalhes na §5.6.
3. `_extrair_parametros()` extrai automaticamente: códigos (`C001`,
   `PED-99`), e-mails, datas, `chave=valor`, números após palavras-chave.
   A **IA complementa** o que o regex não reconheceu (linguagem natural:
   "id cliente igual a 58" → `{id_cliente} = 58`).
4. Os conectores escolhidos são executados (tolerante a falhas — um
   conector com erro não derruba os outros; heartbeat atualizado).
5. Placeholders `{param}` são substituídos pelos valores extraídos.
6. Resultados viram o contexto do prompt (FONTE PRIMÁRIA).
7. **Anti-alucinação**: se os conectores rodarem sem dados vivos, o
   agente é instruído a NÃO inventar valores — responde "não encontrei"
   e sugere reformular (ex: informar `id_cliente=58`).

Extração de parâmetros (exemplos):

| Pergunta | Parâmetros extraídos |
|:---------|:---------------------|
| `cliente id 3` | `{id_cliente} = 3` |
| `PED-99` | `{id_pedido} = PED-99` |
| `FUNC42` | `{id_func} = FUNC42` |
| `user@email.com` | `{email} = user@email.com` |
| `2026-07-22` | `{data} = 2026-07-22` |
| `rental_id=10437` | `{rental_id} = 10437` |
| `title='RACER EGG'` | `{title} = RACER EGG` |

Se nenhum parâmetro for encontrado, o placeholder fica literal (e o banco
retorna vazio — honesto, sem forçar valor padrão).

---
