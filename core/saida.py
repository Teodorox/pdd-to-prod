"""Destinos da saída da extração (o que a área consome): CSV, Excel ou banco de dados.

Regras:
- Cada item grava a SUA parte, identificada pela chave (= id do item). Reprocessar um item substitui os dados
  dele, nunca duplica.
- Gravação atômica: quem consome nunca vê arquivo pela metade nem carga parcial no banco.
- No fluxo, grave sempre via `execucao.entregar(destino, linhas)`, que respeita o DRY_RUN e registra no estado.
"""

import csv
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, SecretStr


class Destino(Protocol):
    def gravar(self, chave: str, linhas: Sequence[BaseModel]) -> str:
        """Grava (ou substitui) as linhas da chave. Retorna onde gravou, para log e auditoria."""
        ...


class DestinoCsv:
    """Um arquivo por item: `<pasta>/<prefixo><chave>.csv`. Separador `;`, decimal com vírgula e data dd/mm/aaaa,
    em UTF-8 com BOM (abre direto no Excel em português)."""

    def __init__(self, pasta: Path, modelo: type[BaseModel], *, prefixo: str = "") -> None:
        self.pasta = pasta
        self.colunas = list(modelo.model_fields)
        self.prefixo = prefixo

    def gravar(self, chave: str, linhas: Sequence[BaseModel]) -> str:
        arquivo = self.pasta / f"{self.prefixo}{_nome_arquivo(chave)}.csv"
        with (
            _escrita_atomica(arquivo) as temporario,
            temporario.open("w", encoding="utf-8-sig", newline="") as f,
        ):
            escritor = csv.writer(f, delimiter=";")
            escritor.writerow(self.colunas)
            for linha in linhas:
                dados = linha.model_dump()
                escritor.writerow([_formatar_br(dados[c]) for c in self.colunas])
        return str(arquivo)


class DestinoExcel:
    """Um .xlsx por item: `<pasta>/<prefixo><chave>.xlsx`, com tipos nativos (número, data). Requer o extra `excel`."""

    def __init__(
        self, pasta: Path, modelo: type[BaseModel], *, prefixo: str = "", aba: str = "dados"
    ) -> None:
        self.pasta = pasta
        self.colunas = list(modelo.model_fields)
        self.prefixo = prefixo
        self.aba = aba

    def gravar(self, chave: str, linhas: Sequence[BaseModel]) -> str:
        from openpyxl import Workbook

        arquivo = self.pasta / f"{self.prefixo}{_nome_arquivo(chave)}.xlsx"
        planilha = Workbook()
        aba = planilha.active
        aba.title = self.aba
        aba.append(self.colunas)
        for linha in linhas:
            dados = linha.model_dump()
            aba.append([dados[c] for c in self.colunas])
        with _escrita_atomica(arquivo) as temporario:
            planilha.save(temporario)
        return str(arquivo)


class DestinoBanco:
    """Grava numa tabela JÁ EXISTENTE (criada pelo time de banco). Requer o extra `banco` e o driver do banco.

    Numa única transação: apaga as linhas da chave e insere as novas. Os campos do modelo precisam existir
    como colunas, além de `coluna_chave`.
    """

    def __init__(self, url: SecretStr, tabela: str, *, coluna_chave: str, schema: str | None = None) -> None:
        from sqlalchemy import MetaData, Table, create_engine

        self._engine = create_engine(url.get_secret_value())
        self._tabela = Table(tabela, MetaData(), schema=schema, autoload_with=self._engine)
        self.coluna_chave = coluna_chave

    def gravar(self, chave: str, linhas: Sequence[BaseModel]) -> str:
        coluna = self._tabela.c[self.coluna_chave]
        registros = [{**linha.model_dump(), self.coluna_chave: chave} for linha in linhas]
        with self._engine.begin() as conexao:
            conexao.execute(self._tabela.delete().where(coluna == chave))
            if registros:
                conexao.execute(self._tabela.insert(), registros)
        return f"tabela {self._tabela.fullname} ({self.coluna_chave}={chave})"


@contextmanager
def _escrita_atomica(arquivo: Path) -> Iterator[Path]:
    """Escreve num arquivo temporário na mesma pasta e só no fim troca pelo definitivo (os.replace)."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_name(f".{arquivo.name}.tmp")
    try:
        yield temporario
        os.replace(temporario, arquivo)
    finally:
        temporario.unlink(missing_ok=True)


def _formatar_br(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return str(valor).replace(".", ",")
    if isinstance(valor, datetime):
        return f"{valor:%d/%m/%Y %H:%M:%S}"
    if isinstance(valor, date):
        return f"{valor:%d/%m/%Y}"
    return valor


def _nome_arquivo(chave: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in chave)
