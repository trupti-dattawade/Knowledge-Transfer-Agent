from datetime import datetime, timezone

from app.agents.doc_generator import DocumentationAgent
from app.agents.email_agent import EmailAgent
from app.agents.file_agent import FileManagementAgent
from app.agents.interview_agent import InterviewAgent
from app.agents.trigger_agent import TriggerAgent
from app.models.constants import STAGE_TO_STATUS
from app.models.schemas import (
    CompleteWorkflowRequest,
    EmployeeSubmissionRequest,
    GenerateDocumentationRequest,
    InterviewCaptureRequest,
    InterviewSession,
    InterviewSchedule,
    InterviewScheduleRequest,
    KTCaseRecord,
    LiveInterviewResponseRequest,
    LiveInterviewStartRequest,
    ReviewDecisionRequest,
    ReviewRecord,
    WorkflowAuditEntry,
)
from app.services.calendar_service import CalendarService
from app.services.case_store import CaseStore


class WorkflowOrchestrator:
    """Coordinates the full local MVP workflow from intake to completion."""

    def __init__(
        self,
        case_store: CaseStore | None = None,
        trigger_agent: TriggerAgent | None = None,
        email_agent: EmailAgent | None = None,
        file_agent: FileManagementAgent | None = None,
        interview_agent: InterviewAgent | None = None,
        documentation_agent: DocumentationAgent | None = None,
        calendar_service: CalendarService | None = None,
    ) -> None:
        self.case_store = case_store or CaseStore()
        self.trigger_agent = trigger_agent or TriggerAgent(case_store=self.case_store)
        self.email_agent = email_agent or EmailAgent()
        self.file_agent = file_agent or FileManagementAgent()
        self.interview_agent = interview_agent or InterviewAgent()
        self.documentation_agent = documentation_agent or DocumentationAgent()
        self.calendar_service = calendar_service or CalendarService()

    def intake_resignation(self, payload) -> KTCaseRecord:
        return self.trigger_agent.register_resignation(payload)

    def send_notifications(self, case_id: str) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        if case_record.workflow.notification_status == "sent":
            return case_record
        form_link = self.file_agent.create_form_link(case_id)
        company_name = "James and James brother technologies pvt ltd"
        # Official employee template (variables mapped from stored case data)
        employee_body = (
            "Dear "
            f"{case_record.employee.employee_name},\n"
            "\n"
            "This email is to formally acknowledge that your resignation has been received and recorded in our system.\n"
            "As part of the offboarding process, we are initiating the Knowledge Transfer (KT) and Handover workflow to ensure a smooth transition of your responsibilities.\n"
            "\n"
            "Employee Details\n"
            "\n"
            "Employee Name: "
            f"{case_record.employee.employee_name}\n"
            "\n"
            "Employee ID: "
            f"{case_record.employee.employee_id}\n"
            "\n"
            "Department / Team: "
            f"{case_record.employee.department}\n"
            "\n"
            "Job Title: "
            f"{case_record.employee.job_title}\n"
            "\n"
            "Manager: "
            f"{case_record.employee.manager_name}\n"
            "\n"
            "Last Working Day: "
            f"{case_record.employee.last_working_day.isoformat()}\n"
            "\n"
            "\n"
            "Required Action\n"
            "You are requested to complete the Knowledge Transfer submission by providing all relevant documentation, project details, and handover materials.\n"
            "Please complete the KT submission form using the link below:\n"
            "Knowledge Transfer Form:\n"
            f"{form_link}\n"
            "\n"
            "Deadline\n"
            "Kindly submit the required information and documents within {X} working days to help ensure business continuity and a seamless handover.\n"
            "If you require any assistance during this process, please contact "
            f"{case_record.employee.hr_contact_name} / {case_record.employee.manager_name}.\n"
            "\n"
            "We appreciate your cooperation and contributions to the organization, and we will continue to support you throughout the transition process.\n"
            "\n"
            "Sincerely,\n"
            "HR Team / Organization Name\n"
            f"{case_record.employee.hr_contact_email}\n"
            f"{company_name}"
        )

        notifications = [
            (
                str(case_record.employee.employee_email),
                "Resignation Acknowledgement & Knowledge Transfer Initiation",
                employee_body,
                "resignation_registered",
            ),

            (
                str(case_record.employee.hr_contact_email),
                "Resignation intake recorded",
                f"KT case {case_id} has been created and awaits employee submission.",
                "resignation_registered",
            ),
            (
                str(case_record.employee.manager_email),
                "Upcoming knowledge transfer review",
                (
                    f"KT case {case_id} has been initiated for {case_record.employee.employee_name}. "
                    "You will receive documentation for review in a later stage."
                ),
                "resignation_registered",
            ),
        ]
        sent = self.email_agent.send_case_notifications(case_record, notifications)
        updated = self._update_case(
            case_record,
            stage="notifications_sent",
            next_action="Await employee submission and uploaded handover inputs.",
            notifications=case_record.notifications + sent,
            form_link=form_link,
            notification_status="sent",
            audit_entry=self._audit(
                "notifications_sent",
                "System",
                "Notification emails sent to HR, employee, and manager.",
            ),
        )
        return updated

    def submit_handover(self, case_id: str, payload: EmployeeSubmissionRequest) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        updated = self._update_case(
            case_record,
            stage="submission_received",
            next_action="Schedule and conduct the AI KT interview.",
            submission=payload,
            audit_entry=self._audit(
                "submission_received",
                f"Employee:{payload.submitted_by}",
                "Employee submitted documents, systems, risks, and open tasks.",
            ),
        )
        return updated

    def schedule_interview(self, case_id: str, payload: InterviewScheduleRequest) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        meeting_link = self.calendar_service.create_invite_link(case_record, payload)
        schedule = InterviewSchedule(
            interview_datetime=payload.interview_datetime,
            duration_minutes=payload.duration_minutes,
            meeting_link=meeting_link,
            scheduled_by=payload.scheduled_by,
        )
        sent = self.email_agent.send_case_notifications(
            case_record,
            [
                (
                    str(case_record.employee.employee_email),
                    f"Knowledge Transfer (KT) Interview Scheduled — {case_record.employee.employee_name}",
                    (
                        f"Hello {case_record.employee.employee_name},\n\n"
                        "This is scheduled for "
                        f"{payload.interview_datetime.isoformat()} "
                        "Please review the details below and join on time.\n\n"
                        "Your Knowledge Transfer (KT) interview has been scheduled for "
                        f"{payload.interview_datetime.isoformat()} " 
                        f"for {payload.duration_minutes} minutes.\n\n"
                        f"Join Zoom meeting: {meeting_link}\n\n"
                        "Agenda (recommended topics):\n"
                        "- Your responsibilities and current ownership\n"
                        "- Key workflows and day-to-day processes\n"
                        "- Systems/tools you use and how to operate them\n"
                        "- Known risks, dependencies, and operational considerations\n"
                        "- Handover advice to ensure continuity\n\n"
                        "Thank you,\n"
                        "Knowledge Transfer Team"
                    ),
                    "interview_scheduled",
                ),
                (
                    str(case_record.employee.manager_email),
                    f"KT interview scheduled for {case_record.employee.employee_name}",
                    (
                        f"The KT interview for {case_record.employee.employee_name} has been scheduled.\n\n"
                        f"Interview time: {payload.interview_datetime.isoformat()}\n"
                        f"Join Zoom meeting: {meeting_link}"
                    ),
                    "interview_scheduled",
                ),
                (
                    str(case_record.employee.hr_contact_email),
                    f"KT interview scheduled for {case_record.employee.employee_name}",
                    (
                        f"The KT interview for {case_record.employee.employee_name} has been scheduled.\n\n"
                        f"Interview time: {payload.interview_datetime.isoformat()}\n"
                        f"Join Zoom meeting: {meeting_link}"
                    ),
                    "interview_scheduled",
                )
            ],
        )
        updated = self._update_case(
            case_record,
            stage="interview_scheduled",
            next_action="Capture structured knowledge from the KT interview.",
            interview_schedule=schedule,
            notifications=case_record.notifications + sent,
            audit_entry=self._audit(
                "interview_scheduled",
                f"Scheduler:{payload.scheduled_by}",
                "Interview scheduled and invite generated.",
            ),
        )
        return updated

    def capture_interview(self, case_id: str, payload: InterviewCaptureRequest) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        interview_record = self.interview_agent.build_record(payload)
        updated = self._update_case(
            case_record,
            stage="interview_completed",
            next_action="Generate KT documentation from submitted material and interview knowledge.",
            interview=interview_record,
            audit_entry=self._audit(
                "interview_completed",
                f"Interviewer:{payload.interviewer}",
                "Interview completed and structured knowledge captured.",
            ),
        )
        return updated

    def start_live_interview(
        self,
        case_id: str,
        payload: LiveInterviewStartRequest,
    ) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        session = self.interview_agent.start_live_session(payload.interviewer_name)
        updated = self._update_case(
            case_record,
            stage=case_record.workflow.stage,
            next_action="Employee should continue the live KT interview conversation.",
            interview_session=session,
            audit_entry=self._audit(
                "live_interview_started",
                f"Interviewer:{payload.interviewer_name}",
                "Live conversational KT interview started.",
            ),
        )
        return updated

    def respond_live_interview(
        self,
        case_id: str,
        payload: LiveInterviewResponseRequest,
    ) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        if not case_record.interview_session:
            raise KeyError(f"Interview session for case {case_id} not found")

        session = self.interview_agent.continue_live_session(case_record.interview_session, payload.answer)
        updates: dict[str, object] = {"interview_session": session}
        stage = case_record.workflow.stage
        next_action = "Continue responding to the live KT interview."
        audit_details = "Employee provided a live interview response."

        if session.status == "completed":
            record = self.interview_agent.session_to_record("AI Interview Agent", session)
            updates["interview"] = record
            stage = "interview_completed"
            next_action = "Generate KT documentation from the completed live interview."
            audit_details = "Live interview completed and structured knowledge captured."

        updated = self._update_case(
            case_record,
            stage=stage,
            next_action=next_action,
            audit_entry=self._audit(
                "live_interview_progressed" if session.status != "completed" else "live_interview_completed",
                f"Employee:{case_record.employee.employee_email}",
                audit_details,
            ),
            **updates,
        )
        return updated

    def get_live_interview_session(self, case_id: str) -> InterviewSession:
        case_record = self.case_store.get_case(case_id)
        if not case_record.interview_session:
            raise KeyError(f"Interview session for case {case_id} not found")
        return case_record.interview_session

    def generate_documentation(
        self,
        case_id: str,
        payload: GenerateDocumentationRequest,
    ) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        documentation = self.documentation_agent.generate(case_record, payload)
        sent = self.email_agent.send_case_notifications(
            case_record,
            [
                (
                    str(case_record.employee.hr_contact_email),
                    "KT documentation ready",
                    f"Documentation for case {case_id} is ready: {documentation.share_link}",
                    "documentation_ready",
                ),
                (
                    str(case_record.employee.employee_email),
                    "KT documentation ready",
                    f"Documentation for your KT workflow is ready: {documentation.share_link}",
                    "documentation_ready",
                ),
                (
                    str(case_record.employee.manager_email),
                    "KT documentation ready for review",
                    f"Please review the KT document here: {documentation.share_link}",
                    "documentation_ready",
                ),
            ],
        )
        updated = self._update_case(
            case_record,
            stage="under_review",
            next_action="Manager or reviewer should approve or request changes.",
            documentation=documentation,
            notifications=case_record.notifications + sent,
            audit_entry=self._audit(
                "documentation_generated",
                f"Generator:{payload.generated_by}",
                "Documentation generated and review notifications sent.",
            ),
        )
        return updated

    def review_documentation(self, case_id: str, payload: ReviewDecisionRequest) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        review_record = ReviewRecord(
            reviewer_email=payload.reviewer_email,
            reviewer_name=payload.reviewer_name,
            decision=payload.decision,
            comments=payload.comments,
            reviewed_at=datetime.now(timezone.utc),
        )
        stage = "completed" if payload.decision == "approved" else "changes_requested"
        next_action = (
            "Workflow completed. Send final confirmation emails."
            if stage == "completed"
            else "Employee or documentation owner should address review comments."
        )
        messages = []
        if stage == "changes_requested":
            messages.append(
                (
                    str(case_record.employee.employee_email),
                    "KT documentation changes requested",
                    f"Reviewer comments: {payload.comments}",
                    "changes_requested",
                )
            )
            messages.append(
                (
                    str(case_record.employee.hr_contact_email),
                    "KT documentation changes requested",
                    f"Reviewer comments for case {case_id}: {payload.comments}",
                    "changes_requested",
                )
            )
        sent = self.email_agent.send_case_notifications(case_record, messages) if messages else []
        updated = self._update_case(
            case_record,
            stage=stage,
            next_action=next_action,
            review=review_record,
            notifications=case_record.notifications + sent,
            audit_entry=self._audit(
                f"review_{payload.decision}",
                f"Reviewer:{payload.reviewer_email}",
                payload.comments,
            ),
        )
        return updated

    def complete_workflow(self, case_id: str, payload: CompleteWorkflowRequest) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        sent = self.email_agent.send_case_notifications(
            case_record,
            [
                (
                    str(case_record.employee.employee_email),
                    "KT workflow completed",
                    f"Your knowledge transfer workflow for case {case_id} is complete.",
                    "workflow_completed",
                ),
                (
                    str(case_record.employee.hr_contact_email),
                    "KT workflow completed",
                    f"Case {case_id} has been completed successfully.",
                    "workflow_completed",
                ),
                (
                    str(case_record.employee.manager_email),
                    "KT workflow completed",
                    f"Case {case_id} has been approved and closed.",
                    "workflow_completed",
                ),
            ],
        )
        updated = self._update_case(
            case_record,
            stage="completed",
            next_action="No further action required.",
            notifications=case_record.notifications + sent,
            final_confirmation_sent_at=datetime.now(timezone.utc),
            audit_entry=self._audit(
                "workflow_completed",
                f"Closer:{payload.completed_by}",
                "Final confirmation emails sent and workflow closed.",
            ),
        )
        return updated

    def list_cases(self) -> list[KTCaseRecord]:
        return self.case_store.list_cases()

    def get_case(self, case_id: str) -> KTCaseRecord:
        return self.case_store.get_case(case_id)

    def _update_case(
        self,
        case_record: KTCaseRecord,
        stage: str,
        next_action: str,
        audit_entry: WorkflowAuditEntry,
        **updates,
    ) -> KTCaseRecord:
        now = datetime.now(timezone.utc)
        workflow = case_record.workflow.model_copy(
            update={
                "stage": stage,
                "status": STAGE_TO_STATUS[stage],
                "updated_at": now,
                "next_action": next_action,
                "notification_status": updates.get(
                    "notification_status", case_record.workflow.notification_status
                ),
            }
        )
        payload = {
            **updates,
            "workflow": workflow,
            "audit_log": case_record.audit_log + [audit_entry],
        }
        updated_case = case_record.model_copy(update=payload)
        self.case_store.update_case(updated_case)
        return updated_case

    def _audit(self, event: str, actor: str, details: str) -> WorkflowAuditEntry:
        return WorkflowAuditEntry(
            event=event,
            occurred_at=datetime.now(timezone.utc),
            actor=actor,
            details=details,
        )
