### 5.25 Arquivo Morto (/portal/arquivo-morto) — snapshot + corte de dados

**Onde:** menu **Operação → Arquivo Morto** (somente **admin** — `admin_required`).

**Propósito:** controlar o crescimento do banco sem perder histórico: gera um
**snapshot selado** do banco (cópia íntegra) e remove do banco quente os
registros até a data de corte.

**Fluxo:**

1. Informe a **data de corte** (registros com `criado_em ≤ corte` serão
   arquivados). O máximo permitido é **ontem à meia-noite (D-1)** — o dia
   corrente nunca é afetado.
2. Clique em **Arquivar**: o sistema mostra a **confirmação com as contagens**
   por tabela (quantos registros serão movidos) e o nome do snapshot.
3. **Confirme o backup**: marque que o backup físico do portal.db foi realizado
   (o snapshot **não** substitui o backup — responsabilidade do cliente). Sem
   essa confirmação, o botão não executa.
4. Confirme: o sistema gera o snapshot e limpa o quente, **na ordem segura**
   (cópia primeiro; se a cópia falhar, nada é apagado).

**Snapshot:** `data/arquivo_morto/arquivo_morto_<execução>_<corte>.db` (primeira
data = execução, segunda = corte). É uma cópia íntegra do banco inteiro naquele
momento e fica **selada** — o sistema nunca mais grava nela (use para auditoria
ou dataset de treinamento). Backup físico do banco principal é responsabilidade
do cliente (volume).

**Tabelas afetadas (DELETE por idade — `criado_em ≤ corte`):**

| Tabela | Critério |
|:-------|:---------|
| tracing | idade (≤ corte) |
| uso_tokens | idade (≤ corte) |
| auditoria | idade (≤ corte) |
| memories | idade (≤ corte) |
| feedback | idade (≤ corte) |
| teste_ab | idade (≤ corte) |
| knowledge | fonte importada (csv/pdf/...) **e** sem uso recente (`acessos = 0` ou `ultimo_acesso ≤ corte`) — fontes `manual` e `skill` (regras/skills) **nunca** são afetadas |

**Nunca são afetadas:** `metricas_diarias` (agregado perpétuo de custos) e dados
mestres (clientes, usuários, agentes, modelos, skills, conectores, canais,
áreas, api_keys, configurações).

**Controle e auditoria:**

- Cada execução fica no **histórico da tela** (execução, corte, arquivo, movidos
  por tabela, status).
- Cada execução — sucesso **ou falha** — também é registrada na **Auditoria**
  (menu Operação): usuário, corte, arquivo gerado e total movido
  (`acao=arquivo_morto`).
- Executar duas vezes no mesmo dia com o mesmo corte é rejeitado (o snapshot já
  existe — nada é sobrescrito).

> A limpeza automática opcional (tela LGPD, `retencao_auto`) faz **DELETE
> físico** com retenções configuráveis e continua independente do arquivo morto.

---
**Campos do formulário:** `corte` (data de corte, no máximo D-1 a meia-noite),
`confirmar` (o segundo clique que executa de fato) e `backup_ok` (caixa que
confirma que o backup físico do portal.db foi feito — sem ela o corte é recusado).
