"""Monta e atualiza a estrutura de um robô a partir do pacote automacao-core.

    uv run automacao iniciar     # pasta nova: cria projeto/, docs/, tests/, scripts/, .github/...
    uv run automacao atualizar   # depois de subir a versão do automacao-core: renova o que é do padrão

Dois tipos de arquivo:
- do PADRÃO (instruções do Copilot, prompts, scripts, modelos, guia): `atualizar` sobrescreve. Não edite no robô.
- do ROBÔ (projeto/, tests/, PDD, dúvidas, .env.example, .gitignore): só são criados se não existirem.
  `atualizar` nunca mexe neles.
"""

import shutil
from collections.abc import Iterator
from importlib import metadata
from pathlib import Path

import core

# origem no pacote -> destino no robô
DO_PADRAO: dict[str, str] = {
    ".github/copilot-instructions.md": ".github/copilot-instructions.md",
    ".github/prompts": ".github/prompts",
    "CLAUDE.md": "CLAUDE.md",
    "scripts": "scripts",
    "docs/modelos": "docs/modelos",
    "docs/monitoramento": "docs/monitoramento",
    "docs/padroes/README.md": "docs/padroes/README.md",
    "docs/requisicoes/README.md": "docs/requisicoes/README.md",
    "docs/passo_a_passo.md": "docs/passo_a_passo.md",
    "README.md": "GUIA.md",
}
DO_ROBO: dict[str, str] = {
    "projeto": "projeto",
    "tests/conftest.py": "tests/conftest.py",
    "tests/test_exemplo_extracao.py": "tests/test_exemplo_extracao.py",
    "tests/portal_fake": "tests/portal_fake",
    "dados/entrada/consultas.csv": "dados/entrada/consultas.csv",
    "docs/pdd.md": "docs/pdd.md",
    "docs/duvidas.md": "docs/duvidas.md",
    "docs/transcricao/.gitkeep": "docs/transcricao/.gitkeep",
    "docs/documento_cliente/.gitkeep": "docs/documento_cliente/.gitkeep",
    "docs/screenshots/.gitkeep": "docs/screenshots/.gitkeep",
    "docs/recordings/.gitkeep": "docs/recordings/.gitkeep",
    ".env.example": ".env.example",
    ".gitignore": ".gitignore",
    ".vscode/mcp.json": ".vscode/mcp.json",
    ".python-version": ".python-version",
}
ARQUIVO_VERSAO = ".automacao-padrao"  # versão do padrão aplicada por último (iniciar/atualizar)
# Arquivos que saíram do padrão: `atualizar` apaga do robô
OBSOLETOS = ("scripts/servico.ps1",)
# O .gitignore é do robô, mas estas regras protegem dados e senhas: `atualizar` acrescenta as que faltarem
GITIGNORE_OBRIGATORIO = (
    ".env",
    "*.har",
    "docs/transcricao/*",
    "docs/documento_cliente/*",
    "docs/screenshots/*",
    "docs/recordings/*",
    "agendamento/",
)

_PYPROJECT_EXTRA = {
    "[dependency-groups]": (
        "[dependency-groups]\n"
        "# pytest/ruff: testes e lint. python-docx: exportar o PDD para Word (core exportar-pdd)\n"
        'dev = ["pytest>=8", "python-docx>=1.1", "ruff>=0.6"]\n'
    ),
    "[tool.pytest.ini_options]": '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["."]\n',
    "[tool.ruff]": (
        "[tool.ruff]\nline-length = 110\n\n"
        "[tool.ruff.lint.isort]\n"
        "# core vem do pacote automacao-core, mas conta como parte do projeto (igual ao template)\n"
        'known-first-party = ["core", "projeto"]\n'
    ),
}


class ModeloNaoEncontrado(Exception):
    pass


def versao() -> str:
    try:
        return metadata.version("automacao-core")
    except metadata.PackageNotFoundError:
        return "dev"


def origem() -> Path:
    """Onde estão os arquivos do modelo: dentro do pacote instalado, ou a raiz do repositório do template."""
    pacote = Path(core.__file__).parent
    for candidata in (pacote / "_modelo", pacote.parent):
        if (candidata / ".github" / "copilot-instructions.md").exists():
            return candidata
    raise ModeloNaoEncontrado(
        f"Arquivos do modelo não encontrados no pacote ({pacote}). Reinstale o automacao-core."
    )


def iniciar(raiz: Path) -> list[str]:
    """Cria a estrutura do robô na pasta. Não sobrescreve nada que já exista."""
    if (raiz / "core" / "runner.py").exists():
        raise ModeloNaoEncontrado("Esta pasta é o próprio template (tem core/). Rode em uma pasta de robô.")
    fonte = origem()
    feitos = [
        *_copiar(fonte, raiz, DO_PADRAO, sobrescrever=False),
        *_copiar(fonte, raiz, DO_ROBO, sobrescrever=False),
    ]
    nome = raiz.resolve().name
    _ajustar_nome(raiz / ".env.example", nome)
    leia = raiz / "README.md"
    if not leia.exists() or not leia.read_text(encoding="utf-8").strip():
        leia.write_text(_readme(nome), encoding="utf-8")
        feitos.append("README.md")
    feitos += _completar_pyproject(raiz / "pyproject.toml")
    (raiz / ARQUIVO_VERSAO).write_text(versao() + "\n", encoding="utf-8")
    return feitos


