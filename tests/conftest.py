import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from core.testes import servir_pasta  # o plugin do automacao-core também traz o fixture api_fake
from projeto.config import ProjetoSettings

PORTAL_DIR = Path(__file__).parent / "portal_fake"


@pytest.fixture(scope="session")
def portal_url() -> Iterator[str]:
    with servir_pasta(PORTAL_DIR) as url:
        yield url


@pytest.fixture
def settings(tmp_path: Path, portal_url: str) -> ProjetoSettings:
    return ProjetoSettings(
        _env_file=None,
        automacao_nome="teste",
        base_url=portal_url,
        portal_usuario="operador",
        portal_senha="senha-teste",
        headless=os.environ.get("HEADLESS", "true").lower() != "false",  # HEADLESS=false: ver na tela
        slow_mo_ms=int(os.environ.get("SLOW_MO_MS", "0")),
        timeout_ms=5_000,
        evidencias_dir=tmp_path / "evidencias",
        logs_dir=tmp_path / "logs",
        estado_db=tmp_path / "estado.db",
        saida_dir=tmp_path / "saida",
    )
