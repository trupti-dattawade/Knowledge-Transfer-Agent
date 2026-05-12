# Knowledge Transfer Agent

Knowledge Transfer Agent is a FastAPI-based workflow system for employee exit handovers. It turns HR resignation intake into a structured knowledge transfer process covering notifications, employee submission, interview capture, documentation generation, reviewer approval, and final completion tracking.

## Current Product Highlights

- Professional PDF handover generation for each KT case
- One-click manager approval and rejection from email
- Automatic return to the interview phase when a report is rejected
- Local outbox copies plus SMTP delivery when configured
- Command-center dashboard with workflow filters and case actions

## Implemented Workflow

1. HR registers a resignation and the system creates a KT case.
2. Notification emails are generated for HR, employee, and manager.
3. Employee submits handover details and supporting artifacts.
4. HR schedules the KT interview.
5. Interview knowledge is captured in structured form.
6. Documentation is generated and stored locally.
7. Reviewer approves or requests changes.
8. Final completion emails are generated and the case is closed.

Manager review links are signed and time-bound, and each approval link is intended for one-time use.

## Architecture Mapping

The project follows the structure shown in the architecture diagrams:

- `app/main.py`: FastAPI entry point
- `app/models/`: request, response, and workflow state models
- `app/agents/`: trigger, email, interview, documentation, file, and orchestrator agents
- `app/services/`: local implementations of email, form, calendar, document, and storage services
- `app/workflows/kt_workflow.py`: API routes for the end-to-end workflow

## Local MVP Notes

This repository currently ships as a local MVP:

- Google Forms is simulated through a submission template endpoint
- Email delivery uses SMTP when configured and always writes a local copy to `data/mailbox/`
- OneDrive storage is simulated under `data/generated_docs/`
- Calendar scheduling produces a local invite link

These service boundaries are intentionally isolated so you can later swap them for Google Forms API, Microsoft Graph, Teams, or OneDrive integrations.

## AI Interviewer

The live interview flow supports two modes:

- Fallback guided interviewer: works by default with no API key
- AI interviewer: enabled automatically when `GROQ_API_KEY` is set

Optional environment variables:

```bash
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
```

When AI mode is enabled, the interview agent will:

- ask more adaptive follow-up questions
- probe vague answers more intelligently
- generate a stronger structured summary from the transcript

## SMTP Email Setup

The notification flow can send real emails in real time through SMTP.

Add these variables to your environment or `.env` file:

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_email_username
SMTP_PASSWORD=your_email_password
SMTP_SENDER_EMAIL=your_sender_email@example.com
SMTP_SENDER_NAME=Knowledge Transfer Agent
SMTP_USE_TLS=true
SMTP_USE_SSL=false
REVIEW_LINK_SECRET=your_long_random_secret
REVIEW_LINK_TTL_SECONDS=604800
```

Notes:

- Use `SMTP_USE_TLS=true` for most providers on port `587`
- Use `SMTP_USE_SSL=true` and `SMTP_USE_TLS=false` for providers that require implicit SSL, commonly on port `465`
- If SMTP is not configured, the app falls back to local notification simulation only
- Review links expire automatically based on `REVIEW_LINK_TTL_SECONDS`

## Zoom Interview Meeting Setup

The interview scheduling step can create a real Zoom meeting automatically and include the meeting link in the employee, HR, and manager emails.

Add these variables:

```bash
ZOOM_ACCOUNT_ID=your_zoom_account_id
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret
ZOOM_USER_ID=me
```

Notes:

- `ZOOM_USER_ID=me` uses the authenticated Zoom user by default
- When Zoom is not configured, the app falls back to a local placeholder meeting link
- Real Zoom meeting creation happens during the interview scheduling step

## Run The App

```bash
uvicorn app.main:app --reload
```

Open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## Main API Flow

1. `POST /api/v1/kt/resignations/intake`
2. `POST /api/v1/kt/cases/{case_id}/notify`
3. `POST /api/v1/kt/cases/{case_id}/submission`
4. `POST /api/v1/kt/cases/{case_id}/interview/schedule`
5. `POST /api/v1/kt/cases/{case_id}/interview/capture`
6. `POST /api/v1/kt/cases/{case_id}/documentation/generate`
7. `POST /api/v1/kt/cases/{case_id}/review`
8. `POST /api/v1/kt/cases/{case_id}/complete`

Support endpoints:

- `GET /api/v1/kt/cases/{case_id}`
- `GET /api/v1/kt/cases/{case_id}/documentation`
- `GET /api/v1/kt/cases/{case_id}/review/action?token=...`
- `GET /api/v1/kt/dashboard`

## Sample Intake Payload

```json
{
  "employee_id": "EMP-104",
  "employee_name": "Riya Sharma",
  "employee_email": "riya.sharma@example.com",
  "department": "Engineering",
  "job_title": "Software Engineer",
  "manager_name": "Amit Verma",
  "manager_email": "amit.verma@example.com",
  "hr_contact_name": "Neha Kapoor",
  "hr_contact_email": "neha.kapoor@example.com",
  "resignation_date": "2026-05-12",
  "last_working_day": "2026-06-15",
  "reason_for_exit": "Career transition",
  "notes": "Priority handover expected for payments service."
}
```

## Future Integration Upgrades

- Replace local outbox with Microsoft Graph email sending
- Replace local document storage with OneDrive or Teams
- Replace submission template endpoint with Google Forms integration
- Replace manual interview capture with an LLM-driven interview agent
- Add authentication, RBAC, and audit dashboards
