"""Destinos de saída e ferramentas do PDD."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pydantic import BaseModel, SecretStr
from sqlalchemy import create_engine, text

from core.pdd import checar, duvidas_pendentes, exportar_docx
from core.saida import DestinoBanco, DestinoCsv, DestinoExcel
from core.texto import data_br


class Linha(BaseModel):
    data: date
    descricao: str
    valor: Decimal


LINHAS = [Linha(data=date(2026, 10, 1), descricao="A", valor=Decimal("1234.50"))]


def test_data_br() -> None:
    assert data_br(" 31/10/2026 ") == date(2026, 10, 31)
    with pytest.raises(ValueError):
        data_br("2026-10-31")


def test_csv_formato_br_e_reprocessar_substitui(tmp_path: Path) -> None:
    destino = DestinoCsv(tmp_path, Linha, prefixo="saida_")
    destino.gravar("ag/01", LINHAS * 2)
    destino.gravar("ag/01", LINHAS)

    arquivo = tmp_path / "saida_ag_01.csv"
    assert arquivo.read_text(encoding="utf-8-sig").splitlines() == [
        "data;descricao;valor",
        "01/10/2026;A;1234,50",
    ]
    assert [p.name for p in tmp_path.iterdir()] == ["saida_ag_01.csv"]  # nenhum .tmp sobrando


def test_excel_tipos_nativos(tmp_path: Path) -> None:
    DestinoExcel(tmp_path, Linha).gravar("X", LINHAS)

    aba = load_workbook(tmp_path / "X.xlsx").active
    assert [c.value for c in aba[1]] == ["data", "descricao", "valor"]
    assert aba["C2"].value == 1234.5


def test_banco_substitui_so_a_chave_do_item(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'saida.db'}"
    with create_engine(url).begin() as con:
        con.execute(text("CREATE TABLE mov (consulta TEXT, data DATE, descricao TEXT, valor NUMERIC(15, 2))"))
    destino = DestinoBanco(SecretStr(url), "mov", coluna_chave="consulta")

    destino.gravar("A", LINHAS * 3)
    destino.gravar("B", LINHAS)
    destino.gravar("A", LINHAS)

    with create_engine(url).connect() as con:
        contagem = dict(con.execute(text("SELECT consulta, COUNT(*) FROM mov GROUP BY consulta")).all())
    assert contagem == {"A": 1, "B": 1}


DUVIDAS = """| ID | Status | Pergunta | Resposta |
|---|---|---|---|
| D-01 | aplicada | a? | sim |
| D-02 | aberta | b? | |
| D-03 | Respondida | c? | não |
"""


def test_duvidas_pendentes() -> None:
    assert duvidas_pendentes(DUVIDAS) == ["D-02", "D-03"]


def test_checar_pdd(tmp_path: Path) -> None:
    pdd, duvidas = tmp_path / "pdd.md", tmp_path / "duvidas.md"
    assert checar(pdd, duvidas) == [f"{pdd} não existe. Gere com /gerar-pdd."]

    pdd.write_text(
        "# PDD\n<!-- [DÚVIDA D-09] em comentário não conta -->\n**Status:** rascunho\nSaída: [DÚVIDA D-02]\n",
        encoding="utf-8",
    )
    duvidas.write_text(DUVIDAS, encoding="utf-8")
    problemas = checar(pdd, duvidas)
    assert len(problemas) == 3
    assert "'rascunho'" in problemas[0]
    assert "D-02" in problemas[1] and "D-09" not in problemas[1]
    assert "D-02, D-03" in problemas[2]

    pdd.write_text("# PDD\n**Status:** aprovado\nSaída: CSV\n", encoding="utf-8")
    duvidas.write_text(
        DUVIDAS.replace("aberta", "aplicada").replace("Respondida", "aplicada"), encoding="utf-8"
    )
    assert checar(pdd, duvidas) == []


def test_exportar_docx(tmp_path: Path) -> None:
    from docx import Document

    pdd = tmp_path / "pdd.md"
    pdd.write_text(
        "# PDD: Extrato\n\n**Status:** em_validacao\n\n## 1. Escopo\n\n- item **um**\n1. passo\n\n"
        "| Campo | Tipo |\n|---|---|\n| data | data |\n\nSaída: [DÚVIDA D-01]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="D-01"):
        exportar_docx(pdd, tmp_path / "PDD.docx")

    documento = Document(str(exportar_docx(pdd, tmp_path / "PDD.docx", rascunho=True)))
    textos = [p.text for p in documento.paragraphs]
    assert textos[:3] == ["PDD: Extrato", "Status: em_validacao", "1. Escopo"]
    assert "item um" in textos
    assert documento.tables[0].cell(1, 0).text == "data"
