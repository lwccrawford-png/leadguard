const $ = (sel) => document.querySelector(sel);

// Every fetch() below hits a path like `${API_BASE}/api/...`. Direct access
// (lmtlss.justaskevolveiq.com/dashboard/) has no prefix, so API_BASE is "".
// Accessed through the admin launcher's proxy (team.justaskevolveiq.com/
// proxy/8002/dashboard/...), a bare "/api/..." fetch would resolve against
// the domain root instead of the proxy path and 404 — the launcher has no
// /api/business route, only each client backend does. Deriving the prefix
// from the current URL instead of hardcoding it makes both paths work.
const API_BASE = window.location.pathname.replace(/\/dashboard(\/.*)?$/, "");

const ROT_CONFIG = { agingMinutes: 1440, rottingMinutes: 4320 };
let PIPELINE_ENABLED = false;

// Cosmetic view-mode toggle for demos — hides agency-only tabs so you can show
// a partner/prospect what a client sees, without exposing Settings/Knowledge/
// Usage. NOT real access control: nothing stops someone from editing the URL
// to drop ?view=client. Real enforcement is the separate Team Access Links
// work (see docs/BIA_team_access_links.md) — not built into this yet.
if (new URLSearchParams(window.location.search).get("view") === "client") {
  document.querySelectorAll(".admin-only").forEach((el) => (el.style.display = "none"));
  $("#viewModeBanner").hidden = false;
  $("#switchToAdmin").addEventListener("click", (e) => {
    e.preventDefault();
    window.location.href = window.location.pathname;
  });
}

document.querySelectorAll("#tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "knowledge") {
      loadSources();
      loadFaqs();
      loadFacts();
      loadFaqSchema();
      loadComposition();
      loadUnresolvedKnowledge();
    }
    if (btn.dataset.tab === "leads") loadLeads();
    if (btn.dataset.tab === "conversations") loadConversations();
    if (btn.dataset.tab === "usage") loadUsage();
    if (btn.dataset.tab === "dashboard") loadDashboard();
    if (btn.dataset.tab === "pipeline") loadPipeline();
  });
});

document.querySelectorAll(".dash-goto").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelector(`#tabs button[data-tab="${btn.dataset.goto}"]`)?.click();
  });
});

document.getElementById("unresolvedFilter")?.addEventListener("change", () => loadLeads());

function greetingPreset(assistantName, businessName) {
  return assistantName
    ? `Hi! I'm ${assistantName} from ${businessName || "the team"} — ask me anything or book an appointment.`
    : `Hi! I'm the AI assistant for ${businessName || "this business"} — ask me anything or book an appointment.`;
}

document.getElementById("useGreetingPreset")?.addEventListener("click", () => {
  const form = $("#settingsForm");
  form.elements["greeting"].value = greetingPreset(form.elements["assistant_name"].value, form.elements["name"].value);
  form.elements["greeting"].dispatchEvent(new Event("input", { bubbles: true }));
});

// Curated starter-question pools an admin can pick 3 from instead of writing from
// scratch — each written to flow naturally with that vertical's BIP. Add a new key
// here whenever a new BIP goes live; "Platform / General" covers EvolveIQ's own
// demo (and anything without a vertical-specific bank yet).
const SUGGESTED_QUESTION_BANKS = {
  "HVAC": [
    "My AC is running but not cooling. What should I check first?",
    "How do I know whether I need a repair or replacement?",
    "Do you offer emergency service or financing options?",
    "What's included in a routine maintenance visit?",
    "My furnace is making a strange noise — is that urgent?",
    "Do you service my area, and how fast can someone come out?",
    "What's a fair price range for a new AC installation?",
    "I smell gas near my furnace — what should I do?",
    "Is there an extra charge for weekend or after-hours visits?",
  ],
  "Personal Injury Legal": [
    "I was in a car accident yesterday — what should I do first?",
    "Do I have a case?",
    "What do I say to the insurance company that called me?",
    "How much does it cost to talk to a lawyer?",
    "My spouse was hospitalized after an accident — can someone talk to me tonight?",
    "How long do I have to file a claim?",
    "What's the process after I hire a personal injury attorney?",
    "Will I have to go to court?",
    "What kind of compensation could I be entitled to?",
  ],
  "Platform / General": [
    "What exactly does EvolveIQ do?",
    "How is this different from a regular chatbot?",
    "How much does EvolveIQ cost?",
    "Can I try this on my own business's website?",
    "How long does setup take?",
    "What happens if the assistant doesn't know an answer?",
    "Can I see a demo built from my own website?",
    "Does this work for my industry?",
    "What's included in the monthly subscription?",
  ],
};

(function setUpSuggestedQuestionBank() {
  const select = document.getElementById("suggestedQuestionBankSelect");
  const list = document.getElementById("suggestedQuestionBankList");
  if (!select || !list) return;
  Object.keys(SUGGESTED_QUESTION_BANKS).forEach((bankName) => {
    const opt = document.createElement("option");
    opt.value = bankName;
    opt.textContent = bankName;
    select.appendChild(opt);
  });
  function renderBank(bankName) {
    list.innerHTML = "";
    const questions = SUGGESTED_QUESTION_BANKS[bankName];
    if (!questions) return;
    const form = $("#settingsForm");
    const slots = [form.elements["demo_suggested_questions_1"], form.elements["demo_suggested_questions_2"], form.elements["demo_suggested_questions_3"]];
    questions.forEach((q) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "suggested-q-chip";
      chip.textContent = q;
      chip.addEventListener("click", () => {
        const emptySlot = slots.find((s) => !s.value.trim());
        if (!emptySlot) return;
        emptySlot.value = q;
        emptySlot.dispatchEvent(new Event("input", { bubbles: true }));
      });
      list.appendChild(chip);
    });
  }
  select.addEventListener("change", () => renderBank(select.value));
})();

