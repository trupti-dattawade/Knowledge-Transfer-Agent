from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from app.agents.orchestrator import WorkflowOrchestrator
from app.models.schemas import (
    CompleteWorkflowRequest,
    DashboardResponse,
    EmployeeSubmissionRequest,
    GenerateDocumentationRequest,
    OperationResponse,
    ResignationIntakeRequest,
    ResignationIntakeResponse,
    ReviewDecisionRequest,
    WorkflowDetailResponse,
    WorkflowSummaryResponse,
)


router = APIRouter(prefix="/api/v1/kt", tags=["knowledge-transfer"])
orchestrator = WorkflowOrchestrator()


class CurrentUser(BaseModel):
    role: Literal["hr", "manager", "employee"]
    email: str
    name: str


def get_current_user(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_name: str | None = Header(default=None, alias="X-User-Name"),
    # Query-param based impersonation is intentionally disabled.
    # Identity should come from X-User-* headers only.
    role: str | None = Query(default=None, include_in_schema=False),
    email: str | None = Query(default=None, include_in_schema=False),
    name: str | None = Query(default=None, include_in_schema=False),
) -> CurrentUser:
    if role or email or name:
        raise HTTPException(
            status_code=401,
            detail="Query parameters for identity are not allowed; use X-User-* headers.",
        )

    resolved_role = (x_user_role or "").strip().lower()
    resolved_email = (x_user_email or email or "").strip().lower()
    resolved_name = (x_user_name or name or "").strip()

    if resolved_role not in {"hr", "manager", "employee"}:
        raise HTTPException(status_code=401, detail="Valid user role is required.")
    if not resolved_email:
        raise HTTPException(status_code=401, detail="User email is required.")
    if not resolved_name:
        resolved_name = resolved_email

    return CurrentUser(role=resolved_role, email=resolved_email, name=resolved_name)


def _enforce_employee_visibility(case_record, user: CurrentUser):
    """Return a case object that is safe to send to the employee."""
    if user.role != "employee":
        return case_record
    # Employee must only see their own case; sensitive HR/manager fields are removed.
    safe = case_record.model_copy(deep=True)
    safe.employee.employee_email = "restricted@company.local"
    safe.employee.manager_name = "Restricted"
    safe.employee.manager_email = "restricted@company.local"
    safe.employee.hr_contact_name = "Restricted"
    safe.employee.hr_contact_email = "restricted@company.local"
    safe.employee.reason_for_exit = None
    safe.employee.notes = None
    safe.notifications = []
    safe.interview_session = None
    safe.interview = None
    safe.audit_log = []
    return safe


def _assert_role(user: CurrentUser, *allowed_roles: Literal["hr", "manager", "employee"]) -> None:
    if user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="You are not allowed to perform this action.")


def _assert_case_access(case_record, user: CurrentUser) -> None:
    if user.role == "hr":
        return
    if user.role == "manager" and str(case_record.employee.manager_email).lower() == user.email:
        return
    if user.role == "employee" and str(case_record.employee.employee_email).lower() == user.email:
        return
    raise HTTPException(status_code=403, detail="You are not allowed to access this case.")


def _assert_submission_access(case_record, user: CurrentUser) -> None:
    _assert_role(user, "employee")
    _assert_case_access(case_record, user)


def _assert_review_access(case_record, user: CurrentUser) -> None:
    _assert_role(user, "manager")
    _assert_case_access(case_record, user)


def _assert_review_ready(case_record) -> None:
    workflow = case_record.workflow
    if workflow.stage != "under_review" and workflow.status != "awaiting_review":
        raise HTTPException(status_code=409, detail="This case is not ready for manager review.")


def _restrict_case_for_hr(case_record):
    if case_record.submission:
        case_record.submission.systems = []
        case_record.submission.open_tasks = []
        case_record.submission.risks = []
        case_record.submission.notes = None

    case_record.employee.employee_email = "restricted@company.local"
    case_record.employee.manager_name = "Restricted"
    case_record.employee.manager_email = "restricted@company.local"
    case_record.employee.hr_contact_name = "Restricted"
    case_record.employee.hr_contact_email = "restricted@company.local"
    case_record.employee.reason_for_exit = None
    case_record.employee.notes = None
    case_record.notifications = []
    case_record.interview_session = None
    case_record.interview = None
    case_record.audit_log = []
    return case_record


def _present_case_for_user(case_record, user: CurrentUser):
    if user.role == "hr":
        return _restrict_case_for_hr(case_record.model_copy(deep=True))
    if user.role == "employee":
        return _enforce_employee_visibility(case_record.model_copy(deep=True), user)
    return case_record


