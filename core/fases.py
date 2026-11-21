"""Fases do robô, do levantamento à produção, registradas pelo próprio fluxo de trabalho.

Cada fase é concluída por uma etapa do fluxo (prompt do Copilot ou script), nunca à mão:
    uv run python -m core concluir-fase <fase> --obs "evidência"   # confere o pré-requisito antes de registrar
    uv run python -m core reabrir-fase <fase> --obs "motivo"        # ex.: PDD reprovado pelo cliente
    uv run python -m core fases                                     # onde o robô está e o próximo passo

O histórico fica em docs/fases.json (versionado). Não edite esse arquivo: use os comandos acima.
"""

import getpass
import json
import logging
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from core import analise
from core.config import Settings
from core.pdd import STATUS_DUVIDA_PENDENTE, checar, duvidas, status_pdd

MARCA_MODELO = "<nome do processo>"  # título do docs/pdd.md enquanto ainda é o modelo
ARQUIVO_FASES = Path("docs/fases.json")


@dataclass(frozen=True)
class DefinicaoFase:
    chave: str
    nome: str
    como_concluir: str  # próximo passo enquanto for a fase atual


FASES = (
    DefinicaoFase(
        "levantamento",
        "Levantamento",
        "Salve a transcrição da call em docs/transcricao/ (ou o PDD do cliente em docs/documento_cliente/) "
        "e rode /gerar-pdd.",
    ),
    DefinicaoFase(
        "pdd",
        "PDD enviado ao cliente",
        "Revise o PDD, responda as dúvidas do dev (/aplicar-respostas) e rode /preparar-envio-pdd.",
    ),
    DefinicaoFase(
        "aprovacao",
        "Aprovação do cliente",
        "Quando o cliente responder o e-mail, rode /registrar-aprovacao e cole a resposta.",
    ),
    DefinicaoFase(
        "desenvolvimento",
        "Desenvolvimento",
        "Rode /nova-automacao e, quando terminar, /revisar-automacao.",
    ),
    DefinicaoFase(
        "homologacao",
        "Homologação",
        "Rode .\\scripts\\executar.ps1 -DryRun, valide a saída com a área e rode /registrar-homologacao.",
    ),
    DefinicaoFase(
        "producao",
        "Produção",
        "Agende como administrador: .\\scripts\\agendar.ps1 instalar (ele registra esta fase).",
    ),
)
CHAVES = tuple(f.chave for f in FASES)


class Situacao(StrEnum):
    FEITA = "x"
    ATUAL = ">"
    PENDENTE = " "


@dataclass(frozen=True)
class Fase:
    nome: str
    situacao: Situacao
    detalhe: str = ""


@dataclass(frozen=True)
class Diagnostico:
    fases: list[Fase]
    proximo_passo: str
    avisos: list[str]

    @property
    def atual(self) -> Fase | None:
        return next((f for f in self.fases if f.situacao is Situacao.ATUAL), None)


class FaseRecusada(Exception):
    """O pré-requisito da fase não foi cumprido. A mensagem diz o que falta."""


# ---------------------------------------------------------------- registro


def concluir(
    raiz: Path,
    estado_db: Path,
    chave: str,
    obs: str,
    *,
    verificar_codigo: Callable[[Path], list[str]] | None = None,
) -> str:
    """Registra a fase como concluída, se a anterior estiver concluída e o pré-requisito for cumprido."""
    definicao = _definicao(chave)
    historico = _ler_historico(raiz)
    concluidas = _concluidas(historico)
    if chave in concluidas:
        return f"{definicao.nome} já estava concluída em {_data(concluidas[chave]['em'])}."
    indice = CHAVES.index(chave)
    if indice > 0 and CHAVES[indice - 1] not in concluidas:
        raise FaseRecusada(f"Conclua antes a fase '{FASES[indice - 1].nome}'.")
    problemas = _pre_requisitos(raiz, estado_db, chave, concluidas, verificar_codigo or _rodar_testes_e_lint)
    if problemas:
        raise FaseRecusada(" ".join(problemas))
    _anotar(raiz, historico, chave, "concluida", obs)
    return f"Fase '{definicao.nome}' concluída."


