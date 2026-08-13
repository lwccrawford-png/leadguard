#!/usr/bin/env python3
"""LeadGuard demo launcher — a local control panel with buttons instead of a
terminal. Run this once (see ops/README.md for auto-start setup), then open
http://localhost:7100 in a browser and never touch Terminal again.

Buttons per client:
  - Start environment (spins up its backend if not already running)
  - Visitor view (opens the widget demo — the personalized sales demo if one
    exists, otherwise the plain widget test page)
  - Client view (opens that instance's dashboard)

Plus a form to generate a brand-new personalized demo for a prospect: give
it their site URL, and pick an existing client's config as a starting
template. This spins up a genuinely independent backend instance for the
prospect (its own port, its own database, its own Settings) seeded from
that template — it does NOT run live against the template's own backend.
That's deliberate: editing a prospect's demo must never mean editing (or
risk corrupting) a real, actively-used client instance like LMTLSS.
"""
import json
import pathlib
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import bip_parser
import outreach_db


class GenerateDemoRequest(BaseModel):
    url: str
    name: str
    client_id: str  # which existing client's config to use as a starting template

OPS_DIR = pathlib.Path(__file__).parent
PROJECT_ROOT = OPS_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
WIDGET_DIR = PROJECT_ROOT / "widget"
CLIENTS_PATH = OPS_DIR / "clients.json"

# Required non-affiliation disclosure (docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md).
DEFAULT_DEMO_DISCLOSURE = (
    "Demonstration created for {name} using publicly available website information — "
    "not currently affiliated with or deployed by {name}."
)
# New prospect demos start with zero suggested questions regardless of vertical (see
# generate_demo() below) — a wrong-industry default caused a live demo to show HVAC
# questions to a personal injury law firm. This HVAC set is kept only as raw content for
# the HVAC category once the question-bank picker (dashboard) is wired up — it must never
# be seeded automatically again.
DEFAULT_DEMO_SUGGESTED_QUESTIONS = [
    "My AC is running but not cooling. What should I check first?",
    "How do I know whether I need a repair or replacement?",
    "Do you offer emergency service or financing options?",
]
# How long a prospect demo link stays live before GET /demo starts showing the
# "no longer available" page. Generating (or regenerating) a demo resets this
# clock — see generate_demo(). Adjust here if 30 days doesn't fit the sales cycle.
DEMO_LINK_LIFETIME_DAYS = 30


def make_slug(name: str, existing_ids: set) -> str:
    """URL-safe slug from a company name — lowercase, hyphen-separated, collision-checked
    against a numeric suffix. See docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md's slug rules."""
    base = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.strip().lower())).strip("-")[:40] or "demo"
    slug = base
    n = 2
    while f"prospect_{slug}" in existing_ids:
        slug = f"{base}-{n}"
        n += 1
    return slug
BIPS_DIR = PROJECT_ROOT / "onboarding" / "bips"

app = FastAPI(title="LeadGuard Demo Launcher")


def load_clients():
    clients = json.loads(CLIENTS_PATH.read_text())
    migrated = False
    for c in clients:
        if "type" not in c:
            c["type"] = "demo" if c["id"].startswith("prospect_") else "client"
            migrated = True
    if migrated:
        save_clients(clients)
    return clients


def save_clients(clients):
    CLIENTS_PATH.write_text(json.dumps(clients, indent=2) + "\n")


