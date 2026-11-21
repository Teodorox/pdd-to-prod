from pathlib import Path

from pydantic import SecretStr

from core.config import Settings


class ProjetoSettings(Settings):
    portal_usuario: str
    portal_senha: SecretStr
    arquivo_entrada: Path = Path("dados/entrada/consultas.csv")
    saida_dir: Path = Path("dados/saida")
