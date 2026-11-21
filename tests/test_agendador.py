"""Execução agendada (disparada pelo Agendador de Tarefas), com relógio simulado."""

import json
import logging
import sys
from datetime import datetime

import pytest

from core.agendador import Agenda, ExecucaoAgendada
from projeto.config import ProjetoSettings

SEGUNDA = datetime(2026, 11, 2)  # 02/11/2026 é segunda-feira


def _execucao(settings: ProjetoSettings, agora: datetime, codigo_saida: int = 0) -> ExecucaoAgendada:
    settings.agenda_dias = "seg,ter,qua,qui,sex"
    settings.agenda_horarios = "07:00,13:30"
    comando = [sys.executable, "-c", f"import sys; sys.exit({codigo_saida})"]
    return ExecucaoAgendada(settings, comando=comando, relogio=lambda: agora)


def _status(execucao: ExecucaoAgendada) -> dict[str, object]:
    return json.loads(execucao.arquivo_status.read_text(encoding="utf-8"))


def test_agenda_proxima_anterior_e_formato_da_tarefa() -> None:
    agenda = Agenda.de_texto("seg,sex", "13:30, 07:00")

    assert agenda.proxima(SEGUNDA.replace(hour=7)) == SEGUNDA.replace(hour=13, minute=30)
    assert agenda.proxima(SEGUNDA.replace(hour=14)) == datetime(2026, 11, 6, 7, 0)  # pula para sexta
    assert agenda.anterior(SEGUNDA.replace(hour=7)) == SEGUNDA.replace(hour=7)
    assert agenda.anterior(SEGUNDA.replace(hour=6)) == datetime(2026, 10, 30, 13, 30)  # sexta anterior
    assert str(agenda) == "seg,sex às 07:00, 13:30"
    assert agenda.para_tarefa() == {"dias": ["Monday", "Friday"], "horarios": ["07:00", "13:30"]}


@pytest.mark.parametrize(("dias", "horarios"), [("segunda", "07:00"), ("seg", ""), ("seg", "7h")])
def test_agenda_invalida(dias: str, horarios: str) -> None:
    with pytest.raises(ValueError):
        Agenda.de_texto(dias, horarios)


def test_disparo_no_horario_executa_e_guarda_o_status(settings: ProjetoSettings) -> None:
    execucao = _execucao(settings, SEGUNDA.replace(hour=7, second=5))

    assert execucao.rodar() == 0

    status = _status(execucao)
    assert status["ultima_prevista"] == "2026-11-02T07:00:00"
    assert status["ultimo_codigo"] == 0
    assert status["proxima"] == "2026-11-02T13:30:00"


def test_robo_com_falha_devolve_1_para_a_tarefa(settings: ProjetoSettings) -> None:
    execucao = _execucao(settings, SEGUNDA.replace(hour=7), codigo_saida=1)

    assert execucao.rodar() == 1
    assert _status(execucao)["ultimo_codigo"] == 1


def test_mesmo_horario_nao_roda_duas_vezes(
    settings: ProjetoSettings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    _execucao(settings, SEGUNDA.replace(hour=7)).rodar()
    repetida = _execucao(settings, SEGUNDA.replace(hour=7, minute=2), codigo_saida=1)

    assert repetida.rodar() == 0
    assert _status(repetida)["ultimo_codigo"] == 0  # não rodou de novo
    assert "disparo repetido" in caplog.text


def test_atraso_dentro_da_tolerancia_roda(settings: ProjetoSettings) -> None:
    execucao = _execucao(settings, SEGUNDA.replace(hour=7, minute=40))  # VM ligou 40 min depois

    assert execucao.rodar() == 0
    assert _status(execucao)["ultimo_codigo"] == 0


def test_atraso_fora_da_tolerancia_nao_roda_e_notifica(
    settings: ProjetoSettings, caplog: pytest.LogCaptureFixture
) -> None:
    execucao = _execucao(settings, SEGUNDA.replace(hour=9))  # 2 h depois das 07:00

    assert execucao.rodar() == 1

    status = _status(execucao)
    assert status["ultima_prevista"] == "2026-11-02T07:00:00"
    assert status["ultimo_codigo"] is None
    assert "PERDIDA" in caplog.text


def test_disparo_fora_da_agenda_do_env_e_erro(
    settings: ProjetoSettings, caplog: pytest.LogCaptureFixture
) -> None:
    execucao = _execucao(settings, SEGUNDA.replace(hour=7))
    # Tarefa criada à mão com um horário que o .env não tem: nenhum horário da agenda nos últimos 7 dias
    execucao.agenda = Agenda(frozenset(), (SEGUNDA.time(),))

    assert execucao.rodar() == 1
    assert not execucao.arquivo_status.exists()  # não executou
    assert "fora da agenda" in caplog.text


def test_execucao_que_passa_do_timeout_e_encerrada(settings: ProjetoSettings) -> None:
    settings.agenda_timeout_min = 0  # encerra assim que começar
    execucao = _execucao(settings, SEGUNDA.replace(hour=7))
    execucao.comando = [sys.executable, "-c", "import time; time.sleep(30)"]

    assert execucao.rodar() == 1
    assert _status(execucao)["ultimo_codigo"] is None
