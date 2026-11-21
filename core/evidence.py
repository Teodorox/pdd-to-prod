"""Coleta de evidências quando algo falha.

Navegador: erro, tela, HTML, URL e trace do Playwright (uv run playwright show-trace evidencias/<pasta>/trace.zip).
HTTP: erro e as últimas chamadas (método, URL sem valores sensíveis, status) com o corpo da última resposta.
"""

import logging
import re
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from playwright.sync_api import BrowserContext, Page

from core.http import SessaoHttp

log = logging.getLogger(__name__)


def iniciar_trace(context: BrowserContext, titulo: str) -> None:
    context.tracing.start_chunk(title=titulo)


def descartar_trace(context: BrowserContext) -> None:
    context.tracing.stop_chunk()


def salvar_trace(context: BrowserContext, base_dir: Path, nome: str) -> Path:
    """Guarda o trace de um item que deu certo (TRACE=sempre), para acompanhar a execução depois."""
    pasta = base_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{_nome_seguro(nome)}_ok"
    pasta.mkdir(parents=True, exist_ok=True)
    context.tracing.stop_chunk(path=pasta / "trace.zip")
    return pasta


def registrar_falha(
    context: BrowserContext, page: Page, base_dir: Path, nome: str, exc: BaseException
) -> Path:
    """Salva tudo que ajuda a entender a falha. Cada etapa é independente: uma página quebrada não impede o resto."""
    pasta = base_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{_nome_seguro(nome)}"
    pasta.mkdir(parents=True, exist_ok=True)

    (pasta / "erro.txt").write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
    _tentar("screenshot", lambda: page.screenshot(path=pasta / "tela.png", full_page=True, timeout=10_000))
    _tentar("html", lambda: (pasta / "pagina.html").write_text(page.content(), encoding="utf-8"))
    _tentar("url", lambda: (pasta / "url.txt").write_text(page.url, encoding="utf-8"))
    _tentar("trace", lambda: context.tracing.stop_chunk(path=pasta / "trace.zip"))
    return pasta


def registrar_falha_http(sessao: SessaoHttp, base_dir: Path, nome: str, exc: BaseException) -> Path:
    """Evidência de robô HTTP. Cabeçalhos (cookies, Authorization) nunca são gravados."""
    pasta = base_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{_nome_seguro(nome)}"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "erro.txt").write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
    chamadas = list(sessao.historico)
    linhas = [
        f"{c.metodo} {c.url} -> {c.status} ({c.duracao_ms} ms, {c.tipo or 'sem Content-Type'})"
        for c in chamadas
    ]
    (pasta / "chamadas.txt").write_text("\n".join(linhas) or "nenhuma chamada feita", encoding="utf-8")
    if chamadas:
        (pasta / "ultima_resposta.txt").write_text(chamadas[-1].corpo, encoding="utf-8")
    return pasta


def _tentar(etapa: str, acao: Callable[[], object]) -> None:
    try:
        acao()
    except Exception:
        log.warning("Não foi possível salvar a evidência '%s'", etapa, exc_info=True)


def _nome_seguro(nome: str) -> str:
    return re.sub(r"[^\w.-]+", "_", nome)[:80]
