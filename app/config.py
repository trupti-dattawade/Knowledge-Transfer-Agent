from pathlib import Path
import os

from pydantic import BaseModel
from dotenv import load_dotenv


load_dotenv()


class Settings(BaseModel):

    app_name: str = "Knowledge Transfer Agent"
    app_version: str = "1.0.0"
    default_data_dir: Path = Path("data")
    docs_dir_name: str = "generated_docs"
    mail_dir_name: str = "mailbox"
    case_prefix: str = "KT"
    initial_stage: str = "resignation_intake"
    initial_status: str = "registered"
    notification_status: str = "pending"
    base_url: str = "http://localhost:8000"
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    smtp_host: str | None = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME")
    smtp_password: str | None = os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
    smtp_sender_email: str | None = os.getenv("SMTP_SENDER_EMAIL")
    smtp_sender_name: str = os.getenv("SMTP_SENDER_NAME", "Knowledge Transfer Agent")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    smtp_use_ssl: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    review_link_secret: str = os.getenv("REVIEW_LINK_SECRET", "kt-review-secret-dev")
    review_link_ttl_seconds: int = int(os.getenv("REVIEW_LINK_TTL_SECONDS", "604800"))
    zoom_account_id: str | None = os.getenv("ZOOM_ACCOUNT_ID")
    zoom_client_id: str | None = os.getenv("ZOOM_CLIENT_ID")
    zoom_client_secret: str | None = os.getenv("ZOOM_CLIENT_SECRET")
    zoom_user_id: str = os.getenv("ZOOM_USER_ID", "me")

    # Google Form used to collect KT submission materials from employees
    google_form_view_url: str | None = os.getenv("GOOGLE_FORM_VIEW_URL")


    @property
    def docs_dir(self) -> Path:
        return self.default_data_dir / self.docs_dir_name

    @property
    def mail_dir(self) -> Path:
        return self.default_data_dir / self.mail_dir_name

    @property
    def ai_interview_enabled(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def smtp_enabled(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_username
            and self.smtp_password
            and self.smtp_sender_email
        )

    @property
    def zoom_enabled(self) -> bool:
        return bool(self.zoom_account_id and self.zoom_client_id and self.zoom_client_secret)


settings = Settings()
