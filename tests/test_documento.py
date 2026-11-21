"""importar-documento: PDD do cliente em Word -> Markdown com as imagens no lugar certo."""

import struct
import zlib
from pathlib import Path

import pytest
from docx import Document

from core.documento import DocumentoInvalido, importar


def _png(cor: int) -> bytes:
    """PNG 1x1 válido, diferente por cor (o Word guarda imagens iguais uma vez só)."""

    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))

    cabecalho = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel = zlib.compress(bytes([0, cor, 0, 0]))
    return b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", cabecalho) + bloco(b"IDAT", pixel) + bloco(b"IEND", b"")


def _docx_do_cliente(pasta: Path) -> Path:
    imagens = []
    for numero in (1, 2):
        imagem = pasta / f"tela{numero}.png"
        imagem.write_bytes(_png(numero * 100))
        imagens.append(imagem)
    documento = Document()
    documento.add_heading("Passo a passo da consulta", level=1)
    documento.add_paragraph("Acessar o portal com o usuário do robô.")
    documento.add_paragraph("Informar a agência", style="List Bullet")
    documento.add_picture(str(imagens[0]))
    documento.add_heading("Resultado", level=2)
    tabela = documento.add_table(rows=2, cols=2)
    tabela.cell(0, 0).text, tabela.cell(0, 1).text = "Campo", "Formato"
    tabela.cell(1, 0).text, tabela.cell(1, 1).text = "Valor", "R$ 0,00 | duas casas"
    tabela.cell(1, 1).paragraphs[0].add_run().add_picture(str(imagens[1]))
    arquivo = pasta / "documento_cliente" / "pdd_cliente.docx"
    arquivo.parent.mkdir()
    documento.save(str(arquivo))
    return arquivo


def test_converte_texto_e_imagens_na_ordem(tmp_path: Path) -> None:
    arquivo = _docx_do_cliente(tmp_path)
    pasta_imagens = tmp_path / "screenshots"

    md, imagens = importar(arquivo, pasta_imagens=pasta_imagens)

    assert md == arquivo.with_suffix(".md")
    assert [i.name for i in imagens] == ["pdd_cliente_01.png", "pdd_cliente_02.png"]
    assert all(i.read_bytes().startswith(b"\x89PNG") for i in imagens)
    texto = md.read_text(encoding="utf-8")
    ordem = [
        "# Passo a passo da consulta",
        "Acessar o portal",
        "- Informar a agência",
        "![Imagem 01](../screenshots/pdd_cliente_01.png)",
        "## Resultado",
        "| Campo | Formato |",
        "| Valor | R$ 0,00 \\| duas casas |",
        "![Imagem 02](../screenshots/pdd_cliente_02.png)",
    ]
    posicoes = [texto.index(trecho) for trecho in ordem]
    assert posicoes == sorted(posicoes)


def test_rodar_de_novo_substitui_sem_duplicar(tmp_path: Path) -> None:
    arquivo = _docx_do_cliente(tmp_path)
    importar(arquivo, pasta_imagens=tmp_path / "screenshots")

    _, imagens = importar(arquivo, pasta_imagens=tmp_path / "screenshots")

    assert len(imagens) == 2 and len(list((tmp_path / "screenshots").iterdir())) == 2


@pytest.mark.parametrize("nome", ["pdd.pdf", "pdd.doc"])
def test_so_aceita_docx(tmp_path: Path, nome: str) -> None:
    (tmp_path / nome).write_bytes(b"x")
    with pytest.raises(DocumentoInvalido, match="salve como .docx"):
        importar(tmp_path / nome)
