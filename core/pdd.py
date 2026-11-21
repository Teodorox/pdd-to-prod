"""Ferramentas do PDD (docs/pdd.md + docs/duvidas.md), usadas no desenvolvimento, nunca em produção.

uv run python -m core checar-pdd      # trava: só passa com PDD aprovado e nenhuma dúvida pendente
uv run python -m core exportar-pdd    # gera o .docx para enviar ao cliente
"""

import re
from pathlib import Path
from typing import Any

STATUS_PDD = ("rascunho", "em_validacao", "enviado", "aprovado", "reprovado")
STATUS_DUVIDA_PENDENTE = ("aberta", "respondida")  # respondida = ainda não aplicada no PDD

_RE_STATUS = re.compile(r"^\*\*Status:\*\*\s*`?([\w_]+)`?", re.MULTILINE)
_RE_MARCADOR = re.compile(r"\[DÚVIDA (D-\d+)\]")
_RE_COMENTARIO = re.compile(r"<!--.*?-->", re.DOTALL)


def status_pdd(texto: str) -> str | None:
    achado = _RE_STATUS.search(texto)
    return achado.group(1) if achado else None


def duvidas(texto_duvidas: str) -> list[dict[str, str]]:
    """Linhas da tabela de docs/duvidas.md como dicts (chave = cabeçalho em minúsculas)."""
    linhas = [linha for linha in texto_duvidas.splitlines() if linha.strip().startswith("|")]
    if not linhas:
        return []
    cabecalho = [c.strip().lower() for c in linhas[0].strip("| ").split("|")]
    tabela = []
    for linha in linhas[2:]:
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        tabela.append(dict(zip(cabecalho, celulas, strict=False)))
    return tabela


def duvidas_pendentes(texto_duvidas: str) -> list[str]:
    """IDs das dúvidas com status aberta/respondida na tabela de docs/duvidas.md."""
    return [d["id"] for d in duvidas(texto_duvidas) if d.get("status", "").lower() in STATUS_DUVIDA_PENDENTE]


def checar(pdd: Path, duvidas: Path) -> list[str]:
    """Lista o que impede começar o desenvolvimento. Lista vazia = pode seguir."""
    if not pdd.exists():
        return [f"{pdd} não existe. Gere com /gerar-pdd."]
    texto = _RE_COMENTARIO.sub("", pdd.read_text(encoding="utf-8"))
    problemas = []
    status = status_pdd(texto)
    if status != "aprovado":
        problemas.append(f"PDD com status {status!r}: precisa estar 'aprovado' pelo cliente.")
    marcadores = sorted(set(_RE_MARCADOR.findall(texto)))
    if marcadores:
        problemas.append(f"PDD ainda cita dúvidas: {', '.join(marcadores)}.")
    if duvidas.exists():
        pendentes = duvidas_pendentes(_RE_COMENTARIO.sub("", duvidas.read_text(encoding="utf-8")))
        if pendentes:
            problemas.append(
                f"Dúvidas não aplicadas no PDD: {', '.join(pendentes)}. Rode /aplicar-respostas."
            )
    return problemas


def exportar_docx(pdd: Path, destino: Path, *, modelo: Path | None = None, rascunho: bool = False) -> Path:
    """Converte o pdd.md em .docx. Com `modelo`, usa os estilos (fontes, capa, cabeçalho) do Word da empresa.

    Recusa exportar com marcadores de dúvida, a não ser como rascunho (para revisão interna).
    """
    from docx import Document

    texto = _RE_COMENTARIO.sub("", pdd.read_text(encoding="utf-8"))
    marcadores = sorted(set(_RE_MARCADOR.findall(texto)))
    if marcadores and not rascunho:
        raise ValueError(
            f"PDD ainda cita dúvidas ({', '.join(marcadores)}). Resolva ou exporte com --rascunho."
        )

    documento = Document(str(modelo)) if modelo else Document()
    estilos = {estilo.name for estilo in documento.styles}
    linhas = texto.splitlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i].rstrip()
        if linha.startswith("|"):
            tabela = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                tabela.append(linhas[i])
                i += 1
            _tabela(documento, tabela, estilos)
            continue
        if titulo := re.match(r"^(#{1,4})\s+(.*)", linha):
            documento.add_heading(_sem_markdown(titulo.group(2)), level=len(titulo.group(1)) - 1)
        elif item := re.match(r"^\s*[-*]\s+(.*)", linha):
            _paragrafo(documento, item.group(1), "List Bullet", estilos)
        elif item := re.match(r"^\s*\d+\.\s+(.*)", linha):
            _paragrafo(documento, item.group(1), "List Number", estilos)
        elif linha.startswith(">"):
            _paragrafo(documento, linha.lstrip("> "), "Quote", estilos)
        elif linha.strip():
            _paragrafo(documento, linha, None, estilos)
        i += 1

    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(str(destino))
    return destino


def _paragrafo(documento: Any, texto: str, estilo: str | None, estilos: set[str]) -> None:
    paragrafo = documento.add_paragraph(style=estilo if estilo in estilos else None)
    # **negrito** vira run em negrito; o resto do markdown é removido
    for parte in re.split(r"(\*\*[^*]+\*\*)", texto):
        if parte.startswith("**") and parte.endswith("**"):
            paragrafo.add_run(_sem_markdown(parte[2:-2])).bold = True
        elif parte:
            paragrafo.add_run(_sem_markdown(parte))


def _tabela(documento: Any, linhas: list[str], estilos: set[str]) -> None:
    celulas = [[c.strip() for c in linha.strip().strip("|").split("|")] for linha in linhas]
    celulas = [linha for linha in celulas if not all(re.fullmatch(r":?-+:?", c) for c in linha)]
    colunas = max(len(linha) for linha in celulas)
    tabela = documento.add_table(rows=0, cols=colunas)
    if "Table Grid" in estilos:
        tabela.style = "Table Grid"
    for numero, linha in enumerate(celulas):
        cells = tabela.add_row().cells
        for coluna, texto in enumerate(linha):
            cells[coluna].text = _sem_markdown(texto)
            if numero == 0:
                for run in cells[coluna].paragraphs[0].runs:
                    run.bold = True


def _sem_markdown(texto: str) -> str:
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)  # [texto](link) -> texto
    texto = re.sub(r"\*\*(.+?)\*\*|`([^`]+)`", lambda m: m.group(1) or m.group(2), texto)
    texto = re.sub(r"(?<!\w)[*_]([^*_]+)[*_](?!\w)", r"\1", texto)  # *itálico* / _itálico_ (não snake_case)
    return texto.replace("<br>", "\n")