def is_running(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://localhost:{port}/api/health", timeout=1)
        return True
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False


def start_client(client: dict):
    if is_running(client["port"]):
        return {"ok": True, "message": f"{client['name']} already running on :{client['port']}"}
    log_path = f"/tmp/leadguard_{client['id']}.log"
    subprocess.Popen(
        ["venv/bin/uvicorn", "app.main:app", "--port", str(client["port"])],
        cwd=str(BACKEND_DIR),
        env={"LEADGUARD_DATA_DIR": client["data_dir"], "PATH": "/usr/bin:/bin:/usr/local/bin"},
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(30):
        time.sleep(0.3)
        if is_running(client["port"]):
            return {"ok": True, "message": f"{client['name']} started on :{client['port']}"}
    return {"ok": False, "message": f"{client['name']} did not start — check {log_path}"}


def stop_client(client: dict) -> dict:
    if not is_running(client["port"]):
        return {"ok": True, "message": f"{client['name']} is already stopped"}
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{client['port']}"], capture_output=True, text=True, timeout=5
        )
        pids = [p for p in result.stdout.split() if p.strip()]
        for pid in pids:
            subprocess.run(["kill", pid], timeout=5)
    except Exception as e:
        return {"ok": False, "message": f"could not stop {client['name']}: {e}"}
    for _ in range(20):
        time.sleep(0.2)
        if not is_running(client["port"]):
            return {"ok": True, "message": f"{client['name']} stopped"}
    return {"ok": False, "message": f"{client['name']} did not stop in time"}


def delete_client_data(client: dict):
    """Best-effort removal of a client's data directory. Refuses to touch anything
    outside BACKEND_DIR — data_dir comes from clients.json, a trusted local file, but
    this stays defensive since the operation is irreversible."""
    data_path = (BACKEND_DIR / client["data_dir"]).resolve()
    try:
        data_path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        return  # outside BACKEND_DIR — refuse to touch it
    if data_path.exists():
        shutil.rmtree(data_path, ignore_errors=True)


def fetch_support_requests(port: int) -> list:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/api/support-requests", timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return []


def fetch_business(port: int) -> dict:
    with urllib.request.urlopen(f"http://localhost:{port}/api/business", timeout=5) as resp:
        return json.loads(resp.read())


def put_business(port: int, payload: dict):
    req = urllib.request.Request(
        f"http://localhost:{port}/api/business",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    urllib.request.urlopen(req, timeout=5)


def post_json(port: int, path: str, payload: dict):
    req = urllib.request.Request(
        f"http://localhost:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=5)


def fetch_composition(port: int) -> dict:
    with urllib.request.urlopen(f"http://localhost:{port}/api/knowledge/composition", timeout=5) as resp:
        return json.loads(resp.read())


def next_free_port(clients: list) -> int:
    used = {c["port"] for c in clients}
    port = 8010
    while port in used:
        port += 1
    return port


def client_card_html(c: dict) -> str:
    running = is_running(c["port"])
    status_html = (
        '<span class="pill pill-up">● running</span>' if running
        else '<span class="pill pill-down">○ stopped</span>'
    )
    visitor_target = c.get("sales_demo") or c.get("widget_demo")
    visitor_href = f"/open/{c['id']}/visitor"
    admin_href = f"http://localhost:{c['port']}/dashboard/"
    client_href = f"http://localhost:{c['port']}/dashboard/?view=client"
    disabled = "" if running else "disabled"
    knowledge_source = ""
    bip_share = None
    if running:
        try:
            knowledge_source = fetch_business(c["port"]).get("knowledge_source", "")
        except Exception:
            pass
        try:
            bip_share = fetch_composition(c["port"]).get("bip_share")
        except Exception:
            pass
    kb_label = knowledge_source or ("Manual" if bip_share is not None else "")
    if bip_share is not None:
        kb_label += f" · {round(bip_share * 100)}% BIP content"
    kb_html = f'<span class="kb-source-pill">{kb_label}</span>' if kb_label else ""
    start_pause_html = (
        f'<button class="btn btn-pause" data-client="{c["id"]}" onclick="stopClient(\'{c["id"]}\', \'{c["name"]}\')">⏸ Pause</button>'
        if running else
        f'<button class="btn btn-start" data-client="{c["id"]}" onclick="startClient(\'{c["id"]}\')">▶ Start environment</button>'
    )
    promote_html = (
        f'<button class="btn btn-promote" onclick="promoteClient(\'{c["id"]}\', \'{c["name"]}\')">⬆ Promote to client</button>'
        if c.get("type") == "demo" else ""
    )
    return f"""
    <div class="card">
      <div class="card-head">
        <h3>{c['name']}</h3>
        {status_html}
      </div>
      <div class="card-actions">
        {start_pause_html}
        <a class="btn btn-visitor {'btn-disabled' if not running else ''}" href="{visitor_href}" target="_blank" {disabled}>🌐 Visitor view</a>
        <a class="btn btn-admin {'btn-disabled' if not running else ''}" href="{admin_href}" target="_blank" {disabled}>🔑 Admin view</a>
        <a class="btn btn-client {'btn-disabled' if not running else ''}" href="{client_href}" target="_blank" {disabled}>🗂 Client view</a>
        {promote_html}
        <button class="btn btn-delete" onclick="deleteClient('{c['id']}', '{c['name']}')">🗑 Delete</button>
      </div>
      <div class="card-meta">port :{c['port']} &middot; {visitor_target or "no demo generated yet"} {kb_html}</div>
    </div>"""


PAGE_CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&family=Schibsted+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

  :root {
    --bg: #f4ecda;
    --surface: #eee1c5;
    --surface-2: #e3d1a8;
    --border: rgba(58, 41, 20, 0.28);
    --border-strong: rgba(58, 41, 20, 0.5);
    --text: #241a0e;
    --text-dim: #5b432a;
    --text-faint: #6f5738;
    --accent: #a8461f;
    --accent-soft: rgba(168, 70, 31, 0.14);
    --accent-strong: #c2551f;
    --teal: #2f7d6c;
    --teal-soft: rgba(47, 125, 108, 0.14);
    --gold: #93701f;
    --danger: #a8461f;
    --ok: #2f7d6c;
    --on-accent: #faf3e2;
    --font-display: 'Fraunces', serif;
    --font-body: 'Schibsted Grotesk', sans-serif;
    --font-mono: 'IBM Plex Mono', monospace;
    --radius: 12px;
  }

  * { box-sizing: border-box; }
  body {
    font-family: var(--font-body);
    background:
      radial-gradient(ellipse 900px 500px at 12% -8%, rgba(168,70,31,0.09), transparent 60%),
      radial-gradient(ellipse 700px 500px at 100% 0%, rgba(47,125,108,0.08), transparent 55%),
      repeating-linear-gradient(135deg, rgba(36,26,14,0.02) 0px, rgba(36,26,14,0.02) 1px, transparent 1px, transparent 3px),
      var(--bg);
    margin: 0; padding: 32px; color: var(--text); min-height: 100vh;
  }
  h1 { font-family: var(--font-display); font-weight: 600; font-optical-sizing: auto; margin: 0 0 4px; font-size: 30px; letter-spacing: -0.01em; color: var(--text); animation: rise .5s ease both; }
  .sub { color: var(--text-dim); font-size: 13.5px; margin-bottom: 28px; animation: rise .5s ease both; animation-delay: .05s; }
  .topnav { display: flex; gap: 22px; margin-bottom: 30px; animation: rise .4s ease both; }
  .topnav a { color: var(--text-dim); font-weight: 600; font-size: 12.5px; text-decoration: none; text-transform: uppercase; letter-spacing: .08em; padding-bottom: 4px; border-bottom: 2px solid transparent; transition: color .15s, border-color .15s; }
  .topnav a:hover { color: var(--accent-strong); border-color: var(--accent); }
  .filters { display: flex; gap: 12px; margin-bottom: 18px; }
  .filters select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: var(--surface); color: var(--text); font-family: var(--font-body); }
  table.requests { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
  table.requests th, table.requests td { text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--border); font-size: 13px; vertical-align: top; }
  table.requests th { background: var(--surface-2); color: var(--text-dim); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }
  table.requests tr:last-child td { border-bottom: none; }
  .req-urgency { font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 20px; display: inline-block; }
  .urg-urgent { background: var(--accent-soft); color: var(--accent-strong); }
  .urg-week { background: rgba(147,112,31,0.16); color: var(--gold); }
  .urg-whenever { background: var(--surface-2); color: var(--text-dim); }
  .status-select { font-size: 12px; padding: 5px 8px; border-radius: 7px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); }
  .req-screenshot { max-width: 90px; max-height: 60px; border-radius: 4px; border: 1px solid var(--border); cursor: pointer; }
  .no-rows { color: var(--text-faint); padding: 24px; text-align: center; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; margin-bottom: 36px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset; animation: rise .4s ease both; }
  .card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
  .card-head h3 { font-family: var(--font-display); font-weight: 600; margin: 0; font-size: 17px; }
  .pill { font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 20px; }
  .pill-up { background: var(--teal-soft); color: var(--teal); }
  .pill-down { background: var(--surface-2); color: var(--text-faint); }
  .card-actions { display: flex; flex-direction: column; gap: 8px; }
  .btn { display: block; text-align: center; padding: 9px 12px; border-radius: 8px; font-size: 13px; font-weight: 600; text-decoration: none; border: none; cursor: pointer; font-family: var(--font-body); transition: transform .1s, filter .15s; }
  .btn:hover { filter: brightness(1.12); }
  .btn:active { transform: scale(.97); }
  .btn-start { background: var(--accent); color: var(--on-accent); }
  .btn-visitor { background: var(--teal-soft); color: var(--teal); }
  .btn-admin { background: var(--accent-soft); color: var(--accent-strong); }
  .btn-client { background: var(--surface-2); color: var(--text-dim); }
  .btn-disabled { opacity: .4; pointer-events: none; }
  .card-meta { margin-top: 10px; font-size: 11.5px; color: var(--text-faint); font-family: var(--font-mono); }
  .btn-pause { background: rgba(147,112,31,0.16); color: var(--gold); }
  .btn-promote { background: var(--teal-soft); color: var(--teal); }
  .btn-delete { background: var(--accent-soft); color: var(--accent-strong); }
  .launcher-tabs { display: flex; gap: 4px; margin-bottom: 22px; border-bottom: 1px solid var(--border); }
  .launcher-tab { background: none; border: none; padding: 10px 18px; font-size: 13.5px; font-weight: 600; color: var(--text-faint); cursor: pointer; border-bottom: 2px solid transparent; font-family: var(--font-body); }
  .launcher-tab.active { color: var(--accent-strong); border-bottom-color: var(--accent); }
  .launcher-view { display: none; }
  .launcher-view.active { display: block; }
  .kb-source-pill { display: inline-block; margin-left: 6px; padding: 1px 8px; border-radius: 999px; background: var(--teal-soft); color: var(--teal); font-weight: 600; }
  form.generate { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; max-width: 520px; }
  form.generate label { display: block; font-size: 12px; font-weight: 600; color: var(--text-dim); margin-bottom: 4px; margin-top: 12px; text-transform: uppercase; letter-spacing: .04em; }
  form.generate input, form.generate select { width: 100%; padding: 9px 11px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; background: var(--surface-2); color: var(--text); font-family: var(--font-body); }
  form.generate button { margin-top: 16px; background: var(--accent); color: var(--on-accent); border: none; padding: 10px 18px; border-radius: 8px; font-weight: 700; cursor: pointer; transition: filter .15s; }
  form.generate button:hover { filter: brightness(1.12); }
  #genStatus { margin-top: 10px; font-size: 13px; color: var(--text-dim); }

  @keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes glow-pulse { 0%, 100% { box-shadow: 0 0 0 0 var(--accent-soft); } 50% { box-shadow: 0 0 0 5px transparent; } }
"""

PAGE_JS = """
async function startClient(id) {
  const btn = document.querySelector(`button[data-client="${id}"]`);
  btn.textContent = "Starting...";
  btn.disabled = true;
  const res = await fetch(`/start/${id}`, { method: "POST" });
  const data = await res.json();
  window.location.reload();
}

async function stopClient(id, name) {
  const btn = document.querySelector(`button[data-client="${id}"]`);
  btn.textContent = "Pausing...";
  btn.disabled = true;
  const res = await fetch(`/stop/${id}`, { method: "POST" });
  const data = await res.json();
  if (!data.ok) alert(data.message || `Could not pause ${name}`);
  window.location.reload();
}

async function deleteClient(id, name) {
  if (!confirm(`Permanently delete "${name}"? This removes all its leads, conversations, and knowledge base — it cannot be undone.`)) return;
  const res = await fetch(`/delete/${id}`, { method: "POST" });
  const data = await res.json();
  if (!data.ok) alert(data.message || `Could not delete ${name}`);
  window.location.reload();
}

async function promoteClient(id, name) {
  if (!confirm(`Move "${name}" from Demos to Clients?`)) return;
  const res = await fetch(`/promote/${id}`, { method: "POST" });
  const data = await res.json();
  if (!data.ok) alert(data.message || `Could not promote ${name}`);
  window.location.reload();
}

function showLauncherTab(view) {
  document.querySelectorAll(".launcher-tab").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".launcher-view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
}

document.getElementById("genForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("genStatus");
  status.textContent = "Screenshotting and generating... (10-20s)";
  const payload = Object.fromEntries(new FormData(e.target).entries());
  const res = await fetch("/generate-demo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (data.ok) {
    status.innerHTML = `${data.message}<br/><a href="${data.open_url}" target="_blank" style="font-weight:700;">Open the demo →</a>` +
      ` &nbsp;·&nbsp; <a href="#" onclick="window.location.reload(); return false;">Refresh page to see its card above ↻</a>`;
  } else {
    status.textContent = "Error: " + data.message;
  }
  // Deliberately no auto-reload — it was wiping this message out before there was
  // realistically enough time to click "Open the demo," the same class of "did it
  // even work" confusion the Settings save-confirmation fix addressed earlier.
});
"""


NAV_HTML = """
<div class="topnav">
  <a href="/">Launcher</a>
  <a href="/outreach">Outreach</a>
  <a href="/support-requests">Support requests</a>
  <a href="/bip-import">BIP import</a>
