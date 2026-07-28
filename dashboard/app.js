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
  for (const key of ["name", "assistant_name", "assistant_image_url", "website_url", "scheduling_link", "handoff_webhook_url", "handoff_email", "flow_script", "accent_color"]) {
    if (form.elements[key]) form.elements[key].value = data[key] ?? "";
  }
  const apiBase = window.location.origin;
  const displayName = data.assistant_name || data.name || "Chat with us";
  $("#embedSnippet").textContent =
    `<script\n` +
    `  src="${apiBase}/widget/widget.js"\n` +
    `  data-api-base="${apiBase}"\n` +
    `  data-business-name="${displayName.replace(/"/g, "&quot;")}"\n` +
    `  data-color="${data.accent_color || "#4f46e5"}"\n` +
    (data.assistant_image_url ? `  data-avatar-url="${data.assistant_image_url.replace(/"/g, "&quot;")}"\n` : "") +
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

  for (const status of ["new", "claimed", "done"]) {
    const col = document.querySelector(`.board-col-cards[data-status="${status}"]`);
    const inCol = rows.filter((r) => (r.status || "new") === status);
    $(`#count-${status}`).textContent = inCol.length;
    col.innerHTML = inCol.map(cardHtml).join("") || `<p class="muted board-empty">Nothing here.</p>`;
  }

  document.querySelectorAll(".lead-card").forEach((card) => {
    card.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", card.dataset.id);
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));

    card.querySelector(".claim-btn")?.addEventListener("click", () => {
      card.querySelector(".claim-prompt").hidden = false;
      card.querySelector(".claim-btn").hidden = true;
      card.querySelector(".claim-input").focus();
    });

    card.querySelector(".claim-confirm")?.addEventListener("click", async () => {
      const input = card.querySelector(".claim-input");
      if (!input.value.trim()) return;
      await patchLead(card.dataset.id, { claimed_by: input.value.trim(), status: "claimed" });
      loadLeads();
    });
    card.querySelector(".claim-input")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") card.querySelector(".claim-confirm").click();
    });

    card.querySelector(".status-select")?.addEventListener("change", async (e) => {
      await patchLead(card.dataset.id, { status: e.target.value });
      loadLeads();
    });

    card.querySelector(".outcome-select")?.addEventListener("change", async (e) => {
      await patchLead(card.dataset.id, { outcome: e.target.value });
    });

    const notesEl = card.querySelector(".card-notes");
    notesEl?.addEventListener("blur", async () => {
      await patchLead(card.dataset.id, { notes: notesEl.value });
    });

    const goodToKnowEl = card.querySelector(".card-good-to-know");
    goodToKnowEl?.addEventListener("blur", async () => {
      await patchLead(card.dataset.id, { good_to_know: goodToKnowEl.value });
    });
  });

  document.querySelectorAll(".board-col-cards").forEach((col) => {
    col.addEventListener("dragover", (e) => e.preventDefault());
    col.addEventListener("drop", async (e) => {
      e.preventDefault();
      const id = e.dataTransfer.getData("text/plain");
      const newStatus = col.dataset.status;
      await patchLead(id, { status: newStatus });
      loadLeads();
    });
  });
}

const STATUS_LABELS = { new: "New", claimed: "Claimed", done: "Done" };
const OUTCOME_LABELS = {
  booked: "✅ Booked",
  not_interested: "🚫 Not interested",
  no_response: "🔇 No response",
  duplicate: "♻️ Duplicate",
  spam: "🗑️ Spam",
  other: "❔ Other",
};

function cardHtml(r) {
  const contact = [r.email, r.phone].filter(Boolean).join(" / ");
  const status = r.status || "new";
  const statusOptions = Object.entries(STATUS_LABELS)
    .map(([val, label]) => `<option value="${val}" ${val === status ? "selected" : ""}>${label}</option>`)
    .join("");
  const outcomeOptions =
    `<option value="">Outcome…</option>` +
    Object.entries(OUTCOME_LABELS)
      .map(([val, label]) => `<option value="${val}" ${val === r.outcome ? "selected" : ""}>${label}</option>`)
      .join("");
  return `
    <div class="lead-card" draggable="true" data-id="${r.id}">
      <div class="lead-card-intent">${INTENT_LABELS[r.intent] || esc(r.intent)}</div>
      <div class="lead-card-name">${esc(r.name) || "<em>No name given</em>"}</div>
      ${contact ? `<div class="lead-card-contact">${esc(contact)}</div>` : ""}
      <label class="card-field-label">Notes</label>
      <textarea class="card-notes" rows="2">${esc(r.notes)}</textarea>
      <label class="card-field-label">Good to know</label>
      <textarea class="card-good-to-know" rows="2" placeholder="Standing context, e.g. referred by X, handle gently...">${esc(r.good_to_know)}</textarea>
      ${status === "done" ? `<select class="outcome-select">${outcomeOptions}</select>` : ""}
      <div class="lead-card-footer">
        <span class="lead-card-date">${fmtDate(r.created_at)}</span>
        <select class="status-select">${statusOptions}</select>
      </div>
      <div class="lead-card-claim">
        ${
          r.claimed_by
            ? `<span class="claimed-by">👤 ${esc(r.claimed_by)}</span>`
            : `<button class="claim-btn">Claim</button>
               <span class="claim-prompt" hidden>
                 <input class="claim-input" type="text" placeholder="Your name" />
                 <button class="claim-confirm">OK</button>
               </span>`
        }
      </div>
    </div>`;
}

async function patchLead(id, body) {
  await fetch(`/api/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

let convFilterDebounce;
function scheduleConversationReload() {
  clearTimeout(convFilterDebounce);
  convFilterDebounce = setTimeout(loadConversations, 300);
}
$("#convSearch")?.addEventListener("input", scheduleConversationReload);
$("#convSince")?.addEventListener("change", loadConversations);
$("#convUntil")?.addEventListener("change", loadConversations);
$("#convClearFilters")?.addEventListener("click", () => {
  $("#convSearch").value = "";
  $("#convSince").value = "";
  $("#convUntil").value = "";
  loadConversations();
});

async function loadConversations() {
  const params = new URLSearchParams();
  const q = $("#convSearch")?.value.trim();
  const since = $("#convSince")?.value;
  const until = $("#convUntil")?.value;
  if (q) params.set("q", q);
  if (since) params.set("since", since);
  if (until) params.set("until", until);

  const res = await fetch("/api/conversations?" + params.toString());
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
