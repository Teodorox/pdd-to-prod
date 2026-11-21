"""Loop padrão de execução: estado por item, evidência na falha, notificação e parada segura.

Regras:
- Item CONCLUIDO ou em REVISAO_MANUAL é pulado (idempotência).
- Falha depois de iniciada a ação crítica: item vai para revisão manual e a execução PARA.
- N erros consecutivos (site fora, layout mudou): a execução PARA.
- Só uma execução por vez do mesmo robô na máquina (trava no arquivo `<ESTADO_DB>.lock`).

Dois motores, mesmas regras (escolhido na análise técnica, docs/analise_tecnica.md):
- `executar`: navegador (Playwright). `processar(page, execucao, item)`, numa aba nova por item.
- `executar_http`: só requests, sem abrir navegador. `processar(sessao, execucao, item)`, com a mesma
  sessão (cookies do login) para todos os itens.
"""

import logging
from collections.abc import Callable, Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Generic, TypeVar

from playwright.sync_api import BrowserContext, Page
from pydantic import BaseModel

from core.browser import abrir_navegador
from core.config import Settings
from core.evidence import descartar_trace, iniciar_trace, registrar_falha, registrar_falha_http, salvar_trace
from core.execucao import ExecucaoItem
from core.fases import registrar_execucao
from core.http import SessaoHttp
from core.monitor import Monitor
from core.notify import Notificador
from core.state import Estado, Status
from core.trava import ExecucaoEmAndamento, trava_execucao


class Item(BaseModel):
    """Base de todo item processado. `id` deve ser estável entre execuções (nº do pedido, nota, título...),
    nunca o número da linha do arquivo."""

    id: str


ItemT = TypeVar("ItemT", bound=Item)
AlvoT = TypeVar("AlvoT")  # o que o fluxo recebe: Page (navegador) ou SessaoHttp


class Desfecho(StrEnum):
    CONCLUIDO = "concluido"
    PULADO = "pulado"
    ERRO = "erro"
    CRITICO = "critico"


@dataclass
class ResultadoExecucao:
    contagem: dict[Desfecho, int] = field(default_factory=lambda: dict.fromkeys(Desfecho, 0))
    interrompida: str | None = None
    registros: int = 0  # soma do "registros" entregue por cada item (execucao.entregar)

    @property
    def sucesso(self) -> bool:
        return (
            self.interrompida is None
            and self.contagem[Desfecho.ERRO] == 0
            and self.contagem[Desfecho.CRITICO] == 0
        )


# ---------------------------------------------------------------- motores


class _Motor(Generic[AlvoT]):
    """O que muda entre navegador e HTTP: como abrir, o que cada item recebe e que evidência guardar."""

    def abrir(self) -> AbstractContextManager[None]:
        raise NotImplementedError

    def iniciar(self, nome: str) -> AlvoT:
        raise NotImplementedError

    def falhou(self, alvo: AlvoT, nome: str, exc: BaseException) -> Path:
        raise NotImplementedError

    def concluiu(self, nome: str) -> None:
        """Item ou preparação deu certo."""

    def encerrar(self, alvo: AlvoT) -> None:
        """Sempre chamado no fim do item, com ou sem erro."""


class _MotorNavegador(_Motor[Page]):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._context: BrowserContext | None = None

    @contextmanager
    def abrir(self) -> Iterator[None]:
        with abrir_navegador(self._settings) as sessao:
            self._context = sessao.context
            yield

    @property
    def _contexto(self) -> BrowserContext:
        assert self._context is not None, "motor não aberto"
        return self._context

    def iniciar(self, nome: str) -> Page:
        page = self._contexto.new_page()
        iniciar_trace(self._contexto, nome)
        return page

    def falhou(self, alvo: Page, nome: str, exc: BaseException) -> Path:
        return registrar_falha(self._contexto, alvo, self._settings.evidencias_dir, nome, exc)

    def concluiu(self, nome: str) -> None:
        if self._settings.trace == "sempre":
            salvar_trace(self._contexto, self._settings.evidencias_dir, nome)
        else:
            descartar_trace(self._contexto)

    def encerrar(self, alvo: Page) -> None:
        alvo.close()


class _MotorHttp(_Motor[SessaoHttp]):
    def __init__(self, settings: Settings, criar_sessao: Callable[[], SessaoHttp] | None) -> None:
        self._settings = settings
        self._criar = criar_sessao or (
            lambda: SessaoHttp(base_url=settings.base_url, timeout_s=settings.timeout_ms / 1000)
        )
        self._sessao: SessaoHttp | None = None

    @contextmanager
    def abrir(self) -> Iterator[None]:
        with self._criar() as sessao:
            self._sessao = sessao
            yield

    def iniciar(self, nome: str) -> SessaoHttp:
        assert self._sessao is not None, "motor não aberto"
        self._sessao.historico.clear()  # a evidência mostra só as chamadas deste item
        return self._sessao

    def falhou(self, alvo: SessaoHttp, nome: str, exc: BaseException) -> Path:
        return registrar_falha_http(alvo, self._settings.evidencias_dir, nome, exc)


