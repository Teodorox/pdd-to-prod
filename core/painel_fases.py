"""Painel de fases do robô: uma página HTML em docs/fases.html, gerada a partir do docs/fases.json.

É refeita a cada `core concluir-fase`, `core reabrir-fase` e `core fases`. Abra no navegador: ela se recarrega
sozinha. Página única, sem internet e sem JavaScript (as fontes vão embutidas). Visual "Central": indicadores no
topo, as fases como um pipeline e o histórico como um registro de bordo.
"""

import base64
import json
import re
from datetime import datetime, timedelta
from functools import cache
from html import escape
from pathlib import Path
from typing import Any

from core.fases import FASES, Diagnostico, Situacao, arquivo_execucoes, avaliar, historico
from core.pdd import status_pdd

ARQUIVO_PAINEL = Path("docs/fases.html")
RECARREGAR_SEGUNDOS = 30
# Inter, JetBrains Mono e Space Grotesk (variáveis, só latim). Licenças em recursos/OFL-*.txt
RECURSOS = Path(__file__).parent / "recursos"
FONTES = (
    ("Inter", "inter.woff2", "400 700"),
    ("JetBrains Mono", "jetbrains-mono.woff2", "400 700"),
    ("Space Grotesk", "space-grotesk.woff2", "500 700"),
)
# Comandos dentro dos textos (/gerar-pdd, .\scripts\executar.ps1 -DryRun) viram <code>
_RE_COMANDO = re.compile(r"(/[a-z][a-z-]+|\.\\scripts\\[\w.]+(?: -[A-Za-z]+)*(?: [a-z]+)?)")
_CHECK = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle>'
    '<path d="m8 12 3 3 5-6"></path></svg>'
)
_SETA = '<li class="seta" aria-hidden="true">→</li>'


def gerar(raiz: Path, estado_db: Path, nome: str) -> Path:
    destino = raiz / ARQUIVO_PAINEL
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    temporario.write_text(montar(raiz, estado_db, nome, datetime.now()), encoding="utf-8")
    temporario.replace(destino)
    return destino


def montar(raiz: Path, estado_db: Path, nome: str, agora: datetime) -> str:
    diagnostico = avaliar(raiz, estado_db)
    registros = historico(raiz)
    pdd = raiz / "docs" / "pdd.md"
    status = status_pdd(pdd.read_text(encoding="utf-8")) if pdd.exists() else None
    db = estado_db if estado_db.is_absolute() else raiz / estado_db
    execucao = _ultima_execucao(arquivo_execucoes(db))

    corpo = [
        _topo(nome, status, agora),
        _indicadores(diagnostico, registros, execucao, agora),
        _pipeline(diagnostico, registros, agora),
        '<div class="colunas">',
        _manobra(diagnostico),
        _registro_de_bordo(registros),
        "</div>",
        _rodape(agora),
    ]
    return _PAGINA.format(
        titulo=escape(f"Fases • {nome}"),
        recarregar=RECARREGAR_SEGUNDOS,
        estilo=_fontes() + _ESTILO,
        corpo="\n".join(corpo),
    )


# ---------------------------------------------------------------- blocos


def _topo(nome: str, status: str | None, agora: datetime) -> str:
    selo = f'<span class="selo ok">PDD {escape(status)}</span>' if status else ""
    return f"""
<header class="topo">
  <div class="identidade">
    <span class="radar" aria-hidden="true"></span>
    <div>
      <p class="rotulo">Central da esteira</p>
      <h1>{escape(nome)}</h1>
    </div>
  </div>
  <div class="selos">{selo}<span class="ao-vivo"><span class="ponto"></span> ao vivo · {agora:%H:%M:%S}</span></div>
</header>"""


