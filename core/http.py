"""Cliente HTTP padrão (requests). Usado quando a análise técnica (docs/analise_tecnica.md) escolhe `http`
ou `hibrido`: o robô chama os endpoints do sistema em vez de ler a tela."""

import re
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from playwright.sync_api import BrowserContext
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Só repete métodos que não alteram nada. POST/PUT/PATCH/DELETE nunca são repetidos automaticamente.
_METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
# Nomes de parâmetro que nunca vão para log ou evidência com o valor
SENSIVEL = re.compile(
    r"senha|password|passwd|pwd|token|secret|segredo|auth|session|sessao|cookie|key|chave|csrf|cpf|cnpj",
    re.IGNORECASE,
)
_LIMITE_HISTORICO = 5


@dataclass(frozen=True)
class Chamada:
    """Resumo de uma requisição feita, sem cabeçalhos (cookies/tokens) e com valores sensíveis ocultos."""

    metodo: str
    url: str
    status: int
    duracao_ms: int
    tipo: str
    corpo: str  # resposta, truncada: só vai para a pasta de evidências (fora do git), nunca para o log


class SessaoHttp(requests.Session):
    """`requests.Session` com timeout padrão, retry só em GET, `base_url` e histórico das últimas chamadas
    (usado pelas evidências quando um item falha)."""

    def __init__(
        self,
        *,
        base_url: str = "",
        timeout_s: float = 30,
        tentativas: int = 3,
        backoff_s: float = 1.0,
        verificar_tls: bool | str = True,
    ) -> None:
        super().__init__()
        self.base_url = base_url
        self.timeout_s = timeout_s
        self.verify = verificar_tls
        self.historico: deque[Chamada] = deque(maxlen=_LIMITE_HISTORICO)
        retry = Retry(
            total=tentativas,
            backoff_factor=backoff_s,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=_METODOS_SEGUROS,
            raise_on_status=False,
        )
        adaptador = HTTPAdapter(max_retries=retry)
        self.mount("https://", adaptador)
        self.mount("http://", adaptador)

    def request(self, method: str | bytes, url: str | bytes, *args: Any, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout_s)
        if isinstance(url, str) and self.base_url and not urlsplit(url).scheme:
            url = urljoin(self.base_url.rstrip("/") + "/", url.lstrip("/"))
        resposta = super().request(method, url, *args, **kwargs)
        self.historico.append(
            Chamada(
                metodo=str(resposta.request.method),
                url=url_segura(resposta.url),
                status=resposta.status_code,
                duracao_ms=int(resposta.elapsed.total_seconds() * 1000),
                tipo=resposta.headers.get("Content-Type", ""),
                corpo=resposta.text[:20_000] if _eh_texto(resposta) else f"<{len(resposta.content)} bytes>",
            )
        )
        return resposta

    def json_ok(self, method: str, url: str, **kwargs: Any) -> Any:
        """Chama e devolve o JSON (números com casas decimais como `Decimal`). Qualquer status fora de 2xx ou resposta que não é JSON é ERRO (sem fallback):
        tela de login no lugar do JSON, por exemplo, quer dizer que a sessão caiu."""
        resposta = self.request(method, url, **kwargs)
        resposta.raise_for_status()
        if "json" not in resposta.headers.get("Content-Type", ""):
            raise ValueError(
                f"{method} {url_segura(resposta.url)} não devolveu JSON "
                f"(Content-Type: {resposta.headers.get('Content-Type') or 'vazio'}). Sessão expirada?"
            )
        return resposta.json(parse_float=Decimal)  # dinheiro nunca vira float


def url_segura(url: str) -> str:
    """URL sem os valores de parâmetros sensíveis (token=***), para log e evidência."""
    partes = urlsplit(url)
    query = [
        (k, "***" if SENSIVEL.search(k) else v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
    ]
    return urlunsplit(partes._replace(query=urlencode(query, safe="*")))


def sessao_http_do_navegador(context: BrowserContext, **kwargs: Any) -> SessaoHttp:
    """Híbrido: reaproveita os cookies do navegador (login feito pela tela) para chamar a API do sistema direto."""
    sessao = SessaoHttp(**kwargs)
    for cookie in context.cookies():
        sessao.cookies.set(
            cookie["name"], cookie["value"], domain=cookie.get("domain"), path=cookie.get("path", "/")
        )
    return sessao


def _eh_texto(resposta: requests.Response) -> bool:
    tipo = resposta.headers.get("Content-Type", "")
    return any(t in tipo for t in ("json", "text", "xml", "html", "javascript"))
