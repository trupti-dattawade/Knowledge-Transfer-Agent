const state = {
  dashboard: null,
  selectedCaseId: null,
  interviewSession: null,
  scheduleCaseId: null,
  approvalCaseId: null,
  currentView: "overview",
  filters: {
    stage: "",
    status: "",
  },
  user: {
    role: null,
    email: null,
    name: null,
  },
};

async function fetchJson(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.user.role && state.user.email) {
    headers.set("X-User-Role", state.user.role);
    headers.set("X-User-Email", state.user.email);
    headers.set("X-User-Name", state.user.name || state.user.email);
  }
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return response.json();
}

function withAuthUrl(url) {
  const base = window.location.origin;
  const resolved = new URL(url, base);
  if (state.user.role && state.user.email) {
    resolved.searchParams.set("role", state.user.role);
    resolved.searchParams.set("email", state.user.email);
    resolved.searchParams.set("name", state.user.name || state.user.email);
  }
  return `${resolved.pathname}${resolved.search}`;
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
  node.textContent = "KT meeting and review workflow";
}

function loadUserFromStorage() {
  const raw = localStorage.getItem("kt_user");
  if (!raw) return;
  try {
    const user = JSON.parse(raw);
    state.user = {
      role: user.role || null,
      email: user.email || null,
      name: user.name || null,
    };
  } catch (_) {
    state.user = { role: null, email: null, name: null };
  }
}

function saveUserToStorage() {
  localStorage.setItem("kt_user", JSON.stringify(state.user));
}

function clearUserFromStorage() {
  localStorage.removeItem("kt_user");
}

function showLoginOverlay() {
  const overlay = document.getElementById("loginOverlay");
  if (overlay) overlay.classList.remove("hidden");
}

function hideLoginOverlay() {
  const overlay = document.getElementById("loginOverlay");
  if (overlay) overlay.classList.add("hidden");
}

function updateUserLabel() {
  const label = document.getElementById("currentUserLabel");
  if (!label) return;
  label.textContent = state.user.role
    ? `${state.user.name} (${state.user.role.toUpperCase()})`
    : "Not signed in";
}

function applyRoleUI() {
  const root = document.querySelector(".page-shell");
  if (!root) return;
  root.classList.remove("role-hr", "role-manager", "role-employee");
  if (state.user.role) {
    root.classList.add(`role-${state.user.role}`);
  }
  updateUserLabel();
}

function filterDashboardByRole(dashboard) {
  if (!dashboard || !state.user.role || state.user.role === "hr") {
    return dashboard;
  }

  const filteredCases = dashboard.cases.filter((item) => {
    if (state.user.role === "manager") {
      return item.manager_email?.toLowerCase() === state.user.email?.toLowerCase();
    }
    if (state.user.role === "employee") {
      return item.employee_email?.toLowerCase() === state.user.email?.toLowerCase();
    }
    return false;
  });

  return {
    ...dashboard,
    cases: filteredCases,
    total_cases: filteredCases.length,
    completed_cases: filteredCases.filter((item) => item.stage === "completed").length,
    pending_review_cases: filteredCases.filter((item) => item.status === "awaiting_review").length,
    awaiting_employee_cases: filteredCases.filter((item) => item.status === "awaiting_employee").length,
  };
}

function renderEmployeeStatus() {
  const panel = document.getElementById("employeeStatusPanel");
  const content = document.getElementById("employeeStatusContent");
  if (!panel || !content) return;
  if (state.user.role !== "employee") {
    panel.classList.add("hidden");
    return;
  }

  panel.classList.remove("hidden");
  const visibleCases = state.dashboard?.cases || [];
  if (!visibleCases.length) {
    content.innerHTML = `<p>You do not have an assigned case yet.</p>`;
    return;
  }
  const selected = visibleCases.find((item) => item.case_id === state.selectedCaseId) || visibleCases[0];
  content.innerHTML = `
    <p>Case assigned to you: <strong>${selected.case_id}</strong></p>
    <p>Stage: <strong>${selected.stage}</strong></p>
    <p>Status: <strong>${selected.status}</strong></p>
    <p>Next action: <strong>${selected.next_action}</strong></p>
  `;
}