def _indicadores(
    diagnostico: Diagnostico,
    registros: list[dict[str, str]],
    execucao: dict[str, Any] | None,
    agora: datetime,
) -> str:
    total = len(FASES)
    feitas = sum(1 for f in diagnostico.fases if f.situacao is Situacao.FEITA)
    atual = diagnostico.atual
    if atual is None:
        estagio, estagio_sub = f"{total}/{total}", "Em produção"
    else:
        estagio, estagio_sub = f"F{feitas + 1}/{total}", escape(atual.nome)
    segmentos = "".join(f'<span class="{_classe(f.situacao)}"></span>' for f in diagnostico.fases)
    if registros:
        inicio, ultimo = (datetime.fromisoformat(registros[i]["em"]) for i in (0, -1))
        tempo, tempo_sub = f"T+{_tempo(agora - inicio)}", f"{_tempo(agora - ultimo)} na fase atual"
    else:
        tempo, tempo_sub = "T+0", "nenhuma fase registrada"
    if execucao is None:
        teste, classe_teste, teste_sub = "–", "", "nenhuma execução ainda"
    else:
        sucesso = execucao["status"] == "sucesso"
        teste, classe_teste = ("OK", "verde") if sucesso else (escape(execucao["status"]).upper(), "ambar")
        teste_sub = f"{execucao['tipo']} · {execucao['registros']:,} reg.".replace(",", ".")
    return f"""
<section class="indicadores">
  <div class="cartao kpi"><p class="rotulo">Estágio</p><p class="valor ciano">{estagio}</p>
    <p class="sub">{estagio_sub}</p></div>
  <div class="cartao kpi"><p class="rotulo">Progresso</p><p class="valor">{round(100 * feitas / total)}%</p>
    <div class="segmentos" title="{feitas} de {total} fases concluídas">{segmentos}</div></div>
  <div class="cartao kpi"><p class="rotulo">Tempo total</p><p class="valor">{tempo}</p>
    <p class="sub">{tempo_sub}</p></div>
  <div class="cartao kpi"><p class="rotulo">Último teste</p><p class="valor {classe_teste}">{teste}</p>
    <p class="sub">{teste_sub}</p></div>
</section>"""


def _pipeline(diagnostico: Diagnostico, registros: list[dict[str, str]], agora: datetime) -> str:
    concluida_em = {r["fase"]: datetime.fromisoformat(r["em"]) for r in registros if r["acao"] == "concluida"}
    reaberturas = {
        f.chave: sum(1 for r in registros if r["fase"] == f.chave and r["acao"] == "reaberta") for f in FASES
    }
    desde = datetime.fromisoformat(registros[-1]["em"]) if registros else None
    jobs = []
    for numero, (definicao, fase) in enumerate(zip(FASES, diagnostico.fases, strict=True), start=1):
        voltas = reaberturas[definicao.chave]
        retorno = f' · <span class="ambar">↺{voltas}</span>' if voltas else ""
        if fase.situacao is Situacao.FEITA:
            icone = f'<span class="icone">{_CHECK}</span>'
            sub = f"F{numero} · {concluida_em[definicao.chave]:%d/%m}{retorno}"
        elif fase.situacao is Situacao.ATUAL:
            icone = '<span class="girando" aria-hidden="true"></span>'
            sub = f"F{numero} · ativo" + (f" · {_tempo(agora - desde)}" if desde else "") + retorno
        else:
            icone = '<span class="vazio" aria-hidden="true"></span>'
            sub = f"F{numero} · espera"
        jobs.append(
            f'<li class="job {_classe(fase.situacao)}">{icone}<div><p class="nome">{escape(fase.nome)}</p>'
            f'<p class="sub">{sub}</p></div></li>'
        )
    return f'<ol class="cartao pipeline">{_SETA.join(jobs)}</ol>'


def _manobra(diagnostico: Diagnostico) -> str:
    atual = diagnostico.atual
    titulo = "Robô em produção" if atual is None else escape(atual.nome)
    detalhe = f'<p class="detalhe">{escape(atual.detalhe)}</p>' if atual and atual.detalhe else ""
    comandos = "".join(
        f'<span><span class="{"ciano" if c.startswith("/") else "verde"}">'
        f"{'copilot&gt;' if c.startswith('/') else 'PS&gt;'}</span> {escape(c)}</span>"
        for c in _RE_COMANDO.findall(diagnostico.proximo_passo)
    )
    terminal = f'<div class="terminal">{comandos}</div>' if comandos else ""
    avisos = "".join(f'<p class="aviso">⚠ {escape(a)}</p>' for a in diagnostico.avisos)
    return f"""
<section class="cartao manobra">
  <p class="rotulo">Próxima manobra · {titulo}</p>
  <p class="passo">{_comandos(diagnostico.proximo_passo)}</p>
  {detalhe}
  {terminal}
  {avisos}
</section>"""


def _registro_de_bordo(registros: list[dict[str, str]]) -> str:
    numeros = {f.chave: n for n, f in enumerate(FASES, start=1)}
    if not registros:
        linhas = (
            '<p class="vazio-texto">Nenhuma fase registrada ainda. O primeiro registro vem do /gerar-pdd.</p>'
        )
    else:
        linhas = "".join(
            f'<div class="linha{" reaberta" if r["acao"] == "reaberta" else ""}">'
            f'<span class="quando">{datetime.fromisoformat(r["em"]):%d/%m %H:%M}</span>'
            f'<span class="fase">F{numeros.get(r["fase"], "?")}</span>'
            f'<span class="texto">{"reaberto" if r["acao"] == "reaberta" else "concluído"} '
            f'<span class="obs">· {escape(r["obs"])} · {escape(r["por"])}</span></span></div>'
            for r in reversed(registros)
        )
    return f"""
<section class="cartao bordo">
  <div class="bordo-topo"><p class="rotulo">Registro de bordo</p><span class="sub">{len(registros)} registro(s)</span></div>
  <div class="log">{linhas}</div>
</section>"""


