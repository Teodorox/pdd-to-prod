"""Base de todos os Page Objects. Seletores ficam SÓ nas classes de pages/, nunca nos fluxos."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Self, TypeVar

from playwright.sync_api import Locator, Page, expect

T = TypeVar("T")


class BasePage:
    caminho: str = ""  # rota relativa a BASE_URL, ex.: "/consultas/movimentacoes"

    def __init__(self, page: Page) -> None:
        self.page = page
        self.log = logging.getLogger(type(self).__name__)

    def abrir(self) -> Self:
        self.log.info("Abrindo %s", self.caminho or "/")
        self.page.goto(self.caminho)
        self.aguardar_carregar()
        return self

    def aguardar_carregar(self) -> None:
        """Sobrescreva esperando um elemento que prove que a tela está pronta para uso."""

    def clicar(self, alvo: Locator, descricao: str) -> None:
        self.log.info("Clicando em %s", descricao)
        alvo.click()

    def preencher(self, alvo: Locator, valor: str, descricao: str, *, sensivel: bool = False) -> None:
        self.log.info("Preenchendo %s = %s", descricao, "***" if sensivel else repr(valor))
        alvo.fill(valor)

    def selecionar(self, alvo: Locator, opcao: str, descricao: str) -> None:
        self.log.info("Selecionando %s = %r", descricao, opcao)
        alvo.select_option(label=opcao)

    def ler_texto(self, alvo: Locator, descricao: str) -> str:
        texto = alvo.inner_text().strip()
        self.log.info("Lido %s = %r", descricao, texto)
        return texto

    def esperar_visivel(self, alvo: Locator, descricao: str) -> None:
        self.log.info("Aguardando %s", descricao)
        expect(alvo).to_be_visible()

    def ler_tabela(self, tabela: Locator, descricao: str) -> list[dict[str, str]]:
        """Lê uma <table> (cabeçalho em <thead><th>, dados em <tbody><tr>) como [{cabeçalho: texto}].

        Linha com número de colunas diferente do cabeçalho é erro (ex.: linha "Nenhum registro" com colspan):
        trate o estado vazio no Page Object ANTES de chamar.
        """
        cabecalhos = [t.strip() for t in tabela.locator("thead th").all_inner_texts()]
        if len(set(cabecalhos)) != len(cabecalhos):
            raise ValueError(f"{descricao}: cabeçalho com colunas repetidas {cabecalhos}")
        linhas = []
        for linha in tabela.locator("tbody tr").all():
            celulas = [c.strip() for c in linha.locator("td").all_inner_texts()]
            if len(celulas) != len(cabecalhos):
                raise ValueError(f"{descricao}: linha com {len(celulas)} colunas, esperado {len(cabecalhos)}")
            linhas.append(dict(zip(cabecalhos, celulas, strict=True)))
        self.log.info("Lida %s: %d linha(s)", descricao, len(linhas))
        return linhas

    def percorrer_paginas(
        self,
        ler_pagina: Callable[[], list[T]],
        botao_proxima: Locator,
        indicador_pagina: Locator,
        descricao: str,
        *,
        max_paginas: int = 500,
    ) -> list[T]:
        """Lê a página atual, clica em "próxima" enquanto estiver visível e habilitado, e junta tudo.

        `indicador_pagina` é obrigatório (ex.: "Página 2 de 5"): é a prova de que a página trocou antes de ler
        de novo. Sem ele, a leitura pode repetir a página anterior.
        """
        registros: list[T] = []
        for numero in range(1, max_paginas + 1):
            registros.extend(ler_pagina())
            if not botao_proxima.is_visible() or botao_proxima.is_disabled():
                self.log.info("%s: %d página(s), %d registro(s)", descricao, numero, len(registros))
                return registros
            anterior = indicador_pagina.inner_text()
            self.clicar(botao_proxima, f"próxima página de {descricao}")
            expect(indicador_pagina).not_to_have_text(anterior)
        raise RuntimeError(
            f"{descricao}: passou de {max_paginas} páginas. Se for esperado, aumente max_paginas."
        )

    def baixar(self, alvo: Locator, pasta: Path, descricao: str) -> Path:
        """Clica num link/botão que gera download (relatório, planilha) e salva em `pasta`."""
        self.log.info("Baixando %s", descricao)
        with self.page.expect_download() as info:
            alvo.click()
        download = info.value
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / download.suggested_filename
        download.save_as(arquivo)
        self.log.info("Baixado %s em %s", descricao, arquivo)
        return arquivo
