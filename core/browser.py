"""Criação padronizada do navegador (Playwright) para todas as automações."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, expect, sync_playwright

from core.config import Settings


@dataclass
class Sessao:
    browser: Browser
    context: BrowserContext

    def salvar_login(self, caminho: Path) -> None:
        """Salva cookies/localStorage para reaproveitar o login (STORAGE_STATE) nas próximas execuções."""
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=caminho)


def apontar_navegadores(settings: Settings) -> None:
    """Usa o Chromium da pasta do projeto, se existir. Assim o serviço acha o navegador com qualquer conta.

    Precisa rodar antes do sync_playwright(): o driver lê a variável ao iniciar.
    """
    if settings.canal_navegador or "PLAYWRIGHT_BROWSERS_PATH" in os.environ:
        return
    if settings.navegadores_dir.is_dir():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(settings.navegadores_dir.resolve())


@contextmanager
def abrir_navegador(settings: Settings) -> Iterator[Sessao]:
    expect.set_options(timeout=settings.timeout_ms)
    apontar_navegadores(settings)
    storage_state = (
        settings.storage_state if settings.storage_state and settings.storage_state.exists() else None
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=settings.headless,
            channel=settings.canal_navegador or None,
            slow_mo=settings.slow_mo_ms,
            proxy={"server": settings.proxy_server} if settings.proxy_server else None,
        )
        try:
            context = browser.new_context(
                base_url=settings.base_url or None,
                storage_state=storage_state,
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                viewport={"width": 1366, "height": 768},
                accept_downloads=True,
            )
            context.set_default_timeout(settings.timeout_ms)
            # O trace é gravado em blocos (um por item) e só é salvo em disco quando o item falha
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            yield Sessao(browser, context)
        finally:
            browser.close()
