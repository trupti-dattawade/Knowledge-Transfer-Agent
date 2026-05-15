from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class ResignationIntakeRequest(BaseModel):
    employee_id: str = Field(..., min_length=2, max_length=50)
    employee_name: str = Field(..., min_length=2, max_length=100)
    employee_email: EmailStr
    department: str = Field(..., min_length=2, max_length=100)
    job_title: str = Field(..., min_length=2, max_length=100)
    manager_name: str = Field(..., min_length=2, max_length=100)
    manager_email: EmailStr
    hr_contact_name: str = Field(..., min_length=2, max_length=100)
    hr_contact_email: EmailStr
    resignation_date: date
    last_working_day: date
    reason_for_exit: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1_000)

    @field_validator("employee_id")
    @classmethod
    def normalize_employee_id(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "employee_name",
        "department",
        "job_title",
        "manager_name",
        "hr_contact_name",
        "reason_for_exit",
        "notes",
    )
    @classmethod
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None

    @field_validator("last_working_day")
    @classmethod
    def validate_last_working_day(cls, value: date, info) -> date:
        resignation_date = info.data.get("resignation_date")
        if resignation_date and value < resignation_date:
            raise ValueError("last_working_day cannot be earlier than resignation_date")
        return value


class NotificationMessage(BaseModel):
    recipient: EmailStr
    subject: str
    body: str
    html_body: Optional[str] = None
    attachments: list[str] = Field(default_factory=list)
    category: Literal[
        "resignation_registered",
        "submission_received",
        "interview_scheduled",
        "documentation_ready",
        "changes_requested",
        "workflow_completed",
    ]
    sent_at: datetime


class SubmissionArtifact(BaseModel):
    name: str
    category: Literal["document", "access", "process", "project", "notes", "other"]
    description: str


class EmployeeSubmissionRequest(BaseModel):
    submitted_by: EmailStr
    documents: list[SubmissionArtifact] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    open_tasks: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=1_500)

    @field_validator("systems", "open_tasks", "risks")
    @classmethod
    def normalize_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None


class InterviewScheduleRequest(BaseModel):
    scheduled_by: EmailStr
    interview_datetime: datetime
    duration_minutes: int = Field(default=60, ge=15, le=180)
    meeting_link: Optional[str] = Field(default=None, max_length=500)
    interview_link: Optional[str] = Field(default=None, max_length=500)


class InterviewQuestionAnswer(BaseModel):
    question: str
    answer: str


class InterviewChatMessage(BaseModel):
    role: Literal["agent", "employee"]
    content: str
    topic: Optional[str] = None
    created_at: datetime


class InterviewSession(BaseModel):
    session_id: str
    status: Literal["not_started", "in_progress", "completed"]
    current_topic_index: int = 0
    current_follow_up_count: int = 0
    pending_question: Optional[str] = None
    pending_topic: Optional[str] = None
    transcript: list[InterviewChatMessage] = Field(default_factory=list)
    captured_qna: list[InterviewQuestionAnswer] = Field(default_factory=list)
    started_at: datetime
    updated_at: datetime


