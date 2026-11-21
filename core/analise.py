"""Análise técnica (docs/analise_tecnica.md): qual motor o robô usa, decidida ANTES do desenvolvimento.

    uv run python -m core checar-analise   # trava do /nova-automacao: só passa com a análise decidida

Motores:
- navegador: Playwright lendo a tela (core.runner.executar + Page Objects)
- http:      só requests, sem navegador (core.runner.executar_http + clientes em projeto/api/)
- hibrido:   login pela tela e dados pela API (executar + core.http.sessao_http_do_navegador)
- download:  o sistema já gera o relatório; o robô só baixa (executar + BasePage.baixar)
"""

import re
from dataclasses import dataclass
from pathlib import Path

ARQUIVO_ANALISE = Path("docs/analise_tecnica.md")
PASTA_PADROES = Path("docs/padroes")
MOTORES = ("navegador", "http", "hibrido", "download")
STATUS_ANALISE = ("pendente_insumos", "decidida")

_RE_CAMPO = re.compile(r"^\*\*{rotulo}:\*\*\s*`?([\w_]+)`?", re.MULTILINE)
_RE_COMENTARIO = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class Analise:
    status: str | None
    motor: str | None


def ler(raiz: Path) -> Analise | None:
    arquivo = raiz / ARQUIVO_ANALISE
    if not arquivo.exists():
        return None
    texto = _RE_COMENTARIO.sub("", arquivo.read_text(encoding="utf-8"))
    return Analise(_campo(texto, "Status"), _campo(texto, "Motor"))


def checar(raiz: Path) -> list[str]:
    """O que impede começar o desenvolvimento pelo lado técnico. Lista vazia = pode seguir."""
    analise = ler(raiz)
    if analise is None:
        return [f"{ARQUIVO_ANALISE.as_posix()} não existe. Rode /analisar-tecnica."]
    problemas = []
    if analise.status != "decidida":
        problemas.append(
            f"Análise técnica com status {analise.status!r}: precisa estar 'decidida'. "
            "Entregue os insumos pendentes listados nela e rode /analisar-tecnica de novo."
        )
    if analise.motor not in MOTORES:
        problemas.append(
            f"Motor {analise.motor!r} inválido na análise técnica: use um de {', '.join(MOTORES)}."
        )
    return problemas


def documentos_da_area(raiz: Path) -> list[Path]:
    """Documentos de padrão da área (boas práticas) em docs/padroes/, além do README."""
    pasta = raiz / PASTA_PADROES
    return sorted(p for p in pasta.glob("*.md") if p.name.lower() != "readme.md") if pasta.is_dir() else []


def _campo(texto: str, rotulo: str) -> str | None:
    achado = re.compile(_RE_CAMPO.pattern.format(rotulo=rotulo), re.MULTILINE).search(texto)
    return achado.group(1).lower() if achado else None
