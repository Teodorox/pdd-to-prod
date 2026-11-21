"""Configuração base lida do .env. Cada projeto estende `Settings` com os próprios campos (ver projeto/config.py)."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    automacao_nome: str = "automacao"
    dry_run: bool = False

    # Navegador
    headless: bool = True
    canal_navegador: str | None = None
    # Chromium do Playwright dentro do projeto (instalar.ps1), e não no perfil de quem instalou
    navegadores_dir: Path = Path("navegadores")
    timeout_ms: int = 15_000
    slow_mo_ms: int = 0
    base_url: str = ""
    storage_state: Path | None = None
    proxy_server: str | None = None

    # Execução
    max_tentativas_item: int = 3
    max_erros_consecutivos: int = 3
    # falha = guarda o trace só quando o item falha; sempre = guarda de todos (útil em DEV/homologação)
    trace: Literal["falha", "sempre"] = "falha"

    # Agendamento (Agendador de Tarefas do Windows, criado por scripts/agendar.ps1 a partir destes campos)
    agenda_dias: str = "seg,ter,qua,qui,sex"
    agenda_horarios: str = ""
    agenda_tolerancia_min: int = 60
    agenda_timeout_min: int = 240

    # Monitoramento central (banco). Vazio = não grava (desenvolvimento local)
    monitor_url: SecretStr | None = None
    monitor_schema: str | None = None
    monitor_heartbeat_min: int = 5

    # Saídas
    evidencias_dir: Path = Path("evidencias")
    logs_dir: Path = Path("logs")
    estado_db: Path = Path("estado.db")

    # Notificação
    notificar_via: str = "log"
    teams_webhook_url: SecretStr | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_starttls: bool = True
    smtp_usuario: str | None = None
    smtp_senha: SecretStr | None = None
    email_de: str | None = None
    email_para: str = ""

    @property
    def canais_notificacao(self) -> list[str]:
        return _lista(self.notificar_via)

    @property
    def destinatarios_email(self) -> list[str]:
        return _lista(self.email_para)


def _lista(valor: str) -> list[str]:
    return [parte.strip() for parte in valor.split(",") if parte.strip()]
