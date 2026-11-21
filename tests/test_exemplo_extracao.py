"""Fluxo completo do projeto de exemplo contra o portal fake. Apague junto com o exemplo."""

import csv
import json
from functools import partial

from pydantic import SecretStr

from core.fases import arquivo_execucoes
from core.runner import Desfecho, ResultadoExecucao, executar
from core.saida import DestinoCsv
from core.state import Estado, Status
from projeto.config import ProjetoSettings
from projeto.flows.extrair import extrair_movimentacoes, fazer_login
from projeto.modelos import Consulta, Movimentacao

CONSULTAS = [
    Consulta(id="0001_2026-10", agencia="0001", competencia="2026-10"),  # 12 registros, 3 páginas
    Consulta(id="0003_2026-10", agencia="0003", competencia="2026-10"),  # nenhum registro
]


def _rodar(settings: ProjetoSettings, consultas: list[Consulta]) -> ResultadoExecucao:
    destino = DestinoCsv(settings.saida_dir, Movimentacao, prefixo="movimentacoes_")
    login = partial(
        fazer_login, usuario=settings.portal_usuario, senha=settings.portal_senha.get_secret_value()
    )
    return executar(consultas, partial(extrair_movimentacoes, destino=destino), settings, preparar=login)


def _ler_csv(settings: ProjetoSettings, item_id: str) -> list[dict[str, str]]:
    arquivo = settings.saida_dir / f"movimentacoes_{item_id}.csv"
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def test_extrai_todas_as_paginas_grava_saida_e_nao_extrai_de_novo(settings: ProjetoSettings) -> None:
    primeira = _rodar(settings, CONSULTAS)
    assert primeira.sucesso
    assert primeira.contagem[Desfecho.CONCLUIDO] == 2

    linhas = _ler_csv(settings, "0001_2026-10")
    assert len(linhas) == 12
    assert linhas[0] == {
        "data": "01/10/2026",
        "historico": "TED RECEBIDA",
        "documento": "000100001",
        "valor": "123,45",
    }
    assert linhas[1]["valor"] == "-246,90"
    assert _ler_csv(settings, "0003_2026-10") == []  # arquivo só com cabeçalho: consulta sem registros

    estado = Estado(settings.estado_db, "teste")
    assert estado.obter("0001_2026-10").resultado["registros"] == 12

    segunda = _rodar(settings, CONSULTAS)
    assert segunda.contagem[Desfecho.PULADO] == 2


def test_total_divergente_bloqueia_saida_e_gera_evidencias(settings: ProjetoSettings) -> None:
    resultado = _rodar(settings, [Consulta(id="9999_2026-10", agencia="9999", competencia="2026-10")])

    assert resultado.contagem[Desfecho.ERRO] == 1
    registro = Estado(settings.estado_db, "teste").obter("9999_2026-10")
    assert registro.status == Status.ERRO  # será tentado de novo na próxima execução
    assert "ValidacaoFalhou" in registro.ultimo_erro and "total de registros" in registro.ultimo_erro
    assert not settings.saida_dir.exists()  # nada pela metade para a área consumir
    evidencias = {arquivo.name for arquivo in settings.evidencias_dir.glob("*/*")}
    assert {"erro.txt", "tela.png", "pagina.html", "url.txt", "trace.zip"} <= evidencias


def test_dry_run_extrai_mas_nao_grava_saida_nem_estado(settings: ProjetoSettings) -> None:
    settings.dry_run = True

    resultado = _rodar(settings, CONSULTAS)

    assert resultado.sucesso
    assert not settings.saida_dir.exists()
    assert not settings.estado_db.exists()
    # Só fica registrado que houve um DRY_RUN (usado pelo "core fases")
    registro = json.loads(arquivo_execucoes(settings.estado_db).read_text(encoding="utf-8"))
    assert registro["dry_run"]["status"] == "sucesso" and "real" not in registro


def test_falha_no_login_interrompe_antes_das_consultas(settings: ProjetoSettings) -> None:
    settings.portal_senha = SecretStr("")  # portal recusa senha vazia

    resultado = _rodar(settings, CONSULTAS)

    assert resultado.interrompida == "falha na preparação"
    assert sum(resultado.contagem.values()) == 0
    assert any(settings.evidencias_dir.glob("*preparacao/trace.zip"))
