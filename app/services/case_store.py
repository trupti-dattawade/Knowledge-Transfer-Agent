import json
from pathlib import Path

from app.config import settings
from app.models.schemas import KTCaseRecord


class CaseStore:
    """JSON-backed store for workflow records."""

    def __init__(self, file_path: Path | None = None) -> None:
        data_dir = settings.default_data_dir
        self.file_path = file_path or data_dir / "kt_cases.json"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def save_case(self, case_record: KTCaseRecord) -> None:
        cases = self.list_cases()
        cases.append(case_record)
        self._write_cases(cases)

    def list_cases(self) -> list[KTCaseRecord]:
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        return [KTCaseRecord.model_validate(item) for item in payload]

    def get_case(self, case_id: str) -> KTCaseRecord:
        for case_record in self.list_cases():
            if case_record.workflow.case_id == case_id:
                return case_record
        raise KeyError(f"Case {case_id} not found")

    def update_case(self, updated_case: KTCaseRecord) -> None:
        cases = self.list_cases()
        replaced = False
        for index, case_record in enumerate(cases):
            if case_record.workflow.case_id == updated_case.workflow.case_id:
                cases[index] = updated_case
                replaced = True
                break
        if not replaced:
            raise KeyError(f"Case {updated_case.workflow.case_id} not found")
        self._write_cases(cases)

    def _write_cases(self, cases: list[KTCaseRecord]) -> None:
        serialized = [case.model_dump(mode="json") for case in cases]
        self.file_path.write_text(
            json.dumps(serialized, indent=2),
            encoding="utf-8",
        )
