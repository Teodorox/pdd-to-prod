"""CLI do padrão (também disponível como `uv run automacao ...`).

Estrutura do robô (pacote automacao-core):
    uv run automacao iniciar      # pasta nova, depois de uv add automacao-core
    uv run automacao atualizar    # depois de subir a versão do automacao-core

Estado dos itens (time de operação):
    uv run python -m core listar [--status revisao_manual]
    uv run python -m core resolver ITEM_ID --como concluido --obs "conferido no sistema, protocolo X"

Agendamento (Agendador de Tarefas do Windows, ver scripts/agendar.ps1):
    uv run python -m core agenda [--json]
    python -m core execucao-agendada              # comando da tarefa agendada (uma execução)
    python -m core agendamento instalado|removido # avisa o monitoramento (chamado pelo agendar.ps1)

Documento do cliente (PDD pronto, em Word):
    uv run python -m core importar-documento docs/documento_cliente/pdd_cliente.docx

Fases do robô (registradas pelos prompts do Copilot e pelo agendar.ps1, não à mão):
    uv run python -m core fases [--abrir]     # e refaz o painel docs/fases.html (--abrir: no navegador)
    uv run python -m core concluir-fase homologacao --obs "área validou a saída de 07/11 (e-mail de Fulana)"
    uv run python -m core reabrir-fase pdd --obs "reprovado: cliente pediu incluir o campo X"

PDD (desenvolvimento):
    uv run python -m core checar-pdd
    uv run python -m core exportar-pdd [--modelo docs/modelos/modelo_pdd.docx] [--rascunho]

Análise técnica (antes do desenvolvimento):
    uv run python -m core resumir-har docs/requisicoes/consulta.har   # gera consulta.resumo.md, sem valores
    uv run python -m core checar-analise
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from core import analise, modelo
from core.agendador import DIAS, Agenda, ExecucaoAgendada, avisar_agendamento
from core.config import Settings
from core.documento import PASTA_IMAGENS, DocumentoInvalido
from core.documento import importar as importar_documento
from core.fases import CHAVES, FaseRecusada, avaliar, concluir, formatar, reabrir
from core.har import gravar_resumo
from core.logger import configurar_logs
from core.painel_fases import gerar as gerar_painel
from core.pdd import checar, exportar_docx
from core.state import Estado, Status

PDD = Path("docs/pdd.md")
DUVIDAS = Path("docs/duvidas.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Estado dos itens e ferramentas do PDD")
    sub = parser.add_subparsers(dest="comando", required=True)
    listar = sub.add_parser("listar", help="lista o estado dos itens")
    listar.add_argument("--status", type=Status, choices=list(Status))
    resolver = sub.add_parser("resolver", help="resolve manualmente um item em revisão")
    resolver.add_argument("item_id")
    resolver.add_argument("--como", type=Status, choices=[Status.CONCLUIDO, Status.PENDENTE], required=True)
    resolver.add_argument("--obs", required=True, help="o que foi conferido (fica registrado)")
    for comando in (listar, resolver):
        comando.add_argument("--db", type=Path)
        comando.add_argument("--automacao")
    agenda = sub.add_parser("agenda", help="mostra a agenda do .env e as próximas execuções")
    agenda.add_argument("--json", action="store_true", help="dias e horários para o agendar.ps1")
    sub.add_parser("execucao-agendada", help="uma execução do robô (comando da tarefa agendada)")
    agendamento = sub.add_parser("agendamento", help="avisa o monitoramento (chamado pelo agendar.ps1)")
    agendamento.add_argument("situacao", choices=["instalado", "removido"])
    importar = sub.add_parser(
        "importar-documento",
        help="converte o PDD do cliente (.docx) em .md, com as imagens em docs/screenshots",
    )
    importar.add_argument("arquivo", type=Path)
    fases = sub.add_parser(
        "fases", help="mostra a fase do robô (do levantamento à produção) e o próximo passo"
    )
    fases.add_argument(
        "--abrir", action="store_true", help="abre o painel de fases (docs/fases.html) no navegador"
    )
    concluir_fase = sub.add_parser(
        "concluir-fase", help="registra uma fase concluída (confere o pré-requisito)"
    )
    reabrir_fase = sub.add_parser("reabrir-fase", help="reabre uma fase e as seguintes (ex.: PDD reprovado)")
    for comando in (concluir_fase, reabrir_fase):
        comando.add_argument("fase", choices=CHAVES)
        comando.add_argument("--obs", required=True, help="evidência ou motivo (fica registrado)")
    sub.add_parser("checar-pdd", help="falha se o PDD não estiver aprovado ou tiver dúvidas pendentes")
    exportar = sub.add_parser("exportar-pdd", help="gera o .docx do PDD para enviar ao cliente")
    exportar.add_argument("--modelo", type=Path, help="Word modelo da empresa (usa os estilos dele)")
    exportar.add_argument("--saida", type=Path, default=Path("docs/envio/PDD.docx"))
    exportar.add_argument("--rascunho", action="store_true", help="permite exportar com dúvidas pendentes")
    sub.add_parser(
        "checar-analise", help="falha se a análise técnica (docs/analise_tecnica.md) não estiver decidida"
    )
    har = sub.add_parser(
        "resumir-har", help="resume um .har (só a estrutura, sem valores) para a análise técnica"
    )
    har.add_argument("arquivo", type=Path)
    sub.add_parser(
        "iniciar", help="cria a estrutura do robô nesta pasta (projeto/, docs/, tests/, scripts/...)"
    )
    sub.add_parser("atualizar", help="renova os arquivos do padrão (prompts, scripts, instruções)")
    args = parser.parse_args()

    if args.comando in ("iniciar", "atualizar"):
        return _estrutura(args.comando)
    if args.comando == "checar-pdd":
        problemas = checar(PDD, DUVIDAS)
        for problema in problemas:
            print(f"BLOQUEADO: {problema}")
        if not problemas:
            print("PDD aprovado e sem dúvidas pendentes: pode desenvolver.")
        return 1 if problemas else 0
    if args.comando == "checar-analise":
        problemas = analise.checar(Path.cwd())
        for problema in problemas:
            print(f"BLOQUEADO: {problema}")
        if not problemas:
            lida = analise.ler(Path.cwd())
            print(f"Análise técnica decidida (motor: {lida.motor if lida else '?'}): pode desenvolver.")
        return 1 if problemas else 0
    if args.comando == "resumir-har":
        resumo = gravar_resumo(args.arquivo)
        print(f"Resumo gerado: {resumo}")
        print(
            "O .har tem cookies, tokens e dados reais: apague-o quando não precisar mais. Nunca o versione."
        )
        return 0
    if args.comando == "importar-documento":
        try:
            md, imagens = importar_documento(args.arquivo)
        except DocumentoInvalido as exc:
            print(f"ERRO: {exc}")
            return 1
        print(f"Texto: {md}")
        print(f"Imagens: {len(imagens)} em {PASTA_IMAGENS}")
        print(
            "Confira os prints: se mostrarem dado real (nome, CPF, conta, valores), não use como exemplo "
            "no PDD nem nos testes."
        )
        return 0
    if args.comando == "exportar-pdd":
        print(f"Gerado {exportar_docx(PDD, args.saida, modelo=args.modelo, rascunho=args.rascunho)}")
        return 0

    settings = Settings()
    if args.comando in ("fases", "concluir-fase", "reabrir-fase"):
        codigo = 0
        if args.comando == "fases":
            print(formatar(avaliar(Path.cwd(), settings.estado_db), settings.automacao_nome))
        elif args.comando == "concluir-fase":
            try:
                print(concluir(Path.cwd(), settings.estado_db, args.fase, args.obs))
            except FaseRecusada as exc:
                print(f"RECUSADO: {exc}")
                codigo = 1
        else:
            print(reabrir(Path.cwd(), args.fase, args.obs))
        # A página do painel de fases é refeita sempre, para nunca ficar atrás do docs/fases.json
        pagina = gerar_painel(Path.cwd(), settings.estado_db, settings.automacao_nome)
        print(f"Painel de fases: {pagina}")
        if getattr(args, "abrir", False):
            os.startfile(pagina)  # abre no navegador padrão (Windows)
        return codigo
    if args.comando == "agenda":
        agenda = Agenda.de_texto(settings.agenda_dias, settings.agenda_horarios)
        if args.json:
            print(json.dumps(agenda.para_tarefa() | {"timeout_min": settings.agenda_timeout_min}))
            return 0
        print(f"Agenda: {agenda}")
        momento = datetime.now()
        for _ in range(5):
            momento = agenda.proxima(momento)
            print(f"  {DIAS[momento.weekday()]} {momento:%d/%m/%Y %H:%M}")
        return 0
    if args.comando == "execucao-agendada":
        configurar_logs("agendamento", settings.logs_dir)
        return ExecucaoAgendada(settings).rodar()
    if args.comando == "agendamento":
        avisar_agendamento(settings, args.situacao)
        print(f"Monitoramento avisado: agendamento {args.situacao}.")
        return 0

    estado = Estado(args.db or settings.estado_db, args.automacao or settings.automacao_nome)
    if args.comando == "listar":
        for r in estado.listar(args.status):
            print(
                f"{r.item_id:<20} {r.status:<15} tentativas={r.tentativas} {r.atualizado_em}  {r.ultimo_erro or ''}"
            )
        print(estado.resumo())
    else:
        estado.resolver(args.item_id, args.como, args.obs)
        print(f"{args.item_id} -> {args.como}")
    return 0


def _estrutura(comando: str) -> int:
    try:
        if comando == "iniciar":
            feitos = modelo.iniciar(Path.cwd())
            print(f"Estrutura do padrão {modelo.versao()} criada ({len(feitos)} arquivo(s)).")
        else:
            anterior, feitos = modelo.atualizar(Path.cwd())
            print(f"Padrão {anterior} -> {modelo.versao()}: {len(feitos)} arquivo(s) atualizado(s).")
    except modelo.ModeloNaoEncontrado as exc:
        print(f"ERRO: {exc}")
        return 1
    for arquivo in feitos:
        print(f"  {arquivo}")
    if comando == "iniciar":
        print(PROXIMOS_PASSOS)
    return 0


PROXIMOS_PASSOS = r"""
Próximos passos:
  1. uv sync
  2. git init  e  git remote add origin <projeto do robô no servidor Git>
  3. copy .env.example .env   (preencha)   e   .\scripts\instalar.ps1
  4. Salve a transcrição em docs/transcricao/ (ou o PDD do cliente em docs/documento_cliente/ e rode
     uv run python -m core importar-documento <arquivo>.docx) e rode /gerar-pdd no Copilot (guia: GUIA.md)"""


if __name__ == "__main__":
    sys.exit(main())
