"""Fixtures de teste do padrão, carregadas automaticamente pelo pytest (plugin `pytest11` do automacao-core).

- `servir_pasta(pasta)`: serve um site simulado (tests/<nome>/index.html) num servidor local.
- `api_fake`: API simulada para robôs HTTP. Rotas por "MÉTODO /caminho" com JSON fixo ou uma função.
"""

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

# Rota da API simulada: um JSON fixo (status 200), um texto (HTML, status 200) ou uma função
# (parâmetros da URL, corpo JSON) -> (status, JSON ou texto)
Resposta = Any | Callable[[dict[str, str], Any], tuple[int, Any]]


class _HandlerSilencioso(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def servir_pasta(pasta: Path) -> Iterator[str]:
    """Sobe um servidor local com os arquivos da pasta e devolve a URL base."""
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), partial(_HandlerSilencioso, directory=str(pasta)))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{servidor.server_address[1]}"
    finally:
        servidor.shutdown()


@dataclass
class ApiFake:
    """API simulada. `chamadas` guarda o que o robô pediu ("GET /api/x"), na ordem."""

    url: str
    rotas: dict[str, Resposta] = field(default_factory=dict)
    chamadas: list[str] = field(default_factory=list)


class _HandlerApi(BaseHTTPRequestHandler):
    api: ApiFake

    def do_GET(self) -> None:
        self._responder()

    def do_POST(self) -> None:
        self._responder()

    def _responder(self) -> None:
        partes = urlsplit(self.path)
        chave = f"{self.command} {partes.path}"
        self.api.chamadas.append(chave)
        tamanho = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(tamanho) if tamanho else b""
        corpo = json.loads(bruto) if bruto and "json" in (self.headers.get("Content-Type") or "") else None
        rota = self.api.rotas.get(chave)
        if rota is None:
            status, dados = 404, {"erro": f"rota não simulada: {chave}"}
        elif callable(rota):
            status, dados = rota(dict(parse_qsl(partes.query)), corpo)
        else:
            status, dados = 200, rota
        texto = isinstance(dados, str)
        conteudo = dados.encode() if texto else json.dumps(dados).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8" if texto else "application/json")
        self.send_header("Content-Length", str(len(conteudo)))
        self.end_headers()
        self.wfile.write(conteudo)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def api_fake() -> Iterator[ApiFake]:
    api = ApiFake(url="")
    handler = type("Handler", (_HandlerApi,), {"api": api})
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    api.url = f"http://127.0.0.1:{servidor.server_address[1]}"
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield api
    servidor.shutdown()