async function loadBusiness() {
  const res = await fetch(API_BASE + "/api/business");
  const data = await res.json();
  if (data.product_name) {
    document.title = `${data.product_name} — Dashboard`;
    const brand = document.getElementById("productName");
    if (brand) brand.textContent = data.product_name;
  }
  const form = $("#settingsForm");
  for (const key of ["name", "industry", "assistant_name", "assistant_image_url", "website_url", "scheduling_link", "handoff_webhook_url", "handoff_email", "flow_script", "accent_color", "monthly_message_limit", "rot_aging_minutes", "rot_rotting_minutes", "knowledge_source", "greeting", "bubble_teaser_text", "disclosure_text"]) {
    if (form.elements[key]) form.elements[key].value = data[key] ?? "";
  }
  const nameHeader = document.getElementById("businessNameHeader");
  if (nameHeader) nameHeader.textContent = data.name || "(unnamed business)";
  const industryBadge = document.getElementById("industryBadge");
  if (industryBadge) {
    if (data.industry) {
      industryBadge.textContent = data.industry;
      industryBadge.hidden = false;
    } else {
      industryBadge.hidden = true;
    }
  }
  const suggestedQuestions = Array.isArray(data.demo_suggested_questions) ? data.demo_suggested_questions : [];
  [1, 2, 3].forEach((n) => {
    if (form.elements[`demo_suggested_questions_${n}`]) {
      form.elements[`demo_suggested_questions_${n}`].value = suggestedQuestions[n - 1] || "";
    }
  });
  const kbBadge = document.getElementById("knowledgeSourceBadge");
  if (kbBadge) {
    if (data.knowledge_source) {
      kbBadge.textContent = data.knowledge_source;
      kbBadge.hidden = false;
    } else {
      kbBadge.hidden = true;
    }
  }
  const lastCrawledEl = document.getElementById("lastCrawledAt");
  if (lastCrawledEl) lastCrawledEl.textContent = data.last_crawled_at ? fmtDate(data.last_crawled_at) : "never";
  ROT_CONFIG.agingMinutes = data.rot_aging_minutes ?? 1440;
  ROT_CONFIG.rottingMinutes = data.rot_rotting_minutes ?? 4320;
  form.elements["pipeline_enabled"].checked = !!data.pipeline_enabled;
  PIPELINE_ENABLED = !!data.pipeline_enabled;
  $("#pipelineTab").hidden = !PIPELINE_ENABLED;
  $("#intelligenceCard").hidden = !data.priority_routing_enabled;
  const apiBase = window.location.origin;
  const displayName = data.assistant_name || data.name || "Chat with us";
  const greeting = data.greeting || greetingPreset(data.assistant_name, data.name);
  $("#embedSnippet").textContent =
    `<script\n` +
    `  src="${apiBase}/widget/widget.js"\n` +
    `  data-api-base="${apiBase}"\n` +
    `  data-business-name="${displayName.replace(/"/g, "&quot;")}"\n` +
    `  data-color="${data.accent_color || "#4f46e5"}"\n` +
    `  data-greeting="${greeting.replace(/"/g, "&quot;")}"\n` +
    (data.assistant_image_url ? `  data-avatar-url="${data.assistant_image_url.replace(/"/g, "&quot;")}"\n` : "") +
    (data.demo_suggested_questions && data.demo_suggested_questions.length
      ? `  data-suggested-questions="${JSON.stringify(data.demo_suggested_questions).replace(/"/g, "&quot;")}"\n`
      : "") +
    `  defer\n` +
    `><\/script>`;

  const used = data.messages_used_this_month ?? 0;
  const limit = data.monthly_message_limit ?? 0;
  const usageEl = $("#usageStatus");
  if (limit > 0) {
    const pct = Math.min(100, Math.round((used / limit) * 100));
    usageEl.textContent = `${used} / ${limit} messages used this month (${pct}%)${used >= limit ? " — at capacity, new chats are handing off to the team." : ""}`;
  } else {
    usageEl.textContent = `${used} messages used this month (no limit set).`;
  }
  initFieldUndo(form);
}

// Snapshots every field's current value as its "last saved" baseline and gives it an
// inline Undo control that reverts just that field — the bottom Save Settings button is
// still what actually confirms/persists changes, this just protects against losing a
// half-edited flow_script or disclosure_text to an accidental keystroke before you hit it.
function initFieldUndo(form) {
  form.querySelectorAll("input[name], textarea[name], select[name]").forEach((el) => {
    const readValue = () => (el.type === "checkbox" ? String(el.checked) : el.value);
    el.dataset.savedValue = readValue();
    let undoBtn = el.nextElementSibling;
    if (!undoBtn || !undoBtn.classList.contains("field-undo")) {
      undoBtn = document.createElement("button");
      undoBtn.type = "button";
      undoBtn.className = "field-undo";
      undoBtn.textContent = "Undo change";
      el.insertAdjacentElement("afterend", undoBtn);
      const refreshDirty = () => {
        undoBtn.classList.toggle("dirty", readValue() !== el.dataset.savedValue);
      };
      el.addEventListener("input", refreshDirty);
      el.addEventListener("change", refreshDirty);
      undoBtn.addEventListener("click", () => {
        if (el.type === "checkbox") {
          el.checked = el.dataset.savedValue === "true";
        } else {
          el.value = el.dataset.savedValue;
        }
        undoBtn.classList.remove("dirty");
      });
    } else {
      undoBtn.classList.remove("dirty");
    }
  });
}

