const state = {
  dashboard: null,
  selectedCaseId: null,
  interviewSession: null,
  scheduleCaseId: null,
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return response.json();
}

function normalizeClassName(value) {
  return String(value || "").replace(/\s+/g, "_");
}

function updateHealth(status = "Live") {
  const node = document.getElementById("systemHealth");
  if (node) node.textContent = status;
}

function updateInterviewMode() {
  const node = document.getElementById("interviewMode");
  if (!node) return;
  node.textContent = "PDF review workflow";
}

function renderMetrics(dashboard) {
  document.getElementById("totalCases").textContent = dashboard.total_cases;
  document.getElementById("completedCases").textContent = dashboard.completed_cases;
  document.getElementById("pendingReviewCases").textContent = dashboard.pending_review_cases;
  document.getElementById("awaitingEmployeeCases").textContent = dashboard.awaiting_employee_cases;
  document.getElementById("casesLoaded").textContent = dashboard.cases.length;
}

function renderCasesTable(dashboard) {
  const tbody = document.getElementById("casesTableBody");
  if (!dashboard.cases.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No cases yet. Create the first intake from the panel on the right.</td></tr>`;
    return;
  }

  tbody.innerHTML = dashboard.cases
    .map(
      (item) => `
    <tr data-case-id="${item.case_id}" class="${state.selectedCaseId === item.case_id ? "is-selected" : ""}">
      <td class="case-id">${item.case_id}</td>
      <td>${item.employee_name}</td>
      <td>${item.department}</td>
      <td><span class="pill ${normalizeClassName(item.stage)}">${item.stage}</span></td>
      <td>${item.status}</td>
      <td>${item.next_action}</td>
    </tr>
  `,
    )
    .join("");

  [...tbody.querySelectorAll("tr[data-case-id]")].forEach((row) => {
    row.addEventListener("click", () => {
      loadCaseDetail(row.dataset.caseId);
    });
  });
}

function renderSpotlight(caseDetail) {
  const title = document.getElementById("spotlightTitle");
  const body = document.getElementById("spotlightBody");
  const workflow = caseDetail.case.workflow;
  const employee = caseDetail.case.employee;
  const documentation = caseDetail.case.documentation;

  title.textContent = `${employee.employee_name} - ${employee.department}`;
  body.innerHTML = `
    <div class="pill ${normalizeClassName(workflow.stage)}">${workflow.stage}</div>
    <div class="spotlight-meta">
      <div class="spotlight-stat">
        <span>Case ID</span>
        <strong>${workflow.case_id}</strong>
      </div>
      <div class="spotlight-stat">
        <span>Status</span>
        <strong>${workflow.status}</strong>
      </div>
      <div class="spotlight-stat">
        <span>Notification</span>
        <strong>${workflow.notification_status}</strong>
      </div>
      <div class="spotlight-stat">
        <span>Last Updated</span>
        <strong>${new Date(workflow.updated_at).toLocaleString()}</strong>
      </div>
    </div>
    <p><strong>Next action:</strong> ${workflow.next_action}</p>
    <p><strong>Manager:</strong> ${employee.manager_name} - ${employee.manager_email}</p>
    <p><strong>HR owner:</strong> ${employee.hr_contact_name} - ${employee.hr_contact_email}</p>
    ${
      caseDetail.case.interview_schedule
        ? `<p><strong>Meeting link:</strong> <a class="case-link" href="${caseDetail.case.interview_schedule.meeting_link}" target="_blank" rel="noreferrer">${caseDetail.case.interview_schedule.meeting_link}</a></p>`
        : ""
    }
    ${
      caseDetail.case.interview_schedule?.interview_link
        ? `<p><strong>Interview link:</strong> <a class="case-link" href="${caseDetail.case.interview_schedule.interview_link}" target="_blank" rel="noreferrer">${caseDetail.case.interview_schedule.interview_link}</a></p>`
        : ""
    }
    ${
      documentation
        ? `
          <div class="document-summary">
            <p><strong>Meeting notes PDF:</strong></p>
            <p><a class="button success" href="/api/v1/kt/cases/${workflow.case_id}/documentation" target="_blank" rel="noreferrer">Download generated KT PDF</a></p>
            <p><strong>Distribution:</strong> Shared with the employee, manager, and HR for review.</p>
            <p><strong>Document title:</strong> ${documentation.title}</p>
          </div>
        `
        : `
          <div class="document-summary">
            <p><strong>Sample meeting notes PDF:</strong></p>
            <p><a class="button success" href="/static/sample_meeting_notes.pdf" target="_blank" rel="noreferrer">Open sample PDF</a></p>
            <p><strong>Distribution:</strong> Example review copy for employee, manager, and HR.</p>
          </div>
        `
    }
  `;
  // Mark lifecycle pulse nodes as completed/green
  syncWorkflowPulse(workflow, Boolean(documentation));
}

// Debug helper: quickly verify backend stage/status driving the UI
function _debugWorkflowPulse(workflow) {
  try {
    // Uncomment locally if needed
    // console.log("syncWorkflowPulse", workflow?.stage, workflow?.status);
  } catch (_) {
    // ignore
  }
}

async function loadDashboard() {
  const dashboard = await fetchJson("/api/v1/kt/dashboard");
  state.dashboard = dashboard;

  if (!state.selectedCaseId && dashboard.cases.length) {
    state.selectedCaseId = dashboard.cases[0].case_id;
  }
  if (
    state.selectedCaseId &&
    !dashboard.cases.find((item) => item.case_id === state.selectedCaseId)
  ) {
    state.selectedCaseId = dashboard.cases[0]?.case_id || null;
  }

  renderMetrics(dashboard);
  renderCasesTable(dashboard);

  if (state.selectedCaseId) {
    await loadCaseDetail(state.selectedCaseId, false);
  } else {
    document.getElementById("spotlightTitle").textContent = "Select a case";
    document.getElementById("spotlightBody").innerHTML =
      "<p>No cases yet. Create one from the intake panel.</p>";
  }
}

async function loadCaseDetail(caseId, rerenderTable = true) {
  state.selectedCaseId = caseId;
  const detail = await fetchJson(`/api/v1/kt/cases/${caseId}`);
  renderSpotlight(detail);
  if (rerenderTable && state.dashboard) {
    renderCasesTable(state.dashboard);
  }
}

function wireWorkflowPulseButtons() {
  const rail = document.getElementById("workflowPulse");
  if (!rail) return;
  const nodes = [...rail.querySelectorAll(".workflow-node[role=\"button\"]")];
  nodes.forEach((node) => {
    if (node.dataset.wired === "true") return;
    node.dataset.wired = "true";

    const phase = node.getAttribute("data-phase");
    const handler = async () => {
      if (!state.selectedCaseId) return;
      if (phase === "collect") {
        const completed = await manualCollect();
        if (completed) {
          openScheduleModal(state.selectedCaseId);
        }
      }
    };

    node.addEventListener("click", handler);
    node.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handler();
      }
    });
  });
}

function getScheduleNodes() {
  return {
    backdrop: document.getElementById("scheduleModalBackdrop"),
    form: document.getElementById("scheduleForm"),
    status: document.getElementById("scheduleFormStatus"),
    meetingLink: document.getElementById("scheduleMeetingLink"),
    interviewLink: document.getElementById("scheduleInterviewLink"),
    interviewDatetime: document.getElementById("scheduleDatetime"),
    duration: document.getElementById("scheduleDuration"),
  };
}

function openScheduleModal(caseId) {
  const nodes = getScheduleNodes();
  if (!nodes.backdrop || !nodes.form || !nodes.status || !nodes.meetingLink || !nodes.interviewDatetime || !nodes.duration) {
    return;
  }
  const now = new Date();
  const interviewStart = new Date(now.getTime() + 30 * 60 * 1000);
  state.scheduleCaseId = caseId;
  nodes.backdrop.classList.remove("is-hidden");
  nodes.backdrop.setAttribute("aria-hidden", "false");
  nodes.status.textContent = "Add the links, then send the interview email.";
  nodes.form.reset();
  nodes.duration.value = "60";
  nodes.interviewDatetime.value = toLocalDatetimeInputValue(interviewStart);
  nodes.meetingLink.focus();
}

function closeScheduleModal() {
  const { backdrop, status, form } = getScheduleNodes();
  if (!backdrop || !status || !form) return;
  state.scheduleCaseId = null;
  backdrop.classList.add("is-hidden");
  backdrop.setAttribute("aria-hidden", "true");
  status.textContent = "Add the links, then send the interview email.";
  form.reset();
}

function toLocalDatetimeInputValue(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function syncWorkflowPulse(workflow, hasDocumentation = false) {
  const rail = document.getElementById("workflowPulse");
  if (!rail || !workflow) return;

  // Map backend stages/statuses to a phase completion model
  const stage = String(workflow.stage || "");
  const status = String(workflow.status || "");

  const phaseOrder = ["intake", "notify", "collect", "interview", "document", "approve", "complete"];

  // Completion rules (best-effort with existing backend stages)
  // intake -> when workflow.stage is anything notifications_sent or later
  // notify -> notifications_sent
  // collect -> submission_received
  // interview -> interview_scheduled or interview_completed or in_progress
  // document -> documentation_generated or under_review
  // approve -> completed via approved path
  // complete -> completed stage
  const completedPhases = new Set();

  if (stage === "notifications_sent") completedPhases.add("intake");
  if (["notifications_sent"].includes(stage)) completedPhases.add("notify");

  if (["submission_received"].includes(stage)) {
    completedPhases.add("intake");
    completedPhases.add("notify");
    completedPhases.add("collect");
  }

  if (["submission_received", "interview_scheduled", "interview_completed"].includes(stage)) {
    completedPhases.add("intake");
    completedPhases.add("notify");
    completedPhases.add("collect");
    if (["interview_scheduled", "interview_completed"].includes(stage)) completedPhases.add("interview");
  }

  if (
    ["documentation_generated", "under_review", "changes_requested"].includes(stage) ||
    status === "awaiting_review" ||
    hasDocumentation
  ) {
    completedPhases.add("intake");
    completedPhases.add("notify");
    completedPhases.add("collect");
    completedPhases.add("interview");
    completedPhases.add("document");
  }

  if (stage === "completed") {
    phaseOrder.forEach((p) => completedPhases.add(p));
  }

  phaseOrder.forEach((phase, idx) => {
    const node = rail.querySelector(`[data-phase="${phase}"]`);
    if (!node) return;

    const span = node.querySelector("span");
    const completed = completedPhases.has(phase);

    if (completed) {
      node.classList.add("phase-complete");
      node.setAttribute("data-complete", "true");
      if (span) {
        span.style.background = "linear-gradient(135deg, rgba(0, 128, 0, 0.35), rgba(0, 128, 0, 0.85))";
        span.style.color = "#ffffff";
      }
    } else {
      node.classList.remove("phase-complete");
      node.removeAttribute("data-complete");
      if (span) {
        span.style.background = "linear-gradient(135deg, rgba(31, 111, 235, 0.16), rgba(31, 111, 235, 0.3))";
        span.style.color = "var(--accent-strong)";
      }
    }
  });
}


function renderInterviewSession(session) {
  const transcriptNode = document.getElementById("interviewTranscript");
  const statusNode = document.getElementById("interviewStatus");
  const hintNode = document.getElementById("interviewHint");
  const answerNode = document.getElementById("interviewAnswer");
  if (!transcriptNode || !statusNode || !hintNode || !answerNode) return;
  state.interviewSession = session;

  if (!session) {
    transcriptNode.innerHTML = `<div class="chat-empty">The interview transcript will appear here.</div>`;
    statusNode.textContent = "No interview session loaded.";
    hintNode.textContent =
      "Select a case, then start a live interview session. The agent will ask guided questions and follow up when answers are too thin.";
    answerNode.disabled = true;
    return;
  }

  transcriptNode.innerHTML = session.transcript
    .map(
      (message) => `
      <div class="chat-bubble ${message.role}">
        <span class="chat-role">${message.role === "agent" ? "Interview Agent" : "Employee"}</span>
        <div>${message.content}</div>
        ${message.topic ? `<span class="chat-topic">${message.topic.replaceAll("_", " ")}</span>` : ""}
      </div>
    `,
    )
    .join("");

  transcriptNode.scrollTop = transcriptNode.scrollHeight;
  statusNode.textContent =
    session.status === "completed"
      ? "Interview status: completed. Professional KT PDF generated and moved to review."
      : `Interview status: ${session.status}`;
  hintNode.textContent =
    session.pending_question ||
    session.next_action ||
    "The live interview is complete. Professional KT meeting notes are ready for review.";
  answerNode.disabled = session.status === "completed";
}

function resetInterviewPanel(caseId = null) {
  const transcriptNode = document.getElementById("interviewTranscript");
  const statusNode = document.getElementById("interviewStatus");
  const hintNode = document.getElementById("interviewHint");
  const answerNode = document.getElementById("interviewAnswer");
  if (!transcriptNode || !statusNode || !hintNode || !answerNode) return;
  state.interviewSession = null;

  transcriptNode.innerHTML = `<div class="chat-empty">The interview transcript will appear here.</div>`;
  statusNode.textContent = caseId
    ? "Interview has not started for this case."
    : "No interview session loaded.";
  hintNode.textContent = caseId
    ? "Click Start Interview to begin the live conversational session for this case."
    : "Select a case, then start a live interview session. The meeting agent will capture the discussion and convert it into a professional review-ready PDF.";
  answerNode.disabled = true;
}

async function loadInterviewSession(caseId) {
  try {
    const session = await fetchJson(`/api/v1/kt/cases/${caseId}/interview/live`);
    renderInterviewSession(session);
  } catch (error) {
    resetInterviewPanel(caseId);
  }
}

async function startInterview() {
  const statusNode = document.getElementById("interviewStatus");
  if (!statusNode) return;
  if (!state.selectedCaseId) {
    statusNode.textContent = "Select a case first.";
    return;
  }

  statusNode.textContent = "Starting live interview...";
  try {
    const session = await fetchJson(
      `/api/v1/kt/cases/${state.selectedCaseId}/interview/live/start`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interviewer_name: "AI Interview Agent" }),
      },
    );
    renderInterviewSession(session);
    document.getElementById("interviewAnswer").disabled = false;
    await loadDashboard();
  } catch (error) {
    statusNode.textContent = `Could not start interview: ${error.message}`;
  }
}

async function sendInterviewResponse(event) {
  event.preventDefault();
  const answerNode = document.getElementById("interviewAnswer");
  const statusNode = document.getElementById("interviewStatus");
  if (!answerNode || !statusNode) return;
  const answer = answerNode.value.trim();

  if (!state.selectedCaseId || !answer) {
    return;
  }

  statusNode.textContent = "Sending response...";
  try {
    const session = await fetchJson(
      `/api/v1/kt/cases/${state.selectedCaseId}/interview/live/respond`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer }),
      },
    );
    answerNode.value = "";
    renderInterviewSession(session);
    await loadDashboard();
  } catch (error) {
    statusNode.textContent = `Could not send response: ${error.message}`;
  }
}

async function collectManual(caseId) {
  const statusNode =
    document.getElementById("scheduleFormStatus") ||
    document.getElementById("formStatus");
  if (!caseId) {
    if (statusNode) statusNode.textContent = "Select a case first.";
    return false;
  }

  if (statusNode) statusNode.textContent = "Collect (manual) in progress...";
  try {
    // Build a payload that satisfies EmployeeSubmissionRequest
    // submitted_by (employee email) + documents/systems/open_tasks/risks lists + optional notes.
    const detail = await fetchJson(`/api/v1/kt/cases/${caseId}`);

    const payload = {
      submitted_by: detail.case.employee.employee_email,
      documents: [],
      // Mark at least one system as provided so the submission isn't completely empty.
      systems: ["uploaded"],
      open_tasks: [],
      risks: [],
      notes: "Manual Collect: employee uploaded all documents successfully.",
    };


    await fetchJson(`/api/v1/kt/cases/${caseId}/submission`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (statusNode) statusNode.textContent = "Collect completed successfully. (Stage updated)";
    await loadDashboard();
    await loadCaseDetail(caseId, false);
    return true;
  } catch (error) {
    if (statusNode) statusNode.textContent = `Collect (manual) failed: ${error.message}`;
    return false;
  }
}

async function manualCollect() {
  return collectManual(state.selectedCaseId);
}

async function submitSchedule(event) {
  event.preventDefault();
  const { status, meetingLink, interviewLink, interviewDatetime, duration } = getScheduleNodes();
  const caseId = state.scheduleCaseId;

  if (!caseId) {
    status.textContent = "Select a case first.";
    return;
  }

  status.textContent = "Sending interview email...";
  try {
    const detail = await fetchJson(`/api/v1/kt/cases/${caseId}`);
    const payload = {
      scheduled_by: detail.case.employee.hr_contact_email,
      interview_datetime: new Date(interviewDatetime.value).toISOString(),
      duration_minutes: Number(duration.value),
      meeting_link: meetingLink.value.trim(),
      interview_link: interviewLink.value.trim(),
    };

    await fetchJson(`/api/v1/kt/cases/${caseId}/interview/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    closeScheduleModal();
    await loadDashboard();
    await loadCaseDetail(caseId, false);
    const updated = await fetchJson(`/api/v1/kt/cases/${caseId}`);
    syncWorkflowPulse(updated.case.workflow);
    const workflowStatusNode = document.getElementById("formStatus");
    if (workflowStatusNode) {
      workflowStatusNode.textContent = "Interview scheduled and employee email sent successfully.";
    }
  } catch (error) {
    status.textContent = `Could not send interview email: ${error.message}`;
  }
}