def _rodape(agora: datetime) -> str:
    return (
        f"<footer>Gerado em {agora:%d/%m/%Y %H:%M:%S} por <code>python -m core fases</code>. "
        f"Não edite: a página é refeita a cada fase registrada e recarrega a cada {RECARREGAR_SEGUNDOS} s.</footer>"
    )


# ---------------------------------------------------------------- apoio


def _classe(situacao: Situacao) -> str:
    return {Situacao.FEITA: "feita", Situacao.ATUAL: "atual", Situacao.PENDENTE: "pendente"}[situacao]


def _ultima_execucao(arquivo: Path) -> dict[str, Any] | None:
    """A execução mais recente entre a última DRY_RUN e a última real (gravadas pelo runner)."""
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    except ValueError:
        return None
    execucoes = [{"tipo": tipo, **dados[tipo]} for tipo in ("dry_run", "real") if tipo in dados]
    return max(execucoes, key=lambda e: e["fim"], default=None)


def _comandos(texto: str) -> str:
    return _RE_COMANDO.sub(r"<code>\1</code>", escape(texto, quote=False))


def _tempo(delta: timedelta) -> str:
    segundos = max(int(delta.total_seconds()), 0)
    if segundos >= 86_400:
        return f"{segundos // 86_400}d"
    if segundos >= 3600:
        return f"{segundos // 3600}h"
    return f"{max(segundos // 60, 1)}min"


@cache
def _fontes() -> str:
    """@font-face embutidas em base64: a página funciona sem internet e sem as fontes instaladas."""
    regras = []
    for familia, arquivo, pesos in FONTES:
        caminho = RECURSOS / arquivo
        if caminho.exists():
            dados = base64.b64encode(caminho.read_bytes()).decode("ascii")
            regras.append(
                f"@font-face {{ font-family: '{familia}'; font-weight: {pesos}; font-display: swap; "
                f"src: url(data:font/woff2;base64,{dados}) format('woff2'); }}"
            )
    return "\n".join(regras)


_PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{recarregar}">
<title>{titulo}</title>
<style>{estilo}</style>
</head>
<body>
<main>
{corpo}
</main>
</body>
</html>
"""

# Verde = concluído, ciano = fase atual, âmbar = reaberta/atenção. Fundo grafite com grade sutil.
_ESTILO = """
:root {
  color-scheme: dark;
  --fundo: #0a0b10; --cartao: #12141b; --cartao-2: #0a0b10; --borda: #22252f; --borda-2: #1c1e26;
  --texto: #e8eaf0; --suave: #9096a6; --apagado: #6b7182;
  --verde: #4cc38a; --verde-borda: #1f3a2c; --ciano: #22d3ee; --ciano-claro: #a5f3fc; --ambar: #f2b84b;
}
* { box-sizing: border-box; }
body {
  margin: 0; background-color: var(--fundo); color: var(--texto); font: 14px/1.5 "Inter", "Segoe UI", sans-serif;
  background-image: linear-gradient(rgba(34, 211, 238, .035) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(34, 211, 238, .035) 1px, transparent 1px);
  background-size: 44px 44px;
}
main { max-width: 1180px; margin: 0 auto; padding: 32px; display: flex; flex-direction: column; gap: 20px; }
p { margin: 0; }
h1 { margin: 0; font: 700 28px/1.2 "Space Grotesk", "Segoe UI", sans-serif; letter-spacing: -.02em; }
code { font: 12.5px "JetBrains Mono", Consolas, monospace; color: var(--ciano-claro); background: var(--cartao-2);
  border: 1px solid var(--borda); border-radius: 6px; padding: 1px 6px; white-space: nowrap; }
.rotulo { font: 11px "JetBrains Mono", Consolas, monospace; color: var(--suave); letter-spacing: .12em; text-transform: uppercase; }
.sub { color: var(--suave); font-size: 13px; }
.verde { color: var(--verde); } .ciano { color: var(--ciano); } .ambar { color: var(--ambar); }
.cartao { background: var(--cartao); border: 1px solid var(--borda); border-radius: 12px; }

