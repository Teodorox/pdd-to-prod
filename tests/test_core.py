"""Comportamentos do runner e do estado: idempotência, retry entre execuções e parada segura."""

from decimal import Decimal

import pytest
from playwright.sync_api import Page

from core.execucao import ExecucaoItem
from core.runner import Desfecho, Item, executar
from core.state import Estado, Status
from core.texto import decimal_br, valor_brl
from core.trava import trava_execucao
from projeto.config import ProjetoSettings


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("R$\xa01.234,56", "1234.56"), ("89,90", "89.90"), ("-R$ 10,00", "-10.00"), ("1000", "1000")],
)
def test_valor_brl(texto: str, esperado: str) -> None:
    assert valor_brl(texto) == Decimal(esperado)


def test_valor_brl_invalido() -> None:
    with pytest.raises(ValueError):
        valor_brl("R$ ,")


def test_decimal_br() -> None:
    assert decimal_br(Decimal("1234.5")) == "1234,50"


def test_execucao_interrompida_durante_acao_critica_vai_para_revisao(settings: ProjetoSettings) -> None:
    estado = Estado(settings.estado_db, "teste")
    estado.atualizar("A", Status.EM_ANDAMENTO)
    estado.atualizar("B", Status.ACAO_CRITICA)

    assert estado.recuperar_execucao_interrompida() == ["B"]
    assert estado.obter("A").status == Status.ERRO
    assert estado.obter("B").status == Status.REVISAO_MANUAL


def test_resolver_manual(settings: ProjetoSettings) -> None:
    estado = Estado(settings.estado_db, "teste")
    estado.atualizar("A", Status.REVISAO_MANUAL, contar_tentativa=True)
    estado.resolver("A", Status.CONCLUIDO, "conferido no sistema")

    registro = estado.obter("A")
    assert registro.status == Status.CONCLUIDO
    assert registro.tentativas == 0
    assert "conferido no sistema" in registro.ultimo_erro

    with pytest.raises(AssertionError):
        estado.resolver("A", Status.PENDENTE, "de novo")


def _falha_depois_da_acao_critica(page: Page, execucao: ExecucaoItem, item: Item) -> None:
    page.goto("/")
    execucao.acao_critica("ação que quebra no meio", lambda: page.locator("#nao-existe").click(timeout=200))


def test_falha_apos_acao_critica_vai_para_revisao_e_para_a_execucao(settings: ProjetoSettings) -> None:
    resultado = executar([Item(id="A"), Item(id="B")], _falha_depois_da_acao_critica, settings)

    assert resultado.contagem[Desfecho.CRITICO] == 1
    assert resultado.contagem[Desfecho.CONCLUIDO] == 0
    assert resultado.interrompida and "A" in resultado.interrompida
    estado = Estado(settings.estado_db, "teste")
    assert estado.obter("A").status == Status.REVISAO_MANUAL
    assert estado.obter("B") is None  # B nunca foi tocado


def _sempre_falha(page: Page, execucao: ExecucaoItem, item: Item) -> None:
    raise RuntimeError("site fora do ar")


def test_erros_consecutivos_interrompem_e_tentativas_esgotadas_vao_para_revisao(
    settings: ProjetoSettings,
) -> None:
    settings.max_erros_consecutivos = 2
    settings.max_tentativas_item = 2
    itens = [Item(id=i) for i in "ABC"]

    primeira = executar(itens, _sempre_falha, settings)
    assert primeira.contagem[Desfecho.ERRO] == 2
    assert primeira.interrompida == "2 erros consecutivos"

    estado = Estado(settings.estado_db, "teste")
    assert estado.obter("A").status == Status.ERRO
    assert estado.obter("C") is None

    executar(itens, _sempre_falha, settings)
    assert estado.obter("A").status == Status.REVISAO_MANUAL
    assert estado.obter("A").tentativas == 2


def _ok(page: Page, execucao: ExecucaoItem, item: Item) -> None:
    page.goto("/")


def test_nao_inicia_se_outra_execucao_do_mesmo_robo_esta_rodando(settings: ProjetoSettings) -> None:
    with trava_execucao(settings.estado_db.with_suffix(".lock")):
        resultado = executar([Item(id="A")], _ok, settings)

    assert resultado.interrompida and "outra execução em andamento" in resultado.interrompida
    assert not resultado.sucesso
    assert Estado(settings.estado_db, "teste").obter("A") is None
    assert executar([Item(id="A")], _ok, settings).sucesso  # trava liberada ao terminar


def test_trace_sempre_guarda_trace_de_quem_deu_certo(settings: ProjetoSettings) -> None:
    settings.trace = "sempre"

    executar([Item(id="A")], _ok, settings)

    assert len(list(settings.evidencias_dir.glob("*_A_ok/trace.zip"))) == 1