def reabrir(raiz: Path, chave: str, obs: str) -> str:
    """Reabre a fase e todas as seguintes que estavam concluídas (ex.: PDD reprovado reabre o PDD)."""
    _definicao(chave)
    historico = _ler_historico(raiz)
    concluidas = _concluidas(historico)
    reabertas = [c for c in CHAVES[CHAVES.index(chave) :] if c in concluidas]
    for c in reabertas:
        _anotar(raiz, historico, c, "reaberta", obs)
    if not reabertas:
        return "Nada a reabrir."
    return "Reaberta(s): " + ", ".join(_definicao(c).nome for c in reabertas) + "."


def arquivo_execucoes(estado_db: Path) -> Path:
    return estado_db.with_suffix(".execucoes.json")


def registrar_execucao(settings: Settings, status: str, registros: int) -> None:
    """Guarda a última execução (DRY_RUN e real, separadas). Chamado pelo runner; nunca derruba o robô."""
    arquivo = arquivo_execucoes(settings.estado_db)
    tipo = "dry_run" if settings.dry_run else "real"
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
        dados[tipo] = {
            "fim": datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "registros": registros,
        }
        _gravar_json(arquivo, dados)
    except (OSError, ValueError) as exc:
        logging.getLogger(settings.automacao_nome).warning("Não foi possível registrar a execução: %s", exc)


# ---------------------------------------------------------------- leitura


def historico(raiz: Path) -> list[dict[str, str]]:
    """Registros de docs/fases.json, do mais antigo ao mais novo."""
    return _ler_historico(raiz)


def avaliar(raiz: Path, estado_db: Path) -> Diagnostico:
    concluidas = _concluidas(_ler_historico(raiz))
    fases: list[Fase] = []
    proximo = "Robô em produção. Acompanhe pelo painel de monitoramento (ou .\\scripts\\agendar.ps1 status)."
    atual_definida = False
    for definicao in FASES:
        registro = concluidas.get(definicao.chave)
        if registro and not atual_definida:
            fases.append(Fase(definicao.nome, Situacao.FEITA, _resumo_registro(registro)))
        elif not atual_definida:
            atual_definida = True
            fases.append(
                Fase(definicao.nome, Situacao.ATUAL, _situacao_atual(raiz, estado_db, definicao.chave))
            )
            proximo = definicao.como_concluir
            if definicao.chave == "desenvolvimento" and analise.checar(raiz):
                proximo = (
                    "Rode /analisar-tecnica: ela escolhe o motor (navegador ou requests) e diz quais insumos "
                    "entregar (ex.: .har em docs/requisicoes/). Depois /nova-automacao."
                )
        else:
            fases.append(Fase(definicao.nome, Situacao.PENDENTE))
    return Diagnostico(fases, proximo, _avisos(raiz, estado_db, concluidas))


def formatar(diagnostico: Diagnostico, nome: str) -> str:
    largura = max(len(f.nome) for f in diagnostico.fases) + 6  # "6. " + 3 espaços até o detalhe
    linhas = [f"Robô: {nome}", ""]
    for numero, fase in enumerate(diagnostico.fases, start=1):
        rotulo = f"{numero}. {fase.nome}"
        linhas.append(f"  [{fase.situacao}] {rotulo:<{largura}}{fase.detalhe}".rstrip())
    linhas += ["", f"Próximo passo: {diagnostico.proximo_passo}"]
    linhas += [f"ATENÇÃO: {aviso}" for aviso in diagnostico.avisos]
    return "\n".join(linhas)


# ---------------------------------------------------------------- pré-requisitos