$("#settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = $("#saveStatus");
  status.textContent = "Saving…";

  // Merge form fields on top of a fresh copy of the current record, rather than
  // sending only what's in the form. Fields with no form control at all — e.g.
  // priority_routing_enabled, which is set by the launcher's tier system, not
  // editable here — would otherwise be absent from the payload and silently
  // reset to the backend model's default on every save.
  const currentRes = await fetch(API_BASE + "/api/business");
  const current = await currentRes.json();

  const formPayload = Object.fromEntries(new FormData(e.target).entries());
  formPayload.pipeline_enabled = e.target.elements["pipeline_enabled"].checked;
  formPayload.demo_suggested_questions = [
    formPayload.demo_suggested_questions_1,
    formPayload.demo_suggested_questions_2,
    formPayload.demo_suggested_questions_3,
  ].map((q) => (q || "").trim()).filter(Boolean);
  delete formPayload.demo_suggested_questions_1;
  delete formPayload.demo_suggested_questions_2;
  delete formPayload.demo_suggested_questions_3;

  const payload = { ...current, ...formPayload };
  if (Number(payload.rot_rotting_minutes) < Number(payload.rot_aging_minutes)) {
    status.textContent = "Rotting threshold must be equal to or later than the aging threshold";
    return;
  }
  const res = await fetch(API_BASE + "/api/business", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    const now = new Date().toLocaleTimeString();
    status.textContent = `All settings saved ✓ at ${now}`;
    status.style.color = "#15803d";
  } else {
    status.textContent = "Error saving — nothing was changed, please try again";
    status.style.color = "#c0392b";
  }
  loadBusiness();
  // Deliberately not auto-cleared — a save confirmation that vanishes in a couple
  // seconds is easy to miss and leaves you unsure whether it actually worked.
  // This stays until the next save attempt overwrites it.
});

$("#crawlBtn").addEventListener("click", async () => {
  const status = $("#crawlStatus");
  status.textContent = "Starting crawl…";
  const res = await fetch(API_BASE + "/api/knowledge/crawl", { method: "POST" });
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
  const res = await fetch(API_BASE + "/api/knowledge/documents", {
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
  const res = await fetch(API_BASE + "/api/knowledge/sources");
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
      await fetch(`${API_BASE}/api/knowledge/sources/${btn.dataset.id}`, { method: "DELETE" });
      loadSources();
    });
  });
}

$("#faqForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  const status = $("#faqStatus");
  status.textContent = "Saving…";
  const res = await fetch(API_BASE + "/api/knowledge/faqs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  status.textContent = res.ok ? "Added ✓" : "Error adding FAQ";
  if (res.ok) e.target.reset();
  loadFaqs();
  loadComposition();
  setTimeout(() => (status.textContent = ""), 2500);
});

async function loadUnresolvedKnowledge() {
  const res = await fetch(API_BASE + "/api/leads");
  const rows = await res.json();
  const open = rows.filter((r) => r.intent === "unresolved_question" && (r.status || "new") !== "done");
  const card = $("#unresolvedKnowledgeCard");
  if (open.length === 0) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  $("#unresolvedKnowledgeList").innerHTML = open
    .map(
      (r) => `
      <li data-id="${r.id}">
        <span class="unresolved-note">${esc(r.notes || "(no detail captured)")}</span>
        <span class="unresolved-actions">
          <button class="add-as-faq" data-id="${r.id}" data-note="${esc(r.notes || "")}">Add as FAQ</button>
          <button class="mark-resolved" data-id="${r.id}">Mark resolved</button>
        </span>
      </li>`
    )
    .join("");

  $("#unresolvedKnowledgeList")
    .querySelectorAll("button.add-as-faq")
    .forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelector('#faqForm [name="question"]').value = btn.dataset.note;
        document.querySelector('#faqForm [name="answer"]').focus();
        document.querySelector("#faqForm").scrollIntoView({ behavior: "smooth", block: "center" });
      });
    });

  $("#unresolvedKnowledgeList")
    .querySelectorAll("button.mark-resolved")
    .forEach((btn) => {
      btn.addEventListener("click", async () => {
        await patchLead(btn.dataset.id, { status: "done" });
        loadUnresolvedKnowledge();
      });
    });
}

async function loadComposition() {
  const res = await fetch(API_BASE + "/api/knowledge/composition");
  const data = await res.json();
  const card = $("#compositionCard");
  if (data.total_rows === 0) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  const pct = Math.round((data.bip_share ?? 0) * 100);
  $("#compositionFill").style.width = `${pct}%`;
  $("#compositionText").textContent =
    `${pct}% from a LeadGuard BIP (${data.total_from_bip} of ${data.total_rows} rows) — ` +
    `${data.facts_from_bip}/${data.facts_total} facts, ${data.faqs_from_bip}/${data.faqs_total} FAQs.`;
}

async function loadFaqs() {
  const res = await fetch(API_BASE + "/api/knowledge/faqs");
  const rows = await res.json();
  const tbody = $("#faqsTable tbody");
  tbody.innerHTML =
    rows
      .map(
        (f) =>
          `<tr data-id="${f.id}"><td>${esc(f.question)}</td><td>${esc(f.answer).slice(0, 100)}${f.answer.length > 100 ? "…" : ""}</td><td>${esc(f.category)}</td><td class="row-actions"><button class="edit" data-id="${f.id}">Edit</button><button class="delete" data-id="${f.id}" data-kind="faq">Remove</button></td></tr>`
      )
      .join("") || `<tr><td colspan="4" class="muted">No FAQs added yet.</td></tr>`;
  tbody.querySelectorAll("button.delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`${API_BASE}/api/knowledge/faqs/${btn.dataset.id}`, { method: "DELETE" });
      loadFaqs();
      loadComposition();
    });
  });
  tbody.querySelectorAll("button.edit").forEach((btn) => {
    btn.addEventListener("click", () => {
      const faq = rows.find((r) => String(r.id) === btn.dataset.id);
      if (faq) startFaqEdit(btn.closest("tr"), faq);
    });
  });
}

