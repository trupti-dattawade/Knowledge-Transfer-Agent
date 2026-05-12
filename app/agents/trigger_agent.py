from datetime import datetime, timezone
from uuid import uuid4

from app.config import settings
from app.models.schemas import (
    KTCaseRecord,
    ResignationIntakeRequest,
    WorkflowAuditEntry,
    WorkflowState,
)
from app.services.case_store import CaseStore
from app.services.onedrive_service import OneDriveService


class TriggerAgent:
    """Captures resignation intake and creates the initial workflow case."""

    def __init__(
        self,
        case_store: CaseStore | None = None,
        file_service: OneDriveService | None = None,
    ) -> None:
        self.case_store = case_store or CaseStore()
        self.file_service = file_service or OneDriveService()

    def register_resignation(self, payload: ResignationIntakeRequest) -> KTCaseRecord:
        now = datetime.now(timezone.utc)
        case_id = self._build_case_id(payload.employee_id, now)
        workflow = WorkflowState(
            case_id=case_id,
            stage=settings.initial_stage,
            status=settings.initial_status,
            notification_status=settings.notification_status,
            created_at=now,
            updated_at=now,
            next_action="Send notifications with form link and interview schedule.",
        )
        case_record = KTCaseRecord(
            workflow=workflow,
            employee=payload,
            onedrive_folder=self.file_service.create_case_folder(case_id),
            audit_log=[
                WorkflowAuditEntry(
                    event="resignation_registered",
                    occurred_at=now,
                    actor=f"HR:{payload.hr_contact_email}",
                    details="HR intake completed and KT case created.",
                )
            ],
        )
        self.case_store.save_case(case_record)
        return case_record

    def _build_case_id(self, employee_id: str, now: datetime) -> str:
        unique_suffix = uuid4().hex[:6].upper()
        return f"{settings.case_prefix}-{employee_id}-{now:%Y%m%d}-{unique_suffix}"