async function createIntake(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const statusNode = document.getElementById("formStatus");
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());

  statusNode.textContent = "Creating KT case...";
  try {
    const result = await fetchJson("/api/v1/kt/resignations/intake", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    statusNode.textContent = `Case created: ${result.case_id}`;
    form.reset();
    state.selectedCaseId = result.case_id;
    await loadDashboard();
  } catch (error) {
    statusNode.textContent = `Could not create case: ${error.message}`;
  }
}


async function boot() {
  updateHealth("Live");
  updateInterviewMode();
  document.getElementById("refreshDashboard").addEventListener("click", () => loadDashboard());
  document.getElementById("intakeForm").addEventListener("submit", createIntake);
  document.getElementById("scheduleForm")?.addEventListener("submit", submitSchedule);
  document.getElementById("scheduleModalClose")?.addEventListener("click", closeScheduleModal);
  document.getElementById("scheduleModalBackdrop")?.addEventListener("click", (event) => {
    if (event.target.id === "scheduleModalBackdrop") {
      closeScheduleModal();
    }
  });

  try {
    await fetchJson("/health");
    updateHealth("Healthy");
    wireWorkflowPulseButtons();
    await loadDashboard();
  } catch (error) {

    updateHealth("Offline");
    document.getElementById("casesTableBody").innerHTML =
      `<tr><td colspan="6" class="empty-state">Could not load dashboard: ${error.message}</td></tr>`;
  }
}

boot();
