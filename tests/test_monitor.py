"""Monitoramento central gravando num SQLite com as mesmas tabelas do DDL de produção."""

import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, select

from core.agendador import ExecucaoAgendada, avisar_agendamento
from core.monitor import tabelas_monitor
from core.runner import Item, executar
from projeto.config import ProjetoSettings
from tests.test_exemplo_extracao import CONSULTAS, _rodar


def _ligar_monitor(settings: ProjetoSettings, tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'monitor.db'}"
    execucoes, _, _ = tabelas_monitor()
    execucoes.metadata.create_all(create_engine(url))
    settings.monitor_url = SecretStr(url)
    return url


def _linhas(url: str, indice: int) -> list[dict[str, object]]:
    tabela = tabelas_monitor()[indice]
    with create_engine(url).connect() as con:
        return [dict(linha._mapping) for linha in con.execute(select(tabela))]


def test_execucao_registra_inicio_meio_fim(settings: ProjetoSettings, tmp_path: Path) -> None:
    url = _ligar_monitor(settings, tmp_path)
    consultas = [*CONSULTAS, CONSULTAS[0].model_copy(update={"id": "9999_2026-10", "agencia": "9999"})]

    _rodar(settings, consultas)

    [execucao] = _linhas(url, 0)
    assert execucao["robo"] == "teste" and execucao["status"] == "com_erros"
    assert (execucao["itens_concluidos"], execucao["itens_erro"], execucao["registros"]) == (2, 1, 12)
    assert execucao["fim"] is not None and execucao["dry_run"] is False
    eventos = [(e["tipo"], e["item_id"]) for e in _linhas(url, 1)]
    assert eventos == [
        ("inicio", None),
        ("item_ok", "0001_2026-10"),
        ("item_ok", "0003_2026-10"),
        ("item_erro", "9999_2026-10"),
        ("falha", None),
    ]
    assert "total de registros" in _linhas(url, 1)[3]["mensagem"]


def test_falha_fora_dos_itens_fecha_a_execucao_como_falha(settings: ProjetoSettings, tmp_path: Path) -> None:
    url = _ligar_monitor(settings, tmp_path)
    settings.canal_navegador = "navegador-que-nao-existe"

    with pytest.raises(Exception, match="navegador-que-nao-existe"):
        executar([Item(id="A")], lambda *_: None, settings)

    [execucao] = _linhas(url, 0)
    assert execucao["status"] == "falha" and execucao["fim"] is not None


def test_monitor_fora_do_ar_nao_derruba_o_robo(settings: ProjetoSettings, tmp_path: Path) -> None:
    settings.monitor_url = SecretStr(f"sqlite:///{tmp_path / 'pasta-inexistente' / 'monitor.db'}")

    resultado = _rodar(settings, CONSULTAS[:1])

    assert resultado.sucesso
    assert (settings.saida_dir / "movimentacoes_0001_2026-10.csv").exists()


def test_execucao_agendada_manda_sinal_com_a_proxima_e_agendar_ps1_avisa(
    settings: ProjetoSettings, tmp_path: Path
) -> None:
    url = _ligar_monitor(settings, tmp_path)
    settings.agenda_dias = "seg,ter,qua,qui,sex"
    settings.agenda_horarios = "07:00"

    avisar_agendamento(settings, "instalado")
    [sinal] = _linhas(url, 2)
    assert sinal["robo"] == "teste" and sinal["situacao"] == "aguardando" and sinal["proxima_execucao"]

    execucao = ExecucaoAgendada(
        settings, comando=[sys.executable, "-c", "pass"], relogio=lambda: datetime(2026, 11, 2, 7, 0)
    )
    assert execucao.rodar() == 0
    [sinal] = _linhas(url, 2)
    assert sinal["situacao"] == "aguardando"
    assert sinal["proxima_execucao"] == datetime(2026, 11, 3, 7, 0)  # o painel cobra este horário

    avisar_agendamento(settings, "removido")
    [sinal] = _linhas(url, 2)
    assert sinal["situacao"] == "removido"