# ---------------------------------------------------------------- entrada pública


def executar(
    itens: Iterable[ItemT],
    processar: Callable[[Page, ExecucaoItem, ItemT], None],
    settings: Settings,
    *,
    preparar: Callable[[Page], None] | None = None,
) -> ResultadoExecucao:
    """Motor navegador. `preparar` roda uma vez antes dos itens (ex.: login). `processar` roda uma vez por item,
    numa aba nova."""
    return _executar_com_trava(itens, processar, settings, preparar, _MotorNavegador(settings))


def executar_http(
    itens: Iterable[ItemT],
    processar: Callable[[SessaoHttp, ExecucaoItem, ItemT], None],
    settings: Settings,
    *,
    preparar: Callable[[SessaoHttp], None] | None = None,
    criar_sessao: Callable[[], SessaoHttp] | None = None,
) -> ResultadoExecucao:
    """Motor HTTP (requests), sem navegador. `preparar` faz o login na sessão; `processar` chama os endpoints
    de cada item. `criar_sessao` só se precisar de algo além de BASE_URL/TIMEOUT_MS (proxy, certificado)."""
    return _executar_com_trava(itens, processar, settings, preparar, _MotorHttp(settings, criar_sessao))


# ---------------------------------------------------------------- loop


def _executar_com_trava(
    itens: Iterable[ItemT],
    processar: Callable[[Any, ExecucaoItem, ItemT], None],
    settings: Settings,
    preparar: Callable[[Any], None] | None,
    motor: _Motor[Any],
) -> ResultadoExecucao:
    try:
        with trava_execucao(settings.estado_db.with_suffix(".lock")):
            return _executar(itens, processar, settings, preparar, motor)
    except ExecucaoEmAndamento as exc:
        # Ex.: alguém rodou o executar.ps1 enquanto a execução agendada estava em andamento
        logging.getLogger(settings.automacao_nome).error("Execução não iniciada: %s", exc)
        Notificador(settings).enviar(f"[{settings.automacao_nome}] Execução não iniciada", str(exc))
        Monitor(settings).evento("nao_iniciada", mensagem=str(exc))
        return ResultadoExecucao(interrompida=str(exc))


def _executar(
    itens: Iterable[ItemT],
    processar: Callable[[Any, ExecucaoItem, ItemT], None],
    settings: Settings,
    preparar: Callable[[Any], None] | None,
    motor: _Motor[Any],
) -> ResultadoExecucao:
    monitor = Monitor(settings)
    id_execucao = monitor.iniciar_execucao()
    resultado = ResultadoExecucao()
    try:
        _executar_itens(itens, processar, settings, preparar, motor, monitor, id_execucao, resultado)
    except BaseException as exc:
        # Erro fora de um item (ex.: navegador não abriu). Registra e deixa estourar: o main sai com erro.
        monitor.finalizar_execucao(id_execucao, "falha", resultado.contagem, resultado.registros, repr(exc))
        registrar_execucao(settings, "falha", resultado.registros)
        raise
    if resultado.sucesso:
        status = "sucesso"
    else:
        status = "interrompida" if resultado.interrompida else "com_erros"
    monitor.finalizar_execucao(
        id_execucao, status, resultado.contagem, resultado.registros, resultado.interrompida
    )
    registrar_execucao(settings, status, resultado.registros)
    return resultado


def _executar_itens(
    itens: Iterable[ItemT],
    processar: Callable[[Any, ExecucaoItem, ItemT], None],
    settings: Settings,
    preparar: Callable[[Any], None] | None,
    motor: _Motor[Any],
    monitor: Monitor,
    id_execucao: str,
    resultado: ResultadoExecucao,
) -> None:
    log = logging.getLogger(settings.automacao_nome)
    estado = Estado(":memory:" if settings.dry_run else settings.estado_db, settings.automacao_nome)
    notificador = Notificador(settings)
    if settings.dry_run:
        log.warning("DRY_RUN ativo: nenhuma ação crítica será executada e o estado não será gravado")

    interrompidos = estado.recuperar_execucao_interrompida()
    if interrompidos:
        notificador.enviar(
            f"[{settings.automacao_nome}] Itens para revisão manual",
            "A execução anterior caiu durante uma ação crítica. Confira no sistema se foram efetivados:\n"
            + "\n".join(interrompidos),
        )

    with motor.abrir():
        if preparar is not None and not _preparar(motor, preparar, settings, notificador):
            resultado.interrompida = "falha na preparação"
            return

        erros_seguidos = 0
        for item in itens:
            desfecho, dados = _processar_item(motor, estado, notificador, settings, processar, item)
            resultado.contagem[desfecho] += 1
            resultado.registros += dados.get("registros", 0)
            _monitorar_item(monitor, id_execucao, estado, item.id, desfecho, dados)
            if desfecho is Desfecho.CRITICO:
                resultado.interrompida = f"falha após ação crítica no item {item.id}"
                break
            if desfecho is Desfecho.ERRO:
                erros_seguidos += 1
            elif desfecho is Desfecho.CONCLUIDO:
                erros_seguidos = 0
            if erros_seguidos >= settings.max_erros_consecutivos:
                resultado.interrompida = f"{erros_seguidos} erros consecutivos"
                break

    if resultado.interrompida:
        notificador.enviar(f"[{settings.automacao_nome}] Execução interrompida", resultado.interrompida)
    _log_resumo(log, resultado)


