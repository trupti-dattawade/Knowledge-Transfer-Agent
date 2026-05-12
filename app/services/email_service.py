import json
import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.config import settings
from app.models.schemas import NotificationMessage


class EmailService:
    """Sends real email through SMTP and stores a local outbox copy."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.mail_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def send(self, case_id: str, message: NotificationMessage) -> Path:
        if settings.smtp_enabled:
            self._send_via_smtp(message)
        return self._write_outbox_copy(case_id, message)

    def _send_via_smtp(self, message: NotificationMessage) -> None:
        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = f"{settings.smtp_sender_name} <{settings.smtp_sender_email}>"
        email["To"] = str(message.recipient)
        email.set_content(message.body)

        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
                server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(email)
            return

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            if settings.smtp_use_tls:
                server.starttls()
                server.ehlo()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(email)

    def _write_outbox_copy(self, case_id: str, message: NotificationMessage) -> Path:
        case_dir = self.base_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        recipient_slug = str(message.recipient).replace("@", "_at_").replace(".", "_")
        file_path = case_dir / f"{message.sent_at:%Y%m%dT%H%M%S}_{recipient_slug}.json"
        file_path.write_text(
            json.dumps(message.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return file_path
