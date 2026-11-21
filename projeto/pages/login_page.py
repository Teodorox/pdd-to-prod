from playwright.sync_api import Page, expect

from core.base_page import BasePage


class LoginPage(BasePage):
    caminho = "/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.titulo = page.get_by_role("heading", name="Acesso ao portal")
        self.campo_usuario = page.get_by_label("Usuário")
        self.campo_senha = page.get_by_label("Senha")
        self.botao_entrar = page.get_by_role("button", name="Entrar")
        self.titulo_area_logada = page.get_by_role("heading", name="Consulta de movimentações")

    def aguardar_carregar(self) -> None:
        self.esperar_visivel(self.titulo, "tela de login")

    def entrar(self, usuario: str, senha: str) -> None:
        self.preencher(self.campo_usuario, usuario, "usuário")
        self.preencher(self.campo_senha, senha, "senha", sensivel=True)
        self.clicar(self.botao_entrar, "Entrar")
        expect(self.titulo_area_logada).to_be_visible()
