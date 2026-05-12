from datetime import datetime, timezone

from app.models.schemas import KTCaseRecord, NotificationMessage
from app.services.email_service import EmailService


class EmailAgent:
    """Handles automated email generation and local outbox storage."""

    def __init__(self, email_service: EmailService | None = None) -> None:
        self.email_service = email_service or EmailService()

    def send_case_notifications(
        self,
        case_record: KTCaseRecord,
        notifications: list[tuple[str, str, str, str]],
    ) -> list[NotificationMessage]:
        sent_messages: list[NotificationMessage] = []
        now = datetime.now(timezone.utc)
        for recipient, subject, body, category in notifications:
            message = NotificationMessage(
                recipient=recipient,
                subject=subject,
                body=body,
                category=category, # type: ignore
                sent_at=now,
            )
            self.email_service.send(case_record.workflow.case_id, message)
            sent_messages.append(message)
        return sent_messages