function startFaqEdit(tr, faq) {
  tr.innerHTML = `
    <td><input class="edit-question" value="${esc(faq.question)}" /></td>
    <td><textarea class="edit-answer" rows="3">${esc(faq.answer)}</textarea></td>
    <td><input class="edit-category" value="${esc(faq.category || "")}" /></td>
    <td class="row-actions"><button class="save">Save</button><button class="cancel">Cancel</button></td>
  `;
  tr.querySelector(".cancel").addEventListener("click", () => loadFaqs());
  tr.querySelector(".save").addEventListener("click", async () => {
    const question = tr.querySelector(".edit-question").value.trim();
    const answer = tr.querySelector(".edit-answer").value.trim();
    const category = tr.querySelector(".edit-category").value.trim();
    if (!question || !answer) return;
    await fetch(`${API_BASE}/api/knowledge/faqs/${faq.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, answer, category, priority: faq.priority }),
    });
    loadFaqs();
    loadComposition();
  });
}

$("#factForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  const status = $("#factStatus");
  status.textContent = "Saving…";
  const res = await fetch(API_BASE + "/api/knowledge/facts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  status.textContent = res.ok ? "Added ✓" : "Error adding fact";
  if (res.ok) e.target.reset();
  loadFacts();
  loadComposition();
  setTimeout(() => (status.textContent = ""), 2500);
});

async function loadFacts() {
  const res = await fetch(API_BASE + "/api/knowledge/facts");
  const rows = await res.json();
  const tbody = $("#factsTable tbody");
  tbody.innerHTML =
    rows
      .map(
        (f) =>
          `<tr data-id="${f.id}"><td>${esc(f.label)}</td><td>${esc(f.value)}</td><td class="row-actions"><button class="edit" data-id="${f.id}">Edit</button><button class="delete" data-id="${f.id}" data-kind="fact">Remove</button></td></tr>`
      )
      .join("") || `<tr><td colspan="3" class="muted">No facts added yet.</td></tr>`;
  tbody.querySelectorAll("button.delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`${API_BASE}/api/knowledge/facts/${btn.dataset.id}`, { method: "DELETE" });
      loadFacts();
      loadComposition();
    });
  });
  tbody.querySelectorAll("button.edit").forEach((btn) => {
    btn.addEventListener("click", () => {
      const fact = rows.find((r) => String(r.id) === btn.dataset.id);
      if (fact) startFactEdit(btn.closest("tr"), fact);
    });
  });
}

function startFactEdit(tr, fact) {
  tr.innerHTML = `
    <td><input class="edit-label" value="${esc(fact.label)}" /></td>
    <td><input class="edit-value" value="${esc(fact.value)}" /></td>
    <td class="row-actions"><button class="save">Save</button><button class="cancel">Cancel</button></td>
  `;
  tr.querySelector(".cancel").addEventListener("click", () => loadFacts());
  tr.querySelector(".save").addEventListener("click", async () => {
    const label = tr.querySelector(".edit-label").value.trim();
    const value = tr.querySelector(".edit-value").value.trim();
    if (!label || !value) return;
    await fetch(`${API_BASE}/api/knowledge/facts/${fact.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, value }),
    });
    loadFacts();
    loadComposition();
  });
}

async function loadFaqSchema() {
  const res = await fetch(API_BASE + "/api/seo/faq-schema");
  const schema = await res.json();
  const el = $("#faqSchemaSnippet");
  if (!schema.mainEntity || schema.mainEntity.length === 0) {
    el.textContent = "Add at least one FAQ above to generate this.";
    return;
  }
  el.textContent = `<script type="application/ld+json">\n${JSON.stringify(schema, null, 2)}\n<\/script>`;
}

$("#checkCrawlersBtn").addEventListener("click", async () => {
  const btn = $("#checkCrawlersBtn");
  const tbody = $("#crawlerTable tbody");
  btn.disabled = true;
  btn.textContent = "Checking…";
  tbody.innerHTML = `<tr><td colspan="3" class="muted">Checking robots.txt…</td></tr>`;

  const res = await fetch(API_BASE + "/api/seo/ai-crawler-access");
  const data = await res.json();
  btn.disabled = false;
  btn.textContent = "Check Now";

  if (!data.checked) {
    tbody.innerHTML = `<tr><td colspan="3" class="muted">${esc(data.message)}</td></tr>`;
    return;
  }
  tbody.innerHTML = data.results
    .map(
      (r) =>
        `<tr><td>${esc(r.bot)}</td><td>${esc(r.description)}</td><td>${r.allowed ? "✅ Allowed" : "🚫 Blocked"}</td></tr>`
    )
    .join("");
});