@router.post(
    "/resignations/intake",
    response_model=ResignationIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
def resignation_intake(
    payload: ResignationIntakeRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ResignationIntakeResponse:
    _assert_role(user, "hr")
    case_record = orchestrator.intake_resignation(payload)
    case_record = orchestrator.send_notifications(case_record.workflow.case_id)
    workflow = case_record.workflow
    return ResignationIntakeResponse(
        message="Resignation intake recorded and notifications sent successfully.",
        case_id=workflow.case_id,
        workflow_stage=workflow.stage,
        workflow_status=workflow.status,
        notification_status=workflow.notification_status,
        next_action=workflow.next_action,
        created_at=workflow.created_at,
    )


@router.post("/cases/{case_id}/notify", response_model=OperationResponse)
def send_notifications(case_id: str, user: CurrentUser = Depends(get_current_user)) -> OperationResponse:
    _assert_role(user, "hr")
    case_record = _safe_execute(lambda: orchestrator.send_notifications(case_id))
    return _operation_response("Notifications sent successfully.", case_record)


@router.post("/cases/{case_id}/submission", response_model=OperationResponse)
def submit_handover(
    case_id: str,
    payload: EmployeeSubmissionRequest,
    user: CurrentUser = Depends(get_current_user),
) -> OperationResponse:
    case_record = _safe_execute(lambda: orchestrator.get_case(case_id))
    _assert_submission_access(case_record, user)
    if str(payload.submitted_by).lower() != user.email:
        raise HTTPException(status_code=403, detail="Employees can submit only their own handover.")
    case_record = _safe_execute(lambda: orchestrator.submit_handover(case_id, payload))
    return _operation_response("Employee handover submission saved.", case_record)


@router.get("/cases/{case_id}/submission-template")
def submission_template(case_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, object]:
    case_record = _safe_execute(lambda: orchestrator.get_case(case_id))
    _assert_case_access(case_record, user)
    return {
        "case_id": case_id,
        "employee": case_record.employee.employee_name,
        "expected_fields": [
            "documents",
            "systems",
            "open_tasks",
            "risks",
            "notes",
        ],
    }


@router.post("/cases/{case_id}/documentation/generate", response_model=OperationResponse)
def generate_documentation(
    case_id: str,
    payload: GenerateDocumentationRequest,
    user: CurrentUser = Depends(get_current_user),
) -> OperationResponse:
    _assert_role(user, "hr")
    case_record = _safe_execute(lambda: orchestrator.generate_documentation(case_id, payload))
    return _operation_response("Documentation generated successfully.", case_record)


@router.get("/cases/{case_id}/documentation", response_class=FileResponse)
def get_documentation(case_id: str, user: CurrentUser = Depends(get_current_user)) -> FileResponse:
    case_record = _safe_execute(lambda: orchestrator.get_case(case_id))
    _assert_case_access(case_record, user)
    if not case_record.documentation:
        raise HTTPException(status_code=404, detail="Documentation has not been generated yet.")
    path = Path(case_record.documentation.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Documentation file not found.")
    return FileResponse(path=path, media_type="application/pdf", filename=path.name)


@router.post("/cases/{case_id}/review", response_model=OperationResponse)
def review_documentation(
    case_id: str,
    payload: ReviewDecisionRequest,
    user: CurrentUser = Depends(get_current_user),
) -> OperationResponse:
    case_record = _safe_execute(lambda: orchestrator.get_case(case_id))
    _assert_review_access(case_record, user)
    _assert_review_ready(case_record)
    if str(payload.reviewer_email).lower() != user.email:
        raise HTTPException(status_code=403, detail="Managers can review only with their own identity.")
    case_record = _safe_execute(lambda: orchestrator.review_documentation(case_id, payload))
    return _operation_response("Review decision recorded successfully.", case_record)


@router.get("/cases/{case_id}/review/action", response_class=HTMLResponse)
def review_documentation_action(
    case_id: str,
    token: str = Query(...),
) -> HTMLResponse:
    try:
        case_record = orchestrator.review_documentation_action(case_id, token)
    except ValueError as exc:
        return HTMLResponse(
            status_code=400,
            content=f"""
            <html>
              <head>
                <title>KT Review Link</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
              </head>
              <body style="font-family: Arial, sans-serif; background: #f4f7fb; color: #10233F; padding: 32px;">
                <div style="max-width: 720px; margin: 0 auto; background: #ffffff; border-radius: 24px; padding: 32px; box-shadow: 0 18px 48px rgba(16,35,63,0.08);">
                  <p style="color: #c2410c; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">Review Link Error</p>
                  <h1 style="margin: 8px 0 16px;">This review link cannot be used.</h1>
                  <p>{exc}</p>
                  <p>Please contact HR if you need a fresh approval email.</p>
                  <p style="margin-top: 24px;"><a href="/" style="display: inline-block; padding: 12px 18px; background: #1F6FEB; color: #ffffff; text-decoration: none; border-radius: 999px; font-weight: 700;">Open Dashboard</a></p>
                </div>
              </body>
            </html>
            """,
        )
    payload = case_record.review
    result = "approved" if payload and payload.decision == "approved" else "rejected"
    next_action = case_record.workflow.next_action
    return HTMLResponse(
        content=f"""
        <html>
          <head>
            <title>KT Review Decision</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          </head>
          <body style="font-family: Arial, sans-serif; background: #f4f7fb; color: #10233F; padding: 32px;">
            <div style="max-width: 720px; margin: 0 auto; background: #ffffff; border-radius: 24px; padding: 32px; box-shadow: 0 18px 48px rgba(16,35,63,0.08);">
              <p style="color: #1F6FEB; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">Knowledge Transfer Review</p>
              <h1 style="margin: 8px 0 16px;">The KT report was {result} successfully.</h1>
              <p><strong>Case ID:</strong> {case_record.workflow.case_id}</p>
              <p><strong>Current stage:</strong> {case_record.workflow.stage}</p>
              <p><strong>Next action:</strong> {next_action}</p>
              <p style="margin-top: 24px;"><a href="/" style="display: inline-block; padding: 12px 18px; background: #1F6FEB; color: #ffffff; text-decoration: none; border-radius: 999px; font-weight: 700;">Open Dashboard</a></p>
            </div>
          </body>
        </html>
        """
    )


@router.post("/cases/{case_id}/complete", response_model=OperationResponse)
def complete_workflow(
    case_id: str,
    payload: CompleteWorkflowRequest,
    user: CurrentUser = Depends(get_current_user),
) -> OperationResponse:
    _assert_role(user, "hr")
    if str(payload.completed_by).lower() != user.email:
        raise HTTPException(status_code=403, detail="HR can complete workflows only with their own identity.")
    case_record = _safe_execute(lambda: orchestrator.complete_workflow(case_id, payload))
    return _operation_response("Workflow marked as completed.", case_record)


@router.get("/cases/{case_id}", response_model=WorkflowDetailResponse)
def get_case(case_id: str, user: CurrentUser = Depends(get_current_user)) -> WorkflowDetailResponse:
    case_record = _safe_execute(lambda: orchestrator.get_case(case_id))
    _assert_case_access(case_record, user)
    return WorkflowDetailResponse(case=_present_case_for_user(case_record, user))


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    stage: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    user: CurrentUser = Depends(get_current_user),
) -> DashboardResponse:
    cases = orchestrator.list_cases()
    if user.role == "manager":
        cases = [
            case
            for case in cases
            if str(case.employee.manager_email).lower() == user.email
        ]
    elif user.role == "employee":
        cases = [
            case
            for case in cases
            if str(case.employee.employee_email).lower() == user.email
        ]
    if stage:
        cases = [case for case in cases if case.workflow.stage == stage]
    if status_value:
        cases = [case for case in cases if case.workflow.status == status_value]
    summaries = [
        WorkflowSummaryResponse(
            case_id=case.workflow.case_id,
            employee_name=case.employee.employee_name,
            employee_email=case.employee.employee_email,
            manager_email=case.employee.manager_email,
            department=case.employee.department,
            stage=case.workflow.stage,
            status=case.workflow.status,
            notification_status=case.workflow.notification_status,
            next_action=case.workflow.next_action,
            last_updated_at=case.workflow.updated_at,
        )
        for case in cases
    ]
    return DashboardResponse(
        total_cases=len(cases),
        completed_cases=sum(1 for case in cases if case.workflow.stage == "completed"),
        pending_review_cases=sum(1 for case in cases if case.workflow.status == "awaiting_review"),
        awaiting_employee_cases=sum(
            1 for case in cases if case.workflow.status == "awaiting_employee"
        ),
        cases=summaries,
    )


def _operation_response(message: str, case_record) -> OperationResponse:
    workflow = case_record.workflow
    return OperationResponse(
        message=message,
        case_id=workflow.case_id,
        stage=workflow.stage,
        status=workflow.status,
        next_action=workflow.next_action,
    )


def _safe_execute(action):
    try:
        return action()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
