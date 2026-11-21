"""Fases do robô registradas pelo fluxo (core concluir-fase / reabrir-fase / fases)."""

import json
from pathlib import Path

import pytest

from core.config import Settings
from core.fases import FaseRecusada, Situacao, avaliar, concluir, formatar, reabrir, registrar_execucao
from core.painel_fases import gerar as gerar_painel

ESTADO = Path("estado.db")
CABECALHO_DUVIDAS = (
    "| ID | Status | Seção do PDD | Pergunta | Trecho da transcrição | Sugestão do Copilot | Quem responde | Resposta |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "transcricao").mkdir(parents=True)
    (tmp_path / "docs" / "pdd.md").write_text(
        "# PDD: <nome do processo>\n\n**Status:** rascunho\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "duvidas.md").write_text(CABECALHO_DUVIDAS, encoding="utf-8")
    return tmp_path


def _pdd(raiz: Path, status: str) -> None:
    (raiz / "docs" / "pdd.md").write_text(f"# PDD: Extrato\n\n**Status:** {status}\n", encoding="utf-8")


def _duvida(raiz: Path, id_: str, status: str, quem: str) -> None:
    with (raiz / "docs" / "duvidas.md").open("a", encoding="utf-8") as f:
        f.write(f"| {id_} | {status} | 4 | Pergunta? | trecho | sugestão | {quem} | |\n")


def _concluir(raiz: Path, fase: str, *, codigo: list[str] | None = None) -> str:
    return concluir(raiz, ESTADO, fase, f"obs {fase}", verificar_codigo=lambda _: codigo or [])


def _dry_run(raiz: Path, status: str = "sucesso") -> None:
    registrar_execucao(Settings(_env_file=None, estado_db=raiz / ESTADO, dry_run=True), status, 15)


def _atual(raiz: Path) -> str | None:
    fase = avaliar(raiz, ESTADO).atual
    return fase.nome if fase else None


def _ate_aprovacao(raiz: Path) -> None:
    _pdd(raiz, "enviado")
    _concluir(raiz, "levantamento")
    _concluir(raiz, "pdd")
    _pdd(raiz, "aprovado")
    _concluir(raiz, "aprovacao")
    _analise_decidida(raiz)


def _analise_decidida(raiz: Path) -> None:
    (raiz / "docs" / "analise_tecnica.md").write_text(
        "**Status:** decidida\n**Motor:** http\n", encoding="utf-8"
    )


def test_projeto_novo_esta_no_levantamento_e_nao_conclui_com_o_modelo(raiz: Path) -> None:
    diagnostico = avaliar(raiz, ESTADO)
    assert diagnostico.atual is not None and diagnostico.atual.nome == "Levantamento"
    assert "/gerar-pdd" in diagnostico.proximo_passo

    with pytest.raises(FaseRecusada, match="ainda é o modelo"):
        _concluir(raiz, "levantamento")


def test_nao_pula_fase(raiz: Path) -> None:
    _pdd(raiz, "aprovado")
    with pytest.raises(FaseRecusada, match="Conclua antes a fase 'PDD enviado ao cliente'"):
        _concluir(raiz, "aprovacao")


def test_pdd_so_e_enviado_sem_duvida_do_dev_e_com_status_enviado(raiz: Path) -> None:
    _pdd(raiz, "rascunho")
    _concluir(raiz, "levantamento")
    _duvida(raiz, "D-01", "aberta", "dev")
    _duvida(raiz, "D-02", "aberta", "cliente")

    assert (
        avaliar(raiz, ESTADO).fases[1].detalhe
        == "status rascunho; 2 dúvida(s) pendente(s): 1 do cliente, 1 do dev"
    )
    with pytest.raises(FaseRecusada) as erro:
        _concluir(raiz, "pdd")
    assert "Dúvidas do dev pendentes: D-01." in str(erro.value) and "'enviado'" in str(erro.value)

    (raiz / "docs" / "duvidas.md").write_text(CABECALHO_DUVIDAS, encoding="utf-8")
    _duvida(raiz, "D-02", "aberta", "cliente")  # dúvida do cliente vai no e-mail: não bloqueia o envio
    _pdd(raiz, "enviado")
    assert _concluir(raiz, "pdd") == "Fase 'PDD enviado ao cliente' concluída."
    assert _atual(raiz) == "Aprovação do cliente"


def test_aprovacao_exige_checar_pdd_e_reprovacao_reabre_o_pdd(raiz: Path) -> None:
    _pdd(raiz, "enviado")
    _concluir(raiz, "levantamento")
    _concluir(raiz, "pdd")

    with pytest.raises(FaseRecusada, match="precisa estar 'aprovado'"):
        _concluir(raiz, "aprovacao")

    assert reabrir(raiz, "pdd", "reprovado: incluir campo X") == "Reaberta(s): PDD enviado ao cliente."
    assert _atual(raiz) == "PDD enviado ao cliente"


def test_desenvolvimento_exige_testes_passando(raiz: Path) -> None:
    _ate_aprovacao(raiz)

    with pytest.raises(FaseRecusada, match="Testes falhando"):
        _concluir(raiz, "desenvolvimento", codigo=["Testes falhando (1 failed)."])
    assert _atual(raiz) == "Desenvolvimento"

    _concluir(raiz, "desenvolvimento")
    assert _atual(raiz) == "Homologação"


def test_desenvolvimento_exige_analise_tecnica_decidida(raiz: Path) -> None:
    _ate_aprovacao(raiz)
    (raiz / "docs" / "analise_tecnica.md").unlink()

    diagnostico = avaliar(raiz, ESTADO)
    assert "/analisar-tecnica" in diagnostico.proximo_passo
    assert diagnostico.fases[3].detalhe.startswith("análise técnica pendente; padrões da área: nenhum")
    with pytest.raises(FaseRecusada, match="Rode /analisar-tecnica"):
        _concluir(raiz, "desenvolvimento")

    _analise_decidida(raiz)
    (raiz / "docs" / "padroes").mkdir()
    (raiz / "docs" / "padroes" / "boas_praticas_python.md").touch()
    diagnostico = avaliar(raiz, ESTADO)
    assert "/nova-automacao" in diagnostico.proximo_passo
    assert (
        diagnostico.fases[3].detalhe
        == "análise: motor http (decidida); padrões da área: boas_praticas_python.md"
    )
    _concluir(raiz, "desenvolvimento")


def test_homologacao_exige_dry_run_com_sucesso_depois_do_desenvolvimento(raiz: Path) -> None:
    _ate_aprovacao(raiz)
    _dry_run(raiz)  # antigo: antes do fim do desenvolvimento
    _concluir(raiz, "desenvolvimento")

    # força o DRY_RUN para antes do registro do desenvolvimento
    arquivo = raiz / "estado.execucoes.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["dry_run"]["fim"] = "2000-01-01T00:00:00"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    with pytest.raises(FaseRecusada, match="Nenhum DRY_RUN com sucesso"):
        _concluir(raiz, "homologacao")

    _dry_run(raiz, "com_erros")
    with pytest.raises(FaseRecusada):
        _concluir(raiz, "homologacao")

    _dry_run(raiz)
    assert "DRY_RUN" in avaliar(raiz, ESTADO).fases[4].detalhe
    _concluir(raiz, "homologacao")
    assert _atual(raiz) == "Produção"


def test_producao_e_aviso_quando_o_pdd_muda_depois(raiz: Path) -> None:
    _ate_aprovacao(raiz)
    _concluir(raiz, "desenvolvimento")
    _dry_run(raiz)
    _concluir(raiz, "homologacao")

    with pytest.raises(FaseRecusada, match="Agendamento não criado"):
        _concluir(raiz, "producao")
    (raiz / "agendamento").mkdir()
    (raiz / "agendamento" / "robo-extrato.xml").touch()
    _concluir(raiz, "producao")

    diagnostico = avaliar(raiz, ESTADO)
    assert diagnostico.atual is None and all(f.situacao is Situacao.FEITA for f in diagnostico.fases)
    assert diagnostico.avisos == []
    assert _concluir(raiz, "producao").startswith("Produção já estava concluída")

    _pdd(raiz, "rascunho")
    assert "o PDD mudou depois da aprovação" in avaliar(raiz, ESTADO).avisos[0]


def test_historico_registra_quem_quando_e_formatar(raiz: Path) -> None:
    _pdd(raiz, "enviado")
    _concluir(raiz, "levantamento")

    historico = json.loads((raiz / "docs" / "fases.json").read_text(encoding="utf-8"))["historico"]
    assert historico[0]["fase"] == "levantamento" and historico[0]["acao"] == "concluida"
    assert historico[0]["por"] and historico[0]["em"] and historico[0]["obs"] == "obs levantamento"

    texto = formatar(avaliar(raiz, ESTADO), "extrato")
    assert "[x] 1. Levantamento" in texto and "obs levantamento" in texto
    assert "[>] 2. PDD enviado ao cliente" in texto
    assert "[ ] 6. Produção" in texto


def test_painel_html_mostra_trilha_fase_atual_e_historico(raiz: Path) -> None:
    _pdd(raiz, "enviado")
    _concluir(raiz, "levantamento")
    concluir(raiz, ESTADO, "pdd", "enviado <v0.2> & revisado", verificar_codigo=lambda _: [])

    pagina = gerar_painel(raiz, ESTADO, "extrato")

    html = pagina.read_text(encoding="utf-8")
    assert pagina == raiz / "docs" / "fases.html"
    assert '<meta http-equiv="refresh"' in html
    assert html.count('<li class="job feita">') == 2 and html.count('<li class="job atual">') == 1
    assert "Próxima manobra · Aprovação do cliente" in html and "<code>/registrar-aprovacao</code>" in html
    assert "copilot&gt;</span> /registrar-aprovacao" in html  # comando do próximo passo no terminal
    assert ">F3/6<" in html
    assert "enviado &lt;v0.2&gt; &amp; revisado" in html  # texto do histórico sempre escapado
    assert "33%" in html


def test_painel_html_em_producao_e_com_aviso(raiz: Path) -> None:
    _ate_aprovacao(raiz)
    _concluir(raiz, "desenvolvimento")
    _dry_run(raiz)
    _concluir(raiz, "homologacao")
    (raiz / "agendamento").mkdir()
    (raiz / "agendamento" / "robo-extrato.xml").touch()
    _concluir(raiz, "producao")
    _pdd(raiz, "rascunho")

    html = gerar_painel(raiz, ESTADO, "extrato").read_text(encoding="utf-8")

    assert "Robô em produção" in html and "100%" in html
    assert 'class="aviso"' in html and "o PDD mudou depois da aprovação" in html
