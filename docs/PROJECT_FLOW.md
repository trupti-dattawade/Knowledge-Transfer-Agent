# Knowledge Transfer Agent Project Flow

This diagram summarizes the implemented system architecture and the end-to-end workflow in a format that is easy to read in GitHub or any Markdown viewer that supports Mermaid.

## End-to-End Flow

```mermaid
flowchart LR
    A[HR Dashboard UI<br/>Manual Web Frontend] --> B[FastAPI Backend]
    B --> C[1. Resignation Intake]
    C --> D[2. Notification Dispatch]
    D --> E[3. Employee Submission]
    E --> F[4. Interview Scheduling]
    F --> G[5. Live KT Interview]
    G --> H[6. Structured Knowledge Record]
    H --> I[7. PDF Documentation Generator]
    I --> J[8. Manager Review]
    J --> K[9. Final Completion]

    D --> L[Local Mailbox / Email Simulation]
    E --> M[Case Store / JSON Persistence]
    G --> N[Interview Session Engine]
    I --> O[Generated PDF Storage]
    J --> M
    K --> M
```

## System Architecture

```mermaid
flowchart TD
    UI[Frontend Dashboard<br/>HTML + CSS + JS] --> API[FastAPI Application]
    Docs[Swagger UI<br/>/docs] --> API

    API --> Routes[Workflow Routes]
    API --> UIRoutes[UI Routes]

    Routes --> Orch[Workflow Orchestrator]

    Orch --> Trigger[Trigger Agent]
    Orch --> Email[Email Agent]
    Orch --> File[File Management Agent]
    Orch --> Interview[Interview Agent]
    Orch --> DocGen[Documentation Agent]

    Trigger --> Store[Case Store<br/>data/kt_cases.json]
    Email --> Mail[Mailbox Service<br/>data/mailbox/]
    File --> Forms[Submission Template Link]
    File --> Drive[Local OneDrive-style Storage<br/>data/generated_docs/]

    Interview --> LiveSession[Live Interview Session]
    Interview --> AI[Groq / LLM Interview Service<br/>Optional]
    Interview --> Record[Structured Interview Record]

    DocGen --> PDF[Professional KT PDF]
    PDF --> Drive

    Store --> DashboardAPI[Dashboard JSON Endpoint]
    DashboardAPI --> UI
```

## Live Interview Flow

```mermaid
sequenceDiagram
    participant Employee
    participant UI as Dashboard UI
    participant API as FastAPI
    participant IA as Interview Agent
    participant AI as Groq AI Service
    participant DB as Case Store

    Employee->>UI: Open selected case
    UI->>API: Start live interview
    API->>IA: Create interview session
    IA-->>API: First question
    API-->>UI: Session state + transcript

    loop Until complete
        Employee->>UI: Submit answer
        UI->>API: Send response
        API->>IA: Continue session
        alt AI enabled
            IA->>AI: Evaluate answer and generate follow-up
            AI-->>IA: Next question / topic completion
        else Fallback mode
            IA-->>IA: Rule-based follow-up
        end
        IA->>DB: Save session progress
        API-->>UI: Updated transcript + next question
    end

    IA->>AI: Structure transcript into KT summary
    AI-->>IA: Summary + responsibilities + risks + recommendations
    IA->>DB: Save final interview record
    API-->>UI: Interview completed
```

## Short Explanation

- `Frontend Dashboard`: HR-facing UI for cases, intake, live interview, and downloads.
- `FastAPI Backend`: central application server for both API and web UI.
- `Workflow Orchestrator`: coordinates every step of the KT lifecycle.
- `Interview Agent`: runs the live conversational interview and structures knowledge.
- `LLM Interview Service`: optional AI layer for adaptive questioning and stronger summarization.
- `Documentation Agent`: converts the final knowledge record into a professional PDF.
- `Case Store`: persists workflow state for each resignation case.
- `Mailbox + Storage`: local simulation of enterprise email and document platforms.
