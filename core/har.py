"""Resumo de um arquivo .har (gravação das requisições do navegador) para a análise técnica e o desenvolvimento.

    uv run python -m core resumir-har docs/requisicoes/consulta.har

O .har tem cookies, tokens e os dados reais das telas: ele NUNCA vai para o git nem é lido pelo Copilot.
O resumo (`docs/requisicoes/<nome>.resumo.md`) guarda só a estrutura: método, caminho, nomes dos parâmetros,
formato dos JSON (chaves e tipos) e o tipo de autenticação. Nenhum valor. Por isso pode ser versionado.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from core.http import SENSIVEL

# Recursos que não interessam para a extração
_IGNORAR_TIPOS = {"image", "stylesheet", "font", "media", "script", "manifest", "ping", "other_static"}
_IGNORAR_MIME = ("image/", "font/", "text/css", "javascript", "video/", "audio/")
_IGNORAR_EXT = re.compile(r"\.(png|jpe?g|gif|svg|ico|webp|css|js|map|woff2?|ttf|eot)$", re.IGNORECASE)
_CAPTCHA = re.compile(r"recaptcha|hcaptcha|captcha|turnstile", re.IGNORECASE)
_CSRF = re.compile(r"csrf|xsrf|requestverification|anti-?forgery", re.IGNORECASE)
_PAGINACAO = re.compile(
    r"^(page|pagina|pag|offset|skip|start|inicio|size|limit|top|per_?page|pagesize)$", re.IGNORECASE
)
_SEGMENTO_ID = re.compile(r"^(\d{3,}|[0-9a-f]{8}-[0-9a-f-]{27,}|[0-9a-f]{24,})$", re.IGNORECASE)
_PROFUNDIDADE = 5


@dataclass
class _Endpoint:
    metodo: str
    host: str
    caminho: str
    status: Counter[int] = field(default_factory=Counter)
    tipo_resposta: str = ""
    parametros: list[str] = field(default_factory=list)
    corpo_enviado: str = ""
    resposta: str = ""
    tempos_ms: list[float] = field(default_factory=list)
    download: bool = False


def resumir(har: Path) -> str:
    dados = json.loads(har.read_text(encoding="utf-8-sig"))
    entradas = dados.get("log", {}).get("entries", [])
    endpoints: dict[tuple[str, str, str], _Endpoint] = {}
    ignoradas = 0
    cookies_servidor: set[str] = set()
    esquemas_auth: Counter[str] = Counter()
    cabecalhos_csrf: set[str] = set()
    captcha: set[str] = set()
    redirecionamentos = 0

    for entrada in entradas:
        requisicao, resposta = entrada.get("request", {}), entrada.get("response", {})
        url = urlsplit(requisicao.get("url", ""))
        if _CAPTCHA.search(url.netloc + url.path):
            captcha.add(url.netloc)
        cookies_servidor |= _cookies_definidos(resposta)
        for nome, valor in _cabecalhos(requisicao).items():
            if nome == "authorization":
                esquemas_auth[valor.split(" ", 1)[0] if " " in valor else "valor sem esquema"] += 1
            elif _CSRF.search(nome):
                cabecalhos_csrf.add(nome)
        if 300 <= resposta.get("status", 0) < 400:
            redirecionamentos += 1
        if _ignorar(entrada):
            ignoradas += 1
            continue

        metodo = requisicao.get("method", "GET").upper()
        caminho = _caminho_generico(url.path)
        chave = (metodo, url.netloc, caminho)
        endpoint = endpoints.get(chave)
        if endpoint is None:
            endpoint = endpoints[chave] = _Endpoint(metodo, url.netloc, caminho)
            endpoint.corpo_enviado = _corpo_enviado(requisicao.get("postData") or {})
            conteudo = resposta.get("content", {})
            endpoint.tipo_resposta = (conteudo.get("mimeType") or "").split(";")[0]
            endpoint.resposta = _formato_resposta(conteudo)
            endpoint.download = "attachment" in _cabecalhos(resposta).get("content-disposition", "")
        for nome, _ in parse_qsl(url.query, keep_blank_values=True):
            rotulo = _rotulo_parametro(nome)
            if rotulo not in endpoint.parametros:
                endpoint.parametros.append(rotulo)
        endpoint.status[resposta.get("status", 0)] += 1
        endpoint.tempos_ms.append(float(entrada.get("time") or 0))

    return _markdown(
        har.name,
        list(endpoints.values()),
        ignoradas=ignoradas,
        cookies=cookies_servidor,
        esquemas_auth=esquemas_auth,
        csrf=cabecalhos_csrf,
        captcha=captcha,
        redirecionamentos=redirecionamentos,
    )


def gravar_resumo(har: Path, destino: Path | None = None) -> Path:
    destino = destino or har.with_name(f"{har.stem}.resumo.md")
    destino.write_text(resumir(har), encoding="utf-8")
    return destino


# ---------------------------------------------------------------- partes


def _cabecalhos(mensagem: dict[str, Any]) -> dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in mensagem.get("headers", [])}


def _cookies_definidos(resposta: dict[str, Any]) -> set[str]:
    nomes = {c.get("name", "") for c in resposta.get("cookies", []) if c.get("name")}
    for h in resposta.get("headers", []):
        if h.get("name", "").lower() == "set-cookie":
            nomes.add(h.get("value", "").split("=", 1)[0].strip())
    return {n for n in nomes if n}


def _ignorar(entrada: dict[str, Any]) -> bool:
    tipo = (entrada.get("_resourceType") or "").lower()
    mime = (entrada.get("response", {}).get("content", {}).get("mimeType") or "").lower()
    caminho = urlsplit(entrada.get("request", {}).get("url", "")).path
    return (
        tipo in _IGNORAR_TIPOS
        or any(m in mime for m in _IGNORAR_MIME)
        or bool(_IGNORAR_EXT.search(caminho))
        or not entrada.get("request", {}).get("url", "").startswith("http")
    )


def _caminho_generico(caminho: str) -> str:
    """/api/contratos/123456/parcelas -> /api/contratos/{id}/parcelas (o valor pode ser dado de cliente)."""
    return "/".join("{id}" if _SEGMENTO_ID.match(parte) else parte for parte in caminho.split("/")) or "/"


def _rotulo_parametro(nome: str) -> str:
    if SENSIVEL.search(nome):
        return f"{nome} (sensível)"
    if _PAGINACAO.match(nome):
        return f"{nome} (paginação?)"
    return nome


def _corpo_enviado(post: dict[str, Any]) -> str:
    mime = (post.get("mimeType") or "").split(";")[0]
    if post.get("params"):
        nomes = [_rotulo_parametro(p.get("name", "")) for p in post["params"]]
        return f"{mime or 'form'}: {', '.join(nomes)}"
    texto = post.get("text") or ""
    if not texto:
        return ""
    if "json" in mime:
        try:
            return f"{mime}: {_formato(json.loads(texto))}"
        except ValueError:
            return f"{mime}: (JSON inválido)"
    if "x-www-form-urlencoded" in mime:
        nomes = [_rotulo_parametro(n) for n, _ in parse_qsl(texto, keep_blank_values=True)]
        return f"{mime}: {', '.join(nomes)}"
    return f"{mime or 'sem tipo'}: ({len(texto)} caracteres)"


def _formato_resposta(conteudo: dict[str, Any]) -> str:
    mime = (conteudo.get("mimeType") or "").lower()
    texto = conteudo.get("text")
    if texto is None:
        return "(corpo não gravado no .har)"
    if conteudo.get("encoding") == "base64":
        return f"(binário, {conteudo.get('size', '?')} bytes)"
    if "json" in mime:
        try:
            return _formato(json.loads(texto))
        except ValueError:
            return "(JSON inválido)"
    if "html" in mime:
        return f"(HTML, {len(texto)} caracteres: dado montado no servidor)"
    return f"({mime or 'sem tipo'}, {len(texto)} caracteres)"


def _formato(valor: Any, nivel: int = 0) -> str:
    """Estrutura do JSON sem nenhum valor: {"itens": [{"id": int, "valor": float}] (20), "total": int}."""
    if nivel >= _PROFUNDIDADE:
        return "…"
    if isinstance(valor, dict):
        partes = [
            f'"{k}": {"str (sensível)" if SENSIVEL.search(k) and not isinstance(v, (dict, list)) else _formato(v, nivel + 1)}'
            for k, v in valor.items()
        ]
        return "{" + ", ".join(partes) + "}"
    if isinstance(valor, list):
        if not valor:
            return "[] (vazia)"
        return f"[{_formato(valor[0], nivel + 1)}] ({len(valor)} itens)"
    if valor is None:
        return "null"
    return {bool: "bool", int: "int", float: "float", str: "str"}.get(type(valor), type(valor).__name__)


# ---------------------------------------------------------------- saída


def _markdown(
    nome: str,
    endpoints: list[_Endpoint],
    *,
    ignoradas: int,
    cookies: set[str],
    esquemas_auth: Counter[str],
    csrf: set[str],
    captcha: set[str],
    redirecionamentos: int,
) -> str:
    json_ = [e for e in endpoints if "json" in e.tipo_resposta]
    html = [e for e in endpoints if "html" in e.tipo_resposta]
    downloads = [e for e in endpoints if e.download]
    linhas = [
        f"# Resumo das requisições: {nome}",
        "",
        (
            f"Gerado por `core resumir-har` em {datetime.now():%d/%m/%Y %H:%M}. Só a estrutura, nenhum valor: "
            "pode ser versionado. O .har original fica fora do git."
        ),
        "",
        "## Sinais para a análise técnica",
        "",
        f"- {len(endpoints)} endpoint(s) distintos; {ignoradas} requisição(ões) ignoradas (imagens, CSS, JS, fontes).",
        f"- Respostas JSON: {len(json_)} endpoint(s). HTML: {len(html)}. Downloads (anexo): {len(downloads)}.",
        (
            f"- Autenticação: cookies definidos pelo servidor: {', '.join(sorted(cookies)) or 'nenhum'}; "
            f"cabeçalho Authorization: {', '.join(f'{k} ({n}x)' for k, n in esquemas_auth.items()) or 'não usado'}."
        ),
        f"- Proteção CSRF em cabeçalho: {', '.join(sorted(csrf)) or 'não vista'}.",
        f"- Redirecionamentos: {redirecionamentos}.",
    ]
    if captcha:
        linhas.append(
            f"- **CAPTCHA detectado** ({', '.join(sorted(captcha))}): login só por requests não é viável."
        )
    linhas += ["", "## Endpoints", ""]
    for numero, e in enumerate(endpoints, start=1):
        status = ", ".join(f"{s} ({n}x)" if n > 1 else str(s) for s, n in sorted(e.status.items()))
        media = sum(e.tempos_ms) / len(e.tempos_ms) if e.tempos_ms else 0
        linhas += [
            f"### {numero}. {e.metodo} {e.caminho}",
            "",
            f"- Host: `{e.host}` · status: {status} · {e.tipo_resposta or 'sem tipo'} · média {media:.0f} ms"
            + (" · **download**" if e.download else ""),
        ]
        if e.parametros:
            linhas.append(f"- Parâmetros na URL: {', '.join(e.parametros)}")
        if e.corpo_enviado:
            linhas.append(f"- Corpo enviado: {e.corpo_enviado}")
        linhas += [f"- Resposta: `{e.resposta}`", ""]
    return "\n".join(linhas)