def atualizar(raiz: Path) -> tuple[str, list[str]]:
    """Renova os arquivos do padrão. Devolve a versão anterior e o que foi atualizado."""
    if not (raiz / "projeto").is_dir():
        raise ModeloNaoEncontrado(
            "Não parece uma pasta de robô (falta projeto/). Para começar um, use: automacao iniciar"
        )
    anterior = (
        (raiz / ARQUIVO_VERSAO).read_text(encoding="utf-8").strip()
        if (raiz / ARQUIVO_VERSAO).exists()
        else "?"
    )
    feitos = _copiar(origem(), raiz, DO_PADRAO, sobrescrever=True)
    for obsoleto in OBSOLETOS:
        if (raiz / obsoleto).exists():
            (raiz / obsoleto).unlink()
            feitos.append(f"{obsoleto} (removido: saiu do padrão)")
    feitos += _completar_gitignore(raiz / ".gitignore")
    (raiz / ARQUIVO_VERSAO).write_text(versao() + "\n", encoding="utf-8")
    return anterior, feitos


# ---------------------------------------------------------------- partes


def _copiar(fonte: Path, raiz: Path, mapa: dict[str, str], *, sobrescrever: bool) -> list[str]:
    feitos = []
    for de, para in mapa.items():
        for arquivo_origem, arquivo_destino in _arquivos(fonte / de, raiz / para):
            if arquivo_destino.exists() and not sobrescrever:
                continue
            if arquivo_destino.exists() and arquivo_destino.read_bytes() == arquivo_origem.read_bytes():
                continue
            arquivo_destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(arquivo_origem, arquivo_destino)
            feitos.append(arquivo_destino.relative_to(raiz).as_posix())
    return feitos


def _arquivos(origem_: Path, destino: Path) -> Iterator[tuple[Path, Path]]:
    if origem_.is_file():
        yield origem_, destino
        return
    if not origem_.is_dir():
        raise ModeloNaoEncontrado(f"Falta {origem_} no pacote. Reinstale o automacao-core.")
    for arquivo in sorted(origem_.rglob("*")):
        if arquivo.is_file() and "__pycache__" not in arquivo.parts and arquivo.suffix != ".pyc":
            yield arquivo, destino / arquivo.relative_to(origem_)


def _ajustar_nome(env_example: Path, nome: str) -> None:
    if not env_example.exists():
        return
    linhas = env_example.read_text(encoding="utf-8").splitlines()
    nome_env = nome.replace("-", "_")
    linhas = [
        f"AUTOMACAO_NOME={nome_env}" if linha.startswith("AUTOMACAO_NOME=extracao_exemplo") else linha
        for linha in linhas
    ]
    env_example.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _completar_gitignore(gitignore: Path) -> list[str]:
    texto = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    linhas = {linha.strip() for linha in texto.splitlines()}
    faltando = [regra for regra in GITIGNORE_OBRIGATORIO if regra not in linhas]
    if not faltando:
        return []
    excecoes = [f"!{r[:-1]}.gitkeep" for r in faltando if r.endswith("/*")]
    bloco = "\n# Regras obrigatórias do padrão (dados do cliente, senhas)\n" + "\n".join(faltando + excecoes)
    gitignore.write_text(texto.rstrip() + "\n" + bloco + "\n", encoding="utf-8")
    return [f".gitignore (+ {', '.join(faltando)})"]


def _completar_pyproject(pyproject: Path) -> list[str]:
    if not pyproject.exists():
        raise ModeloNaoEncontrado(
            "Falta o pyproject.toml. Comece com: uv init --bare, depois uv add automacao-core (do repositório Git)."
        )
    texto = pyproject.read_text(encoding="utf-8")
    faltando = [bloco for secao, bloco in _PYPROJECT_EXTRA.items() if secao not in texto]
    if not faltando:
        return []
    pyproject.write_text(texto.rstrip() + "\n\n" + "\n".join(faltando), encoding="utf-8")
    return ["pyproject.toml (testes, lint e dependências de desenvolvimento)"]


def _readme(nome: str) -> str:
    return (
        f"# {nome}\n\n"
        f"Robô de extração criado com o automacao-core {versao()}.\n\n"
        "- O que o robô faz: [docs/pdd.md](docs/pdd.md)\n"
        "- Como trabalhar (fluxo, prompts do Copilot, instalação, serviço): [GUIA.md](GUIA.md)\n"
        "- Onde o desenvolvimento está: `uv run python -m core fases --abrir`\n"
    )
