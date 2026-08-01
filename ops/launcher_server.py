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
import subprocess
import time
import urllib.error
import urllib.request

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel


class GenerateDemoRequest(BaseModel):
    url: str
    name: str
    client_id: str  # which existing client's config to use as a starting template

OPS_DIR = pathlib.Path(__file__).parent
PROJECT_ROOT = OPS_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
WIDGET_DIR = PROJECT_ROOT / "widget"
CLIENTS_PATH = OPS_DIR / "clients.json"

app = FastAPI(title="LeadGuard Demo Launcher")


def load_clients():
    return json.loads(CLIENTS_PATH.read_text())


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
    return f"""
    <div class="card">
      <div class="card-head">
        <h3>{c['name']}</h3>
        {status_html}
      </div>
      <div class="card-actions">
        <button class="btn btn-start" data-client="{c['id']}" onclick="startClient('{c['id']}')">▶ Start environment</button>
        <a class="btn btn-visitor {'btn-disabled' if not running else ''}" href="{visitor_href}" target="_blank" {disabled}>🌐 Visitor view</a>
        <a class="btn btn-admin {'btn-disabled' if not running else ''}" href="{admin_href}" target="_blank" {disabled}>🔑 Admin view</a>
        <a class="btn btn-client {'btn-disabled' if not running else ''}" href="{client_href}" target="_blank" {disabled}>🗂 Client view</a>
      </div>
      <div class="card-meta">port :{c['port']} &middot; {visitor_target or "no demo generated yet"}</div>
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
</div>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    clients = load_clients()
    cards = "\n".join(client_card_html(c) for c in clients)
    options = "\n".join(f'<option value="{c["id"]}">{c["name"]} (:{c["port"]})</option>' for c in clients)
    return f"""<!doctype html>
<html><head><title>LeadGuard Launcher</title><style>{PAGE_CSS}</style></head>
<body>
  {NAV_HTML}
  <h1>LeadGuard Demo Launcher</h1>
  <div class="sub">Local control panel — no terminal needed. Bookmark this page.</div>
  <div class="grid">{cards}</div>

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

  <script>{PAGE_JS}</script>
</body></html>"""


@app.post("/start/{client_id}")
def start(client_id: str):
    clients = load_clients()
    client = next((c for c in clients if c["id"] == client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    return start_client(client)


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
        timeout=90,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7100)