async function loadUsage() {
  const res = await fetch(API_BASE + "/api/usage/summary");
  const d = await res.json();

  const stats = [
    { label: "Messages this month", value: d.messages_used_this_month },
    { label: "Avg response time", value: d.avg_latency_ms ? (d.avg_latency_ms / 1000).toFixed(1) + "s" : "—" },
    { label: "Input tokens", value: d.total_input_tokens.toLocaleString() },
    { label: "Output tokens", value: d.total_output_tokens.toLocaleString() },
  ];
  $("#usageStats").innerHTML = stats
    .map((s) => `<div class="stat-tile"><div class="stat-value">${s.value}</div><div class="stat-label">${s.label}</div></div>`)
    .join("");

  const coverage = [
    { label: "FAQs", count: d.faq_count, emptyMsg: "No FAQs added yet — common questions will fall back to general search." },
    { label: "Business Facts", count: d.facts_count, emptyMsg: "No quick facts added yet — things like hours/phone rely on the site scan or script." },
    { label: "Knowledge sources", count: d.source_count, emptyMsg: "No site scan or manual documents yet — run a crawl in the Knowledge tab." },
  ];
  $("#coverageList").innerHTML = coverage
    .map(
      (c) =>
        `<li class="${c.count > 0 ? "coverage-ok" : "coverage-empty"}">${c.count > 0 ? "✅" : "⚠️"} ${c.label}: ${c.count}${c.count === 0 ? ` — <span class="muted">${c.emptyMsg}</span>` : ""}</li>`
    )
    .join("");

  const tbody = $("#gapsTable tbody");
  tbody.innerHTML =
    d.knowledge_gaps_this_month
      .map((g) => `<tr><td>${fmtDate(g.created_at)}</td><td>${esc(g.notes)}</td></tr>`)
      .join("") || `<tr><td colspan="2" class="muted">No unanswered questions logged this month.</td></tr>`;
}

async function loadDashboard() {
  const [usageRes, leadsRes, businessRes] = await Promise.all([
    fetch(API_BASE + "/api/usage/summary"),
    fetch(API_BASE + "/api/leads"),
    fetch(API_BASE + "/api/business"),
  ]);
  const d = await usageRes.json();
  const leads = await leadsRes.json();
  const business = await businessRes.json();

  const stats = [
    { label: "Messages this month", value: d.messages_used_this_month },
    { label: "Avg response time", value: d.avg_latency_ms ? (d.avg_latency_ms / 1000).toFixed(1) + "s" : "—" },
    { label: "Open leads", value: leads.filter((r) => (r.status || "new") !== "done").length },
  ];
  $("#dashStats").innerHTML = stats
    .map((s) => `<div class="stat-tile"><div class="stat-value">${s.value}</div><div class="stat-label">${s.label}</div></div>`)
    .join("");

  const counts = { new: 0, claimed: 0, done: 0 };
  leads.forEach((r) => (counts[r.status || "new"] = (counts[r.status || "new"] || 0) + 1));
  $("#dashLeadsSummary").innerHTML = Object.entries(STATUS_LABELS)
    .map(([val, label]) => `<div class="mini-stat"><div class="mini-value">${counts[val] || 0}</div><div class="mini-label">${label}</div></div>`)
    .join("");

  const recent = [...leads].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)).slice(0, 5);
  $("#dashRecentLeads").innerHTML =
    recent
      .map(
        (r) =>
          `<li><span class="dash-recent-name">${esc(r.name) || "<em>No name</em>"} — ${INTENT_LABELS[r.intent] || esc(r.intent) || ""}</span><span class="dash-recent-date">${fmtDate(r.created_at)}</span></li>`
      )
      .join("") || `<li class="muted">No leads captured yet.</li>`;

  const coverage = [
    { label: "FAQs", count: d.faq_count },
    { label: "Business Facts", count: d.facts_count },
    { label: "Knowledge sources", count: d.source_count },
  ];
  $("#dashCoverageList").innerHTML = coverage
    .map((c) => `<li class="${c.count > 0 ? "coverage-ok" : "coverage-empty"}">${c.count > 0 ? "✅" : "⚠️"} ${c.label}: ${c.count}</li>`)
    .join("");

  // Pipeline add-on summary: only shown once a business has it enabled.
  const pipelineCard = $("#dashPipelineCard");
  if (business.pipeline_enabled) {
    pipelineCard.hidden = false;
    const cardsRes = await fetch(API_BASE + "/api/pipeline/cards");
    const pipelineCards = await cardsRes.json();
    $("#dashPipelineSummary").textContent = `${pipelineCards.length} card${pipelineCards.length === 1 ? "" : "s"} in the pipeline.`;
  } else {
    pipelineCard.hidden = true;
  }

  // Prospect demo engagement (docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md, Phase 2). Only
  // real client instances never accumulate any demo_events, so the card stays hidden for
  // them automatically — no separate "is this a demo" flag needed on the business record.
  const demoCard = $("#dashDemoEngagementCard");
  try {
    const demoRes = await fetch(API_BASE + "/api/demo/events/summary");
    const demo = await demoRes.json();
    if (demo.has_any_events) {
      demoCard.hidden = false;
      const lastActivity = demo.last_activity_at ? timeAgo(demo.last_activity_at) : "—";
      const stats = [
        ["Page opens", demo.total_opens],
        ["Unique sessions", demo.unique_sessions],
        ["Conversations started", demo.conversations_started],
        ["Messages sent", demo.messages_sent],
        ["Suggested-question clicks", demo.suggested_question_clicks],
      ];
      // Only shown once a video/booking-link CTA is actually in play on this demo —
      // most prospects never get one, so a permanent zero row would just be noise.
      if (demo.video_views > 0) {
        stats.push(["Video views", demo.video_views], ["Video completions", demo.video_completions]);
      }
      if (demo.lead_cta_clicks > 0) {
        stats.push(["Booking link clicks", demo.lead_cta_clicks]);
      }
      stats.push(["Last activity", lastActivity]);
      $("#dashDemoStats").innerHTML = stats
        .map(([label, value]) => `<li><span>${label}</span><strong>${value}</strong></li>`).join("");
    } else {
      demoCard.hidden = true;
    }
  } catch (e) {
    demoCard.hidden = true;
  }
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
  capacity_reached: "📈 Cap reached",
};

