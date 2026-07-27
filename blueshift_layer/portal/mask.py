"""Funções de mascaramento de dados pessoais (LGPD Arts. 12, 13).

Cada funcao recebe um texto e retorna o texto com o padrao mascarado.
Todas sao seguras para chamar em texto que nao contem o padrao — retornam
o texto original inalterado.

Uso:
    from . import mask
    texto = mask.mascarar_cpf(texto)
"""

import re

# ── padrões regex ──────────────────────────────────────────────────────────
_RE_CPF = re.compile(r"\b(\d{3})[\.\s]?(\d{3})[\.\s]?(\d{3})[-\.\s]?(\d{2})\b")
_RE_CNPJ = re.compile(r"\b(\d{2})[\.\s]?(\d{3})[\.\s]?(\d{3})[/\s]?(\d{4})[-\.\s]?(\d{2})\b")
_RE_EMAIL = re.compile(r"\b([\w.+-]+)@([\w-]+\.)+[\w-]{2,}\b")
_RE_TEL = re.compile(r"\(?(\d{2})\)?\s*(\d{4,5})-?(\d{4})\b")
_RE_NOME = re.compile(
    r"\b([A-ZÀ-Ú][a-zà-ú]+)\s+([A-ZÀ-Ú][a-zà-ú]+)\b"           # Joao Silva
    r"|\b([A-ZÀ-Ú]{2,})\s+([A-ZÀ-Ú]{2,})\b",                    # SARAH LEWIS
)
# Endereço: "Rua", "Av", "Travessa" seguido de nome e número
_RE_ENDERECO = re.compile(
    r"\b(?:Rua|Av\.?|Avenida|Travessa|Praça|Alameda|Rodovia|Estrada)"
    r"\s+[\w\s]+?\s+,\s*(\d{1,5})\b",
    re.IGNORECASE,
)


def mascarar_cpf(texto: str) -> str:
    """Mascara CPF: 12345678900 -> ***.789.00"""
    return _RE_CPF.sub(r"***.\3-\4", texto)


def mascarar_cnpj(texto: str) -> str:
    """Mascara CNPJ: 11222333000181 -> **.222.333/0001-**"""
    return _RE_CNPJ.sub(r"**.\2.\3/\4-**", texto)


def mascarar_email(texto: str) -> str:
    """Mascara email: usuario@dominio.com -> u***@dominio.com"""

    def _mask(m):
        nome = m.group(1)
        if len(nome) <= 2:
            return nome[0] + "***@" + m.group(0).split("@")[1]
        return nome[0] + "***@" + m.group(0).split("@")[1]

    return _RE_EMAIL.sub(_mask, texto)


def mascarar_telefone(texto: str) -> str:
    """Mascara telefone: (11) 91234-5678 -> (11) ****-5678"""
    return _RE_TEL.sub(r"(\1) ****-\3", texto)


def mascarar_nome(texto: str) -> str:
    """Mascara sobrenome: Joao Silva -> Joao S*****, SARAH LEWIS -> SARAH L*****"""

    def _mask(m):
        if m.group(1):
            return f"{m.group(1)} {m.group(2)[0]}*****"
        return f"{m.group(3)} {m.group(4)[0]}*****"

    return _RE_NOME.sub(_mask, texto)


def mascarar_endereco(texto: str) -> str:
    """Mascara numero do endereco: Rua X, 123 -> Rua X, ***"""
    return _RE_ENDERECO.sub(lambda m: m.group(0).replace(m.group(1), "***"), texto)


# ── Aplicador único ───────────────────────────────────────────────────────

_MASK_MAP = {
    "cpf": mascarar_cpf,
    "email": mascarar_email,
    "telefone": mascarar_telefone,
    "nome": mascarar_nome,
    "endereco": mascarar_endereco,
    "cnpj": mascarar_cnpj,
}


def aplicar_mascaras(texto: str, config: dict[str, str]) -> str:
    """Aplica todas as máscaras ativas conforme config.

    config é o dict vindo de carregar_lgpd_config() — chaves 'mask_cpf',
    'mask_email', etc. com valor '1' ou '0'.
    """
    for chave, func in _MASK_MAP.items():
        if config.get(f"mask_{chave}", "0") == "1":
            texto = func(texto)
    return texto
