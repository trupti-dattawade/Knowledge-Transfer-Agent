from app.config import settings


class GoogleFormsService:
    """Builds Google Form links for KT submissions.

    Uses a single shared Google Form URL configured via environment.
    """

    def create_form_link(self, case_id: str) -> str:
        if not settings.google_form_view_url:
            raise RuntimeError(
                "Missing configuration: GOOGLE_FORM_VIEW_URL. "
                "Set it in the environment to the Google Form view URL."
            )
        # Optional: you can add prefill query params later (if you configure the form).
        return settings.google_form_view_url


