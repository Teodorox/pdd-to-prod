"""Objeto entregue ao fluxo de cada item: validações, entrega da saída e a porta de entrada das ações críticas."""

import logging
from collections.abc import Callable, MutableMapping, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel

from core.saida import Destino
from core.state import Estado, Status

T = TypeVar("T")


class ValidacaoFalhou(Exception):
    """Dado na tela diverge do esperado. Nunca capture esta exceção para seguir em frente."""


class _LogDoItem(logging.LoggerAdapter):
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        item_id = self.extra["item_id"] if self.extra else "?"
        kwargs.setdefault("extra", {})["item_id"] = item_id
        return f"[{item_id}] {msg}", kwargs


class ExecucaoItem:
    def __init__(self, item_id: str, estado: Estado, *, dry_run: bool) -> None:
        self.item_id = item_id
        self.dry_run = dry_run
        self.resultado: dict[str, Any] = {}
        self.acao_critica_iniciada = False
        self.log = _LogDoItem(logging.getLogger("execucao"), {"item_id": item_id})
        self._estado = estado

    def conferir(self, campo: str, esperado: object, encontrado: object) -> None:
        """Compara dois valores e falha se divergirem. Ex.: total de registros informado pela tela x linhas
        extraídas. Normalize os tipos ANTES (int com int, Decimal com Decimal)."""
        if esperado != encontrado:
            raise ValidacaoFalhou(f"{campo}: esperado {esperado!r}, encontrado na tela {encontrado!r}")
        self.log.info("Conferido %s = %r", campo, encontrado)

    def validar(self, condicao: bool, mensagem: str) -> None:
        if not condicao:
            raise ValidacaoFalhou(mensagem)

    def registrar(self, chave: str, valor: Any) -> None:
        """Guarda um dado do resultado (ex.: protocolo) no estado do item, para auditoria."""
        self.resultado[chave] = valor

    def entregar(self, destino: Destino, linhas: Sequence[BaseModel]) -> None:
        """Grava a saída do item (arquivo/banco). No DRY_RUN não grava. Valide tudo ANTES de entregar."""
        if self.dry_run:
            self.log.warning("DRY_RUN: %d registro(s) NÃO gravados", len(linhas))
            return
        onde = destino.gravar(self.item_id, linhas)
        self.registrar("registros", len(linhas))
        self.registrar("saida", onde)
        self.log.info("Entregue: %d registro(s) em %s", len(linhas), onde)

    def acao_critica(self, descricao: str, acao: Callable[[], T]) -> T | None:
        """Executa uma ação que ALTERA o sistema e não pode ser desfeita (aprovar, enviar, baixar título...).
        Robô só de extração não usa.

        - Executa UMA vez, nunca repete.
        - Marca o item como ACAO_CRITICA antes de agir: qualquer falha daqui em diante vai para revisão manual.
        - No DRY_RUN não executa e retorna None.
        """
        if self.dry_run:
            self.log.warning("DRY_RUN: ação crítica '%s' NÃO executada", descricao)
            return None
        self._estado.atualizar(self.item_id, Status.ACAO_CRITICA)
        self.acao_critica_iniciada = True
        self.log.info("Executando ação crítica: %s", descricao)
        return acao()
