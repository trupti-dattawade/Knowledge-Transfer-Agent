from app.services.google_forms import GoogleFormsService
from app.services.onedrive_service import OneDriveService


class FileManagementAgent:
    """Prepares links and file-system locations used across the workflow."""

    def __init__(
        self,
        forms_service: GoogleFormsService | None = None,
        onedrive_service: OneDriveService | None = None,
    ) -> None:
        self.forms_service = forms_service or GoogleFormsService()
        self.onedrive_service = onedrive_service or OneDriveService()

    def create_form_link(self, case_id: str) -> str:
        return self.forms_service.create_form_link(case_id)

    def create_share_link(self, case_id: str) -> str:
        return self.onedrive_service.build_share_link(case_id)
