const $ = (sel) => document.querySelector(sel);

document.querySelectorAll("#tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "knowledge") loadSources();
    if (btn.dataset.tab === "leads") loadLeads();
    if (btn.dataset.tab === "conversations") loadConversations();
  });
});

async function loadBusiness() {
  const res = await fetch("/api/business");
  const data = await res.json();
  const form = $("#settingsForm");
  for (const key of ["name", "website_url", "scheduling_link", "handoff_webhook_url", "flow_script", "accent_color"]) {
    if (form.elements[key]) form.elements[key].value = data[key] ?? "";
  }
  const apiBase = window.location.origin;
  $("#embedSnippet").textContent =
    `<script\n` +
    `  src="${apiBase}/widget/widget.js"\n` +
    `  data-api-base="${apiBase}"\n` +
    `  data-business-name="${(data.name || "Chat with us").replace(/"/g, "&quot;")}"\n` +
    `  data-color="${data.accent_color || "#4f46e5"}"\n` +
    `  defer\n` +
    `><\/script>`;
}

$("#settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  const status = $("#saveStatus");
  status.textContent = "Saving…";
  const res = await fetch("/api/business", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  status.textContent = res.ok ? "Saved ✓" : "Error saving";
  loadBusiness();
  setTimeout(() => (status.textContent = ""), 2500);
});

$("#crawlBtn").addEventListener("click", async () => {
  const status = $("#crawlStatus");
  status.textContent = "Starting crawl…";
  const res = await fetch("/api/knowledge/crawl", { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    status.textContent = err.detail || "Could not start crawl";
    return;
  }
  pollCrawl(status);
});

function pollCrawl(status) {
  let tries = 0;
  const iv = setInterval(async () => {
    tries++;
    await loadSources();
    status.textContent = "Crawling… check Ingested Sources below for progress.";
    if (tries > 15) clearInterval(iv);
  }, 3000);
  setTimeout(() => clearInterval(iv), 50000);
}

$("#docForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  const status = $("#docStatus");
  status.textContent = "Adding…";
  const res = await fetch("/api/knowledge/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  status.textContent = res.ok ? "Added ✓" : "Error adding document";
  if (res.ok) e.target.reset();
  loadSources();
  setTimeout(() => (status.textContent = ""), 2500);
});

async function loadSources() {
  const res = await fetch("/api/knowledge/sources");
  const rows = await res.json();
  const tbody = $("#sourcesTable tbody");
  tbody.innerHTML =
    rows
      .map(
        (s) =>
          `<tr><td>${s.source_type === "site" ? "Site page" : "Manual"}</td><td>${esc(s.url || s.label)}</td><td>${s.chunk_count}</td><td>${fmtDate(s.fetched_at)}</td><td><button class="delete" data-id="${s.id}">Remove</button></td></tr>`
      )
      .join("") || `<tr><td colspan="5" class="muted">No knowledge sources yet.</td></tr>`;
  tbody.querySelectorAll("button.delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/knowledge/sources/${btn.dataset.id}`, { method: "DELETE" });
      loadSources();
    });
  });
}

const INTENT_LABELS = {
  event_rsvp: "🎟️ Event RSVP",
  meetup_request: "☕ Meetup",
  call_booking: "📅 Call",
  human_request: "🙋 Wants human",
  unresolved_question: "❓ Unresolved",
  complaint: "⚠️ Complaint",
  leadership_inquiry: "⭐ Leadership",
  general_inquiry: "💬 Inquiry",
  urgent_crisis: "🚨 Urgent",
};

async function loadLeads() {
  const res = await fetch("/api/leads");
  const rows = await res.json();
  const tbody = $("#leadsTable tbody");
  tbody.innerHTML =
    rows
      .map(
        (r) =>
          `<tr><td>${fmtDate(r.created_at)}</td><td>${INTENT_LABELS[r.intent] || esc(r.intent)}</td><td>${esc(r.name)}</td><td>${esc(r.email)}</td><td>${esc(r.phone)}</td><td>${esc(r.notes)}</td><td>${r.handoff_notified ? "✅" : "—"}</td></tr>`
      )
      .join("") || `<tr><td colspan="7" class="muted">No leads yet.</td></tr>`;
}

async function loadConversations() {
  const res = await fetch("/api/conversations");
  const rows = await res.json();
  const tbody = $("#conversationsTable tbody");
  tbody.innerHTML =
    rows
      .map(
        (r) =>
          `<tr data-id="${r.id}"><td>${esc(r.session_id).slice(0, 14)}…</td><td>${fmtDate(r.created_at)}</td><td>${r.message_count}</td></tr>`
      )
      .join("") || `<tr><td colspan="3" class="muted">No conversations yet.</td></tr>`;
  tbody.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.addEventListener("click", () => loadConversationDetail(tr.dataset.id));
  });
}

async function loadConversationDetail(id) {
  const res = await fetch(`/api/conversations/${id}/messages`);
  const rows = await res.json();
  $("#conversationDetail").innerHTML = rows
    .map((m) => `<div class="msg-row"><div class="msg-role">${esc(m.role)}</div><div class="msg-content">${esc(m.content)}</div></div>`)
    .join("");
}

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function fmtDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

loadBusiness();