def _pre_requisitos(
    raiz: Path,
    estado_db: Path,
    chave: str,
    concluidas: dict[str, dict[str, str]],
    verificar_codigo: Callable[[Path], list[str]],
) -> list[str]:
    pdd, arquivo_duvidas = raiz / "docs" / "pdd.md", raiz / "docs" / "duvidas.md"
    if chave == "levantamento":
        return [] if _pdd_preenchido(pdd) else ["docs/pdd.md ainda é o modelo: rode /gerar-pdd."]
    if chave == "pdd":
        problemas = [] if _pdd_preenchido(pdd) else ["docs/pdd.md ainda é o modelo."]
        do_dev = [d["id"] for d in _pendentes(arquivo_duvidas) if d.get("quem responde", "").lower() == "dev"]
        if do_dev:
            problemas.append(f"Dúvidas do dev pendentes: {', '.join(do_dev)}.")
        status = _status(pdd)
        if status != "enviado":
            problemas.append(f"PDD com status {status!r}: precisa estar 'enviado'.")
        return problemas
    if chave == "aprovacao":
        return checar(pdd, arquivo_duvidas)
    if chave == "desenvolvimento":
        return checar(pdd, arquivo_duvidas) or analise.checar(raiz) or verificar_codigo(raiz)
    if chave == "homologacao":
        dry_run = _ler_json(arquivo_execucoes(_absoluto(raiz, estado_db))).get("dry_run")
        fim_desenvolvimento = concluidas["desenvolvimento"]["em"]
        if not dry_run or dry_run["status"] != "sucesso" or dry_run["fim"] < fim_desenvolvimento:
            fim = _data(fim_desenvolvimento)
            return [
                f"Nenhum DRY_RUN com sucesso depois do fim do desenvolvimento ({fim}). Rode .\\scripts\\executar.ps1 -DryRun."
            ]
        return []
    # producao
    return [] if _agendamentos(raiz) else ["Agendamento não criado: rode .\\scripts\\agendar.ps1 instalar."]


def _rodar_testes_e_lint(raiz: Path) -> list[str]:
    problemas = []
    for nome, comando in (
        ("Testes", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]),
        ("Lint", [sys.executable, "-m", "ruff", "check", "."]),
    ):
        processo = subprocess.run(comando, cwd=raiz, capture_output=True, text=True, check=False)
        if processo.returncode != 0:
            ultima = (processo.stdout.strip().splitlines() or ["sem saída"])[-1]
            problemas.append(f"{nome} falhando ({ultima}).")
    return problemas


# ---------------------------------------------------------------- detalhes e avisos


def _situacao_atual(raiz: Path, estado_db: Path, chave: str) -> str:
    """Informação deduzida que ajuda na fase atual (não decide nada)."""
    if chave == "levantamento":
        transcricoes = sorted(
            p.name for p in (raiz / "docs" / "transcricao").glob("*") if p.name != ".gitkeep"
        )
        return f"transcrição: {', '.join(transcricoes)}" if transcricoes else ""
    if chave == "pdd":
        contagem: dict[str, int] = {}
        for duvida in _pendentes(raiz / "docs" / "duvidas.md"):
            quem = duvida.get("quem responde", "").lower() or "?"
            contagem[quem] = contagem.get(quem, 0) + 1
        partes = [f"status {_status(raiz / 'docs' / 'pdd.md')}"]
        if contagem:
            quem = ", ".join(f"{n} do {q}" for q, n in sorted(contagem.items()))
            partes.append(f"{sum(contagem.values())} dúvida(s) pendente(s): {quem}")
        return "; ".join(partes)
    if chave == "aprovacao":
        return "aguardando resposta do cliente"
    if chave == "desenvolvimento":
        lida = analise.ler(raiz)
        partes = [
            f"análise: motor {lida.motor} ({lida.status})" if lida else "análise técnica pendente",
            "padrões da área: "
            + (", ".join(p.name for p in analise.documentos_da_area(raiz)) or "nenhum em docs/padroes/"),
        ]
        return "; ".join(partes)
    if chave == "homologacao":
        execucoes = _ler_json(arquivo_execucoes(_absoluto(raiz, estado_db)))
        partes = [
            f"{rotulo} {_data(e['fim'])}: {e['status']} ({e['registros']} reg.)"
            for rotulo, e in (
                ("último DRY_RUN", execucoes.get("dry_run")),
                ("última real", execucoes.get("real")),
            )
            if e
        ]
        return "; ".join(partes)
    return ""


