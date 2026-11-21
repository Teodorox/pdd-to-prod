"""Logs: texto legível no console e JSON (um por linha) em arquivo, com rotação diária."""

import io
import json
import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_CAMPOS_PADRAO = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados = {
            "ts": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Campos passados via `extra=` (ex.: item_id) entram no JSON
        dados.update({k: v for k, v in record.__dict__.items() if k not in _CAMPOS_PADRAO})
        if record.exc_info:
            dados["exc"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False, default=str)


def configurar_logs(nome: str, logs_dir: Path, nivel: int = logging.INFO) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)

    # No Windows, saída redirecionada (tarefa agendada, pipe) usa cp1252 e quebra acentos
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S"))

    arquivo = TimedRotatingFileHandler(
        logs_dir / f"{nome}.jsonl", when="midnight", backupCount=30, encoding="utf-8"
    )
    arquivo.setFormatter(JsonFormatter())

    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.setLevel(nivel)
    raiz.addHandler(console)
    raiz.addHandler(arquivo)
