from playwright.sync_api import Page

from core.base_page import BasePage
from core.texto import data_br, somente_digitos, valor_brl
from projeto.modelos import Movimentacao


class ConsultaPage(BasePage):
    caminho = "/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # Filtros
        self.titulo = page.get_by_role("heading", name="Consulta de movimentações")
        self.campo_agencia = page.get_by_label("Agência")
        self.campo_competencia = page.get_by_label("Competência")
        self.botao_consultar = page.get_by_role("button", name="Consultar")
        # Resultado
        self.total_registros = page.get_by_test_id("total-registros")
        self.tabela = page.get_by_role("table", name="Movimentações")
        self.indicador_pagina = page.get_by_test_id("pagina-atual")
        self.botao_proxima = page.get_by_role("button", name="Próxima página")

    def aguardar_carregar(self) -> None:
        self.esperar_visivel(self.titulo, "tela de consulta")

    def consultar(self, agencia: str, competencia: str) -> int:
        """Aplica os filtros e retorna o total de registros informado pelo portal."""
        self.preencher(self.campo_agencia, agencia, "agência")
        self.preencher(self.campo_competencia, competencia, "competência")
        self.clicar(self.botao_consultar, "Consultar")
        self.esperar_visivel(self.total_registros, "resultado da consulta")
        return int(somente_digitos(self.ler_texto(self.total_registros, "total de registros")))

    def extrair_movimentacoes(self) -> list[Movimentacao]:
        """Lê todas as páginas da tabela. Só chame se a consulta retornou registros."""
        return self.percorrer_paginas(
            self._ler_pagina, self.botao_proxima, self.indicador_pagina, "movimentações"
        )

    def _ler_pagina(self) -> list[Movimentacao]:
        return [
            Movimentacao(
                data=data_br(linha["Data"]),
                historico=linha["Histórico"],
                documento=linha["Documento"],
                valor=valor_brl(linha["Valor"]),
            )
            for linha in self.ler_tabela(self.tabela, f"tabela ({self.indicador_pagina.inner_text()})")
        ]
