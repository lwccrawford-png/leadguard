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
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import bip_parser


class GenerateDemoRequest(BaseModel):
    url: str
    name: str
    client_id: str  # which existing client's config to use as a starting template

OPS_DIR = pathlib.Path(__file__).parent
PROJECT_ROOT = OPS_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
WIDGET_DIR = PROJECT_ROOT / "widget"
CLIENTS_PATH = OPS_DIR / "clients.json"
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
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f7f7f9; margin: 0; padding: 32px; color: #222; }
  h1 { margin: 0 0 4px; font-size: 22px; }
  .sub { color: #777; font-size: 13px; margin-bottom: 28px; }
  .topnav { display: flex; gap: 18px; margin-bottom: 24px; }
  .topnav a { color: #4f46e5; font-weight: 600; font-size: 13px; text-decoration: none; }
  .topnav a:hover { text-decoration: underline; }
  .filters { display: flex; gap: 12px; margin-bottom: 18px; }
  .filters select { padding: 7px 10px; border: 1px solid #e5e5ea; border-radius: 6px; font-size: 13px; background: #fff; }
  table.requests { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; }
  table.requests th, table.requests td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e5ea; font-size: 13px; vertical-align: top; }
  table.requests th { background: #f0f0f4; color: #555; font-size: 11.5px; text-transform: uppercase; letter-spacing: .02em; }
  table.requests tr:last-child td { border-bottom: none; }
  .req-urgency { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px; display: inline-block; }
  .urg-urgent { background: #fef2f2; color: #b91c1c; }
  .urg-week { background: #fff7e6; color: #b45309; }
  .urg-whenever { background: #f0f0f4; color: #666; }
  .status-select { font-size: 12px; padding: 4px 6px; border-radius: 6px; border: 1px solid #e5e5ea; }
  .req-screenshot { max-width: 90px; max-height: 60px; border-radius: 4px; border: 1px solid #e5e5ea; cursor: pointer; }
  .no-rows { color: #999; padding: 24px; text-align: center; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; margin-bottom: 36px; }
  .card { background: #fff; border: 1px solid #e5e5ea; border-radius: 10px; padding: 18px; }
  .card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
  .card-head h3 { margin: 0; font-size: 15px; }
  .pill { font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px; }
  .pill-up { background: #eafbf0; color: #15803d; }
  .pill-down { background: #f0f0f4; color: #888; }
  .card-actions { display: flex; flex-direction: column; gap: 8px; }
  .btn { display: block; text-align: center; padding: 9px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; text-decoration: none; border: none; cursor: pointer; }
  .btn-start { background: #4f46e5; color: #fff; }
  .btn-visitor { background: #eef0ff; color: #4f46e5; }
  .btn-admin { background: #fff1f2; color: #be123c; }
  .btn-client { background: #f0f0f4; color: #444; }
  .btn-disabled { opacity: .45; pointer-events: none; }
  .card-meta { margin-top: 10px; font-size: 11.5px; color: #999; }
  .btn-pause { background: #fff7e6; color: #b45309; }
  .btn-promote { background: #eafbf0; color: #15803d; }
  .btn-delete { background: #fef2f2; color: #b91c1c; }
  .launcher-tabs { display: flex; gap: 6px; margin-bottom: 20px; border-bottom: 1px solid #e5e5ea; }
  .launcher-tab { background: none; border: none; padding: 10px 16px; font-size: 14px; font-weight: 600; color: #888; cursor: pointer; border-bottom: 2px solid transparent; }
  .launcher-tab.active { color: #4f46e5; border-bottom-color: #4f46e5; }
  .launcher-view { display: none; }
  .launcher-view.active { display: block; }
  .kb-source-pill { display: inline-block; margin-left: 6px; padding: 1px 8px; border-radius: 999px; background: #eef2ff; color: #4f46e5; font-weight: 600; }
  form.generate { background: #fff; border: 1px solid #e5e5ea; border-radius: 10px; padding: 20px; max-width: 520px; }
  form.generate label { display: block; font-size: 12px; font-weight: 600; color: #444; margin-bottom: 4px; margin-top: 12px; }
  form.generate input, form.generate select { width: 100%; padding: 8px 10px; border: 1px solid #e5e5ea; border-radius: 6px; font-size: 14px; }
  form.generate button { margin-top: 16px; background: #4f46e5; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; cursor: pointer; }
  #genStatus { margin-top: 10px; font-size: 13px; }
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
    return RedirectResponse(f"/file?path={target}")


@app.post("/generate-demo")
async def generate_demo(req: GenerateDemoRequest):
    clients = load_clients()
    template = next((c for c in clients if c["id"] == req.client_id), None)
    if not template:
        return {"ok": False, "message": "unknown template client"}
    if not is_running(template["port"]):
        return {"ok": False, "message": f"{template['name']}'s backend isn't running — start it first, it's only used as a config template"}

    safe_name = "".join(ch if ch.isalnum() else "_" for ch in req.name.lower())[:40]
    prospect_id = f"prospect_{safe_name}"

    prospect = next((c for c in clients if c["id"] == prospect_id), None)
    if prospect is None:
        # First time generating for this prospect: provision a genuinely independent
        # backend instance — its own port, its own database — so editing its Settings
        # later can never touch the template client's real, actively-used config.
        prospect = {
            "id": prospect_id,
            "name": req.name,
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
                "name": req.name,
                "assistant_name": template_business.get("assistant_name", ""),
                "flow_script": template_business.get("flow_script", ""),
                "accent_color": prospect["accent_color"],
            })
        except Exception as e:
            return {"ok": False, "message": f"provisioned but could not seed config: {e}"}
        clients.append(prospect)
        save_clients(clients)
    elif not is_running(prospect["port"]):
        started = start_client(prospect)
        if not started["ok"]:
            return started

    out_path = WIDGET_DIR / f"{prospect_id}.html"
    result = subprocess.run(
        [
            str(BACKEND_DIR / "venv" / "bin" / "python3"), str(OPS_DIR / "generate_site_demo.py"),
            "--url", req.url,
            "--name", req.name,
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
        "open_url": f"/file?path={rel_path}",
        "message": f"Created its own instance on :{prospect['port']}, seeded from {template['name']}'s config — "
                    f"edit it independently anytime via its own Admin view on the launcher.",
    }


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
  .bip-row select {{ padding: 8px 10px; border-radius: 6px; border: 1px solid #ddd; min-width: 260px; }}
  #placeholderFields {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px 16px; margin-bottom: 20px; }}
  #placeholderFields label {{ display: flex; flex-direction: column; font-size: 12px; font-weight: 600; color: #555; gap: 4px; text-transform: capitalize; }}
  #placeholderFields input {{ font-size: 13px; padding: 6px 8px; border: 1px solid #ddd; border-radius: 5px; font-weight: 400; text-transform: none; }}
  #preview {{ background: #fff; border: 1px solid #e5e5ea; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  #preview h4 {{ margin: 0 0 8px; font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: #888; }}
  #previewScript {{ white-space: pre-wrap; font-size: 13px; background: #f7f7f9; padding: 10px; border-radius: 6px; margin: 0 0 16px; }}
  #preview table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 16px; }}
  #preview td {{ padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
  #applyBtn {{ padding: 10px 20px; background: #4f46e5; color: #fff; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; }}
  #applyBtn:disabled {{ background: #ccc; cursor: not-allowed; }}
  #applyStatus {{ margin-left: 12px; font-size: 13px; font-weight: 600; }}
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
    <h4>Facts Preview</h4>
    <table><tbody id="previewFacts"></tbody></table>
    <h4>FAQs Preview</h4>
    <table><tbody id="previewFaqs"></tbody></table>
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7100)
