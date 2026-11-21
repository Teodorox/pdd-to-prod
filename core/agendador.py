"""Agendamento pelo Agendador de Tarefas do Windows (ver scripts/agendar.ps1).

A agenda fica no .env (AGENDA_*). O `agendar.ps1` cria a tarefa a partir dela; em cada horário, a tarefa roda:

    python -m core execucao-agendada   # uma execução do robô, com timeout, sinal de vida e notificação

Outros comandos:
    uv run python -m core agenda               # mostra a agenda configurada e as próximas execuções
    uv run python -m core agenda --json        # dias e horários para o agendar.ps1 montar os gatilhos
    uv run python -m core agendamento instalado|removido   # avisa o monitoramento (chamado pelo agendar.ps1)

Regras da execução agendada:
- O robô roda num processo separado (`python -m projeto.main`), com HEADLESS=true.
- Execução que passa de AGENDA_TIMEOUT_MIN é encerrada (com o navegador) e notificada.
- Disparo atrasado (VM desligada no horário; a tarefa roda quando a VM volta): roda se o atraso for até
  AGENDA_TOLERANCIA_MIN; acima disso, NÃO roda atrasado e notifica.
- O mesmo horário não roda duas vezes. O estado fica em `<ESTADO_DB>.agenda.json`.
- Com MONITOR_URL, manda o sinal de vida (heartbeat) ao começar, a cada MONITOR_HEARTBEAT_MIN durante a
  execução e ao terminar, com a próxima execução prevista. O painel acusa quando o horário previsto passa
  sem a execução começar (tarefa desativada, VM desligada).
- Execução manual (fora da agenda) é com scripts\\executar.ps1, que não passa por aqui.
"""

import json
import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as hora
from pathlib import Path
from typing import Any

from core.config import Settings
from core.monitor import Monitor
from core.notify import Notificador

DIAS = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
DIAS_INGLES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
COMANDO_ROBO = (sys.executable, "-m", "projeto.main")


@dataclass(frozen=True)
class Agenda:
    dias: frozenset[int]  # 0 = segunda
    horarios: tuple[hora, ...]

    @classmethod
    def de_texto(cls, dias: str, horarios: str) -> "Agenda":
        """dias "seg,ter,qua,qui,sex" (ou "todos"); horarios "07:00,13:30". Texto inválido levanta ValueError."""
        nomes = [d.strip().lower() for d in dias.split(",") if d.strip()]
        if nomes == ["todos"]:
            nomes = list(DIAS)
        invalidos = [d for d in nomes if d not in DIAS]
        if invalidos or not nomes:
            raise ValueError(f"AGENDA_DIAS inválido: {dias!r}. Use {','.join(DIAS)} ou todos.")
        lista = sorted(
            {datetime.strptime(h.strip(), "%H:%M").time() for h in horarios.split(",") if h.strip()}
        )
        if not lista:
            raise ValueError("AGENDA_HORARIOS vazio. Ex.: AGENDA_HORARIOS=07:00,13:30")
        return cls(frozenset(DIAS.index(d) for d in nomes), tuple(lista))

    def proxima(self, depois_de: datetime) -> datetime:
        """Primeiro horário agendado estritamente depois de `depois_de`."""
        return min(h for h in self._horarios_entre(depois_de.date(), 8) if h > depois_de)

    def anterior(self, ate: datetime) -> datetime | None:
        """Último horário agendado até `ate` (inclusive), olhando no máximo 7 dias para trás."""
        candidatos = [h for h in self._horarios_entre(ate.date() - timedelta(days=7), 8) if h <= ate]
        return max(candidatos, default=None)

    def para_tarefa(self) -> dict[str, list[str]]:
        """Dias (em inglês, como o New-ScheduledTaskTrigger pede) e horários, para o agendar.ps1."""
        return {
            "dias": [DIAS_INGLES[d] for d in sorted(self.dias)],
            "horarios": [h.strftime("%H:%M") for h in self.horarios],
        }

    def _horarios_entre(self, inicio: date, dias: int) -> list[datetime]:
        datas = (inicio + timedelta(days=n) for n in range(dias))
        return [datetime.combine(d, h) for d in datas if d.weekday() in self.dias for h in self.horarios]

    def __str__(self) -> str:
        dias = ",".join(DIAS[d] for d in sorted(self.dias))
        return f"{dias} às {', '.join(h.strftime('%H:%M') for h in self.horarios)}"


