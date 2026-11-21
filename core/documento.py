"""Converte o documento do cliente (PDD ou passo a passo em Word) em Markdown, com as imagens em arquivos.

    uv run python -m core importar-documento docs/documento_cliente/pdd_cliente.docx

Gera:
- `docs/documento_cliente/pdd_cliente.md`: o texto na ordem do Word (títulos, listas e tabelas), com a marca
  de cada imagem no lugar exato dela. É o que o /gerar-pdd lê.
- `docs/screenshots/pdd_cliente_01.png`, `_02`...: as imagens, numeradas na ordem em que aparecem.

Só .docx. PDF perde a posição das imagens: peça o Word ao cliente (ou abra o PDF no Word e salve como .docx,
conferindo o resultado). As duas pastas não vão para o git: os prints costumam ter dados reais.
"""

import os
import re
from pathlib import Path
from typing import Any

PASTA_IMAGENS = Path("docs/screenshots")
_NIVEL_TITULO = re.compile(r"^(?:heading|título|titulo)\s*(\d)$", re.IGNORECASE)


class DocumentoInvalido(Exception):
    pass


def importar(arquivo: Path, *, pasta_imagens: Path = PASTA_IMAGENS) -> tuple[Path, list[Path]]:
    """Grava o .md ao lado do .docx e as imagens em `pasta_imagens`. Devolve o .md e as imagens."""
    if arquivo.suffix.lower() != ".docx":
        raise DocumentoInvalido(
            f"{arquivo.name}: só .docx. PDF ou .doc: abra no Word, salve como .docx e confira o resultado."
        )
    if not arquivo.exists():
        raise DocumentoInvalido(f"Arquivo não encontrado: {arquivo}")
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise DocumentoInvalido(
            "Falta o python-docx. Rode: uv sync (ele vem nas dependências de dev)."
        ) from exc

    documento = Document(str(arquivo))
    destino_md = arquivo.with_suffix(".md")
    conversor = _Conversor(documento, arquivo.stem, pasta_imagens, destino_md.parent, qn)
    linhas = [
        (
            f"<!-- Gerado por `core importar-documento` a partir de {arquivo.name}. "
            "Não edite: corrija o Word e rode de novo. -->"
        ),
        "",
    ]
    for elemento in documento.element.body.iterchildren():
        if elemento.tag == qn("w:p"):
            linhas += conversor.paragrafo(Paragraph(elemento, documento))
        elif elemento.tag == qn("w:tbl"):
            linhas += conversor.tabela(Table(elemento, documento))
    texto = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip() + "\n"
    destino_md.write_text(texto, encoding="utf-8")
    return destino_md, conversor.imagens


class _Conversor:
    def __init__(self, documento: Any, nome: str, pasta_imagens: Path, pasta_md: Path, qn: Any) -> None:
        self.documento = documento
        self.nome = nome
        self.pasta_imagens = pasta_imagens
        self.pasta_md = pasta_md
        self.qn = qn
        self.imagens: list[Path] = []
        self._por_id: dict[str, Path] = {}

    def paragrafo(self, paragrafo: Any) -> list[str]:
        texto = paragrafo.text.strip()
        estilo = paragrafo.style.name if paragrafo.style is not None else ""
        linhas = []
        if texto:
            nivel = _NIVEL_TITULO.match(estilo)
            if nivel:
                linhas += ["", "#" * min(int(nivel.group(1)), 6) + " " + texto, ""]
            elif estilo.lower() in ("title", "título", "titulo"):
                linhas += ["", "# " + texto, ""]
            elif self._lista(paragrafo, estilo):
                linhas.append("- " + texto)
            else:
                linhas += [texto, ""]
        for imagem in self._imagens(paragrafo._element):
            linhas += [self._marca(imagem), ""]
        return linhas

    def tabela(self, tabela: Any) -> list[str]:
        linhas, imagens = [""], []
        for numero, linha in enumerate(tabela.rows):
            celulas = []
            for celula in linha.cells:
                celulas.append(" ".join(celula.text.split()).replace("|", "\\|"))
                imagens += [i for i in self._imagens(celula._element) if i not in imagens]
            linhas.append("| " + " | ".join(celulas) + " |")
            if numero == 0:
                linhas.append("|" + "---|" * len(celulas))
        linhas.append("")
        for imagem in imagens:
            linhas += [self._marca(imagem), ""]
        return linhas

    def _lista(self, paragrafo: Any, estilo: str) -> bool:
        propriedades = paragrafo._element.pPr
        numerado = propriedades is not None and propriedades.find(self.qn("w:numPr")) is not None
        return numerado or "list" in estilo.lower() or "lista" in estilo.lower()

    def _imagens(self, elemento: Any) -> list[Path]:
        """Imagens do elemento, na ordem do documento (desenho moderno e VML de Word antigo)."""
        ids = [b.get(self.qn("r:embed")) for b in elemento.iter(self.qn("a:blip"))]
        ids += [v.get(self.qn("r:id")) for v in elemento.iter("{urn:schemas-microsoft-com:vml}imagedata")]
        return [self._salvar(i) for i in ids if i]

    def _salvar(self, id_relacao: str) -> Path:
        if id_relacao in self._por_id:  # a mesma imagem usada duas vezes vira um arquivo só
            return self._por_id[id_relacao]
        parte = self.documento.part.related_parts[id_relacao]
        extensao = Path(str(parte.partname)).suffix.lower() or ".png"
        destino = self.pasta_imagens / f"{self.nome}_{len(self.imagens) + 1:02d}{extensao}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(parte.blob)
        self.imagens.append(destino)
        self._por_id[id_relacao] = destino
        return destino

    def _marca(self, imagem: Path) -> str:
        numero = self.imagens.index(imagem) + 1
        caminho = Path(os.path.relpath(imagem, self.pasta_md)).as_posix()
        return f"![Imagem {numero:02d}]({caminho})"
