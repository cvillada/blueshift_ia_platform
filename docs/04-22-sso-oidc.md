### 5.22 SSO (OIDC) (/portal/sso/config)

**Onde:** Configurações → SSO (OIDC).

**Propósito:** login federado (Azure AD, Okta, Keycloak, Google).

| Campo | Obrigatório | Exemplo |
|:------|:-----------:|:--------|
| SSO ativo | checkbox | |
| Modo dev (IdP mock) | checkbox | Teste sem provedor real |
| Criar usuário automaticamente | checkbox | Se não cadastrado |
| Issuer (URL base do IdP) | ✅ | `https://login.microsoftonline.com/.../v2.0` |
| Client ID | ✅ | GUID do app |
| Client Secret | ✅ | Segredo do app |
| Redirect URI | ✅ | `http://host:8080/portal/sso/callback` |
| Domínio de admin | ❌ | `@suaempresa.com.br` (emails deste domínio viram admin) |

Fluxo: `/sso/login` → IdP → callback com `code` → troca por id_token →
validação (HMAC HS256 ou emissor) → sessão criada. Defesa CSRF via `state` +
`nonce`. Em modo dev, o token é gerado localmente (sem rede).
**Variáveis de ambiente equivalentes (opcional, para instalação automatizada):**
`BLUESHIFT_SSO_ATIVO`, `BLUESHIFT_SSO_CLIENT_ID`, `BLUESHIFT_SSO_CLIENT_SECRET`,
`BLUESHIFT_SSO_REDIRECT`, `BLUESHIFT_SSO_DOMINIO_ADMIN`, `BLUESHIFT_SSO_DEV_SECRET`
(segredo do IdP mock em modo dev). A tela acima tem precedência sobre elas.