.topo { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.identidade { display: flex; align-items: center; gap: 14px; }
.radar { flex: none; width: 38px; height: 38px; border-radius: 50%; border: 3px solid var(--ciano);
  border-right-color: transparent; animation: girar 2.4s linear infinite; }
@keyframes girar { to { transform: rotate(360deg); } }
.selos { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.selo { font-size: 12px; font-weight: 500; padding: 3px 10px; border-radius: 6px; }
.selo.ok { color: var(--verde); background: rgba(76, 195, 138, .12); border: 1px solid rgba(76, 195, 138, .25); }
.ao-vivo { font: 12px "JetBrains Mono", Consolas, monospace; color: var(--suave); }
.ponto { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--ciano);
  animation: piscar 2s ease-in-out infinite; }
@keyframes piscar { 50% { opacity: .3; } }

.indicadores { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.kpi { padding: 16px 18px; }
.valor { margin-top: 4px; font: 700 26px/1.25 "Space Grotesk", "Segoe UI", sans-serif; }
.segmentos { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 3px; margin-top: 8px; }
.segmentos span { height: 4px; border-radius: 2px; background: var(--borda); }
.segmentos .feita { background: var(--verde); } .segmentos .atual { background: var(--ciano); }

.pipeline { list-style: none; margin: 0; padding: 20px; display: flex; align-items: stretch; gap: 8px; }
.job { flex: 1; min-width: 0; display: flex; gap: 10px; align-items: center; padding: 12px; border-radius: 10px;
  background: var(--cartao-2); border: 1px solid var(--verde-borda); }
.job > div { min-width: 0; }
.job .nome { font-size: 13px; font-weight: 600; line-height: 1.3; }
.job .sub { font: 11px "JetBrains Mono", Consolas, monospace; }
.job .icone { flex: none; display: grid; color: var(--verde); }
.job.atual { background: rgba(34, 211, 238, .08); border-color: var(--ciano); box-shadow: 0 0 18px rgba(34, 211, 238, .18); }
.job.atual .nome { color: var(--ciano-claro); } .job.atual .sub { color: var(--ciano); }
.job.pendente { background: transparent; border: 1px dashed #2a2e3a; }
.job.pendente .nome, .job.pendente .sub { color: var(--apagado); }
.girando { flex: none; width: 16px; height: 16px; border-radius: 50%; border: 2.5px solid var(--ciano);
  border-right-color: transparent; animation: girar 1.2s linear infinite; }
.vazio { flex: none; width: 16px; height: 16px; border-radius: 50%; border: 2px solid #2a2e3a; }
.seta { color: #3a3f4d; align-self: center; }

.colunas { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.manobra { padding: 22px; display: flex; flex-direction: column; gap: 14px; }
.passo { font: 600 18px/1.45 "Space Grotesk", "Segoe UI", sans-serif; }
.passo code { font-size: 13px; }
.detalhe { color: var(--suave); }
.terminal { background: var(--cartao-2); border: 1px solid var(--borda); border-radius: 10px; padding: 14px;
  font: 13px "JetBrains Mono", Consolas, monospace; display: flex; flex-direction: column; gap: 6px; overflow-wrap: anywhere; }
.aviso { padding: 10px 14px; border-radius: 10px; background: rgba(242, 184, 75, .10); color: var(--ambar);
  border: 1px solid rgba(242, 184, 75, .25); font-weight: 500; }

.bordo { overflow: hidden; }
.bordo-topo { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px;
  border-bottom: 1px solid var(--borda-2); }
.log { padding: 14px 20px; font: 12.5px "JetBrains Mono", Consolas, monospace; display: flex; flex-direction: column; gap: 12px; }
.linha { display: grid; grid-template-columns: 92px 28px minmax(0, 1fr); gap: 8px; }
.linha .quando { color: var(--apagado); }
.linha .fase { color: var(--verde); }
.linha .texto { overflow-wrap: anywhere; }
.linha .obs { color: var(--suave); }
.linha.reaberta .fase, .linha.reaberta .texto { color: var(--ambar); }
.vazio-texto { color: var(--suave); font-family: "Inter", "Segoe UI", sans-serif; }

footer { color: var(--apagado); font-size: 12px; text-align: center; margin-top: 8px; }

@media (max-width: 860px) {
  main { padding: 20px 16px; }
  .topo { flex-direction: column; align-items: flex-start; }
  .indicadores { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pipeline { flex-direction: column; align-items: stretch; }
  .seta { transform: rotate(90deg); align-self: center; }
  .colunas { grid-template-columns: 1fr; }
}
"""
