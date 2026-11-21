"""Motor HTTP (executar_http), resumo do .har e trava da análise técnica."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from core import analise, runner
from core.execucao import ExecucaoItem
from core.har import resumir
from core.http import SessaoHttp, url_segura
from core.runner import Item, executar_http
from core.state import Estado, Status
from core.testes import ApiFake
from projeto.config import ProjetoSettings


class Consulta(Item):
    agencia: str


def _login(sessao: SessaoHttp) -> None:
    dados = sessao.json_ok("POST", "/api/login", json={"usuario": "robo", "senha": "senha-teste"})
    sessao.headers["Authorization"] = f"Bearer {dados['token']}"


def _extrair(sessao: SessaoHttp, execucao: ExecucaoItem, item: Consulta) -> None:
    linhas: list[dict[str, Any]] = []
    pagina, total = 1, None
    while total is None or len(linhas) < total:
        dados = sessao.json_ok("GET", "/api/movimentos", params={"agencia": item.agencia, "page": pagina})
        total = dados["total"]
        linhas += dados["itens"]
        pagina += 1
    execucao.conferir("total de registros", total, len(linhas))
    execucao.registrar("registros", len(linhas))
    execucao.registrar("soma", str(sum(linha["valor"] for linha in linhas)))


def _movimentos(params: dict[str, str], _corpo: Any) -> tuple[int, Any]:
    paginas = {"1": [{"id": 1, "valor": 10.10}, {"id": 2, "valor": 0.20}], "2": [{"id": 3, "valor": 5.05}]}
    return 200, {"total": 3, "itens": paginas[params["page"]]}


@pytest.fixture
def settings_http(settings: ProjetoSettings, api_fake: ApiFake) -> ProjetoSettings:
    return settings.model_copy(update={"base_url": api_fake.url})


def test_executar_http_extrai_sem_abrir_navegador(
    settings_http: ProjetoSettings, api_fake: ApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _sem_navegador(*_: Any) -> None:
        raise AssertionError("o motor http não pode abrir o navegador")

    monkeypatch.setattr(runner, "abrir_navegador", _sem_navegador)
    api_fake.rotas["POST /api/login"] = lambda _p, corpo: (200, {"token": f"tk-{corpo['usuario']}"})
    api_fake.rotas["GET /api/movimentos"] = _movimentos

    resultado = executar_http([Consulta(id="0001", agencia="0001")], _extrair, settings_http, preparar=_login)

    assert resultado.sucesso
    registro = Estado(settings_http.estado_db, settings_http.automacao_nome).obter("0001")
    assert registro is not None and registro.status is Status.CONCLUIDO
    assert api_fake.chamadas == ["POST /api/login", "GET /api/movimentos", "GET /api/movimentos"]
    assert Decimal(registro.resultado["soma"]) == Decimal("15.35")  # sem erro de float


def test_executar_http_falha_quando_a_api_devolve_html_e_guarda_evidencia_sem_segredo(
    settings_http: ProjetoSettings, api_fake: ApiFake
) -> None:
    api_fake.rotas["POST /api/login"] = {"token": "tk-secreto"}
    api_fake.rotas["GET /api/movimentos"] = lambda _p, _c: (200, "<html>Faça login</html>")  # sessão caiu

    resultado = executar_http([Consulta(id="0001", agencia="0001")], _extrair, settings_http, preparar=_login)

    assert not resultado.sucesso
    registro = Estado(settings_http.estado_db, settings_http.automacao_nome).obter("0001")
    assert registro is not None and registro.status is Status.ERRO
    assert "não devolveu JSON" in (registro.ultimo_erro or "")
    pasta = Path(registro.evidencia or "")
    chamadas = (pasta / "chamadas.txt").read_text(encoding="utf-8")
    assert "GET " in chamadas and "/api/movimentos?agencia=0001&page=1 -> 200" in chamadas
    assert "Faça login" in (pasta / "ultima_resposta.txt").read_text(encoding="utf-8")
    assert "tk-secreto" not in "".join(p.read_text(encoding="utf-8") for p in pasta.iterdir())


def test_url_segura_esconde_parametros_sensiveis() -> None:
    url = url_segura("https://sistema/api?agencia=1&access_token=abc&cpf=12345678900")
    assert url == "https://sistema/api?agencia=1&access_token=***&cpf=***"


# ---------------------------------------------------------------- .har


def _entrada(
    metodo: str, url: str, *, status: int = 200, mime: str = "application/json", **extra: Any
) -> dict:
    entrada: dict[str, Any] = {
        "request": {"method": metodo, "url": url, "headers": extra.get("cabecalhos", [])},
        "response": {
            "status": status,
            "headers": extra.get("cabecalhos_resposta", []),
            "content": {"mimeType": mime, "text": extra.get("resposta", "")},
        },
        "time": 120,
    }
    if "corpo" in extra:
        entrada["request"]["postData"] = {"mimeType": "application/json", "text": json.dumps(extra["corpo"])}
    return entrada


def test_resumo_do_har_tem_a_estrutura_e_nenhum_valor(tmp_path: Path) -> None:
    har = tmp_path / "consulta.har"
    entradas = [
        _entrada(
            "POST",
            "https://sistema.local/api/login",
            corpo={"usuario": "fulano.real", "senha": "senha-super-secreta"},
            resposta=json.dumps({"token": "eyJ-token-real"}),
            cabecalhos_resposta=[{"name": "Set-Cookie", "value": "JSESSIONID=abc123; Path=/"}],
        ),
        _entrada(
            "GET",
            "https://sistema.local/api/contratos/987654/parcelas?page=2&access_token=xyz",
            cabecalhos=[
                {"name": "Authorization", "value": "Bearer eyJ-token-real"},
                {"name": "X-XSRF-TOKEN", "value": "csrf-real"},
            ],
            resposta=json.dumps(
                {"total": 1, "itens": [{"cpf": "123.456.789-00", "valor": 1234.56, "venc": "2024-01-10"}]}
            ),
        ),
        _entrada("GET", "https://sistema.local/img/logo.png", mime="image/png"),
        _entrada("GET", "https://www.google.com/recaptcha/api.js", mime="text/javascript"),
    ]
    har.write_text(json.dumps({"log": {"entries": entradas}}), encoding="utf-8")

    resumo = resumir(har)

    for segredo in (
        "fulano.real",
        "senha-super-secreta",
        "eyJ-token-real",
        "abc123",
        "xyz",
        "csrf-real",
        "123.456",
        "987654",
        "1234.56",
    ):
        assert segredo not in resumo, segredo
    assert "POST /api/login" in resumo and "GET /api/contratos/{id}/parcelas" in resumo
    assert '"senha": str (sensível)' in resumo and '"cpf": str (sensível)' in resumo
    assert '"valor": float' in resumo and "(1 itens)" in resumo
    assert "page (paginação?)" in resumo and "access_token (sensível)" in resumo
    assert "JSESSIONID" in resumo and "Bearer (1x)" in resumo and "x-xsrf-token" in resumo
    assert "CAPTCHA detectado" in resumo
    assert "2 endpoint(s) distintos; 2 requisição(ões) ignoradas" in resumo


# ---------------------------------------------------------------- análise técnica


def _analise(raiz: Path, status: str, motor: str) -> None:
    (raiz / "docs").mkdir(exist_ok=True)
    (raiz / "docs" / "analise_tecnica.md").write_text(
        f"# Análise técnica: Extrato\n\n<!-- **Status:** decidida -->\n**Status:** {status}\n**Motor:** {motor}\n",
        encoding="utf-8",
    )


def test_checar_analise(tmp_path: Path) -> None:
    assert "Rode /analisar-tecnica" in analise.checar(tmp_path)[0]

    _analise(tmp_path, "pendente_insumos", "http")
    assert "precisa estar 'decidida'" in analise.checar(tmp_path)[0]  # o comentário do modelo não conta

    _analise(tmp_path, "decidida", "a_definir")
    assert "Motor 'a_definir' inválido" in analise.checar(tmp_path)[0]

    _analise(tmp_path, "decidida", "http")
    assert analise.checar(tmp_path) == []
    assert analise.ler(tmp_path) == analise.Analise("decidida", "http")