function requireLogin() {
  return Boolean(state.user.role && state.user.email && state.user.name);
}

function ensureSignedIn() {
  if (requireLogin()) {
    hideLoginOverlay();
    return;
  }
  showLoginOverlay();
}

function handleLogout() {
  state.user = { role: null, email: null, name: null };
  state.dashboard = null;
  state.selectedCaseId = null;
  clearUserFromStorage();
  applyRoleUI();
  ensureSignedIn();
  document.getElementById("casesTableBody").innerHTML =
    `<tr><td colspan="6" class="empty-state">Please sign in to view case dashboards.</td></tr>`;
  document.getElementById("spotlightTitle").textContent = "Select a case";
  document.getElementById("spotlightBody").innerHTML =
    "<p>Please sign in to view case details.</p>";
}

function handleLogin(event) {
  event.preventDefault();
  const roleInput = document.getElementById("loginRole");
  const emailInput = document.getElementById("loginEmail");
  const nameInput = document.getElementById("loginName");
  if (!roleInput || !emailInput || !nameInput) return;

  const role = roleInput.value;
  const email = emailInput.value.trim();
  const name = nameInput.value.trim();
  if (!role || !email || !name) {
    return;
  }

  state.user = { role, email, name };
  saveUserToStorage();
  applyRoleUI();
  ensureSignedIn();
  loadDashboard();
}

function setActiveView(view) {
  if (view === "intake" && state.user.role !== "hr") {
    view = "overview";
  }
  state.currentView = view;
  document.querySelectorAll(".dashboard-view").forEach((section) => {
    section.classList.toggle("is-active", section.dataset.view === view);
  });
  document.querySelectorAll(".menu-link").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewTarget === view);
  });
  if (window.location.hash !== `#${view}`) {
    history.replaceState(null, "", `#${view}`);
  }
}

function wireViewNavigation() {
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const view = button.dataset.viewTarget;
      if (view) setActiveView(view);
    });
  });
  window.addEventListener("hashchange", () => {
    const next = window.location.hash.replace("#", "");
    if (["overview", "cases", "intake"].includes(next)) {
      setActiveView(next);
    }
  });
  const initial = window.location.hash.replace("#", "");
  if (["overview", "cases", "intake"].includes(initial)) {
    setActiveView(initial);
  } else {
    setActiveView("overview");
  }
}

