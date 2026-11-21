from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from core.runner import Item


class Consulta(Item):
    """Uma consulta ao portal. id = agência + competência: estável entre execuções."""

    agencia: str = Field(pattern=r"^\d{4}$")
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class Movimentacao(BaseModel):
    """Uma linha extraída da tabela. É o layout da saída: a ordem dos campos é a ordem das colunas."""

    data: date
    historico: str = Field(min_length=1)
    documento: str = Field(min_length=1)
    valor: Decimal
