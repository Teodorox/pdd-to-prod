"""automacao iniciar / atualizar: estrutura do robô numa pasta nova, a partir do pacote."""

from pathlib import Path

import pytest

from core import modelo


@pytest.fixture
def robo(tmp_path: Path) -> Path:
    pasta = tmp_path / "extracao-test"
    pasta.mkdir()
    (pasta / "pyproject.toml").write_text(
        '[project]\nname = "extracao-test"\nversion = "0.1.0"\ndependencies = ["automacao-core"]\n',
        encoding="utf-8",
    )
    return pasta


def test_iniciar_cria_a_estrutura_sem_o_core(robo: Path) -> None:
    feitos = modelo.iniciar(robo)

    for arquivo in (
        ".github/copilot-instructions.md",
        ".github/prompts/analisar-tecnica.prompt.md",
        "scripts/instalar.ps1",
        "projeto/main.py",
        "tests/conftest.py",
        "docs/pdd.md",
        "docs/modelos/analise_tecnica.md",
        "GUIA.md",
        "README.md",
    ):
        assert (robo / arquivo).is_file(), arquivo
    assert not (robo / "core").exists()  # o core fica no pacote instalado
    assert not (robo / "tests" / "test_core.py").exists()  # testes do template não vão para o robô
    assert not any("__pycache__" in f for f in feitos)
    assert "AUTOMACAO_NOME=extracao_test" in (robo / ".env.example").read_text(encoding="utf-8")
    pyproject = (robo / "pyproject.toml").read_text(encoding="utf-8")
    assert "[dependency-groups]" in pyproject and 'known-first-party = ["core", "projeto"]' in pyproject


def test_iniciar_nao_sobrescreve_e_atualizar_so_renova_o_padrao(robo: Path) -> None:
    modelo.iniciar(robo)
    (robo / "docs" / "pdd.md").write_text("# PDD: Extrato\n", encoding="utf-8")
    (robo / "projeto" / "main.py").write_text("# robô de verdade\n", encoding="utf-8")
    prompt = robo / ".github" / "prompts" / "nova-automacao.prompt.md"
    prompt.write_text("editado à mão no robô\n", encoding="utf-8")

    assert "docs/pdd.md" not in modelo.iniciar(robo)  # rodar de novo não apaga nada

    anterior, feitos = modelo.atualizar(robo)
    assert anterior == modelo.versao()
    assert feitos == [".github/prompts/nova-automacao.prompt.md"]  # só o que mudou
    assert "editado à mão" not in prompt.read_text(encoding="utf-8")
    assert (robo / "docs" / "pdd.md").read_text(encoding="utf-8") == "# PDD: Extrato\n"
    assert (robo / "projeto" / "main.py").read_text(encoding="utf-8") == "# robô de verdade\n"


def test_nao_inicia_dentro_do_template_nem_atualiza_pasta_que_nao_e_robo(tmp_path: Path) -> None:
    with pytest.raises(modelo.ModeloNaoEncontrado, match="falta projeto/"):
        modelo.atualizar(tmp_path)
    with pytest.raises(modelo.ModeloNaoEncontrado, match="próprio template"):
        modelo.iniciar(Path(modelo.core.__file__).parent.parent)


def test_atualizar_remove_o_que_saiu_do_padrao_e_completa_o_gitignore(robo: Path) -> None:
    modelo.iniciar(robo)
    (robo / "scripts" / "servico.ps1").write_text("# serviço antigo\n", encoding="utf-8")
    (robo / ".gitignore").write_text(".venv/\n.env\n", encoding="utf-8")  # .gitignore de versão antiga

    _, feitos = modelo.atualizar(robo)

    assert not (robo / "scripts" / "servico.ps1").exists()
    assert (robo / "scripts" / "agendar.ps1").exists()
    linhas = (robo / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert {"docs/recordings/*", "docs/screenshots/*", "!docs/recordings/.gitkeep", "*.har"} <= set(linhas)
    assert linhas.count(".env") == 1
    assert any("servico.ps1" in f for f in feitos) and any(".gitignore" in f for f in feitos)
    assert modelo.atualizar(robo)[1] == []  # rodar de novo não muda nada