function showLeadsView(view) {
  document.querySelectorAll("#leadsViewToggle .view-toggle-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.getElementById("leadsListView").hidden = view !== "list";
  document.getElementById("leadsBoard").hidden = view !== "board";
}

function renderLeadsList(rows) {
  const tbody = document.getElementById("leadsListBody");
  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="muted">No leads yet.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((r) => {
    const contact = [r.email, r.phone].filter(Boolean).join(" / ") || "—";
    const status = r.status || "new";
    return `<tr data-id="${r.id}">
      <td>${esc(r.name) || "—"}</td>
      <td>${esc(contact)}</td>
      <td>${esc(INTENT_LABELS[r.intent] || r.intent || "")}</td>
      <td>${esc(STATUS_LABELS[status] || status)}</td>
      <td><input class="claimed-by-input" value="${esc(r.claimed_by) || ""}" placeholder="Unclaimed" /></td>
      <td>${fmtDate(r.created_at)}</td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll(".claimed-by-input").forEach((input) => {
    const priorName = input.value;
    input.addEventListener("change", async () => {
      const row = input.closest("tr");
      const id = row.dataset.id;
      const r = rows.find((x) => String(x.id) === id);
      const newName = input.value.trim();
      const patch = { claimed_by: newName };
      if (!priorName && newName) {
        patch.status = "claimed";
      } else if (priorName && newName && priorName !== newName) {
        const stamp = new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" });
        const line = `— Reassigned from ${priorName} to ${newName} (${stamp}) —`;
        patch.notes = r?.notes ? `${r.notes}\n${line}` : line;
      }
      await patchLead(id, patch);
      loadLeads();
    });
  });
}

async function loadLeads() {
  const res = await fetch(API_BASE + "/api/leads");
  const allRows = await res.json();
  // Premium intelligence (priority/routing/summary) is optional — most businesses don't have
  // it enabled, so this 404s or returns {} for them and cards just render without a badge.
  const intelMap = await fetch(API_BASE + "/api/intelligence/leads")
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));

  const unresolvedOpen = allRows.filter((r) => r.intent === "unresolved_question" && (r.status || "new") !== "done");
  const badge = document.getElementById("unresolvedBadge");
  if (badge) {
    badge.textContent = unresolvedOpen.length;
    badge.hidden = unresolvedOpen.length === 0;
  }
  const unresolvedCard = document.getElementById("unresolvedCard");
  const hasAnyUnresolved = allRows.some((r) => r.intent === "unresolved_question");
  if (unresolvedCard) unresolvedCard.hidden = !hasAnyUnresolved;

  const filterOn = document.getElementById("unresolvedFilter")?.checked;
  const rows = filterOn ? allRows.filter((r) => r.intent === "unresolved_question") : allRows;

  renderLeadsList(rows);

  for (const status of ["new", "claimed", "done"]) {
    const col = document.querySelector(`.board-col-cards[data-status="${status}"]`);
    const inCol = rows.filter((r) => (r.status || "new") === status);
    $(`#count-${status}`).textContent = inCol.length;
    col.innerHTML = inCol.map((r) => cardHtml(r, intelMap[String(r.id)])).join("") || `<p class="muted board-empty">Nothing here.</p>`;
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
    card.querySelector(".reassign-btn")?.addEventListener("click", () => {
      const prompt = card.querySelector(".claim-prompt");
      prompt.hidden = false;
      card.querySelector(".claimed-by").hidden = true;
      card.querySelector(".reassign-btn").hidden = true;
      const input = card.querySelector(".claim-input");
      input.value = "";
      input.placeholder = "New name";
      input.focus();
    });

    card.querySelector(".claim-confirm")?.addEventListener("click", async () => {
      const input = card.querySelector(".claim-input");
      const newName = input.value.trim();
      if (!newName) return;
      const priorName = r.claimed_by;
      const patch = { claimed_by: newName };
      if (!priorName) {
        patch.status = "claimed";
      } else if (priorName !== newName) {
        // Reassignment, not a first claim — leave a plain-text trail rather than a new
        // column, per Larry's call: "something easy" beats a schema change for this.
        const stamp = new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" });
        const line = `— Reassigned from ${priorName} to ${newName} (${stamp}) —`;
        patch.notes = r.notes ? `${r.notes}\n${line}` : line;
      }
      await patchLead(card.dataset.id, patch);
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

    card.querySelector(".promote-btn")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      const res = await fetch(`${API_BASE}/api/leads/${card.dataset.id}/promote`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Could not move this lead to Pipeline.");
        return;
      }
      loadLeads();
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
const DISCOVERY_PHASE_LABELS = {
  fact_finding: "Fact finding",
  price_shopping: "Price shopping",
  comparing_providers: "Comparing providers",
  evaluating_fit: "Evaluating fit",
  ready_to_book: "Ready to book",
};
const OUTCOME_LABELS = {
  booked: "✅ Booked",
  not_interested: "🚫 Not interested",
  no_response: "🔇 No response",
  duplicate: "♻️ Duplicate",
  spam: "🗑️ Spam",
  other: "❔ Other",
};

function rotPhase(createdAt) {
  const ageMs = Date.now() - new Date(createdAt).getTime();
  if (ageMs >= ROT_CONFIG.rottingMinutes * 60000) return { level: "rotting", label: "Needs attention" };
  if (ageMs >= ROT_CONFIG.agingMinutes * 60000) return { level: "aging", label: "Getting stale" };
  return { level: "fresh", label: "New" };
}

function cardHtml(r, intel) {
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
  const priorityHtml = intel
    ? `<div class="lead-card-priority ${esc((intel.priority_level || "p4").toLowerCase())}" title="${esc((intel.signals || []).join(", "))}">${esc(intel.priority_level)} · ${esc(intel.priority_score)}${
        intel.routing_destination ? ` <span class="priority-dest">→ ${esc(intel.routing_destination)}</span>` : ""
      }</div>`
    : "";
  return `
    <div class="lead-card" draggable="true" data-id="${r.id}">
      <div class="lead-card-intent">${INTENT_LABELS[r.intent] || esc(r.intent)}</div>
      ${priorityHtml}
      ${r.discovery_phase ? `<div class="lead-card-phase">${esc(DISCOVERY_PHASE_LABELS[r.discovery_phase] || r.discovery_phase)}</div>` : ""}
      <div class="lead-card-name">${
        !r.claimed_by
          ? (() => {
              const rot = rotPhase(r.created_at);
              return `<span class="rot-dot ${rot.level}" title="${rot.label} — untouched since ${fmtDate(r.created_at)}"></span>`;
            })()
          : ""
      }${esc(r.name) || "<em>No name given</em>"}</div>
      ${contact ? `<div class="lead-card-contact">${esc(contact)}</div>` : ""}
      ${intel && intel.intelligent_summary ? `<div class="lead-card-summary">${esc(intel.intelligent_summary)}</div>` : ""}
      <label class="card-field-label">Notes</label>
      <textarea class="card-notes" rows="2">${esc(r.notes)}</textarea>
      <label class="card-field-label">Good to know</label>
      <textarea class="card-good-to-know" rows="2" placeholder="Standing context, e.g. referred by X, handle gently...">${esc(r.good_to_know)}</textarea>
      ${status === "done" ? `<select class="outcome-select">${outcomeOptions}</select>` : ""}
      <div class="lead-card-footer">
        <span class="lead-card-date" title="${fmtDate(r.created_at)}">${timeAgo(r.created_at)}</span>
        <select class="status-select">${statusOptions}</select>
      </div>
      <div class="lead-card-claim">
        ${
          r.claimed_by
            ? `<span class="claimed-by">👤 ${esc(r.claimed_by)}</span>
               <button type="button" class="reassign-btn" title="Reassign to someone else">Reassign</button>`
            : `<button type="button" class="claim-btn">Claim</button>`
        }
        <span class="claim-prompt" hidden>
          <input class="claim-input" type="text" placeholder="Name" />
          <button type="button" class="claim-confirm">OK</button>
        </span>
      </div>
      ${status === "claimed" && PIPELINE_ENABLED ? `<button class="promote-btn" data-id="${r.id}">Move to Pipeline →</button>` : ""}
    </div>`;
}

async function patchLead(id, body) {
  await fetch(`${API_BASE}/api/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------- Pipeline (paid add-on)

const pipelineExpanded = {};

async function loadPipeline() {
  const [stagesRes, cardsRes] = await Promise.all([fetch(API_BASE + "/api/pipeline/stages"), fetch(API_BASE + "/api/pipeline/cards")]);
  const stages = await stagesRes.json();
  const cards = await cardsRes.json();
  renderStageConfig(stages);
  renderPipelineBoard(stages, cards);
}

function renderStageConfig(stages) {
  const list = $("#pipelineStageList");
  list.innerHTML = stages.map((s) => `
    <div class="stage-row" data-id="${s.id}">
      <span class="stage-label">${esc(s.label)}</span>
      <label class="stage-flag"><input type="checkbox" class="stage-notes-toggle" ${s.notes_enabled ? "checked" : ""} /> Outcome notes</label>
      <label class="stage-flag"><input type="radio" name="won-stage" class="stage-won-toggle" ${s.is_won ? "checked" : ""} /> Won stage</label>
      <button type="button" class="stage-delete" data-id="${s.id}">Remove</button>
    </div>
    ${s.is_won ? `
      <div class="stage-dropdown-opts" data-stage-id="${s.id}">
        <label class="card-field-label">Dropdown options (shown on Won cards)</label><br/>
        ${s.dropdown_options.map((o) => `<input type="text" value="${esc(o.label)}" readonly data-option-id="${o.id}" />`).join("")}
        <form class="add-option-form" data-stage-id="${s.id}" style="display:inline;">
          <input type="text" name="label" placeholder="New option" style="width:140px;" required />
          <button type="submit" class="stage-add-option-btn">Add</button>
        </form>
      </div>` : ""}
  `).join("") || `<p class="muted">No stages configured yet — add one above.</p>`;

  list.querySelectorAll(".stage-notes-toggle").forEach((cb) => {
    cb.addEventListener("change", async () => {
      const id = cb.closest(".stage-row").dataset.id;
      await patchStage(id, { notes_enabled: cb.checked });
      loadPipeline();
    });
  });
  list.querySelectorAll(".stage-won-toggle").forEach((radio) => {
    radio.addEventListener("change", async () => {
      const id = radio.closest(".stage-row").dataset.id;
      const res = await patchStage(id, { is_won: true });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Could not mark this stage as Won.");
      }
      loadPipeline();
    });
  });
  list.querySelectorAll(".stage-delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Remove this stage? Any cards in it will be removed too.")) return;
      await fetch(`${API_BASE}/api/pipeline/stages/${btn.dataset.id}`, { method: "DELETE" });
      loadPipeline();
    });
  });
  list.querySelectorAll(".add-option-form").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const label = form.elements["label"].value.trim();
      if (!label) return;
      await fetch(`${API_BASE}/api/pipeline/stages/${form.dataset.stageId}/dropdown-options`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
      });
      loadPipeline();
    });
  });
}

async function patchStage(id, body) {
  return fetch(`${API_BASE}/api/pipeline/stages/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

$("#pipelineStageForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const status = $("#pipelineStageStatus");
  const payload = {
    label: form.elements["label"].value.trim(),
    notes_enabled: form.elements["notes_enabled"].checked,
    is_won: form.elements["is_won"].checked,
  };
  if (!payload.label) return;
  const res = await fetch(API_BASE + "/api/pipeline/stages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    status.textContent = err.detail || "Could not add stage";
  } else {
    status.textContent = "Added ✓";
    form.reset();
  }
  loadPipeline();
  setTimeout(() => (status.textContent = ""), 2500);
});

function renderPipelineBoard(stages, cards) {
  const board = $("#pipelineBoard");
  board.innerHTML = stages.map((stage) => {
    const inStage = cards.filter((c) => c.stage_id === stage.id);
    return `
      <div class="pipe-col" data-stage-id="${stage.id}">
        <div class="pipe-col-head">
          <h3>${esc(stage.label)} <span class="count">${inStage.length}</span></h3>
          <button type="button" class="pipe-eye" data-toggle-col="${stage.id}" title="Expand/collapse all in this column">&#128065;</button>
        </div>
        <div class="pipe-cards" data-stage-id="${stage.id}">
          ${inStage.map((c) => pipelineCardHtml(c, stage)).join("") || `<p class="muted board-empty">Nothing here.</p>`}
        </div>
      </div>`;
  }).join("") || `<p class="muted">Add a stage above to start your pipeline board.</p>`;

  board.querySelectorAll(".pipe-card").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (["SELECT", "TEXTAREA", "INPUT", "BUTTON"].includes(e.target.tagName)) return;
      const id = Number(el.dataset.id);
      pipelineExpanded[id] = !pipelineExpanded[id];
      renderPipelineBoard(stages, cards);
    });

    el.querySelector(".pipe-card-claim-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      el.querySelector(".pipe-claim-prompt").hidden = false;
      el.querySelector(".pipe-card-claim-btn").hidden = true;
      el.querySelector(".pipe-claim-input").focus();
    });
    el.querySelector(".pipe-claim-confirm")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      const input = el.querySelector(".pipe-claim-input");
      if (!input.value.trim()) return;
      await patchCard(el.dataset.id, { claimed_by: input.value.trim() });
      loadPipeline();
    });
    el.querySelector(".pipe-claim-input")?.addEventListener("click", (e) => e.stopPropagation());
    el.querySelector(".pipe-claim-input")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") el.querySelector(".pipe-claim-confirm").click();
    });

    el.querySelector(".pipe-notes")?.addEventListener("blur", async (e) => {
      await patchCard(el.dataset.id, { notes: e.target.value });
    });
    el.querySelector(".pipe-outcome-notes")?.addEventListener("blur", async (e) => {
      await patchCard(el.dataset.id, { outcome_notes: e.target.value });
    });
    el.querySelector(".pipe-dropdown")?.addEventListener("change", async (e) => {
      await patchCard(el.dataset.id, { chosen_option_id: Number(e.target.value) });
    });

    el.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", el.dataset.id);
      el.classList.add("dragging");
    });
    el.addEventListener("dragend", () => el.classList.remove("dragging"));
  });

  board.querySelectorAll("[data-toggle-col]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const stageId = Number(btn.dataset.toggleCol);
      const idsInCol = cards.filter((c) => c.stage_id === stageId).map((c) => c.id);
      const anyCollapsed = idsInCol.some((id) => !pipelineExpanded[id]);
      idsInCol.forEach((id) => (pipelineExpanded[id] = anyCollapsed));
      renderPipelineBoard(stages, cards);
    });
  });

  board.querySelectorAll(".pipe-cards").forEach((col) => {
    col.addEventListener("dragover", (e) => e.preventDefault());
    col.addEventListener("drop", async (e) => {
      e.preventDefault();
      const id = e.dataTransfer.getData("text/plain");
      await patchCard(id, { stage_id: Number(col.dataset.stageId) });
      loadPipeline();
    });
  });
}