def _avisos(raiz: Path, estado_db: Path, concluidas: dict[str, dict[str, str]]) -> list[str]:
    """Contradições entre o que foi registrado e o estado atual do projeto."""
    avisos = []
    if "aprovacao" in concluidas:
        problemas = checar(raiz / "docs" / "pdd.md", raiz / "docs" / "duvidas.md")
        if problemas:
            avisos.append(f"o PDD mudou depois da aprovação: {' '.join(problemas)}")
    if "producao" in concluidas and not _agendamentos(raiz):
        avisos.append("fase Produção registrada, mas o agendamento não foi criado nesta pasta.")
    return avisos


def _resumo_registro(registro: dict[str, str]) -> str:
    obs = registro["obs"] if len(registro["obs"]) <= 60 else registro["obs"][:57] + "..."
    return f"{_data(registro['em'])} {registro['por']}: {obs}"


# ---------------------------------------------------------------- arquivos


def _definicao(chave: str) -> DefinicaoFase:
    for definicao in FASES:
        if definicao.chave == chave:
            return definicao
    raise ValueError(f"Fase desconhecida: {chave!r}. Use: {', '.join(CHAVES)}")


def _ler_historico(raiz: Path) -> list[dict[str, str]]:
    return _ler_json(raiz / ARQUIVO_FASES).get("historico", [])


def _concluidas(historico: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Fase -> registro de conclusão, considerando só o último registro de cada fase."""
    ultimo = {registro["fase"]: registro for registro in historico}
    return {fase: registro for fase, registro in ultimo.items() if registro["acao"] == "concluida"}


def _anotar(raiz: Path, historico: list[dict[str, str]], chave: str, acao: str, obs: str) -> None:
    historico.append(
        {
            "fase": chave,
            "acao": acao,
            "em": datetime.now().isoformat(timespec="seconds"),
            "por": getpass.getuser(),
            "obs": obs.strip(),
        }
    )
    _gravar_json(
        raiz / ARQUIVO_FASES,
        {"aviso": "Gerado por 'python -m core concluir-fase'. Não edite.", "historico": historico},
    )


def _pendentes(arquivo_duvidas: Path) -> list[dict[str, str]]:
    if not arquivo_duvidas.exists():
        return []
    return [
        d
        for d in duvidas(arquivo_duvidas.read_text(encoding="utf-8"))
        if d.get("status", "").lower() in STATUS_DUVIDA_PENDENTE
    ]


def _pdd_preenchido(pdd: Path) -> bool:
    return pdd.exists() and MARCA_MODELO not in pdd.read_text(encoding="utf-8")


def _status(pdd: Path) -> str | None:
    return status_pdd(pdd.read_text(encoding="utf-8")) if pdd.exists() else None


def _agendamentos(raiz: Path) -> list[Path]:
    """Cópia da tarefa gravada pelo agendar.ps1 (agendamento/robo-<nome>.xml)."""
    return sorted((raiz / "agendamento").glob("robo-*.xml"))


def _absoluto(raiz: Path, caminho: Path) -> Path:
    return caminho if caminho.is_absolute() else raiz / caminho


def _ler_json(arquivo: Path) -> dict[str, Any]:
    if not arquivo.exists():
        return {}
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _gravar_json(arquivo: Path, dados: dict[str, Any]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_name(arquivo.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(arquivo)


def _data(iso: str) -> str:
    return f"{datetime.fromisoformat(iso):%d/%m %H:%M}"
