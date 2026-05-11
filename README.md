# Knowledge Transfer Agent 

Overview

The Knowledge Transfer Agent is an agentic AI system that automates the entire knowledge handover process when an employee resigns.
It ensures critical knowledge is captured, documented, reviewed, and stored without manual HR follow-ups.

The system orchestrates HR, Employee, Manager, Email, Google Forms, Interview AI, and OneDrive into a single automated workflow.

Problem

When employees leave, organizations lose:

Tribal knowledge
Project context
Process documentation
Access to important files

Traditional knowledge transfer is manual, inconsistent, and often incomplete.

This system eliminates knowledge loss using AI-driven automation.

End-to-End Workflow
1. HR Resignation Intake

HR registers a resignation inside the system.

System Actions

Create KT workflow instance
Trigger automated notifications
2. Email Notifications Sent

Emails are automatically sent to:

Employee
HR
Employee’s Manager / Documentation Reviewer

Email contains

Google Form link for document upload
Interview scheduling link
3. Employee Upload via Google Form

Employee uploads:

Documents
Files
Credentials/process info
Project references

System Actions

Automatically create OneDrive folder
Upload submitted files to the folder
4. AI Knowledge Transfer Interview

AI schedules and conducts a KT interview via chat.

Agent extracts

Role responsibilities
Daily workflows
Tools & systems used
Project insights
Hidden tribal knowledge
5. Documentation Generator Agent

AI converts interview + uploaded data into:

Professional KT documentation
Structured knowledge base content
Handover task checklist

Documentation is saved automatically to OneDrive.

6. Manager Review Stage

Manager receives email notification with OneDrive link.

Manager reviews and approves documentation.

7. Final Confirmation Emails

After approval:

Employee receives confirmation
HR receives confirmation
Manager receives confirmation
8. Workflow Completion

System updates HR dashboard:

Status:
Employee KT has been successfully completed

System Architecture (High Level)
Interfaces
HR Dashboard
Employee Email + Google Form
Manager Review Email
AI Agents
Orchestrator Agent
Interview Agent
Documentation Generator Agent
Email Automation Agent
File Management Agent
Integrations
Google Forms (Data Collection)
Email Service (Notifications)
Calendar (Interview Scheduling)
OneDrive / Teams (Storage)
Key Features
Fully automated KT lifecycle
AI-driven interview and documentation
Centralized knowledge storage
Manager approval workflow
Real-time HR status tracking
Tech Stack (Planned)
Python
LangChain (Agent Framework)
Groq API (LLM)
FastAPI (Backend)
Google Forms API
Microsoft Graph API (OneDrive & Email)
Outcome

This system ensures:

Zero knowledge loss
Consistent documentation
Reduced HR workload
Smooth employee offboarding