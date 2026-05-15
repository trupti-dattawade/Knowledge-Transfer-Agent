from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse

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


@router.post(
    "/resignations/intake",
    response_model=ResignationIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
def resignation_intake(payload: ResignationIntakeRequest) -> ResignationIntakeResponse:
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
def send_notifications(case_id: str) -> OperationResponse:
    case_record = _safe_execute(lambda: orchestrator.send_notifications(case_id))
    return _operation_response("Notifications sent successfully.", case_record)


@router.post("/cases/{case_id}/submission", response_model=OperationResponse)
def submit_handover(case_id: str, payload: EmployeeSubmissionRequest) -> OperationResponse:
    case_record = _safe_execute(lambda: orchestrator.submit_handover(case_id, payload))
    return _operation_response("Employee handover submission saved.", case_record)


@router.get("/cases/{case_id}/submission-template")
def submission_template(case_id: str) -> dict[str, object]:
    case_record = _safe_execute(lambda: orchestrator.get_case(case_id))
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
) -> OperationResponse:
    case_record = _safe_execute(lambda: orchestrator.generate_documentation(case_id, payload))
    return _operation_response("Documentation generated successfully.", case_record)


@router.get("/cases/{case_id}/documentation", response_class=FileResponse)
def get_documentation(case_id: str) -> FileResponse:
    case_record = _safe_execute(lambda: orchestrator.get_case(case_id))
    if not case_record.documentation:
        raise HTTPException(status_code=404, detail="Documentation has not been generated yet.")
    path = Path(case_record.documentation.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Documentation file not found.")
    return FileResponse(path=path, media_type="application/pdf", filename=path.name)


@router.post("/cases/{case_id}/review", response_model=OperationResponse)
def review_documentation(case_id: str, payload: ReviewDecisionRequest) -> OperationResponse:
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
def complete_workflow(case_id: str, payload: CompleteWorkflowRequest) -> OperationResponse:
    case_record = _safe_execute(lambda: orchestrator.complete_workflow(case_id, payload))
    return _operation_response("Workflow marked as completed.", case_record)


@router.get("/cases/{case_id}", response_model=WorkflowDetailResponse)
def get_case(case_id: str) -> WorkflowDetailResponse:
    case_record = _safe_execute(lambda: orchestrator.get_case(case_id))
    return WorkflowDetailResponse(case=case_record)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    stage: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
) -> DashboardResponse:
    cases = orchestrator.list_cases()
    if stage:
        cases = [case for case in cases if case.workflow.stage == stage]
    if status_value:
        cases = [case for case in cases if case.workflow.status == status_value]
    summaries = [
        WorkflowSummaryResponse(
            case_id=case.workflow.case_id,
            employee_name=case.employee.employee_name,
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
