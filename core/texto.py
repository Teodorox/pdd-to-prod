"""Conversões comuns em sistemas brasileiros."""

import re
from datetime import date, datetime
from decimal import Decimal


def valor_brl(texto: str) -> Decimal:
    """'R$ 1.234,56' / '1234,56' / '-R$ 10,00' -> Decimal. Nunca use float para dinheiro."""
    limpo = re.sub(r"[^\d,.-]", "", texto)
    if not re.search(r"\d", limpo):
        raise ValueError(f"valor monetário inválido: {texto!r}")
    return Decimal(limpo.replace(".", "").replace(",", "."))


def decimal_br(valor: Decimal) -> str:
    """Decimal('1234.5') -> '1234,50' (formato para digitar em campos de valor)."""
    return f"{valor:.2f}".replace(".", ",")


def somente_digitos(texto: str) -> str:
    """'123.456.789-00' -> '12345678900'."""
    return re.sub(r"\D", "", texto)


def data_br(texto: str) -> date:
    """'31/10/2026' -> date(2026, 10, 31). Formato diferente levanta ValueError (nunca adivinha)."""
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
