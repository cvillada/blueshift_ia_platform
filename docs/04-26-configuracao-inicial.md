### 5.26 Configuração inicial (primeira entrada com banco limpo)

**O que é:** tela exibida apenas na PRIMEIRA abertura de uma instalação nova
(`BLUESHIFT_SEED_DEMO=0`, banco sem dados). Ela cria a empresa e o primeiro
usuário admin — depois disso o portal passa a mostrar o login normal.

**Quando usar:** na entrega/instalação, antes de qualquer cadastro.

**Passo a passo:**
1. Preencha os dados da empresa e do administrador e clique em
   **Criar empresa e acessar**;
2. Você entra direto no portal como admin da empresa criada;
3. Cadastre os modelos de IA (Cadastros → Modelos IA) — sem modelo não há
   resposta de agente nem Ajuda IA;
4. Siga a ordem de configuração: modelos → skills → agentes → conectores → canais.

**Campos:**

| Campo | Obrigatório | O que é | Exemplo |
|:------|:-----------:|:--------|:--------|
| Nome da empresa | ✅ | Nome de exibição da empresa | `XPTO Seguros` |
| Código | ✅ | Identificador curto (minúsculo, sem espaços) usado em integrações | `xpto` |
| Razão social | ❌ | Razão social formal (documentos/relatórios) | `XPTO Seguro S/A` |
| E-mail de contato | ❌ | Contato técnico da empresa | `ti@empresa.com.br` |
| Nome do admin | ✅ | Nome completo do primeiro administrador | `Maria Souza` |
| Login do admin | ✅ | Login de acesso do admin | `admin` |
| Senha do admin | ✅ | Senha do admin (mínimo 8 caracteres) | `••••••••` |

**Importante:** os campos técnicos deste formulário são `empresa_nome`,
`empresa_codigo`, `empresa_razao`, `empresa_email`, `admin_nome`, `admin_login`
e `admin_senha`. A chave de licença (`BLUESHIFT_LICENSE`) é definida na
instalação — não nesta tela.

**Relacionado:** `04-01-login.md`, `02-como-executar.md`.
