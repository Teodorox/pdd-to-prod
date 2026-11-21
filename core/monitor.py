"""Monitoramento central: grava no banco os eventos de cada execução e o sinal de vida (heartbeat) do agendamento.

Tabelas (DDL do MySQL em docs/monitoramento/ddl_mysql.sql):
- robo_execucao: uma linha por execução (início, fim, status, contagens, registros extraídos)
- robo_evento: início, meio (cada item), fim e falha, com mensagem curta. O detalhe fica no log em arquivo.
- robo_heartbeat: uma linha por robô, atualizada pela execução agendada (ao começar, durante e ao terminar)
  e pelo agendar.ps1 (instalado/removido): último sinal, situação e próxima execução prevista

Regras:
- Sem MONITOR_URL, nada é gravado (desenvolvimento local).
- O monitoramento NUNCA derruba o robô: falha ao gravar vira aviso no log em arquivo. A falta de sinal é
  detectada fora da VM (horário previsto que passou sem a execução começar), não aqui.
"""

import logging
import socket
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from core.config import Settings

MENSAGEM_MAX = 1000


class Monitor:
    def __init__(self, settings: Settings) -> None:
        self.robo = settings.automacao_nome
        self.vm = socket.gethostname()
        self.dry_run = settings.dry_run
        self._log = logging.getLogger("monitor")
        self._engine: Any = None
        if settings.monitor_url is not None:
            self._seguro("conectar", lambda: self._conectar(settings))

    @property
    def ativo(self) -> bool:
        return self._engine is not None

    def iniciar_execucao(self) -> str:
        id_execucao = str(uuid.uuid4())
        agora = datetime.now()
        self._gravar(
            "início da execução",
            lambda c: (
                c.execute(
                    self._execucoes.insert(),
                    {**self._origem(), "id_execucao": id_execucao, "inicio": agora, "status": "em_andamento"},
                ),
                c.execute(self._eventos.insert(), self._evento("inicio", id_execucao, None, None, agora)),
            ),
        )
        return id_execucao

    def evento(
        self,
        tipo: str,
        *,
        id_execucao: str | None = None,
        item_id: str | None = None,
        mensagem: str | None = None,
    ) -> None:
        """tipo: inicio, item_ok, item_erro, item_critico, fim, falha, nao_iniciada, perdida, timeout..."""
        self._gravar(
            f"evento {tipo}",
            lambda c: c.execute(self._eventos.insert(), self._evento(tipo, id_execucao, item_id, mensagem)),
        )

    def finalizar_execucao(
        self, id_execucao: str, status: str, contagem: dict[str, int], registros: int, mensagem: str | None
    ) -> None:
        """status: sucesso, com_erros, interrompida, falha."""
        agora = datetime.now()
        tipo = "fim" if status == "sucesso" else "falha"
        valores = {
            "fim": agora,
            "status": status,
            "itens_concluidos": contagem.get("concluido", 0),
            "itens_erro": contagem.get("erro", 0) + contagem.get("critico", 0),
            "itens_pulados": contagem.get("pulado", 0),
            "registros": registros,
            "mensagem": _cortar(mensagem),
        }
        self._gravar(
            "fim da execução",
            lambda c: (
                c.execute(
                    self._execucoes.update()
                    .where(self._execucoes.c.id_execucao == id_execucao)
                    .values(**valores)
                ),
                c.execute(self._eventos.insert(), self._evento(tipo, id_execucao, None, mensagem, agora)),
            ),
        )

    def heartbeat(self, situacao: str, *, proxima: datetime | None = None, agenda: str | None = None) -> None:
        """situacao: aguardando, executando, removido. Uma linha por robô (atualiza ou cria)."""
        valores = {
            "vm": self.vm,
            "ultimo_sinal": datetime.now(),
            "situacao": situacao,
            "proxima_execucao": proxima,
            "agenda": agenda,
        }

        def gravar(c: Any) -> None:
            tabela = self._heartbeats
            atualizadas = c.execute(
                tabela.update().where(tabela.c.robo == self.robo).values(**valores)
            ).rowcount
            if atualizadas == 0:
                c.execute(tabela.insert(), {"robo": self.robo, **valores})

        self._gravar("heartbeat", gravar)

    def _conectar(self, settings: Settings) -> None:
        from sqlalchemy import create_engine

        assert settings.monitor_url is not None
        tabelas = tabelas_monitor(settings.monitor_schema)
        self._execucoes, self._eventos, self._heartbeats = tabelas
        self._engine = create_engine(settings.monitor_url.get_secret_value(), pool_pre_ping=True)

    def _gravar(self, descricao: str, operacao: Callable[[Any], object]) -> None:
        if self._engine is None:
            return

        def executar() -> None:
            with self._engine.begin() as conexao:
                operacao(conexao)

        self._seguro(descricao, executar)

    def _seguro(self, descricao: str, acao: Callable[[], object]) -> None:
        try:
            acao()
        except Exception:  # noqa: BLE001
            # Monitoramento fora do ar não pode parar a extração; a falta de sinal é detectada fora da VM
            self._log.warning("Monitoramento: falha ao gravar %s", descricao, exc_info=True)

    def _origem(self) -> dict[str, Any]:
        return {"robo": self.robo, "vm": self.vm, "dry_run": self.dry_run}

    def _evento(
        self,
        tipo: str,
        id_execucao: str | None,
        item_id: str | None,
        mensagem: str | None,
        momento: datetime | None = None,
    ) -> dict[str, Any]:
        return {
            "robo": self.robo,
            "vm": self.vm,
            "id_execucao": id_execucao,
            "momento": momento or datetime.now(),
            "tipo": tipo,
            "item_id": item_id,
            "mensagem": _cortar(mensagem),
        }


def tabelas_monitor(schema: str | None = None) -> tuple[Any, Any, Any]:
    """Definição das tabelas (igual ao DDL de docs/monitoramento). Usada também para criar no SQLite dos testes."""
    from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table

    meta = MetaData(schema=schema)
    execucoes = Table(
        "robo_execucao",
        meta,
        Column("id_execucao", String(36), primary_key=True),
        Column("robo", String(100), nullable=False),
        Column("vm", String(100), nullable=False),
        Column("inicio", DateTime, nullable=False),
        Column("fim", DateTime),
        Column("status", String(20), nullable=False),
        Column("itens_concluidos", Integer),
        Column("itens_erro", Integer),
        Column("itens_pulados", Integer),
        Column("registros", Integer),
        Column("dry_run", Boolean, nullable=False),
        Column("mensagem", String(MENSAGEM_MAX)),
    )
    eventos = Table(
        "robo_evento",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("id_execucao", String(36)),
        Column("robo", String(100), nullable=False),
        Column("vm", String(100), nullable=False),
        Column("momento", DateTime, nullable=False),
        Column("tipo", String(30), nullable=False),
        Column("item_id", String(200)),
        Column("mensagem", String(MENSAGEM_MAX)),
    )
    heartbeats = Table(
        "robo_heartbeat",
        meta,
        Column("robo", String(100), primary_key=True),
        Column("vm", String(100), nullable=False),
        Column("ultimo_sinal", DateTime, nullable=False),
        Column("situacao", String(20), nullable=False),
        Column("proxima_execucao", DateTime),
        Column("agenda", String(200)),
    )
    return execucoes, eventos, heartbeats


def _cortar(texto: str | None) -> str | None:
    return texto if texto is None or len(texto) <= MENSAGEM_MAX else texto[: MENSAGEM_MAX - 3] + "..."
