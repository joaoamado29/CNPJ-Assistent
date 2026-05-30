"""Validação e formatação de CNPJ."""

import re

from src.core.cnpj_validator import extract_cnpjs as _extract_cnpjs
from src.core.cnpj_validator import is_valid_cnpj

# Limite de CNPJs aceitos em uma única mensagem. Aumente se precisar.
MAX_CNPJS_POR_MENSAGEM = 100


def extrair_cnpj(texto: str) -> str | None:
    """Retorna o primeiro CNPJ (14 dígitos) válido encontrado no texto, ou None."""
    cnpjs = extrair_cnpjs(texto, limite=1)
    return cnpjs[0] if cnpjs else None


def extrair_cnpjs(texto: str, limite: int = MAX_CNPJS_POR_MENSAGEM) -> list[str]:
    """Retorna CNPJs válidos (com dígito verificador OK), únicos, na ordem de aparição.

    Aceita formatação livre (00.000.000/0000-00, 14 dígitos contínuos, etc.).
    Limita ao `limite` informado (padrão: MAX_CNPJS_POR_MENSAGEM).
    """
    candidatos = _extract_cnpjs(texto or "")
    validos = [c for c in candidatos if is_valid_cnpj(c)]
    return validos[:limite]


def formatar_cnpj(cnpj: str) -> str:
    """00.000.000/0000-00 a partir dos 14 dígitos."""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def _cnpj_valido(cnpj: str) -> bool:
    if len(set(cnpj)) == 1:  # todos dígitos iguais
        return False

    def dv(base: str, pesos: list[int]) -> str:
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    d1 = dv(cnpj[:12], pesos1)
    d2 = dv(cnpj[:12] + d1, pesos2)
    return cnpj[12] == d1 and cnpj[13] == d2