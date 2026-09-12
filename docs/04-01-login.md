### 5.1 Login (/portal/login)

**Propósito:** autenticar usuários do portal.

**Primeiro acesso (setup inicial):** se o banco não tem nenhum usuário admin
(instalação nova com `BLUESHIFT_SEED_DEMO=0`), a tela de login vira um
formulário de **Configuração inicial** — o cliente cadastra a própria empresa
e o administrador inicial. Depois disso, o login normal aparece. Campos:

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Nome da empresa | ✅ | `XPTO Seguros` | Nome comercial |
| Código | ✅ | `xpto` | Identificador único (minúsculas) |
| Razão social | ❌ | `XPTO Seguro S/A` | |
| E-mail de contato | ❌ | `ti@empresa.com.br` | |
| Nome do admin | ✅ | `Administrador Inicial` | |
| Login do admin | ✅ | `admin` | |
| Senha do admin | ✅ | `••••••` | Mínimo 8 caracteres |

**Login normal** (quando já existe admin):

| Campo | Obrigatório | Exemplo | Dica |
|:------|:-----------:|:--------|:-----|
| Login | ✅ | `admin` | Nome de usuário cadastrado |
| Senha | ✅ | `••••••` | Senha definida no cadastro |

- Botão **Entrar**: autentica e redireciona.
- Link **Entrar com SSO (OIDC)**: login federado (se configurado).
- Aviso de privacidade (LGPD) pode aparecer acima do card, se ativado nas
  configurações LGPD.
- Proteções: rate limit de 5 tentativas/min por IP (bloqueio de 15 min),
  senha com hash scrypt, CSRF no formulário.
- Botão de tema 🌙/☀️/💻 no topo direito (claro/escuro/sistema).
**Sair:** a rota `/portal/logout` encerra a sessão e volta para a tela de login
(as sessões também expiram por inatividade — padrão 30 minutos).