</div>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    clients = load_clients()
    client_cards = "\n".join(client_card_html(c) for c in clients if c.get("type") == "client") \
        or '<p class="sub">No clients yet.</p>'
    demo_cards = "\n".join(client_card_html(c) for c in clients if c.get("type") == "demo") \
        or '<p class="sub">No demos yet — generate one below.</p>'
    options = "\n".join(f'<option value="{c["id"]}">{c["name"]} (:{c["port"]})</option>' for c in clients)
    return f"""<!doctype html>
<html><head><title>LeadGuard Launcher</title><style>{PAGE_CSS}</style></head>
<body>
  {NAV_HTML}
  <h1>LeadGuard Demo Launcher</h1>
  <div class="sub">Local control panel — no terminal needed. Bookmark this page.</div>

  <div class="launcher-tabs">
    <button class="launcher-tab active" data-view="clients" onclick="showLauncherTab('clients')">Clients</button>
    <button class="launcher-tab" data-view="demos" onclick="showLauncherTab('demos')">Demos</button>
  </div>

  <div class="launcher-view active" id="view-clients">
    <div class="grid">{client_cards}</div>
  </div>

  <div class="launcher-view" id="view-demos">
    <div class="grid">{demo_cards}</div>

    <h1 style="font-size:16px;">Create a new personalized demo</h1>
    <div class="sub">Screenshots a prospect's real homepage and drops a live widget on top.</div>
    <form class="generate" id="genForm">
      <label>Prospect's website URL</label>
      <input name="url" type="url" placeholder="https://prospect.com" required />
      <label>Prospect's business name</label>
      <input name="name" type="text" placeholder="Prospect Business" required />
      <label>Start from which client's config as a template?</label>
      <select name="client_id">{options}</select>
      <div class="sub" style="margin-top:4px;">Creates its own independent instance seeded from this — never edits the template client itself.</div>
      <button type="submit">Generate demo</button>
      <div id="genStatus"></div>
    </form>
  </div>

  <script>{PAGE_JS}</script>
</body></html>"""


