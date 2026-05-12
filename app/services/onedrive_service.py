from pathlib import Path

from app.config import settings


class OneDriveService:
    """Stores workflow files in a local folder that mirrors OneDrive usage."""

    def __init__(self, docs_dir: Path | None = None) -> None:
        self.docs_dir = docs_dir or settings.docs_dir
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def create_case_folder(self, case_id: str) -> str:
        folder = self.docs_dir / case_id
        folder.mkdir(parents=True, exist_ok=True)
        return str(folder)

    def build_share_link(self, case_id: str) -> str:
        return f"{settings.base_url}/api/v1/kt/cases/{case_id}/documentation"

    def save_document(self, case_id: str, filename: str, content: str) -> str:
        case_folder = self.docs_dir / case_id
        case_folder.mkdir(parents=True, exist_ok=True)
        document_path = case_folder / filename
        document_path.write_text(content, encoding="utf-8")
        return str(document_path)

    def save_binary_document(self, case_id: str, filename: str, content: bytes) -> str:
        case_folder = self.docs_dir / case_id
        case_folder.mkdir(parents=True, exist_ok=True)
        document_path = case_folder / filename
        document_path.write_bytes(content)
        return str(document_path)
