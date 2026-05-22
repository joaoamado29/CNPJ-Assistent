"""CNPJ validation and extraction utilities."""

from __future__ import annotations

import re


def clean_cnpj(raw: str) -> str:
    """Strip formatting characters, keeping only digits."""
    return re.sub(r"\D", "", raw.strip())


def is_valid_cnpj(cnpj: str) -> bool:
    """Validate a CNPJ using the official check-digit algorithm."""
    digits = clean_cnpj(cnpj)

    if len(digits) != 14:
        return False

    if digits == digits[0] * 14:
        return False

    weights_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    total = sum(int(digits[i]) * weights_1[i] for i in range(12))
    remainder = total % 11
    check_1 = 0 if remainder < 2 else 11 - remainder
    if int(digits[12]) != check_1:
        return False

    total = sum(int(digits[i]) * weights_2[i] for i in range(13))
    remainder = total % 11
    check_2 = 0 if remainder < 2 else 11 - remainder
    return int(digits[13]) == check_2


def format_cnpj(cnpj: str) -> str:
    """Format a 14-digit CNPJ string as XX.XXX.XXX/XXXX-XX."""
    d = clean_cnpj(cnpj)
    if len(d) != 14:
        return cnpj
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def extract_cnpjs(text: str) -> list[str]:
    """Extract all potential CNPJs from free-form text.

    Accepts formatted (XX.XXX.XXX/XXXX-XX) and raw 14-digit sequences.
    Returns a list of cleaned 14-digit strings (duplicates removed, order preserved).
    """
    pattern = r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"
    matches = re.findall(pattern, text)

    seen: set[str] = set()
    result: list[str] = []
    for match in matches:
        cleaned = clean_cnpj(match)
        if len(cleaned) == 14 and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)

    if not result:
        raw_digits = re.findall(r"\d{14,}", text)
        for seq in raw_digits:
            for i in range(0, len(seq) - 13):
                candidate = seq[i : i + 14]
                if candidate not in seen:
                    seen.add(candidate)
                    result.append(candidate)

    return result
