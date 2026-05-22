"""Validação e formatação de CNPJ."""

import re


def extrair_cnpj(texto: str) -> str | None:
    """Retorna o CNPJ (14 dígitos) válido encontrado no texto, ou None."""
    digitos = re.sub(r"\D", "", texto or "")
    if len(digitos) != 14 or not _cnpj_valido(digitos):
        return None
    return digitos


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
