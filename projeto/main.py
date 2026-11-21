"""Entrypoint: uv run python -m projeto.main  (código de saída 1 se algo falhou, para a tarefa agendada perceber)."""

import sys
from functools import partial

from core.logger import configurar_logs
from core.runner import executar
from core.saida import DestinoCsv
from projeto.config import ProjetoSettings
from projeto.entrada import ler_consultas
from projeto.flows.extrair import extrair_movimentacoes, fazer_login
from projeto.modelos import Movimentacao


def main() -> int:
    settings = ProjetoSettings()
    configurar_logs(settings.automacao_nome, settings.logs_dir)
    consultas = ler_consultas(settings.arquivo_entrada)
    destino = DestinoCsv(settings.saida_dir, Movimentacao, prefixo="movimentacoes_")
    resultado = executar(
        consultas,
        partial(extrair_movimentacoes, destino=destino),
        settings,
        preparar=partial(
            fazer_login, usuario=settings.portal_usuario, senha=settings.portal_senha.get_secret_value()
        ),
    )
    return 0 if resultado.sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
