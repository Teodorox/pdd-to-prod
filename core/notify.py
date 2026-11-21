"""Notificação de falhas. Canais configurados em NOTIFICAR_VIA (log, teams, email)."""

import logging
import mimetypes
import smtplib
from collections.abc import Callable, Sequence
from email.message import EmailMessage
from pathlib import Path

import requests

from core.config import Settings

_LIMITE_ANEXO_BYTES = 5 * 1024 * 1024


class Notificador:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._log = logging.getLogger("notificacao")
        self._canais: dict[str, Callable[[str, str, list[Path]], None]] = {
            "log": self._via_log,
            "teams": self._via_teams,
            "email": self._via_email,
        }
        desconhecidos = set(settings.canais_notificacao) - self._canais.keys()
        if desconhecidos:
            raise ValueError(f"NOTIFICAR_VIA com canal desconhecido: {sorted(desconhecidos)}")

    def enviar(self, titulo: str, mensagem: str, anexos: Sequence[Path] = ()) -> None:
        existentes = [a for a in anexos if a.exists()]
        for canal in self._settings.canais_notificacao:
            try:
                self._canais[canal](titulo, mensagem, existentes)
            except Exception:  # noqa: BLE001
                # Falha ao notificar não pode esconder o erro original
                self._log.exception("Falha ao notificar via %s", canal)

    def _via_log(self, titulo: str, mensagem: str, anexos: list[Path]) -> None:
        self._log.warning("%s\n%s", titulo, mensagem)

    def _via_teams(self, titulo: str, mensagem: str, anexos: list[Path]) -> None:
        """Webhook do Teams (Workflows/Power Automate ou conector de entrada) com Adaptive Card."""
        assert self._settings.teams_webhook_url, "TEAMS_WEBHOOK_URL não configurado"
        cartao = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {"type": "TextBlock", "text": titulo, "weight": "Bolder", "size": "Medium", "wrap": True},
                {"type": "TextBlock", "text": mensagem, "wrap": True},
            ],
        }
        payload = {
            "type": "message",
            "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": cartao}],
        }
        resposta = requests.post(
            self._settings.teams_webhook_url.get_secret_value(), json=payload, timeout=15
        )
        resposta.raise_for_status()

    def _via_email(self, titulo: str, mensagem: str, anexos: list[Path]) -> None:
        s = self._settings
        assert s.smtp_host and s.email_de and s.destinatarios_email, (
            "SMTP_HOST, EMAIL_DE e EMAIL_PARA são obrigatórios"
        )
        msg = EmailMessage()
        msg["Subject"] = titulo
        msg["From"] = s.email_de
        msg["To"] = ", ".join(s.destinatarios_email)
        msg.set_content(mensagem)
        for anexo in anexos:
            if anexo.stat().st_size > _LIMITE_ANEXO_BYTES:
                continue
            tipo = mimetypes.guess_type(anexo.name)[0] or "application/octet-stream"
            principal, sub = tipo.split("/", 1)
            msg.add_attachment(anexo.read_bytes(), maintype=principal, subtype=sub, filename=anexo.name)

        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_usuario and s.smtp_senha:
                smtp.login(s.smtp_usuario, s.smtp_senha.get_secret_value())
            smtp.send_message(msg)
