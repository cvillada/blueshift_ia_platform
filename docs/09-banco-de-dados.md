## 10. Banco de Dados (SQLite)

24 tabelas principais:

| Tabela | Conteúdo |
|:-------|:---------|
| clientes | Empresas contratantes |
| usuarios | Usuários do portal (papel, área, ativo) |
| areas | Áreas/departamentos (cadastro no banco; env BLUESHIFT_AREAS só seed inicial) |
| agentes | Agentes por área (modelo principal/secundário, skills) |
| conectores | Fontes externas (config JSON, área, finalidade) |
| health | Saúde do container por cliente |
| uso_tokens | Consumo de tokens por execução |
| contratos | Contratos/licença |
| skills | Skills persistentes (dual-write com arquivo) |
| tracing | Execuções completas (rastreio) |
| auditoria | Trilha de ações sensíveis |
| feedback | Avaliações 👍/👎 (tipo manual/api) |
| metricas_diarias | Agregações diárias (observabilidade) |
| alertas_config | Thresholds de alerta |
| custos_modelo | Preços por modelo |
| memories | Histórico por usuário (conversa grava a cada resposta; preferência/contexto alimentam o RAG) |
| knowledge | Base RAG (docs, área, acessos) |
| modelos | Modelos OpenAI-compatíveis |
| api_keys | Chaves de API (legado) |
| canais | Canais de integração (token próprio) |
| gateway_config | Gateways OpenAI-compatíveis (canal vinculado, modo streaming/completa) |
| sso_config | Configuração OIDC |
| lgpd_config | Configurações LGPD (chave/valor) |
| teste_ab | Julgamentos do Teste A/B (pergunta, respostas A/B, voto, justificativa, modelos) |

Índices nas tabelas mais consultadas (auditoria, memories, knowledge).
Backup: copiar o arquivo `portal.db` (o volume Docker `blueshift_data`
persiste entre rebuilds).

---
**Tabela `arquivo_morto_log`:** registra cada execução do Arquivo Morto
(snapshot + corte) — quando rodou, o corte aplicado e as contagens por tabela.
Alimenta o histórico mostrado na tela Arquivo Morto.
