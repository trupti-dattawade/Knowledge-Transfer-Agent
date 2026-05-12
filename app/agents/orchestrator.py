from datetime import datetime, timezone
from urllib.parse import quote_plus

from app.agents.doc_generator import DocumentationAgent
from app.agents.email_agent import EmailAgent
from app.agents.file_agent import FileManagementAgent
from app.agents.interview_agent import InterviewAgent
from app.agents.trigger_agent import TriggerAgent
from app.config import settings
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
            interview_link=payload.interview_link,
            scheduled_by=payload.scheduled_by,
        )
        interview_link_text = payload.interview_link or "Not provided"
        sent = self.email_agent.send_case_notifications(
            case_record,
            [
                (
                    str(case_record.employee.employee_email),
                    f"Knowledge Transfer (KT) Interview Scheduled - {case_record.employee.employee_name}",
                    (
                        f"Hello {case_record.employee.employee_name},\n\n"
                        "This is scheduled for "
                        f"{payload.interview_datetime.isoformat()} "
                        "Please review the details below and join on time.\n\n"
                        "Your Knowledge Transfer (KT) interview has been scheduled for "
                        f"{payload.interview_datetime.isoformat()} "
                        f"for {payload.duration_minutes} minutes.\n\n"
                        f"Meeting link: {meeting_link}\n"
                        f"Interview link: {interview_link_text}\n\n"
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
                        f"Meeting link: {meeting_link}\n"
                        f"Interview link: {interview_link_text}"
                    ),
                    "interview_scheduled",
                ),
                (
                    str(case_record.employee.hr_contact_email),
                    f"KT interview scheduled for {case_record.employee.employee_name}",
                    (
                        f"The KT interview for {case_record.employee.employee_name} has been scheduled.\n\n"
                        f"Interview time: {payload.interview_datetime.isoformat()}\n"
                        f"Meeting link: {meeting_link}\n"
                        f"Interview link: {interview_link_text}"
                    ),
                    "interview_scheduled",
                ),
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
            next_action="Generate the KT review PDF from submitted material and interview knowledge.",
            interview=interview_record,
            audit_entry=self._audit(
                "interview_completed",
                f"Interviewer:{payload.interviewer}",
                "Interview completed and structured knowledge captured.",
            ),
        )
        return self._generate_documentation_and_notify(updated, payload.interviewer)

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
            completed_case = self._update_case(
                case_record,
                stage="interview_completed",
                next_action="Generate the KT review PDF from the completed live interview.",
                audit_entry=self._audit(
                    "live_interview_completed",
                    f"Employee:{case_record.employee.employee_email}",
                    "Live interview completed and structured knowledge captured.",
                ),
                interview_session=session,
                interview=record,
            )
            return self._generate_documentation_and_notify(completed_case, "AI Meeting Agent")

        updated = self._update_case(
            case_record,
            stage=stage,
            next_action=next_action,
            audit_entry=self._audit(
                "live_interview_progressed",
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
        return self._generate_documentation_and_notify(case_record, payload.generated_by)

    def _generate_documentation_and_notify(
        self,
        case_record: KTCaseRecord,
        generated_by: str,
    ) -> KTCaseRecord:
        case_id = case_record.workflow.case_id
        documentation = self.documentation_agent.generate(
            case_record,
            GenerateDocumentationRequest(generated_by=generated_by),
        )
        approval_link = self._build_review_action_link(
            case_id=case_id,
            reviewer_email=str(case_record.employee.manager_email),
            reviewer_name=case_record.employee.manager_name,
            decision="approved",
            comments="Approved by manager from review email.",
        )
        reject_link = self._build_review_action_link(
            case_id=case_id,
            reviewer_email=str(case_record.employee.manager_email),
            reviewer_name=case_record.employee.manager_name,
            decision="changes_requested",
            comments="Rejected by manager from review email. Interview report needs revision.",
        )
        attachment_path = documentation.storage_path
        sent = self.email_agent.send_rich_notifications(
            case_record,
            [
                {
                    "recipient": str(case_record.employee.employee_email),
                    "subject": "KT meeting notes PDF ready",
                    "body": (
                        f"Hello {case_record.employee.employee_name},\n\n"
                        "Your Knowledge Transfer meeting notes PDF has been generated successfully.\n"
                        f"Document title: {documentation.title}\n"
                        f"Download link: {documentation.share_link}\n\n"
                        "The PDF is attached to this email and has also been shared with your manager for review.\n"
                        "Once the manager approves it, the KT workflow will be completed.\n"
                    ),
                    "html_body": self._build_document_email_html(
                        recipient_name=case_record.employee.employee_name,
                        title=documentation.title,
                        share_link=documentation.share_link,
                    ),
                    "attachments": [attachment_path],
                    "category": "documentation_ready",
                },
                {
                    "recipient": str(case_record.employee.manager_email),
                    "subject": f"KT PDF review required for {case_record.employee.employee_name}",
                    "body": (
                        f"Hello {case_record.employee.manager_name},\n\n"
                        f"The KT PDF for {case_record.employee.employee_name} is ready for your review.\n"
                        f"Document title: {documentation.title}\n"
                        f"Download link: {documentation.share_link}\n\n"
                        f"Approve: {approval_link}\n"
                        f"Reject: {reject_link}\n\n"
                        "The PDF is attached to this email. Approving it will complete the KT workflow.\n"
                    ),
                    "html_body": self._build_manager_review_email_html(
                        manager_name=case_record.employee.manager_name,
                        employee_name=case_record.employee.employee_name,
                        title=documentation.title,
                        share_link=documentation.share_link,
                        approval_link=approval_link,
                        reject_link=reject_link,
                    ),
                    "attachments": [attachment_path],
                    "category": "documentation_ready",
                },
            ],
        )
        updated = self._update_case(
            case_record,
            stage="under_review",
            next_action=(
                "Professional KT meeting notes were converted into a PDF, phase 5 is complete, "
                "and the review email has been sent to the employee and manager."
            ),
            documentation=documentation,
            notifications=case_record.notifications + sent,
            audit_entry=self._audit(
                "documentation_generated",
                f"Generator:{generated_by}",
                "Documentation generated and review notifications sent.",
            ),
        )
        return updated

    def review_documentation(self, case_id: str, payload: ReviewDecisionRequest) -> KTCaseRecord:
        case_record = self.case_store.get_case(case_id)
        if case_record.workflow.stage == "completed":
            return case_record
        if case_record.workflow.stage == "changes_requested" and payload.decision == "changes_requested":
            return case_record
        review_record = ReviewRecord(
            reviewer_email=payload.reviewer_email,
            reviewer_name=payload.reviewer_name,
            decision=payload.decision,
            comments=payload.comments,
            reviewed_at=datetime.now(timezone.utc),
        )
        if payload.decision == "changes_requested":
            sent = self.email_agent.send_rich_notifications(
                case_record,
                [
                    {
                        "recipient": str(case_record.employee.employee_email),
                        "subject": "KT interview report rejected",
                        "body": (
                            f"Hello {case_record.employee.employee_name},\n\n"
                            "The manager reviewed the KT PDF and rejected the report.\n"
                            f"Comments: {payload.comments}\n\n"
                            "Please update or recapture the interview report and generate the document again."
                        ),
                        "category": "changes_requested",
                    },
                    {
                        "recipient": str(case_record.employee.manager_email),
                        "subject": "KT report marked for rework",
                        "body": (
                            f"The KT report for {case_record.employee.employee_name} has been marked as rejected.\n"
                            f"Comments recorded: {payload.comments}"
                        ),
                        "category": "changes_requested",
                    },
                ],
            )
            updated = self._update_case(
                case_record,
                stage="changes_requested",
                next_action="Manager rejected the report. Re-run the interview report and generate a fresh PDF for review.",
                review=review_record,
                notifications=case_record.notifications + sent,
                audit_entry=self._audit(
                    "review_changes_requested",
                    f"Reviewer:{payload.reviewer_email}",
                    payload.comments,
                ),
            )
            return updated

        sent = self.email_agent.send_rich_notifications(
            case_record,
            [
                {
                    "recipient": str(case_record.employee.employee_email),
                    "subject": "KT session completed successfully",
                    "body": (
                        f"Hello {case_record.employee.employee_name},\n\n"
                        "Your Knowledge Transfer session has been approved and completed successfully.\n"
                        f"Case ID: {case_id}\n"
                        "Thank you for completing the KT process."
                    ),
                    "category": "workflow_completed",
                },
                {
                    "recipient": str(case_record.employee.manager_email),
                    "subject": f"KT session completed for {case_record.employee.employee_name}",
                    "body": (
                        f"Hello {case_record.employee.manager_name},\n\n"
                        f"The KT session for {case_record.employee.employee_name} has been approved and completed successfully.\n"
                        f"Case ID: {case_id}\n"
                        "The workflow is now closed."
                    ),
                    "category": "workflow_completed",
                },
            ],
        )
        updated = self._update_case(
            case_record,
            stage="completed",
            next_action="No further action required.",
            review=review_record,
            notifications=case_record.notifications + sent,
            final_confirmation_sent_at=datetime.now(timezone.utc),
            audit_entry=self._audit(
                "review_approved",
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

    def _build_review_action_link(
        self,
        case_id: str,
        reviewer_email: str,
        reviewer_name: str,
        decision: str,
        comments: str,
    ) -> str:
        return (
            f"{settings.base_url}/api/v1/kt/cases/{case_id}/review/action"
            f"?decision={quote_plus(decision)}"
            f"&reviewer_email={quote_plus(reviewer_email)}"
            f"&reviewer_name={quote_plus(reviewer_name)}"
            f"&comments={quote_plus(comments)}"
        )

    def _build_document_email_html(
        self,
        recipient_name: str,
        title: str,
        share_link: str,
    ) -> str:
        return f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #243B53;">
            <p>Hello {recipient_name},</p>
            <p>Your Knowledge Transfer meeting notes PDF has been generated successfully.</p>
            <p><strong>Document title:</strong> {title}</p>
            <p><a href="{share_link}">Open KT PDF</a></p>
            <p>The PDF is attached to this email and has been shared with your manager for review.</p>
          </body>
        </html>
        """

    def _build_manager_review_email_html(
        self,
        manager_name: str,
        employee_name: str,
        title: str,
        share_link: str,
        approval_link: str,
        reject_link: str,
    ) -> str:
        return f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #243B53;">
            <p>Hello {manager_name},</p>
            <p>The KT PDF for <strong>{employee_name}</strong> is ready for your review.</p>
            <p><strong>Document title:</strong> {title}</p>
            <p><a href="{share_link}">Open KT PDF</a></p>
            <p style="margin-top: 24px;">
              <a href="{approval_link}" style="display: inline-block; padding: 12px 18px; background: #159957; color: #ffffff; text-decoration: none; border-radius: 999px; font-weight: 700; margin-right: 12px;">Approve</a>
              <a href="{reject_link}" style="display: inline-block; padding: 12px 18px; background: #c2410c; color: #ffffff; text-decoration: none; border-radius: 999px; font-weight: 700;">Reject</a>
            </p>
            <p>The PDF is attached to this email. Approving it will complete the KT workflow.</p>
          </body>
        </html>
        """