@app.post("/start/{client_id}")
def start(client_id: str):
    clients = load_clients()
    client = next((c for c in clients if c["id"] == client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    return start_client(client)


@app.post("/stop/{client_id}")
def stop(client_id: str):
    clients = load_clients()
    client = next((c for c in clients if c["id"] == client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    return stop_client(client)


@app.post("/delete/{client_id}")
def delete(client_id: str):
    clients = load_clients()
    client = next((c for c in clients if c["id"] == client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    stop_client(client)
    delete_client_data(client)
    clients = [c for c in clients if c["id"] != client_id]
    save_clients(clients)
    return {"ok": True, "message": f"{client['name']} deleted"}


@app.post("/promote/{client_id}")
def promote(client_id: str):
    clients = load_clients()
    client = next((c for c in clients if c["id"] == client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    client["type"] = "client"
    save_clients(clients)
    # Also retire its public /demo page — a promoted client is a real customer now,
    # not a prospect, and the demo's "not affiliated with X" banner would be actively
    # wrong to keep showing. Fetch-then-put (not a partial payload) so every other
    # setting on this instance survives untouched — see PUT /api/business's full-replace
    # semantics.
    if is_running(client["port"]):
        try:
            current = fetch_business(client["port"])
            current["demo_enabled"] = False
            put_business(client["port"], current)
        except Exception as e:
            return {"ok": True, "message": f"{client['name']} promoted to client status, but could not retire its demo page: {e}"}
    return {"ok": True, "message": f"{client['name']} promoted to client status"}


@app.get("/file")
def serve_file(path: str):
    from fastapi.responses import FileResponse
    target = (PROJECT_ROOT / path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT.resolve()) + "/"):
        return JSONResponse({"ok": False, "message": "invalid path"}, status_code=400)
    if not target.exists():
        return JSONResponse({"ok": False, "message": f"{path} not found"}, status_code=404)
    return FileResponse(target, media_type="text/html")


@app.get("/open/{client_id}/visitor")
def open_visitor(client_id: str):
    from fastapi.responses import RedirectResponse
    clients = load_clients()
    client = next((c for c in clients if c["id"] == client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    target = client.get("sales_demo") or client.get("widget_demo")
    if not target:
        return JSONResponse({"ok": False, "message": "no demo generated for this client yet"}, status_code=404)
    # New-style prospect demos (Phase 1, docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md) are
    # written into the prospect's own data_dir and served by that instance's own GET
    # /demo route — recognizable by the "backend/data_..." path generate-demo writes.
    # Clients that predate that architecture (LMTLSS, Evolve) still carry a path under
    # the shared widget/ directory instead; those never get a GET /demo on their own
    # instance, so redirecting there 404s — serve them via the old /file route instead.
    if target.startswith("widget/"):
        return RedirectResponse(f"/file?path={target}")
    return RedirectResponse(f"http://localhost:{client['port']}/demo")


def _generate_demo(url: str, name: str, client_id: str, industry: str = "") -> dict:
    """Core demo-generation logic, shared by POST /generate-demo (the launcher's own
    form) and the Outreach CRM's create-demo action — see docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md
    and ops/outreach_db.py. Provisions (or regenerates) a prospect's own isolated backend
    instance and writes its personalized demo.html. Returns the same {"ok", "message",
    "open_url"} shape either way."""
    clients = load_clients()
    template = next((c for c in clients if c["id"] == client_id), None)
    if not template:
        return {"ok": False, "message": "unknown template client"}
    if not is_running(template["port"]):
        return {"ok": False, "message": f"{template['name']}'s backend isn't running — start it first, it's only used as a config template"}

    # Reuse the existing prospect if this is the same company by name (case-insensitive) —
    # that's a regeneration, not a collision. Only mint a fresh, collision-checked slug for
    # a genuinely new company name.
    existing_same_name = next(
        (c for c in clients if c.get("type") == "demo" and c["name"].strip().lower() == name.strip().lower()),
        None,
    )
    if existing_same_name:
        prospect_id = existing_same_name["id"]
    else:
        slug = make_slug(name, {c["id"] for c in clients})
        prospect_id = f"prospect_{slug}"

    prospect = next((c for c in clients if c["id"] == prospect_id), None)
    if prospect is None:
        # First time generating for this prospect: provision a genuinely independent
        # backend instance — its own port, its own database — so editing its Settings
        # later can never touch the template client's real, actively-used config.
        prospect = {
            "id": prospect_id,
            "name": name,
            "port": next_free_port(clients),
            "data_dir": f"./data_{prospect_id}",
            "accent_color": template.get("accent_color", "#4f46e5"),
            "widget_demo": None,
            "sales_demo": None,
            "type": "demo",
        }
        started = start_client(prospect)
        if not started["ok"]:
            return started
        try:
            template_business = fetch_business(template["port"])
        except Exception as e:
            return {"ok": False, "message": f"could not read template config: {e}"}
        try:
            put_business(prospect["port"], {
                "name": name,
                "industry": industry,
                "assistant_name": template_business.get("assistant_name", ""),
                "flow_script": template_business.get("flow_script", ""),
                "accent_color": prospect["accent_color"],
                "disclosure_text": DEFAULT_DEMO_DISCLOSURE.format(name=name),
                "demo_suggested_questions": [],
                "demo_expires_at": (datetime.now(timezone.utc) + timedelta(days=DEMO_LINK_LIFETIME_DAYS)).isoformat(),
            })
        except Exception as e:
            return {"ok": False, "message": f"provisioned but could not seed config: {e}"}
        clients.append(prospect)
        save_clients(clients)
    else:
        if not is_running(prospect["port"]):
            started = start_client(prospect)
            if not started["ok"]:
                return started
        # Regenerating an existing prospect's demo means renewed sales engagement —
        # push its expiration clock back out rather than leaving the original one to
        # lapse underneath a demo the prospect just received a fresh link to.
        try:
            current = fetch_business(prospect["port"])
            current["demo_expires_at"] = (
                datetime.now(timezone.utc) + timedelta(days=DEMO_LINK_LIFETIME_DAYS)
            ).isoformat()
            put_business(prospect["port"], current)
        except Exception:
            pass  # non-fatal — the demo itself still regenerates below

    # Written into the prospect's own isolated data dir (served by that instance's own
    # GET /demo route) rather than the shared widget/ directory every instance mounts —
    # see docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md on why demos stay instance-isolated.
    out_path = (BACKEND_DIR / prospect["data_dir"]).resolve() / "demo.html"
    result = subprocess.run(
        [
            str(BACKEND_DIR / "venv" / "bin" / "python3"), str(OPS_DIR / "generate_site_demo.py"),
            "--url", url,
            "--name", name,
            "--api-base", f"http://localhost:{prospect['port']}",
            "--color", prospect["accent_color"],
            "--out", str(out_path),
        ],
        capture_output=True,
        text=True,
        # Worst case: screenshot() up to 60s + render_page_text() up to 45s (both in
        # generate_site_demo.py) + a Claude summarize call + a few knowledge POSTs —
        # keep real headroom above that sum so a slow-but-recoverable site doesn't get
        # cut off mid-pipeline and turn a graceful "skip knowledge" into a hard failure.
        timeout=150,
    )
    if not out_path.exists():
        return {"ok": False, "message": result.stderr[-500:] or "screenshot failed"}

    rel_path = out_path.relative_to(PROJECT_ROOT)
    prospect["sales_demo"] = str(rel_path)
    clients = [prospect if c["id"] == prospect_id else c for c in load_clients()]
    if not any(c["id"] == prospect_id for c in clients):
        clients.append(prospect)
    save_clients(clients)

    return {
        "ok": True,
        "client_id": prospect_id,
        "open_url": f"http://localhost:{prospect['port']}/demo",
        "message": f"Created its own instance on :{prospect['port']}, seeded from {template['name']}'s config — "
                    f"edit it independently anytime via its own Admin view on the launcher.",
    }


@app.post("/generate-demo")
async def generate_demo(req: GenerateDemoRequest):
    return _generate_demo(req.url, req.name, req.client_id)


URGENCY_CLASS = {
    "Urgent — affecting customers now": "urg-urgent",
    "This week": "urg-week",
    "Whenever you get a chance": "urg-whenever",
}

REQUESTS_PAGE_JS = """
async function updateStatus(clientId, requestId, status) {
  await fetch(`/support-requests/${clientId}/${requestId}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

function applyFilters() {
  const clientVal = document.getElementById("filterClient").value;
  const statusVal = document.getElementById("filterStatus").value;
  document.querySelectorAll("tr[data-client][data-status]").forEach((row) => {
    const clientMatch = !clientVal || row.dataset.client === clientVal;
    const statusMatch = !statusVal || row.dataset.status === statusVal;
    row.style.display = (clientMatch && statusMatch) ? "" : "none";
  });
}
document.getElementById("filterClient")?.addEventListener("change", applyFilters);
document.getElementById("filterStatus")?.addEventListener("change", applyFilters);

document.querySelectorAll(".status-select").forEach((sel) => {
  sel.addEventListener("change", (e) => {
    const row = e.target.closest("tr");
    updateStatus(row.dataset.client, row.dataset.requestId, e.target.value);
    row.dataset.status = e.target.value;
    applyFilters();
  });
});

document.querySelectorAll(".req-screenshot").forEach((img) => {
  img.addEventListener("click", () => window.open(img.src, "_blank"));
});
"""


@app.get("/support-requests", response_class=HTMLResponse)
def support_requests_page():
    clients = load_clients()
    all_rows = []
    for c in clients:
        if not is_running(c["port"]):
            continue
        for r in fetch_support_requests(c["port"]):
            r["_client_id"] = c["id"]
            r["_client_name"] = c["name"]
            all_rows.append(r)
    all_rows.sort(key=lambda r: r["created_at"], reverse=True)

    client_options = "\n".join(f'<option value="{c["id"]}">{c["name"]}</option>' for c in clients)
    status_options = "".join(
        f'<option value="{s}">{s.replace("_", " ").title()}</option>' for s in ["new", "in_progress", "resolved"]
    )

    def row_html(r):
        urg_class = URGENCY_CLASS.get(r.get("urgency", ""), "urg-whenever")
        screenshot_html = (
            f'<img class="req-screenshot" src="{r["screenshot_data_uri"]}" alt="screenshot" />'
            if r.get("screenshot_data_uri") else "—"
        )
        status_opts = "".join(
            f'<option value="{s}" {"selected" if r.get("status", "new") == s else ""}>{s.replace("_", " ").title()}</option>'
            for s in ["new", "in_progress", "resolved"]
        )
        return f"""
        <tr data-client="{r['_client_id']}" data-status="{r.get('status', 'new')}" data-request-id="{r['id']}">
          <td><strong>{r['_client_name']}</strong></td>
          <td>{r['category']}</td>
          <td style="max-width:280px;">{r['details']}</td>
          <td><span class="req-urgency {urg_class}">{r.get('urgency', '')}</span></td>
          <td>{r.get('contact_info') or '—'}</td>
          <td>{screenshot_html}</td>
          <td>{r['created_at'][:16].replace('T', ' ')}</td>
          <td><select class="status-select">{status_opts}</select></td>
        </tr>"""

    rows_html = "\n".join(row_html(r) for r in all_rows) or ""
    no_rows_html = '<div class="no-rows">No support requests yet.</div>' if not all_rows else ""

    return f"""<!doctype html>
<html><head><title>Support Requests — LeadGuard Launcher</title><style>{PAGE_CSS}</style></head>
<body>
  {NAV_HTML}
  <h1>Support Requests</h1>
  <div class="sub">Aggregated across every running client instance — {len(all_rows)} total.</div>

  <div class="filters">
    <select id="filterClient"><option value="">All clients</option>{client_options}</select>
    <select id="filterStatus"><option value="">All statuses</option>{status_options}</select>
  </div>

  {no_rows_html}
  <table class="requests" style="{'display:none;' if not all_rows else ''}">
    <thead><tr>
      <th>Client</th><th>Category</th><th>Details</th><th>Urgency</th><th>Contact</th><th>Screenshot</th><th>Submitted</th><th>Status</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>

  <script>{REQUESTS_PAGE_JS}</script>
</body></html>"""


@app.post("/support-requests/{client_id}/{request_id}/status")
async def proxy_update_status(client_id: str, request_id: int, body: dict):
    clients = load_clients()
    client = next((c for c in clients if c["id"] == client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    try:
        req = urllib.request.Request(
            f"http://localhost:{client['port']}/api/support-requests/{request_id}",
            data=json.dumps({"status": body.get("status")}).encode(),
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        urllib.request.urlopen(req, timeout=5)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


class BipApplyRequest(BaseModel):
    client_id: str
    values: dict


BIP_IMPORT_JS = """
let currentBip = null;

async function loadBipList() {
  const res = await fetch('/bip-import/list');
  const bips = await res.json();
  const sel = document.getElementById('bipSelect');
  sel.innerHTML = '<option value="">Choose a BIP...</option>' +
    bips.map(b => `<option value="${b.id}">${b.title} (v${b.version})</option>`).join('');
}

async function loadBip() {
  const bipId = document.getElementById('bipSelect').value;
  const fieldsDiv = document.getElementById('placeholderFields');
  const previewDiv = document.getElementById('preview');
  fieldsDiv.innerHTML = '';
  previewDiv.hidden = true;
  document.getElementById('applyBtn').disabled = true;
  if (!bipId) { currentBip = null; return; }
  const res = await fetch(`/bip-import/${bipId}`);
  currentBip = await res.json();
  fieldsDiv.innerHTML = currentBip.placeholders.map(p => `
    <label>${p.replace(/_/g, ' ')}
      <input data-placeholder="${p}" oninput="renderPreview()" placeholder="Fill in from the intake form..." />
    </label>`).join('');
  renderPreview();
}

function currentValues() {
  const values = {};
  document.querySelectorAll('#placeholderFields input').forEach(input => {
    values[input.dataset.placeholder] = input.value;
  });
  return values;
}

function substitute(text, values) {
  for (const [key, value] of Object.entries(values)) {
    text = text.split('{{' + key + '}}').join(value || `{{${key}}}`);
  }
  return text;
}

function renderPreview() {
  if (!currentBip) return;
  const values = currentValues();
  const previewDiv = document.getElementById('preview');
  previewDiv.hidden = false;
  document.getElementById('previewScript').textContent = substitute(currentBip.flow_script, values);
  document.getElementById('previewFacts').innerHTML = currentBip.facts.map(f =>
    `<tr><td>${f.label}</td><td>${substitute(f.value, values)}</td></tr>`).join('');
  document.getElementById('previewFaqs').innerHTML = currentBip.faqs.map(f =>
    `<tr><td>${substitute(f.question, values)}</td><td>${substitute(f.answer, values)}</td></tr>`).join('');

  const emptyNote = document.getElementById('previewEmptyNote');
  const noFacts = currentBip.facts.length === 0;
  const noFaqs = currentBip.faqs.length === 0;
  emptyNote.hidden = !(noFacts && noFaqs);
  if (!emptyNote.hidden) {
    emptyNote.textContent = 'This BIP has no Facts/FAQ table by design — its knowledge lives entirely in the flow script above. Nothing is broken; review the Required Configuration checklist below before applying.';
  }

  const configWrap = document.getElementById('previewConfigWrap');
  const config = currentBip.required_config || [];
  configWrap.hidden = config.length === 0;
  document.getElementById('previewConfig').innerHTML = config.map(item => `<li>${item}</li>`).join('');

  document.getElementById('applyBtn').disabled = !document.getElementById('clientSelect').value;
}

document.getElementById('clientSelect').addEventListener('change', renderPreview);

async function applyBip() {
  const bipId = document.getElementById('bipSelect').value;
  const clientId = document.getElementById('clientSelect').value;
  const statusEl = document.getElementById('applyStatus');
  statusEl.textContent = 'Applying...';
  const res = await fetch(`/bip-import/${bipId}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, values: currentValues() }),
  });
  const data = await res.json();
  statusEl.textContent = data.ok
    ? `Applied — ${data.facts_added} facts, ${data.faqs_added} FAQs written, knowledge_source set to "${data.knowledge_source}".`
    : `Failed: ${data.message}`;
}
"""


@app.get("/bip-import", response_class=HTMLResponse)
def bip_import_page():
    clients = load_clients()
    client_options = "\n".join(f'<option value="{c["id"]}">{c["name"]} (:{c["port"]})</option>' for c in clients)
    return f"""<!doctype html>
<html><head><title>BIP Import — LeadGuard Launcher</title><style>{PAGE_CSS}</style>
<style>
  .bip-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }}
  .bip-row select {{ padding: 9px 11px; border-radius: 8px; border: 1px solid var(--border); min-width: 260px; background: var(--surface); color: var(--text); font-family: var(--font-body); }}
  #placeholderFields {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px 16px; margin-bottom: 20px; }}
  #placeholderFields label {{ display: flex; flex-direction: column; font-size: 12px; font-weight: 600; color: var(--text-dim); gap: 4px; text-transform: capitalize; }}
  #placeholderFields input {{ font-size: 13px; padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px; font-weight: 400; text-transform: none; background: var(--surface-2); color: var(--text); }}
  #preview {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  #preview h4 {{ margin: 0 0 8px; font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--text-faint); }}
  #previewScript {{ white-space: pre-wrap; font-family: var(--font-mono); font-size: 13px; background: var(--surface-2); padding: 10px; border-radius: 6px; margin: 0 0 16px; color: var(--text); }}
  #preview table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 16px; }}
  #preview td {{ padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  #previewEmptyNote {{ font-size: 12.5px; color: var(--text-dim); background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; margin-bottom: 16px; }}
  #previewConfig {{ font-size: 12.5px; color: var(--text); margin: 0 0 16px; padding-left: 20px; line-height: 1.6; }}
  #applyBtn {{ padding: 10px 20px; background: var(--accent); color: var(--on-accent); border: none; border-radius: 6px; font-weight: 700; cursor: pointer; }}
  #applyBtn:disabled {{ background: var(--surface-2); color: var(--text-faint); cursor: not-allowed; }}
  #applyStatus {{ margin-left: 12px; font-size: 13px; font-weight: 600; color: var(--text-dim); }}
</style>
</head>
<body>
  {NAV_HTML}
  <h1>BIP Import</h1>
  <div class="sub">Load a vertical starter pack, fill in the client's specifics once, review, then write it to a client instance.</div>

  <div class="bip-row">
    <select id="bipSelect" onchange="loadBip()"><option value="">Loading BIPs...</option></select>
    <select id="clientSelect"><option value="">Choose a client...</option>{client_options}</select>
  </div>

  <div id="placeholderFields"></div>

  <div id="preview" hidden>
    <h4>Flow Script Preview</h4>
    <pre id="previewScript"></pre>
    <div id="previewEmptyNote" hidden></div>
    <h4>Facts Preview</h4>
    <table><tbody id="previewFacts"></tbody></table>
    <h4>FAQs Preview</h4>
    <table><tbody id="previewFaqs"></tbody></table>
    <div id="previewConfigWrap" hidden>
      <h4>Required Configuration (not applied automatically — set these up yourself before treating this BIP as ready)</h4>
      <ul id="previewConfig"></ul>
    </div>
    <button id="applyBtn" onclick="applyBip()" disabled>Apply to selected client</button>
    <span id="applyStatus"></span>
  </div>

  <script>{BIP_IMPORT_JS}</script>
  <script>loadBipList();</script>
</body></html>"""


@app.get("/bip-import/list")
def bip_import_list():
    return bip_parser.list_bips(BIPS_DIR)


@app.get("/bip-import/{bip_id}")
def bip_import_get(bip_id: str):
    path = BIPS_DIR / f"{bip_id}.md"
    if not path.exists():
        return JSONResponse({"ok": False, "message": "unknown BIP"}, status_code=404)
    return bip_parser.parse_bip(path)


@app.post("/bip-import/{bip_id}/apply")
def bip_import_apply(bip_id: str, req: BipApplyRequest):
    path = BIPS_DIR / f"{bip_id}.md"
    if not path.exists():
        return JSONResponse({"ok": False, "message": "unknown BIP"}, status_code=404)
    parsed = bip_parser.parse_bip(path)

    clients = load_clients()
    client = next((c for c in clients if c["id"] == req.client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    if not is_running(client["port"]):
        return JSONResponse({"ok": False, "message": f"{client['name']} isn't running — start it first"}, status_code=400)

    knowledge_source = f"BIP: {parsed['title']} v{parsed['version']}"
    try:
        business = fetch_business(client["port"])
        business["flow_script"] = bip_parser.substitute(parsed["flow_script"], req.values)
        business["knowledge_source"] = knowledge_source
        put_business(client["port"], business)
    except Exception as e:
        return JSONResponse({"ok": False, "message": f"could not write flow script: {e}"}, status_code=500)

    facts_added = 0
    for fact in parsed["facts"]:
        try:
            post_json(client["port"], "/api/knowledge/facts", {
                "label": fact["label"],
                "value": bip_parser.substitute(fact["value"], req.values),
                "source": "bip",
            })
            facts_added += 1
        except Exception:
            pass

    faqs_added = 0
    for faq in parsed["faqs"]:
        try:
            post_json(client["port"], "/api/knowledge/faqs", {
                "question": bip_parser.substitute(faq["question"], req.values),
                "answer": bip_parser.substitute(faq["answer"], req.values),
                "category": faq.get("category", ""),
                "priority": faq.get("priority", 0),
                "source": "bip",
            })
            faqs_added += 1
        except Exception:
            pass

    return {
        "ok": True,
        "facts_added": facts_added,
        "faqs_added": faqs_added,
        "facts_total": len(parsed["facts"]),
        "faqs_total": len(parsed["faqs"]),
        "knowledge_source": knowledge_source,
    }


# ---------------------------------------------------------------------------
# Outreach CRM — the agency's own outbound prospect list, sales-cadence
# tracking, and script library (ops/outreach_db.py). Separate concept from
# clients.json: a prospect here may not have a demo instance yet at all.
# ---------------------------------------------------------------------------


def _prospect_row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["demo_questions"] = json.loads(d.get("demo_questions") or "[]")
    except json.JSONDecodeError:
        d["demo_questions"] = []
    return d


# Sheet verticals are short codes (fine for table badges) but read oddly spoken aloud
# verbatim — scripts get the natural-language industry name instead.
VERTICAL_SPOKEN_NAMES = {"HVAC": "HVAC", "PI": "personal injury"}


def _merge_fields(prospect: dict, rep_name: str) -> dict:
    questions = prospect.get("demo_questions") or []
    vertical_code = prospect.get("vertical") or ""
    return {
        "company": prospect.get("company_name") or "",
        "name": prospect.get("decision_maker_name") or "there",
        "vertical": VERTICAL_SPOKEN_NAMES.get(vertical_code, vertical_code),
        "hook": prospect.get("personalization_hook") or "",
        "demo_link": prospect.get("demo_url") or "[DEMO LINK]",
        "decision_maker_role": prospect.get("decision_maker_role") or "",
        "rep": rep_name or prospect.get("assigned_rep") or "Larry",
        "demo_questions": "\n".join(f"- {q}" for q in questions),
    }


def _render_script(body_template: str, fields: dict) -> str:
    body = body_template
    for k, v in fields.items():
        body = body.replace("{{" + k + "}}", v)
    return body


class ProspectUpdate(BaseModel):
    status: Optional[str] = None
    assigned_rep: Optional[str] = None
    notes: Optional[str] = None


class TouchInput(BaseModel):
    channel: str
    outcome: str = ""
    notes: str = ""


class CreateDemoInput(BaseModel):
    client_id: str
    url: Optional[str] = None
    name: Optional[str] = None


class ScriptUpdate(BaseModel):
    title: Optional[str] = None
    body_template: Optional[str] = None


@app.get("/api/outreach/prospects")
def list_prospects(rep: str = "", status: str = ""):
    query = "SELECT * FROM prospects WHERE 1=1"
    params = []
    if rep:
        query += " AND assigned_rep = ?"
        params.append(rep)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += (
        " ORDER BY (priority_rank IS NULL), priority_rank ASC,"
        " (next_touch_at IS NULL), next_touch_at ASC"
    )
    with outreach_db.db_session() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_prospect_row_to_dict(r) for r in rows]


@app.get("/api/outreach/prospects/{prospect_id}")
def get_prospect(prospect_id: int):
    with outreach_db.db_session() as conn:
        row = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        if not row:
            return JSONResponse({"ok": False, "message": "unknown prospect"}, status_code=404)
        scripts = conn.execute(
            "SELECT * FROM script_templates WHERE cadence_step = ? ORDER BY channel", (row["cadence_step"],)
        ).fetchall()
        touches = conn.execute(
            "SELECT * FROM touches WHERE prospect_id = ? ORDER BY created_at DESC", (prospect_id,)
        ).fetchall()
    prospect = _prospect_row_to_dict(row)
    fields = _merge_fields(prospect, prospect.get("assigned_rep"))
    prospect["scripts"] = [
        {
            "key": s["key"],
            "title": s["title"],
            "channel": s["channel"],
            "body": _render_script(s["body_template"], fields),
        }
        for s in scripts
    ]
    prospect["touches"] = [dict(t) for t in touches]
    return prospect


@app.patch("/api/outreach/prospects/{prospect_id}")
def update_prospect(prospect_id: int, update: ProspectUpdate):
    fields = update.model_dump(exclude_unset=True)
    with outreach_db.db_session() as conn:
        existing = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        if not existing:
            return JSONResponse({"ok": False, "message": "unknown prospect"}, status_code=404)
        if fields:
            fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE prospects SET {set_clause} WHERE id = ?", (*fields.values(), prospect_id))
        row = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    return _prospect_row_to_dict(row)


@app.post("/api/outreach/prospects/{prospect_id}/touches")
def log_touch(prospect_id: int, touch: TouchInput):
    with outreach_db.db_session() as conn:
        row = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        if not row:
            return JSONResponse({"ok": False, "message": "unknown prospect"}, status_code=404)
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        conn.execute(
            """INSERT INTO touches (prospect_id, channel, outcome, notes, cadence_step_at_time, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (prospect_id, touch.channel, touch.outcome, touch.notes, row["cadence_step"], now),
        )
        # Advancing the cadence step on every logged touch matches the runbook's Daily
        # Workflow ("Log Last Touch, Next Touch, Status, and Notes every time") — a step
        # 12 touch has no next step, so it just logs and leaves next_touch_at unset;
        # closing out is a manual status change from there.
        next_step = outreach_db.next_cadence_step(row["cadence_step"])
        next_touch_at = outreach_db.compute_next_touch(row["cadence_step"], now_dt)
        new_step = next_step if next_step is not None else row["cadence_step"]
        conn.execute(
            "UPDATE prospects SET last_touch_at = ?, next_touch_at = ?, cadence_step = ?, updated_at = ? WHERE id = ?",
            (now, next_touch_at, new_step, now, prospect_id),
        )
    return get_prospect(prospect_id)


@app.post("/api/outreach/prospects/{prospect_id}/create-demo")
def create_demo_for_prospect(prospect_id: int, body: CreateDemoInput):
    with outreach_db.db_session() as conn:
        row = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    if not row:
        return JSONResponse({"ok": False, "message": "unknown prospect"}, status_code=404)
    url = body.url or row["website"]
    name = body.name or row["company_name"]
    if not url:
        return JSONResponse({"ok": False, "message": "prospect has no website URL on file"}, status_code=400)
    industry = VERTICAL_SPOKEN_NAMES.get(row["vertical"], row["vertical"])
    result = _generate_demo(url, name, body.client_id, industry=industry)
    if result.get("ok"):
        with outreach_db.db_session() as conn:
            conn.execute(
                "UPDATE prospects SET client_id = ?, demo_url = ?, updated_at = ? WHERE id = ?",
                (result.get("client_id"), result.get("open_url"), datetime.now(timezone.utc).isoformat(), prospect_id),
            )
    return result


@app.get("/api/outreach/scripts")
def list_scripts():
    with outreach_db.db_session() as conn:
        rows = conn.execute("SELECT * FROM script_templates ORDER BY cadence_step, channel").fetchall()
    return [dict(r) for r in rows]


@app.patch("/api/outreach/scripts/{key}")
def update_script(key: str, update: ScriptUpdate):
    fields = update.model_dump(exclude_unset=True)
    with outreach_db.db_session() as conn:
        existing = conn.execute("SELECT * FROM script_templates WHERE key = ?", (key,)).fetchone()
        if not existing:
            return JSONResponse({"ok": False, "message": "unknown script"}, status_code=404)
        if fields:
            fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE script_templates SET {set_clause} WHERE key = ?", (*fields.values(), key))
        row = conn.execute("SELECT * FROM script_templates WHERE key = ?", (key,)).fetchone()
    return dict(row)


class RepInput(BaseModel):
    name: str


class RepUpdate(BaseModel):
    name: str


@app.get("/api/outreach/reps")
def list_reps():
    with outreach_db.db_session() as conn:
        rows = conn.execute("SELECT * FROM reps ORDER BY position").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/outreach/reps")
def add_rep(rep: RepInput):
    name = rep.name.strip()
    if not name:
        return JSONResponse({"ok": False, "message": "name can't be empty"}, status_code=400)
    with outreach_db.db_session() as conn:
        existing = conn.execute("SELECT id FROM reps WHERE name = ?", (name,)).fetchone()
        if existing:
            return JSONResponse({"ok": False, "message": f'"{name}" is already on the team'}, status_code=400)
        position = conn.execute("SELECT COALESCE(MAX(position), -1) AS n FROM reps").fetchone()["n"] + 1
        cur = conn.execute(
            "INSERT INTO reps (name, position, created_at) VALUES (?, ?, ?)",
            (name, position, datetime.now(timezone.utc).isoformat()),
        )
        row = conn.execute("SELECT * FROM reps WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.patch("/api/outreach/reps/{rep_id}")
def rename_rep(rep_id: int, update: RepUpdate):
    new_name = update.name.strip()
    if not new_name:
        return JSONResponse({"ok": False, "message": "name can't be empty"}, status_code=400)
    with outreach_db.db_session() as conn:
        existing = conn.execute("SELECT * FROM reps WHERE id = ?", (rep_id,)).fetchone()
        if not existing:
            return JSONResponse({"ok": False, "message": "unknown rep"}, status_code=404)
        name_clash = conn.execute(
            "SELECT id FROM reps WHERE name = ? AND id != ?", (new_name, rep_id)
        ).fetchone()
        if name_clash:
            return JSONResponse({"ok": False, "message": f'"{new_name}" is already on the team'}, status_code=400)
        old_name = existing["name"]
        conn.execute("UPDATE reps SET name = ? WHERE id = ?", (new_name, rep_id))
        # Cascade so existing assignments/scripts follow the rename instead of orphaning —
        # assigned_rep is a plain text label, not a foreign key, per this table's own schema.
        conn.execute("UPDATE prospects SET assigned_rep = ? WHERE assigned_rep = ?", (new_name, old_name))
        row = conn.execute("SELECT * FROM reps WHERE id = ?", (rep_id,)).fetchone()
    return dict(row)


@app.delete("/api/outreach/reps/{rep_id}")
def delete_rep(rep_id: int):
    with outreach_db.db_session() as conn:
        existing = conn.execute("SELECT * FROM reps WHERE id = ?", (rep_id,)).fetchone()
        if not existing:
            return JSONResponse({"ok": False, "message": "unknown rep"}, status_code=404)
        assigned_count = conn.execute(
            "SELECT COUNT(*) AS n FROM prospects WHERE assigned_rep = ?", (existing["name"],)
        ).fetchone()["n"]
        if assigned_count > 0:
            return JSONResponse(
                {"ok": False, "message": f'{existing["name"]} still has {assigned_count} assigned prospects — reassign them first'},
                status_code=400,
            )
        conn.execute("DELETE FROM reps WHERE id = ?", (rep_id,))
    return {"ok": True}


OUTREACH_CSS = """
  .rep-picker { display: flex; align-items: center; gap: 10px; margin-bottom: 18px; font-size: 13.5px; color: var(--text-dim); animation: rise .4s ease both; animation-delay: .08s; }
  .rep-picker select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: var(--surface); color: var(--text); font-family: var(--font-body); }
  .outreach-layout { display: grid; grid-template-columns: minmax(280px, 380px) 1fr; gap: 20px; align-items: start; }
  table.prospects { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
  table.prospects th, table.prospects td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 12.5px; }
  table.prospects th { background: var(--surface-2); color: var(--text-dim); font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }
  table.prospects tr { cursor: pointer; opacity: 0; animation: rise .35s ease both; transition: background .12s; }
  table.prospects tr:hover { background: var(--surface-2); }
  table.prospects tr.selected { background: var(--accent-soft); }
  table.prospects tr.selected td strong { color: var(--accent-strong); }
  .cadence-badge { font-family: var(--font-mono); font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: 20px; background: var(--teal-soft); color: var(--teal); white-space: nowrap; }
  .next-touch { font-size: 12px; font-family: var(--font-mono); color: var(--text-dim); }
  .next-touch.overdue { color: var(--accent-strong); font-weight: 700; padding: 2px 7px; border-radius: 6px; background: var(--accent-soft); animation: glow-pulse 2.2s ease-in-out infinite; }
  .detail-panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; animation: rise .35s ease both; }
  .detail-panel h2 { font-family: var(--font-display); font-weight: 600; margin: 0 0 4px; font-size: 24px; color: var(--text); }
  .detail-empty { color: var(--text-faint); padding: 60px 40px; text-align: center; background: var(--surface); border: 1px dashed var(--border-strong); border-radius: var(--radius); font-family: var(--font-display); font-size: 15px; }
  .detail-section { margin-top: 20px; }
  .detail-section h4 { margin: 0 0 10px; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--text-faint); font-weight: 700; }
  .ref-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; font-size: 12.5px; }
  .ref-grid dt { color: var(--text-faint); font-weight: 600; }
  .ref-grid dd { margin: 0 0 8px; color: var(--text); }
  .script-card { background: var(--surface-2); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; opacity: 0; animation: rise .35s ease both; }
  .script-card .script-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .script-card .script-title { font-family: var(--font-display); font-weight: 600; font-size: 14.5px; color: var(--accent-strong); }
  .script-card pre { white-space: pre-wrap; font-family: var(--font-mono); font-size: 12.5px; line-height: 1.6; margin: 0; color: var(--text); }
  .copy-btn { background: var(--accent-soft); color: var(--accent-strong); border: none; border-radius: 6px; padding: 4px 11px; font-size: 11px; font-weight: 700; cursor: pointer; font-family: var(--font-mono); transition: filter .15s; }
  .copy-btn:hover { filter: brightness(1.2); }
  .touch-buttons { display: flex; flex-wrap: wrap; gap: 8px; }
  .touch-buttons button { background: var(--surface-2); border: 1px solid var(--border); color: var(--text-dim); border-radius: 7px; padding: 8px 12px; font-size: 12.5px; cursor: pointer; font-family: var(--font-body); transition: all .12s; }
  .touch-buttons button:hover { background: var(--teal-soft); border-color: var(--teal); color: var(--teal); }
  .notes-box { width: 100%; min-height: 70px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; font-family: var(--font-body); background: var(--surface-2); color: var(--text); }
  .status-select-lg { padding: 8px 11px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: var(--surface-2); color: var(--text); font-family: var(--font-body); }
  .demo-panel { background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .demo-panel input { width: 100%; padding: 8px 10px; border: 1px solid var(--border); border-radius: 7px; font-size: 13px; margin-bottom: 8px; background: var(--bg); color: var(--text); font-family: var(--font-mono); }
  .demo-panel button { background: var(--accent); color: var(--on-accent); border: none; padding: 9px 16px; border-radius: 7px; font-weight: 700; cursor: pointer; font-family: var(--font-body); }
  .demo-link-box { margin-top: 10px; font-size: 13px; font-family: var(--font-mono); word-break: break-all; color: var(--teal); }
  .touch-history { font-size: 12px; color: var(--text-dim); font-family: var(--font-mono); padding-left: 18px; }
  .touch-history li { margin-bottom: 4px; }
  .link-btn { background: none; border: none; color: var(--teal); font-size: 12.5px; font-weight: 600; cursor: pointer; text-decoration: underline; font-family: var(--font-body); padding: 0; margin-left: 4px; }
  .manage-team-panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; margin-bottom: 18px; max-width: 420px; }
  .manage-team-panel h4 { margin: 0 0 10px; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--text-faint); font-weight: 700; }
  .rep-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .rep-name-input { flex: 1; padding: 6px 9px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; background: var(--surface-2); color: var(--text); font-family: var(--font-body); }
  .rep-remove-btn { background: var(--accent-soft); color: var(--accent-strong); border: none; border-radius: 6px; padding: 5px 10px; font-size: 11.5px; font-weight: 700; cursor: pointer; }
  .add-rep-form { display: flex; gap: 8px; margin-top: 10px; }
  .add-rep-form input { flex: 1; padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; background: var(--surface-2); color: var(--text); font-family: var(--font-body); }
  .add-rep-form button { background: var(--teal-soft); color: var(--teal); border: none; border-radius: 6px; padding: 7px 14px; font-size: 12.5px; font-weight: 700; cursor: pointer; }
"""

OUTREACH_JS = """
let outreachProspects = [];
let selectedProspectId = null;
let OUTREACH_REPS = [];

function currentRep() {
  return localStorage.getItem("outreachRep") || (OUTREACH_REPS[0] && OUTREACH_REPS[0].name) || "";
}

async function loadReps() {
  const res = await fetch("/api/outreach/reps");
  OUTREACH_REPS = await res.json();
  const sel = document.getElementById("repSelect");
  const saved = localStorage.getItem("outreachRep");
  sel.innerHTML = OUTREACH_REPS.map((r) => `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join("");
  if (saved && OUTREACH_REPS.some((r) => r.name === saved)) {
    sel.value = saved;
  } else if (OUTREACH_REPS.length) {
    localStorage.setItem("outreachRep", OUTREACH_REPS[0].name);
  }
  renderRepList();
}

function renderRepList() {
  const box = document.getElementById("repList");
  if (!box) return;
  box.innerHTML = OUTREACH_REPS.map((r) => `
    <div class="rep-row" data-id="${r.id}">
      <input class="rep-name-input" value="${esc(r.name)}" onblur="renameRep(${r.id}, this.value)" />
      <button type="button" class="rep-remove-btn" data-id="${r.id}" data-name="${esc(r.name)}">Remove</button>
    </div>`).join("");
  box.querySelectorAll(".rep-remove-btn").forEach((btn) => {
    btn.addEventListener("click", () => removeRep(Number(btn.dataset.id), btn.dataset.name));
  });
}

async function renameRep(id, newNameRaw) {
  const newName = newNameRaw.trim();
  const rep = OUTREACH_REPS.find((r) => r.id === id);
  if (!rep || !newName || rep.name === newName) { renderRepList(); return; }
  const res = await fetch(`/api/outreach/reps/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: newName }),
  });
  const data = await res.json();
  const status = document.getElementById("repFormStatus");
  if (data.ok === false) {
    status.textContent = data.message;
    renderRepList();
    return;
  }
  if (currentRep() === rep.name) localStorage.setItem("outreachRep", data.name);
  status.textContent = `Renamed to "${data.name}".`;
  await loadReps();
  loadProspects();
  if (selectedProspectId) selectProspect(selectedProspectId);
}

async function removeRep(id, name) {
  if (!confirm(`Remove ${name} from the team?`)) return;
  const res = await fetch(`/api/outreach/reps/${id}`, { method: "DELETE" });
  const data = await res.json();
  const status = document.getElementById("repFormStatus");
  if (data.ok === false) {
    status.textContent = data.message;
    return;
  }
  status.textContent = `${name} removed.`;
  await loadReps();
  if (selectedProspectId) selectProspect(selectedProspectId);
}

document.getElementById("addRepForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("newRepName");
  const name = input.value.trim();
  if (!name) return;
  const res = await fetch("/api/outreach/reps", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  });
  const data = await res.json();
  const status = document.getElementById("repFormStatus");
  if (data.ok === false) {
    status.textContent = data.message;
    return;
  }
  input.value = "";
  status.textContent = `Added ${data.name}.`;
  await loadReps();
  if (selectedProspectId) selectProspect(selectedProspectId);
});

document.getElementById("manageTeamToggle")?.addEventListener("click", () => {
  const panel = document.getElementById("manageTeamPanel");
  panel.hidden = !panel.hidden;
});

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function esc(s) {
  return (s ?? "").toString().replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function loadProspects() {
  const rep = document.getElementById("repSelect").value;
  localStorage.setItem("outreachRep", rep);
  const statusFilter = document.getElementById("statusFilter").value;
  const params = new URLSearchParams();
  if (rep !== "__all__") params.set("rep", rep);
  if (statusFilter) params.set("status", statusFilter);
  const res = await fetch(`/api/outreach/prospects?${params.toString()}`);
  outreachProspects = await res.json();
  renderProspectList();
}

function renderProspectList() {
  const tbody = document.getElementById("prospectListBody");
  if (!outreachProspects.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="no-rows">No prospects match this filter.</td></tr>';
    return;
  }
  const now = new Date();
  tbody.innerHTML = outreachProspects.map((p, i) => {
    const overdue = p.next_touch_at && new Date(p.next_touch_at) < now;
    const delay = Math.min(i * 0.025, 0.4);
    return `<tr class="${p.id === selectedProspectId ? 'selected' : ''}" style="animation-delay:${delay}s" onclick="selectProspect(${p.id})">
      <td><strong>${esc(p.company_name)}</strong><br/><span style="color:var(--text-faint);">${esc(p.vertical)}</span></td>
      <td><span class="cadence-badge">Day ${p.cadence_step}</span></td>
      <td><span class="next-touch ${overdue ? 'overdue' : ''}">${fmtDate(p.next_touch_at)}</span></td>
      <td>${esc(p.status)}</td>
    </tr>`;
  }).join("");
}

async function selectProspect(id) {
  selectedProspectId = id;
  renderProspectList();
  const res = await fetch(`/api/outreach/prospects/${id}`);
  const p = await res.json();
  renderProspectDetail(p);
}

function renderProspectDetail(p) {
  const panel = document.getElementById("prospectDetail");
  panel.className = "detail-panel";
  const questions = (p.demo_questions || []).map((q) => `<li>${esc(q)}</li>`).join("");
  const scripts = (p.scripts || []).map((s, i) => `
    <div class="script-card" style="animation-delay:${i * 0.06}s">
      <div class="script-head">
        <span class="script-title">${esc(s.title)}</span>
        <button class="copy-btn" onclick="copyScript(this)">Copy</button>
      </div>
      <pre>${esc(s.body)}</pre>
    </div>`).join("") || '<div class="sub">No script for this step yet.</div>';
  const demoSection = p.demo_url
    ? `<div class="demo-link-box">Live demo: <a href="${p.demo_url}" target="_blank">${p.demo_url}</a>
        &nbsp;<button class="copy-btn" onclick="copyPlain('${p.demo_url}')">Copy link</button></div>`
    : `<div class="demo-panel">
        <label style="font-size:11px;font-weight:600;color:var(--text-faint);text-transform:uppercase;letter-spacing:.04em;">Website to demo</label>
        <input id="demoUrl" value="${esc(p.website)}" />
        <label style="font-size:11px;font-weight:600;color:var(--text-faint);text-transform:uppercase;letter-spacing:.04em;">Business name</label>
        <input id="demoName" value="${esc(p.company_name)}" />
        <label style="font-size:11px;font-weight:600;color:var(--text-faint);text-transform:uppercase;letter-spacing:.04em;">Template client id</label>
        <input id="demoClientId" placeholder="e.g. lmtlss" />
        <button onclick="createDemo(${p.id})">Create demo</button>
        <div id="demoStatus" class="sub" style="margin-top:6px;"></div>
      </div>`;
  const touches = (p.touches || []).map((t) =>
    `<li>${fmtDate(t.created_at)} — ${esc(t.channel)}${t.outcome ? ': ' + esc(t.outcome) : ''}</li>`
  ).join("") || "<li>No touches logged yet.</li>";

  panel.innerHTML = `
    <h2>${esc(p.company_name)}</h2>
    <div class="sub">${esc(p.vertical)} · ${esc(p.city_metro)} · Score ${p.score ?? "—"} · Priority #${p.priority_rank ?? "—"}</div>

    <div class="detail-section">
      <select class="status-select-lg" id="statusSelect" onchange="updateStatus(${p.id}, this.value)">
        ${["Not Started", "Working", "Follow-up Due", "Engaged", "Won", "Lost", "Paused"].map(
          (s) => `<option value="${s}" ${s === p.status ? "selected" : ""}>${s}</option>`
        ).join("")}
      </select>
      &nbsp;assigned to
      <select class="status-select-lg" id="repAssignSelect" onchange="updateAssignedRep(${p.id}, this.value)">
        ${OUTREACH_REPS.map((r) => `<option value="${esc(r.name)}" ${r.name === p.assigned_rep ? "selected" : ""}>${esc(r.name)}</option>`).join("")}
      </select>
    </div>

    <div class="detail-section">
      <h4>Reference</h4>
      <dl class="ref-grid">
        <dt>Website</dt><dd><a href="${esc(p.website)}" target="_blank">${esc(p.website)}</a></dd>
        <dt>Decision-maker</dt><dd>${esc(p.decision_maker_name) || "—"} (${esc(p.decision_maker_role) || "—"})</dd>
        <dt>Phone</dt><dd>${esc(p.phone) || "—"}</dd>
        <dt>Contact</dt><dd>${esc(p.email_or_contact_url) || "—"}</dd>
        <dt>Preferred channel</dt><dd>${esc(p.preferred_channel) || "—"}</dd>
        <dt>Personalization hook</dt><dd>${esc(p.personalization_hook) || "—"}</dd>
      </dl>
      ${questions ? `<div class="sub">Suggested demo questions:</div><ul style="font-size:12.5px;">${questions}</ul>` : ""}
    </div>

    <div class="detail-section">
      <h4>Script for Day ${p.cadence_step}</h4>
      ${scripts}
    </div>

    <div class="detail-section">
      <h4>Demo</h4>
      ${demoSection}
    </div>

    <div class="detail-section">
      <h4>Log a touch</h4>
      <div class="touch-buttons">
        <button onclick="logTouch(${p.id}, 'phone', 'talked to owner')">Called — talked to owner</button>
        <button onclick="logTouch(${p.id}, 'phone', 'gatekeeper')">Called — gatekeeper</button>
        <button onclick="logTouch(${p.id}, 'voicemail', 'left voicemail')">Called — voicemail</button>
        <button onclick="logTouch(${p.id}, 'email', 'sent')">Emailed</button>
        <button onclick="logTouch(${p.id}, 'text', 'sent')">Sent text</button>
        <button onclick="logTouch(${p.id}, 'video', 'sent')">Sent video</button>
        <button onclick="logTouch(${p.id}, 'phone', 'no answer')">No answer</button>
      </div>
    </div>

    <div class="detail-section">
      <h4>Notes</h4>
      <textarea class="notes-box" id="notesBox" onblur="saveNotes(${p.id}, this.value)">${esc(p.notes)}</textarea>
    </div>

    <div class="detail-section">
      <h4>Touch history</h4>
      <ul class="touch-history">${touches}</ul>
    </div>
  `;
}

function copyPlain(text) {
  navigator.clipboard.writeText(text);
}

function copyScript(btn) {
  const text = btn.closest(".script-card").querySelector("pre").textContent;
  navigator.clipboard.writeText(text);
  const original = btn.textContent;
  btn.textContent = "Copied!";
  setTimeout(() => (btn.textContent = original), 1200);
}

async function updateStatus(id, status) {
  await fetch(`/api/outreach/prospects/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
  });
  loadProspects();
}

async function updateAssignedRep(id, assigned_rep) {
  await fetch(`/api/outreach/prospects/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ assigned_rep }),
  });
  loadProspects();
}

async function saveNotes(id, notes) {
  await fetch(`/api/outreach/prospects/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ notes }),
  });
}

async function logTouch(id, channel, outcome) {
  const res = await fetch(`/api/outreach/prospects/${id}/touches`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ channel, outcome }),
  });
  const p = await res.json();
  renderProspectDetail(p);
  loadProspects();
}

async function createDemo(id) {
  const status = document.getElementById("demoStatus");
  status.textContent = "Screenshotting and generating... this can take up to ~2 minutes.";
  const payload = {
    url: document.getElementById("demoUrl").value,
    name: document.getElementById("demoName").value,
    client_id: document.getElementById("demoClientId").value,
  };
  const res = await fetch(`/api/outreach/prospects/${id}/create-demo`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (data.ok) {
    selectProspect(id);
    loadProspects();
  } else {
    status.textContent = "Error: " + data.message;
  }
}

document.getElementById("repSelect")?.addEventListener("change", loadProspects);
document.getElementById("statusFilter")?.addEventListener("change", loadProspects);
"""


@app.get("/outreach", response_class=HTMLResponse)
def outreach_page():
    status_options = "".join(
        f'<option value="{s}">{s}</option>' for s in
        ["Not Started", "Working", "Follow-up Due", "Engaged", "Won", "Lost", "Paused"]
    )
    return f"""<!doctype html>
<html><head><title>Outreach — LeadGuard Launcher</title><style>{PAGE_CSS}</style><style>{OUTREACH_CSS}</style></head>
<body>
  {NAV_HTML}
  <h1>Outreach</h1>
  <div class="sub">Work your assigned prospects — scripts, cadence, and demo creation in one place.</div>

  <div class="rep-picker">
    Who's working? <select id="repSelect"><option>Loading…</option></select>
    <select id="statusFilter"><option value="">All statuses</option>{status_options}</select>
    <button type="button" id="manageTeamToggle" class="link-btn">⚙ Manage team</button>
  </div>

  <div id="manageTeamPanel" class="manage-team-panel" hidden>
    <h4>Team</h4>
    <div id="repList"></div>
    <form id="addRepForm" class="add-rep-form">
      <input id="newRepName" placeholder="Add a team member's name" maxlength="60" />
      <button type="submit">Add</button>
    </form>
    <div id="repFormStatus" class="sub"></div>
  </div>

  <div class="outreach-layout">
    <table class="prospects">
      <thead><tr><th>Company</th><th>Cadence</th><th>Next touch</th><th>Status</th></tr></thead>
      <tbody id="prospectListBody"><tr><td colspan="4" class="no-rows">Loading...</td></tr></tbody>
    </table>
    <div id="prospectDetail" class="detail-empty">Select a prospect to see their script and log a touch.</div>
  </div>

  <script>{OUTREACH_JS}</script>
  <script>
    (async function() {{
      await loadReps();
      loadProspects();
    }})();
  </script>
</body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7100)
