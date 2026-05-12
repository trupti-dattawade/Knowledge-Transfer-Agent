const state = {
  dashboard: null,
  selectedCaseId: null,
  interviewSession: null,
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
  node.textContent = "AI-ready when configured";
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
      documentation
        ? `<p><a class="case-link" href="/api/v1/kt/cases/${workflow.case_id}/documentation" target="_blank" rel="noreferrer">Download generated KT PDF</a></p>`
        : ""
    }
  `;
  // Mark lifecycle pulse nodes as completed/green
  syncWorkflowPulse(workflow);
  resetInterviewPanel(workflow.case_id);
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

function syncWorkflowPulse(workflow) {
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

  if (["documentation_generated", "under_review", "changes_requested"].includes(stage)) {
    completedPhases.add("intake");
    completedPhases.add("notify");
    completedPhases.add("collect");
    completedPhases.add("interview");
    completedPhases.add("document");
    if (stage === "documentation_generated") completedPhases.add("document");
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
  state.interviewSession = session;
  const transcriptNode = document.getElementById("interviewTranscript");
  const statusNode = document.getElementById("interviewStatus");
  const hintNode = document.getElementById("interviewHint");
  const answerNode = document.getElementById("interviewAnswer");

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
  statusNode.textContent = `Interview status: ${session.status}`;
  hintNode.textContent = session.pending_question || "The live interview is complete. You can generate documentation next.";
  answerNode.disabled = session.status === "completed";
}

function resetInterviewPanel(caseId = null) {
  state.interviewSession = null;
  const transcriptNode = document.getElementById("interviewTranscript");
  const statusNode = document.getElementById("interviewStatus");
  const hintNode = document.getElementById("interviewHint");
  const answerNode = document.getElementById("interviewAnswer");

  transcriptNode.innerHTML = `<div class="chat-empty">The interview transcript will appear here.</div>`;
  statusNode.textContent = caseId
    ? "Interview has not started for this case."
    : "No interview session loaded.";
  hintNode.textContent = caseId
    ? "Click Start Interview to begin the live conversational session for this case."
    : "Select a case, then start a live interview session. The agent will ask guided questions and follow up when answers are too thin.";
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
  resetInterviewPanel();
  document.getElementById("refreshDashboard").addEventListener("click", () => loadDashboard());
  document.getElementById("intakeForm").addEventListener("submit", createIntake);
  document.getElementById("startInterviewBtn").addEventListener("click", startInterview);
  document
    .getElementById("refreshInterviewBtn")
    .addEventListener("click", () => state.selectedCaseId && loadInterviewSession(state.selectedCaseId));
  document.getElementById("interviewForm").addEventListener("submit", sendInterviewResponse);
  try {
    await fetchJson("/health");
    updateHealth("Healthy");
    await loadDashboard();
  } catch (error) {
    updateHealth("Offline");
    document.getElementById("casesTableBody").innerHTML =
      `<tr><td colspan="6" class="empty-state">Could not load dashboard: ${error.message}</td></tr>`;
  }
}

boot();
