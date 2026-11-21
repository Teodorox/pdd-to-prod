"""Trava de execução: impede duas execuções do mesmo robô ao mesmo tempo na mesma máquina.

Usa trava do sistema operacional no arquivo: se o processo morrer, o Windows/Linux libera sozinho
(não existe trava "presa" para limpar à mão).
"""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class ExecucaoEmAndamento(Exception):
    """Outra execução do mesmo robô está rodando."""


@contextmanager
def trava_execucao(arquivo: Path) -> Iterator[None]:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with arquivo.open("a+", encoding="utf-8") as f:
        if not _travar(f.fileno()):
            f.seek(0)
            raise ExecucaoEmAndamento(f"outra execução em andamento ({f.read().strip() or 'sem detalhes'})")
        try:
            f.truncate(0)
            f.write(f"pid={os.getpid()} desde {datetime.now():%d/%m/%Y %H:%M:%S}")
            f.flush()
            yield
        finally:
            _destravar(f.fileno())


if sys.platform == "win32":
    import msvcrt

    # Trava 1 byte longe do texto: no Windows a região travada não pode ser lida por outro processo
    _POSICAO = 1 << 20

    def _travar(fd: int) -> bool:
        os.lseek(fd, _POSICAO, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _destravar(fd: int) -> None:
        os.lseek(fd, _POSICAO, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _travar(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _destravar(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
