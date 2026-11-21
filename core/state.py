"""Estado persistente por item (SQLite), que garante que nada seja processado duas vezes.

Ciclo de vida de um item:
    (novo) -> EM_ANDAMENTO -> [ACAO_CRITICA] -> CONCLUIDO
    falha ANTES da ação crítica  -> ERRO (será tentado de novo; após N falhas vai para REVISAO_MANUAL)
    falha DEPOIS da ação crítica -> REVISAO_MANUAL (alguém precisa conferir no sistema se foi efetivado)
Se o processo cair no meio, a próxima execução aplica a mesma regra (ver `recuperar_execucao_interrompida`).

CLI para o time de operação:
    uv run python -m core listar [--status revisao_manual]
    uv run python -m core resolver ITEM_ID --como concluido --obs "conferido no sistema, protocolo X"
"""

import json
import sqlite3
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Status(StrEnum):
    PENDENTE = "pendente"
    EM_ANDAMENTO = "em_andamento"
    ACAO_CRITICA = "acao_critica"
    CONCLUIDO = "concluido"
    ERRO = "erro"
    REVISAO_MANUAL = "revisao_manual"


class RegistroItem(BaseModel):
    item_id: str
    status: Status
    tentativas: int
    ultimo_erro: str | None
    evidencia: str | None
    resultado: dict[str, Any]
    atualizado_em: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
    automacao TEXT NOT NULL,
    item_id TEXT NOT NULL,
    status TEXT NOT NULL,
    tentativas INTEGER NOT NULL DEFAULT 0,
    ultimo_erro TEXT,
    evidencia TEXT,
    resultado TEXT NOT NULL DEFAULT '{}',
    atualizado_em TEXT NOT NULL,
    PRIMARY KEY (automacao, item_id)
)
"""


class Estado:
    def __init__(self, db: Path | str, automacao: str) -> None:
        """`db` pode ser ":memory:" (usado no DRY_RUN para não sujar o estado real)."""
        if isinstance(db, Path):
            db.parent.mkdir(parents=True, exist_ok=True)
        self.automacao = automacao
        self._con = sqlite3.connect(db)
        self._con.row_factory = sqlite3.Row
        with self._con:
            self._con.execute(_SCHEMA)

    def obter(self, item_id: str) -> RegistroItem | None:
        linha = self._con.execute(
            "SELECT * FROM itens WHERE automacao = ? AND item_id = ?", (self.automacao, item_id)
        ).fetchone()
        return None if linha is None else _registro(linha)

    def listar(self, status: Status | None = None) -> list[RegistroItem]:
        sql = "SELECT * FROM itens WHERE automacao = ?"
        params: list[str] = [self.automacao]
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        return [_registro(linha) for linha in self._con.execute(sql + " ORDER BY atualizado_em", params)]

    def atualizar(
        self,
        item_id: str,
        status: Status,
        *,
        erro: str | None = None,
        evidencia: str | None = None,
        resultado: dict[str, Any] | None = None,
        contar_tentativa: bool = False,
        zerar_tentativas: bool = False,
    ) -> None:
        atual = self.obter(item_id)
        tentativas = 0 if zerar_tentativas or atual is None else atual.tentativas
        with self._con:
            self._con.execute(
                "INSERT OR REPLACE INTO itens VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.automacao,
                    item_id,
                    status,
                    tentativas + (1 if contar_tentativa else 0),
                    erro if erro is not None else (atual.ultimo_erro if atual else None),
                    evidencia if evidencia is not None else (atual.evidencia if atual else None),
                    json.dumps(resultado if resultado is not None else (atual.resultado if atual else {})),
                    _agora(),
                ),
            )

    def recuperar_execucao_interrompida(self) -> list[str]:
        """Trata itens que ficaram no meio porque o processo caiu. Retorna os que foram para revisão manual."""
        para_revisao = [r.item_id for r in self.listar(Status.ACAO_CRITICA)]
        with self._con:
            self._con.execute(
                "UPDATE itens SET status = ?, ultimo_erro = ?, atualizado_em = ? WHERE automacao = ? AND status = ?",
                (
                    Status.ERRO,
                    "execução interrompida antes da ação crítica",
                    _agora(),
                    self.automacao,
                    Status.EM_ANDAMENTO,
                ),
            )
            self._con.execute(
                "UPDATE itens SET status = ?, ultimo_erro = ?, atualizado_em = ? WHERE automacao = ? AND status = ?",
                (
                    Status.REVISAO_MANUAL,
                    "execução interrompida DURANTE a ação crítica: conferir no sistema",
                    _agora(),
                    self.automacao,
                    Status.ACAO_CRITICA,
                ),
            )
        return para_revisao

    def resolver(self, item_id: str, como: Status, observacao: str) -> None:
        """Usado por uma pessoa depois de conferir o item no sistema."""
        assert como in (Status.CONCLUIDO, Status.PENDENTE), (
            "só é possível resolver como concluido ou pendente"
        )
        atual = self.obter(item_id)
        assert atual is not None, f"item {item_id} não existe para a automação {self.automacao}"
        assert atual.status in (Status.REVISAO_MANUAL, Status.ERRO), (
            f"item está {atual.status}, nada a resolver"
        )
        self.atualizar(item_id, como, erro=f"resolvido manualmente: {observacao}", zerar_tentativas=True)

    def resumo(self) -> dict[str, int]:
        linhas = self._con.execute(
            "SELECT status, COUNT(*) FROM itens WHERE automacao = ? GROUP BY status", (self.automacao,)
        )
        return {status: total for status, total in linhas}


def _registro(linha: sqlite3.Row) -> RegistroItem:
    return RegistroItem(**{**dict(linha), "resultado": json.loads(linha["resultado"])})


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")
