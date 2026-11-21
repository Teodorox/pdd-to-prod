"""Núcleo compartilhado por todas as automações. Não coloque regra de negócio aqui."""

from core.base_page import BasePage
from core.config import Settings
from core.execucao import ExecucaoItem, ValidacaoFalhou
from core.runner import Item, ResultadoExecucao, executar
from core.saida import Destino, DestinoBanco, DestinoCsv, DestinoExcel
from core.state import Estado, Status

__all__ = [
    "BasePage",
    "Destino",
    "DestinoBanco",
    "DestinoCsv",
    "DestinoExcel",
    "Estado",
    "ExecucaoItem",
    "Item",
    "ResultadoExecucao",
    "Settings",
    "Status",
    "ValidacaoFalhou",
    "executar",
]