function renderMetrics(dashboard) {
  document.getElementById("totalCases").textContent = dashboard.total_cases;
  document.getElementById("completedCases").textContent = dashboard.completed_cases;
  document.getElementById("pendingReviewCases").textContent = dashboard.pending_review_cases;
  document.getElementById("awaitingEmployeeCases").textContent = dashboard.awaiting_employee_cases;
  document.getElementById("casesLoaded").textContent = dashboard.cases.length;

  // Overview focus cards
  const pendingFocus = document.getElementById("pendingReviewCasesFocus");
  const awaitingFocus = document.getElementById("awaitingEmployeeCasesFocus");
  if (pendingFocus) pendingFocus.textContent = dashboard.pending_review_cases;
  if (awaitingFocus) awaitingFocus.textContent = dashboard.awaiting_employee_cases;
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

function isManagerApprovalsAllowedForCase(caseDetail) {
  if (!caseDetail?.case?.workflow) return false;
  // Manager approvals are allowed only when the case is ready for review.
  // Backend sets stage="under_review" and/or status="awaiting_review".
  const workflow = caseDetail.case.workflow;
  return workflow.stage === "under_review" || workflow.status === "awaiting_review";
}


function renderSpotlight(caseDetail) {
  const title = document.getElementById("spotlightTitle");
  const body = document.getElementById("spotlightBody");
  const workflow = caseDetail.case.workflow;
  const employee = caseDetail.case.employee;
  const documentation = caseDetail.case.documentation;
  const submission = caseDetail.case.submission;
  const selectedCaseBadges = [
    document.getElementById("selectedCaseBadge"),
    document.getElementById("selectedCaseBadgeCases"),
  ];
  const selectedCaseSubtexts = [
    document.getElementById("selectedCaseSubtext"),
    document.getElementById("selectedCaseSubtextCases"),
  ];

  title.textContent = `${employee.employee_name} - ${employee.department}`;
  selectedCaseBadges.forEach((node) => {
    if (node) node.textContent = workflow.case_id;
  });
  selectedCaseSubtexts.forEach((node) => {
    if (node) node.textContent = `${employee.employee_name} - ${workflow.stage.replaceAll("_", " ")} - ${workflow.status.replaceAll("_", " ")}`;
  });
  const roleSpecificContent = state.user.role === "hr"
    ? `
        <p><strong>Process:</strong> ${workflow.next_action}</p>
        <p><strong>Employee stage:</strong> ${workflow.stage}</p>
        <p><strong>Employee status:</strong> ${workflow.status}</p>
        <p><strong>Uploaded documents:</strong> ${submission?.documents?.length || 0}</p>
      `
    : `
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
            ? `<p><strong>Recording link:</strong> <a class="case-link" href="${caseDetail.case.interview_schedule.interview_link}" target="_blank" rel="noreferrer">${caseDetail.case.interview_schedule.interview_link}</a></p>`
            : ""
        }
      `;

  const documentContent = documentation
    ? `
        <div class="document-summary">
          <p><strong>Meeting notes PDF:</strong></p>
          <p><a class="button success" href="${withAuthUrl(`/api/v1/kt/cases/${workflow.case_id}/documentation`)}" target="_blank" rel="noreferrer">Download generated KT PDF</a></p>
          <p><strong>Document title:</strong> ${documentation.title}</p>
        </div>
      `
    : `
        <div class="document-summary">
          <p><strong>Sample meeting notes PDF:</strong></p>
          <p><a class="button success" href="/static/sample_meeting_notes.pdf" target="_blank" rel="noreferrer">Open sample PDF</a></p>
        </div>
      `;

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
    ${roleSpecificContent}
    ${documentContent}
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
  if (!requireLogin()) {
    return;
  }
  const query = new URLSearchParams();
  if (state.filters.stage) query.set("stage", state.filters.stage);
  if (state.filters.status) query.set("status", state.filters.status);
  const dashboard = await fetchJson(`/api/v1/kt/dashboard${query.toString() ? `?${query.toString()}` : ""}`);
  state.dashboard = filterDashboardByRole(dashboard);

  if (!state.selectedCaseId && state.dashboard.cases.length) {
    state.selectedCaseId = state.dashboard.cases[0].case_id;
  }
  if (
    state.selectedCaseId &&
    !state.dashboard.cases.find((item) => item.case_id === state.selectedCaseId)
  ) {
    state.selectedCaseId = state.dashboard.cases[0]?.case_id || null;
  }

  renderMetrics(state.dashboard);
  renderCasesTable(state.dashboard);
  renderEmployeeStatus();

  if (state.selectedCaseId) {
    await loadCaseDetail(state.selectedCaseId, false);
  } else {
    document.getElementById("spotlightTitle").textContent = "Select a case";
    document.getElementById("spotlightBody").innerHTML =
      "<p>No cases yet. Create one from the intake panel.</p>";
    [
      document.getElementById("selectedCaseBadge"),
      document.getElementById("selectedCaseBadgeCases"),
    ].forEach((node) => {
      if (node) node.textContent = "No case selected";
    });
    [
      document.getElementById("selectedCaseSubtext"),
      document.getElementById("selectedCaseSubtextCases"),
    ].forEach((node) => {
      if (node) node.textContent = "Pick a case from the board to run workflow actions.";
    });
  }
}

async function loadCaseDetail(caseId, rerenderTable = true) {
  if (!requireLogin()) {
    return;
  }
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
        if (state.user.role !== "employee") {
          const statusNode = document.getElementById("formStatus");
          if (statusNode) statusNode.textContent = "Only the employee assigned to this case can submit handover details.";
          return;
        }
        await manualCollect();
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

function getActionNodes() {
  return {
    stageFilter: document.getElementById("stageFilter"),
    statusFilter: document.getElementById("statusFilter"),
    actionStatus: document.getElementById("actionStatus"),
  };
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

async function generateDocumentationForSelectedCase() {
  const { actionStatus } = getActionNodes();
  if (!state.selectedCaseId) {
    if (actionStatus) actionStatus.textContent = "Select a case first.";
    return;
  }
  if (state.user.role !== "hr") {
    if (actionStatus) actionStatus.textContent = "Only HR users can generate the review PDF.";
    return;
  }
  if (actionStatus) actionStatus.textContent = "Generating professional KT review PDF...";
  try {
    await fetchJson(`/api/v1/kt/cases/${state.selectedCaseId}/documentation/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ generated_by: "Dashboard Command Center" }),
    });
    await loadDashboard();
    await loadCaseDetail(state.selectedCaseId, false);
    if (actionStatus) actionStatus.textContent = "KT review PDF generated and review email sent.";
  } catch (error) {
    if (actionStatus) actionStatus.textContent = `Could not generate PDF: ${error.message}`;
  }
}

async function applyFilters() {
  const { stageFilter, statusFilter, actionStatus } = getActionNodes();
  state.filters.stage = stageFilter?.value || "";
  state.filters.status = statusFilter?.value || "";
  await loadDashboard();
  if (actionStatus) {
    actionStatus.textContent = state.filters.stage || state.filters.status
      ? "Case board filtered successfully."
      : "Showing all cases.";
  }
}

async function clearFilters() {
  const { stageFilter, statusFilter, actionStatus } = getActionNodes();
  state.filters.stage = "";
  state.filters.status = "";
  if (stageFilter) stageFilter.value = "";
  if (statusFilter) statusFilter.value = "";
  await loadDashboard();
  if (actionStatus) actionStatus.textContent = "Filters cleared. Showing all cases.";
}

async function submitSchedule(event) {
  event.preventDefault();
  const { status, meetingLink, interviewLink, interviewDatetime, duration } = getScheduleNodes();
  const caseId = state.scheduleCaseId;

  if (!caseId) {
    status.textContent = "Select a case first.";
    return;
  }

  status.textContent = "Sending meeting email...";
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
      workflowStatusNode.textContent = "Meeting scheduled and employee email sent successfully.";
    }
  } catch (error) {
    status.textContent = `Could not send meeting email: ${error.message}`;
  }
}

async function createIntake(event) {
  event.preventDefault();
  if (state.user.role !== "hr") {
    const statusNode = document.getElementById("formStatus");
    if (statusNode) statusNode.textContent = "Only HR users can create a new intake.";
    return;
  }
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
    setActiveView("cases");
  } catch (error) {
    statusNode.textContent = `Could not create case: ${error.message}`;
  }
}

function getApprovalNodes() {
  return {
    backdrop: document.getElementById("approvalModalBackdrop"),
    form: document.getElementById("approvalForm"),
    status: document.getElementById("approvalFormStatus"),
    decision: document.getElementById("approvalDecision"),
    comments: document.getElementById("approvalComments"),
    preview: document.getElementById("approvalDocumentPreview"),
  };
}

function openApprovalModal(caseId) {
  const nodes = getApprovalNodes();
  if (!nodes.backdrop || !nodes.form || !nodes.status || !nodes.decision || !nodes.comments || !nodes.preview) {
    return;
  }

  state.approvalCaseId = caseId;
  nodes.backdrop.classList.remove("is-hidden");
  nodes.backdrop.setAttribute("aria-hidden", "false");
  nodes.status.textContent = "Review the document and submit your decision.";
  nodes.form.reset();

  // Load document preview
  loadDocumentPreview(caseId);
  nodes.decision.focus();
}

function closeApprovalModal() {
  const { backdrop, status, form } = getApprovalNodes();
  if (!backdrop || !status || !form) return;
  state.approvalCaseId = null;
  backdrop.classList.add("is-hidden");
  backdrop.setAttribute("aria-hidden", "true");
  status.textContent = "Review the document and submit your decision.";
  form.reset();
}

async function loadDocumentPreview(caseId) {
  const { preview } = getApprovalNodes();
  if (!preview) return;

  try {
    const detail = await fetchJson(`/api/v1/kt/cases/${caseId}`);
    if (detail.case.documentation) {
      preview.innerHTML = `
        <iframe src="${withAuthUrl(`/api/v1/kt/cases/${caseId}/documentation`)}" title="KT Report Preview"></iframe>
        <p><strong>Document:</strong> ${detail.case.documentation.title}</p>
        <p><strong>Generated:</strong> ${new Date(detail.case.documentation.generated_at).toLocaleString()}</p>
      `;
    } else {
      preview.innerHTML = `<p>No documentation available for review.</p>`;
    }
  } catch (error) {
    preview.innerHTML = `<p>Could not load document preview: ${error.message}</p>`;
  }
}

async function submitApproval(event) {
  event.preventDefault();
  const { status, decision, comments } = getApprovalNodes();
  const caseId = state.approvalCaseId;

  if (!caseId) {
    status.textContent = "Select a case first.";
    return;
  }

  if (state.user.role !== "manager") {
    status.textContent = "Only managers can submit approval decisions.";
    return;
  }

  // Enforce allowed states on the client side as requested.
  let detail = null;
  try {
    detail = await fetchJson(`/api/v1/kt/cases/${caseId}`);
  } catch (e) {
    // fall through; backend will handle if needed
  }

  if (detail && !isManagerApprovalsAllowedForCase(detail)) {
    status.textContent = "This case is not ready for manager review.";
    return;
  }

  const decisionValue = decision.value;
  const commentsValue = comments.value.trim();

  if (!decisionValue) {
    status.textContent = "Please select a decision.";
    return;
  }

  if (commentsValue.length < 5) {
    status.textContent = "Please add at least a short comment (min 5 characters).";
    return;
  }

  status.textContent = "Submitting approval decision...";
  try {
    const payload = {
      reviewer_email: state.user.email,
      reviewer_name: state.user.name,
      decision: decisionValue,
      comments: commentsValue,
    };

    await fetchJson(`/api/v1/kt/cases/${caseId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    // Refresh everything so every role sees updated state.
    closeApprovalModal();
    await loadDashboard();
    await loadCaseDetail(caseId, false);

    const workflowStatusNode = document.getElementById("actionStatus");
    if (workflowStatusNode) {
      workflowStatusNode.textContent = `Report ${decisionValue === "approved" ? "approved" : "changes requested"} successfully.`;
    }
  } catch (error) {
    status.textContent = `Could not submit decision: ${error.message}`;
  }
}

async function approveReportForSelectedCase() {
  const { actionStatus } = getActionNodes();
  if (!state.selectedCaseId) {
    if (actionStatus) actionStatus.textContent = "Select a case first.";
    return;
  }
  if (state.user.role !== "manager") {
    if (actionStatus) actionStatus.textContent = "Only managers can approve reports.";
    return;
  }

  // Enforce allowed states on the client side.
  let detail = null;
  try {
    detail = await fetchJson(`/api/v1/kt/cases/${state.selectedCaseId}`);
  } catch (e) {
    // If we can't load detail, backend will still guard.
  }

  if (detail && !isManagerApprovalsAllowedForCase(detail)) {
    if (actionStatus) actionStatus.textContent = "This case is not ready for manager approval.";
    return;
  }

  openApprovalModal(state.selectedCaseId);
  const { decision } = getApprovalNodes();
  if (decision) decision.value = "approved";
  if (actionStatus) actionStatus.textContent = "Approval modal opened for the selected case.";
}

async function rejectReportForSelectedCase() {
  const { actionStatus } = getActionNodes();
  if (!state.selectedCaseId) {
    if (actionStatus) actionStatus.textContent = "Select a case first.";
    return;
  }
  if (state.user.role !== "manager") {
    if (actionStatus) actionStatus.textContent = "Only managers can request changes.";
    return;
  }

  // Enforce allowed states on the client side.
  let detail = null;
  try {
    detail = await fetchJson(`/api/v1/kt/cases/${state.selectedCaseId}`);
  } catch (e) {
    // If we can't load detail, backend will still guard.
  }

  if (detail && !isManagerApprovalsAllowedForCase(detail)) {
    if (actionStatus) actionStatus.textContent = "This case is not ready for manager review.";
    return;
  }

  openApprovalModal(state.selectedCaseId);
  // Pre-select reject option
  const { decision } = getApprovalNodes();
  if (decision) decision.value = "changes_requested";
  if (actionStatus) actionStatus.textContent = "Changes request modal opened for the selected case.";
}

async function boot() {
  updateHealth("Live");
  updateInterviewMode();
  loadUserFromStorage();
  applyRoleUI();
  ensureSignedIn();
  wireViewNavigation();
  document.getElementById("refreshDashboard").addEventListener("click", () => loadDashboard());
  document.getElementById("loginForm")?.addEventListener("submit", handleLogin);
  document.getElementById("logoutBtn")?.addEventListener("click", handleLogout);
  document.getElementById("intakeForm").addEventListener("submit", createIntake);
  document.getElementById("generateDocumentBtn")?.addEventListener("click", generateDocumentationForSelectedCase);
  document.getElementById("approveReportBtn")?.addEventListener("click", approveReportForSelectedCase);
  document.getElementById("rejectReportBtn")?.addEventListener("click", rejectReportForSelectedCase);

  // Overview focus cards
  document.getElementById("focusGenerateDoc")?.addEventListener("click", async () => {
    document.getElementById("actionStatus")?.scrollIntoView({ behavior: "smooth", block: "center" });
    await loadDashboard();
    await generateDocumentationForSelectedCase();
  });
  document.getElementById("reviewReportsBtn")?.addEventListener("click", () => {
    setActiveView("cases");
  });

  document.getElementById("applyFiltersBtn")?.addEventListener("click", applyFilters);
  document.getElementById("clearFiltersBtn")?.addEventListener("click", clearFilters);
  document.getElementById("approvalForm")?.addEventListener("submit", submitApproval);
  document.getElementById("approvalModalClose")?.addEventListener("click", closeApprovalModal);
  document.getElementById("approvalModalBackdrop")?.addEventListener("click", (event) => {
    if (event.target.id === "approvalModalBackdrop") {
      closeApprovalModal();
    }
  });

  try {
    await fetchJson("/health");
    updateHealth("Healthy");
    wireWorkflowPulseButtons();
    if (requireLogin()) {
      await loadDashboard();
    } else {
      document.getElementById("casesTableBody").innerHTML =
        `<tr><td colspan="6" class="empty-state">Please sign in to view case dashboards.</td></tr>`;
    }
  } catch (error) {

    updateHealth("Offline");
    document.getElementById("casesTableBody").innerHTML =
      `<tr><td colspan="6" class="empty-state">Could not load dashboard: ${error.message}</td></tr>`;
  }
}

boot();