class InterviewCaptureRequest(BaseModel):
    interviewer: str = Field(..., min_length=2, max_length=100)
    summary: str = Field(..., min_length=20, max_length=3_000)
    responsibilities: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    project_insights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    qna: list[InterviewQuestionAnswer] = Field(default_factory=list)

    @field_validator(
        "responsibilities",
        "workflows",
        "tools",
        "project_insights",
        "risks",
        "recommendations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class ReviewDecisionRequest(BaseModel):
    reviewer_email: EmailStr
    reviewer_name: str = Field(..., min_length=2, max_length=100)
    decision: Literal["approved", "changes_requested"]
    comments: str = Field(..., min_length=5, max_length=2_000)


class WorkflowAuditEntry(BaseModel):
    event: str
    occurred_at: datetime
    actor: str
    details: str


class InterviewSchedule(BaseModel):
    interview_datetime: datetime
    duration_minutes: int
    meeting_link: Optional[str] = None
    interview_link: Optional[str] = None
    scheduled_by: EmailStr


class InterviewRecord(BaseModel):
    interviewer: str
    summary: str
    responsibilities: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    project_insights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    qna: list[InterviewQuestionAnswer] = Field(default_factory=list)
    captured_at: datetime


class GeneratedDocumentation(BaseModel):
    title: str
    summary: str
    key_responsibilities: list[str] = Field(default_factory=list)
    daily_workflows: list[str] = Field(default_factory=list)
    systems_and_tools: list[str] = Field(default_factory=list)
    project_insights: list[str] = Field(default_factory=list)
    risks_and_dependencies: list[str] = Field(default_factory=list)
    handover_checklist: list[str] = Field(default_factory=list)
    reviewer_guidance: str
    storage_path: str
    share_link: str
    generated_at: datetime


class ReviewRecord(BaseModel):
    reviewer_email: EmailStr
    reviewer_name: str
    decision: Literal["approved", "changes_requested"]
    comments: str
    reviewed_at: datetime


class WorkflowState(BaseModel):
    case_id: str
    stage: Literal[
        "resignation_intake",
        "notifications_sent",
        "submission_received",
        "interview_scheduled",
        "interview_completed",
        "documentation_generated",
        "under_review",
        "changes_requested",
        "completed",
    ]
    status: Literal[
        "registered",
        "in_progress",
        "awaiting_employee",
        "awaiting_interview",
        "awaiting_review",
        "changes_requested",
        "completed",
    ]
    notification_status: Literal["pending", "sent"]
    created_at: datetime
    updated_at: datetime
    next_action: str


class KTCaseRecord(BaseModel):
    workflow: WorkflowState
    employee: ResignationIntakeRequest
    notifications: list[NotificationMessage] = Field(default_factory=list)
    form_link: Optional[str] = None
    onedrive_folder: Optional[str] = None
    interview_schedule: Optional[InterviewSchedule] = None
    interview_session: Optional[InterviewSession] = None
    submission: Optional[EmployeeSubmissionRequest] = None
    interview: Optional[InterviewRecord] = None
    documentation: Optional[GeneratedDocumentation] = None
    review: Optional[ReviewRecord] = None
    used_review_action_tokens: list[str] = Field(default_factory=list)
    final_confirmation_sent_at: Optional[datetime] = None
    audit_log: list[WorkflowAuditEntry] = Field(default_factory=list)


class ResignationIntakeResponse(BaseModel):
    message: str
    case_id: str
    workflow_stage: str
    workflow_status: str
    notification_status: str
    next_action: str
    created_at: datetime


class WorkflowSummaryResponse(BaseModel):
    case_id: str
    employee_name: str
    employee_email: EmailStr
    manager_email: EmailStr
    department: str
    stage: str
    status: str
    notification_status: str
    next_action: str
    last_updated_at: datetime


class DashboardResponse(BaseModel):
    total_cases: int
    completed_cases: int
    pending_review_cases: int
    awaiting_employee_cases: int
    cases: list[WorkflowSummaryResponse]


class WorkflowDetailResponse(BaseModel):
    case: KTCaseRecord


class OperationResponse(BaseModel):
    message: str
    case_id: str
    stage: str
    status: str
    next_action: str


class GenerateDocumentationRequest(BaseModel):
    generated_by: str = Field(..., min_length=2, max_length=100)

    @field_validator("generated_by")
    @classmethod
    def normalize_generated_by(cls, value: str) -> str:
        return value.strip()


class CompleteWorkflowRequest(BaseModel):
    completed_by: EmailStr


class LiveInterviewStartRequest(BaseModel):
    interviewer_name: str = Field(..., min_length=2, max_length=100)


class LiveInterviewResponseRequest(BaseModel):
    answer: str = Field(..., min_length=2, max_length=3000)

    @field_validator("answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        return value.strip()


class LiveInterviewStateResponse(BaseModel):
    case_id: str
    session_id: str
    status: str
    pending_question: Optional[str]
    transcript: list[InterviewChatMessage]
    next_action: str


class CaseSearchFilters(BaseModel):
    stage: Optional[str] = None
    status: Optional[str] = None

    @model_validator(mode="after")
    def strip_values(self) -> "CaseSearchFilters":
        if self.stage:
            self.stage = self.stage.strip()
        if self.status:
            self.status = self.status.strip()
        return self