function pipelineCardHtml(c, stage) {
  const isExpanded = !!pipelineExpanded[c.id];
  const dropdownOptions = stage.dropdown_options
    .map((o) => `<option value="${o.id}" ${o.id === c.chosen_option_id ? "selected" : ""}>${esc(o.label)}</option>`)
    .join("");
  return `
    <div class="pipe-card draggable ${isExpanded ? "expanded" : ""}" draggable="true" data-id="${c.id}">
      <div class="pipe-card-collapsed-row">
        <span class="pipe-card-name">${esc(c.name) || "<em>No name</em>"}</span>
        ${
          c.claimed_by
            ? `<span class="claimed-by">👤 ${esc(c.claimed_by)}</span>`
            : `<button class="pipe-card-claim-btn">Claim</button>
               <span class="pipe-claim-prompt" hidden>
                 <input class="pipe-claim-input" type="text" placeholder="Your name" />
                 <button class="pipe-claim-confirm">OK</button>
               </span>`
        }
      </div>
      <div class="pipe-card-phone">${esc(c.phone || "")}</div>
      <div class="pipe-card-detail">
        ${stage.is_won ? `<div class="pipe-won-tag">Won</div>` : ""}
        <label>Notes</label>
        <textarea class="pipe-notes" rows="2">${esc(c.notes || "")}</textarea>
        ${stage.notes_enabled ? `<label>Outcome notes</label><textarea class="pipe-outcome-notes" rows="2" placeholder="Why won/lost...">${esc(c.outcome_notes || "")}</textarea>` : ""}
        ${stage.is_won ? `<label>Product / service chosen</label><select class="pipe-dropdown"><option value="">Select...</option>${dropdownOptions}</select>` : ""}
      </div>
    </div>`;
}

async function patchCard(id, body) {
  await fetch(`${API_BASE}/api/pipeline/cards/${id}`, {
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

  const res = await fetch(API_BASE + "/api/conversations?" + params.toString());
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
  const res = await fetch(`${API_BASE}/api/conversations/${id}/messages`);
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

function timeAgo(iso) {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

loadBusiness();
loadDashboard();