def _monitorar_item(
    monitor: Monitor,
    id_execucao: str,
    estado: Estado,
    item_id: str,
    desfecho: Desfecho,
    dados: dict[str, Any],
) -> None:
    """O "meio" da execução no monitoramento: um evento por item processado (pulados não geram evento)."""
    if desfecho is Desfecho.CONCLUIDO:
        mensagem = f"{dados['registros']} registro(s)" if "registros" in dados else None
        monitor.evento("item_ok", id_execucao=id_execucao, item_id=item_id, mensagem=mensagem)
    elif desfecho in (Desfecho.ERRO, Desfecho.CRITICO):
        registro = estado.obter(item_id)
        monitor.evento(
            f"item_{desfecho}",
            id_execucao=id_execucao,
            item_id=item_id,
            mensagem=registro.ultimo_erro if registro else None,
        )


def _preparar(
    motor: _Motor[Any], preparar: Callable[[Any], None], settings: Settings, notificador: Notificador
) -> bool:
    alvo = motor.iniciar("preparacao")
    try:
        preparar(alvo)
    except Exception as exc:
        pasta = motor.falhou(alvo, "preparacao", exc)
        logging.getLogger(settings.automacao_nome).exception("Falha na preparação")
        notificador.enviar(
            f"[{settings.automacao_nome}] Falha na preparação",
            f"{type(exc).__name__}: {exc}\n\nEvidências: {pasta.resolve()}",
            [pasta / "tela.png"],
        )
        return False
    else:
        motor.concluiu("preparacao")
        return True
    finally:
        motor.encerrar(alvo)


def _processar_item(
    motor: _Motor[Any],
    estado: Estado,
    notificador: Notificador,
    settings: Settings,
    processar: Callable[[Any, ExecucaoItem, ItemT], None],
    item: ItemT,
) -> tuple[Desfecho, dict[str, Any]]:
    registro = estado.obter(item.id)
    execucao = ExecucaoItem(item.id, estado, dry_run=settings.dry_run)
    if registro and registro.status in (Status.CONCLUIDO, Status.REVISAO_MANUAL):
        execucao.log.info("Pulado: status %s", registro.status)
        return Desfecho.PULADO, {}

    estado.atualizar(item.id, Status.EM_ANDAMENTO)
    alvo = motor.iniciar(item.id)
    try:
        processar(alvo, execucao, item)
    except Exception as exc:
        pasta = motor.falhou(alvo, item.id, exc)
        tentativas = (registro.tentativas if registro else 0) + 1
        if execucao.acao_critica_iniciada:
            status, desfecho = Status.REVISAO_MANUAL, Desfecho.CRITICO
            motivo = "Falhou DEPOIS de iniciar a ação crítica. Confira no sistema se foi efetivado."
        elif tentativas >= settings.max_tentativas_item:
            status, desfecho = Status.REVISAO_MANUAL, Desfecho.ERRO
            motivo = f"Falhou {tentativas} vezes. Não será tentado de novo automaticamente."
        else:
            status, desfecho = Status.ERRO, Desfecho.ERRO
            motivo = (
                f"Tentativa {tentativas}/{settings.max_tentativas_item}. Será tentado na próxima execução."
            )

        erro = f"{type(exc).__name__}: {exc}"
        estado.atualizar(item.id, status, erro=erro, evidencia=str(pasta), contar_tentativa=True)
        execucao.log.exception("Falhou (%s)", status)
        notificador.enviar(
            f"[{settings.automacao_nome}] {status.upper()} - item {item.id}",
            f"{motivo}\n\nErro: {erro}\n\nEvidências: {pasta.resolve()}",
            [pasta / "tela.png"],
        )
        return desfecho, {}
    else:
        motor.concluiu(item.id)
        estado.atualizar(item.id, Status.CONCLUIDO, resultado=execucao.resultado)
        execucao.log.info("Concluído %s", execucao.resultado or "")
        return Desfecho.CONCLUIDO, execucao.resultado
    finally:
        motor.encerrar(alvo)


def _log_resumo(log: logging.Logger, resultado: ResultadoExecucao) -> None:
    contagem = ", ".join(f"{d}={n}" for d, n in resultado.contagem.items())
    if resultado.interrompida:
        log.error("Execução INTERROMPIDA (%s): %s", resultado.interrompida, contagem)
    else:
        log.info("Execução finalizada: %s", contagem)
