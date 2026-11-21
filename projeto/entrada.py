"""Leitura da entrada. Valida o arquivo INTEIRO antes de começar: uma linha inválida aborta tudo."""

import csv
from pathlib import Path

from projeto.modelos import Consulta


def ler_consultas(arquivo: Path) -> list[Consulta]:
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        consultas = [
            Consulta(id=f"{linha['agencia']}_{linha['competencia']}", **linha)
            for linha in csv.DictReader(f, delimiter=";")
        ]
    ids = [c.id for c in consultas]
    assert len(ids) == len(set(ids)), f"Consultas duplicadas na entrada {arquivo}"
    return consultas
