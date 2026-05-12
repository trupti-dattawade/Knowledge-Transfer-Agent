STAGE_TO_STATUS: dict[str, str] = {
    "resignation_intake": "registered",
    "notifications_sent": "awaiting_employee",
    "submission_received": "awaiting_interview",
    "interview_scheduled": "awaiting_interview",
    "interview_completed": "in_progress",
    "documentation_generated": "awaiting_review",
    "under_review": "awaiting_review",
    "changes_requested": "changes_requested",
    "completed": "completed",
}
