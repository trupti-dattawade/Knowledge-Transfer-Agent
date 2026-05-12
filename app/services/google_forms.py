from app.config import settings


class GoogleFormsService:
    """Builds local placeholder Google Form links for the MVP."""

    def create_form_link(self, case_id: str) -> str:
        return f"{settings.base_url}/api/v1/kt/cases/{case_id}/submission-template"