class ExecucaoAgendada:
    """Uma execução disparada pela tarefa agendada. `rodar()` devolve o código de saída da tarefa."""

    def __init__(
        self,
        settings: Settings,
        *,
        comando: Sequence[str] = COMANDO_ROBO,
        relogio: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.agenda = Agenda.de_texto(settings.agenda_dias, settings.agenda_horarios)
        self.settings = settings
        self.comando = list(comando)
        self.arquivo_status = arquivo_status(settings)
        self.log = logging.getLogger("agendamento")
        self._notificador = Notificador(settings)
        self._monitor = Monitor(settings)
        self._agora = relogio

    def rodar(self) -> int:
        agora = self._agora()
        previsto = self.agenda.anterior(agora)
        if previsto is None:
            return self._fora_da_agenda(agora)
        if _data(self._ler_status().get("ultima_prevista")) == previsto:
            self.log.info(
                "Execução das %s já foi feita; disparo repetido ignorado", f"{previsto:%d/%m %H:%M}"
            )
            return 0
        atraso = agora - previsto
        if atraso > timedelta(minutes=self.settings.agenda_tolerancia_min):
            self._perdida(previsto, atraso)
            self._salvar_status(ultima_prevista=previsto, ultimo_codigo=None, ultimo_fim=None)
            self._sinal("aguardando")
            return 1
        codigo = self._executar(previsto)
        self._salvar_status(ultima_prevista=previsto, ultimo_codigo=codigo, ultimo_fim=self._agora())
        self._sinal("aguardando")
        return 0 if codigo == 0 else 1

    def _executar(self, previsto: datetime) -> int | None:
        self.log.info("Iniciando execução das %s", f"{previsto:%d/%m %H:%M}")
        self._sinal("executando")
        # Sem tela na tarefa agendada; UTF-8 para os acentos nos logs redirecionados
        ambiente = os.environ | {"HEADLESS": "true", "PYTHONUTF8": "1"}
        processo = subprocess.Popen(self.comando, env=ambiente)
        intervalo = self.settings.monitor_heartbeat_min * 60
        limite = time.monotonic() + self.settings.agenda_timeout_min * 60
        while True:
            # Espera em blocos para continuar mandando o sinal de vida durante execuções longas
            bloco = min(limite - time.monotonic(), intervalo)
            try:
                codigo = processo.wait(timeout=max(bloco, 0))
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() < limite:
                    self._sinal("executando")
                    continue
            _encerrar_arvore(processo)
            minutos = self.settings.agenda_timeout_min
            self.log.error("Execução das %s passou de %d min e foi encerrada", previsto, minutos)
            self._notificador.enviar(
                f"[{self.settings.automacao_nome}] Execução encerrada por tempo",
                f"A execução das {previsto:%d/%m %H:%M} passou de {minutos} min e foi encerrada. "
                "Itens no meio serão tratados na próxima execução. Veja logs/ e evidencias/.",
            )
            self._monitor.evento(
                "timeout", mensagem=f"execução das {previsto:%d/%m %H:%M} encerrada após {minutos} min"
            )
            return None
        if codigo == 0:
            self.log.info("Execução das %s concluída", f"{previsto:%d/%m %H:%M}")
        else:
            self.log.error("Execução das %s terminou com código %d", f"{previsto:%d/%m %H:%M}", codigo)
            self._notificador.enviar(
                f"[{self.settings.automacao_nome}] Execução terminou com falha",
                f"A execução das {previsto:%d/%m %H:%M} terminou com código {codigo}. "
                "Veja as notificações anteriores, logs/ e evidencias/.",
            )
            self._monitor.evento(
                "processo_erro", mensagem=f"execução das {previsto:%d/%m %H:%M} saiu com código {codigo}"
            )
        return codigo

    def _perdida(self, previsto: datetime, atraso: timedelta) -> None:
        minutos = int(atraso.total_seconds() // 60)
        self.log.error("Execução das %s PERDIDA (%d min de atraso)", f"{previsto:%d/%m %H:%M}", minutos)
        self._notificador.enviar(
            f"[{self.settings.automacao_nome}] Execução perdida",
            f"A execução das {previsto:%d/%m %H:%M} não rodou no horário (VM desligada ou tarefa desativada) e "
            f"o atraso de {minutos} min passou da tolerância de {self.settings.agenda_tolerancia_min} min. "
            "Rode manualmente se precisar: scripts\\executar.ps1",
        )
        self._monitor.evento(
            "perdida", mensagem=f"execução das {previsto:%d/%m %H:%M} perdida ({minutos} min de atraso)"
        )

    def _fora_da_agenda(self, agora: datetime) -> int:
        mensagem = (
            f"A tarefa agendada disparou às {agora:%d/%m %H:%M}, fora da agenda do .env ({self.agenda}). "
            "A tarefa e o .env estão diferentes: rode .\\scripts\\agendar.ps1 instalar de novo."
        )
        self.log.error(mensagem)
        self._notificador.enviar(f"[{self.settings.automacao_nome}] Disparo fora da agenda", mensagem)
        self._monitor.evento("processo_erro", mensagem=mensagem)
        return 1

    def _sinal(self, situacao: str) -> None:
        self._monitor.heartbeat(situacao, proxima=self.agenda.proxima(self._agora()), agenda=str(self.agenda))

    def _ler_status(self) -> dict[str, Any]:
        if not self.arquivo_status.exists():
            return {}
        return json.loads(self.arquivo_status.read_text(encoding="utf-8"))

    def _salvar_status(self, **campos: datetime | int | None) -> None:
        status = self._ler_status() | {k: _texto(v) for k, v in campos.items()}
        status["agenda"] = str(self.agenda)
        status["proxima"] = _texto(self.agenda.proxima(self._agora()))
        status["atualizado_em"] = _texto(self._agora())
        self.arquivo_status.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo_status.with_name(self.arquivo_status.name + ".tmp")
        temporario.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(self.arquivo_status)


def avisar_agendamento(settings: Settings, situacao: str) -> None:
    """Chamado pelo agendar.ps1: 'instalado' passa a esperar a próxima execução; 'removido' para de cobrar."""
    agenda = Agenda.de_texto(settings.agenda_dias, settings.agenda_horarios)
    monitor = Monitor(settings)
    if situacao == "instalado":
        monitor.heartbeat("aguardando", proxima=agenda.proxima(datetime.now()), agenda=str(agenda))
    else:
        monitor.heartbeat("removido", agenda=str(agenda))


def arquivo_status(settings: Settings) -> Path:
    return settings.estado_db.with_suffix(".agenda.json")


def _encerrar_arvore(processo: subprocess.Popen[bytes]) -> None:
    """Encerra o robô e os filhos dele (navegador). No Windows, kill() sozinho deixa o navegador aberto."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(processo.pid)], capture_output=True, check=False)
    else:
        processo.kill()
    processo.wait()


def _texto(valor: datetime | int | None) -> str | int | None:
    return valor.isoformat(timespec="seconds") if isinstance(valor, datetime) else valor


def _data(valor: str | None) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None
