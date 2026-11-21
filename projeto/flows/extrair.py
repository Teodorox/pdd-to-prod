"""Regra de negócio: usa os Page Objects, nunca seletores diretos."""

from playwright.sync_api import Page

from core.execucao import ExecucaoItem
from core.saida import Destino
from projeto.modelos import Consulta
from projeto.pages.consulta_page import ConsultaPage
from projeto.pages.login_page import LoginPage


def fazer_login(page: Page, usuario: str, senha: str) -> None:
    LoginPage(page).abrir().entrar(usuario, senha)


def extrair_movimentacoes(
    page: Page, execucao: ExecucaoItem, consulta: Consulta, *, destino: Destino
) -> None:
    tela = ConsultaPage(page).abrir()
    total_informado = tela.consultar(consulta.agencia, consulta.competencia)
    movimentacoes = tela.extrair_movimentacoes() if total_informado > 0 else []

    # Completude: o que foi extraído tem que bater com o que o portal diz que existe
    execucao.conferir("total de registros", total_informado, len(movimentacoes))
    documentos = [m.documento for m in movimentacoes]
    execucao.validar(len(documentos) == len(set(documentos)), "documento repetido na extração")

    execucao.entregar(destino, movimentacoes)
