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
import asyncio
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

import auth
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
PROSPECT_VIDEOS_DIR = OPS_DIR / "prospect_videos"

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

# This tool is internal-only — every route requires a valid signed session cookie
# except /login and /proxy/. Prospect-facing demo pages are self-contained static
# files sent directly (see generate_site_demo.py's docstring), but their live
# widget/chat still needs to reach that instance's own backend (a separate process,
# only listening on 127.0.0.1) — /proxy/{port}/... (below) is the scoped relay for
# that, restricted to ports this launcher actually knows about, not an open proxy.
# It must stay public: a real prospect's browser hits it, not a logged-in teammate.
PUBLIC_PATH_PREFIXES = ("/login", "/proxy/")

# Login is required by default (the cloud deployment, on a public IP, needs it) — this
# is an explicit opt-out, not an opt-in, so a fresh deploy anywhere else stays secure
# by default. Local dev only listens on 127.0.0.1 (see uvicorn.run below) — nobody but
# this Mac can ever reach it, so requiring a password here is friction with no real
# security benefit. Set via the local LaunchAgent plist (ops/README.md), not here.
LOGIN_DISABLED = os.environ.get("EVOLVEIQ_DISABLE_LOGIN") == "1"

# Set on the cloud deployment only (systemd Environment=, not here) to
# https://team.justaskevolveiq.com — when set, generated demo links route through
# /proxy/{port}/... (a real, publicly reachable address) instead of localhost, which
# is meaningless to anyone except the machine that generated it. Unset locally, where
# localhost is exactly right since only this Mac ever opens these links.
PUBLIC_BASE_URL = os.environ.get("EVOLVEIQ_PUBLIC_BASE_URL", "").rstrip("/")


def public_base_for(port: int) -> str:
    return f"{PUBLIC_BASE_URL}/proxy/{port}" if PUBLIC_BASE_URL else f"http://localhost:{port}"


@app.middleware("http")
async def require_login(request: Request, call_next):
    if LOGIN_DISABLED or request.url.path.startswith(PUBLIC_PATH_PREFIXES):
        return await call_next(request)
    username = auth.verify_session_cookie(request.cookies.get(auth.SESSION_COOKIE, ""))
    if not username:
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)
    request.state.username = username
    return await call_next(request)


LOGIN_PAGE_CSS = """
  :root {
    --bg: #ffffff; --surface: #f5f5f7; --border: rgba(28,22,12,0.12);
    --text: #1c160c; --text-dim: #5b5342; --accent: #2f5fe0; --accent-strong: #1b3fae;
    --danger: #c23b3b;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    font-family: var(--font); background: var(--bg); color: var(--text);
    min-height: 100vh; margin: 0; display: grid; place-items: center;
    -webkit-font-smoothing: antialiased;
  }
  .login-card {
    width: min(360px, 90vw); padding: 36px 32px; border: 1px solid var(--border);
    border-radius: 14px; background: var(--surface);
  }
  .login-card h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.01em; margin: 0 0 4px; }
  .login-card p.sub { color: var(--text-dim); font-size: 13px; margin: 0 0 22px; }
  .login-card label { display: block; font-size: 12px; font-weight: 600; color: var(--text-dim); margin: 14px 0 5px; text-transform: uppercase; letter-spacing: .04em; }
  .login-card input {
    width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px;
    font-size: 15px; background: #fff; color: var(--text); font-family: var(--font);
  }
  .login-card button {
    width: 100%; margin-top: 22px; padding: 11px; border: none; border-radius: 8px;
    background: var(--accent); color: #fff; font-weight: 700; font-size: 14px; cursor: pointer;
  }
  .login-card button:hover { background: var(--accent-strong); }
  .login-error { color: var(--danger); font-size: 13px; margin-top: 14px; }
"""


@app.get("/login", response_class=HTMLResponse)
def login_page(next: str = "/", error: str = ""):
    error_html = f'<div class="login-error">{error}</div>' if error else ""
    return f"""<!doctype html>
<html><head><title>Sign in — EvolveIQ</title><style>{LOGIN_PAGE_CSS}</style></head>
<body>
  <form class="login-card" method="post" action="/login">
    <h1>EvolveIQ Ops</h1>
    <p class="sub">Sign in to continue.</p>
    <input type="hidden" name="next" value="{next}" />
    <label>Username</label>
    <input name="username" autocomplete="username" autofocus required />
    <label>Password</label>
    <input name="password" type="password" autocomplete="current-password" required />
    <button type="submit">Sign in</button>
    {error_html}
  </form>
</body></html>"""


@app.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    next_path = str(form.get("next", "/")) or "/"
    if not auth.check_login(username, password):
        return RedirectResponse(url=f"/login?next={next_path}&error=Wrong+username+or+password", status_code=303)
    response = RedirectResponse(url=next_path, status_code=303)
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.make_session_cookie(username.lower()),
        max_age=auth.SESSION_LIFETIME_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(auth.SESSION_COOKIE)
    return response


ADMIN_USERS_CSS = """
  .users-table { width: 100%; max-width: 560px; border-collapse: collapse; margin-bottom: 28px; }
  .users-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 13.5px; }
  .users-table .remove-btn { background: none; border: 1px solid var(--border); color: var(--danger); border-radius: 6px; padding: 5px 10px; font-size: 12px; cursor: pointer; }
  .users-table .remove-btn:hover { background: var(--accent-soft); }
  .add-user-form { display: flex; gap: 10px; align-items: flex-end; max-width: 560px; }
  .add-user-form > div { flex: 1; }
  .add-user-form label { display: block; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; color: var(--text-dim); margin-bottom: 4px; }
  .add-user-form input { width: 100%; padding: 9px 11px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; background: var(--surface); color: var(--text); font-family: var(--font-body); }
  .add-user-form button { padding: 10px 18px; background: var(--accent); color: var(--on-accent); border: none; border-radius: 8px; font-weight: 700; cursor: pointer; white-space: nowrap; }
  #userFormStatus { margin-top: 10px; font-size: 13px; color: var(--text-dim); }
"""

ADMIN_USERS_JS = """
async function removeUser(username) {
  if (!confirm(`Remove "${username}"? They will not be able to sign in anymore.`)) return;
  const res = await fetch(`/admin/users/${username}`, { method: "DELETE" });
  const data = await res.json();
  if (data.ok) window.location.reload();
  else alert(data.message || "Could not remove user");
}

document.getElementById("addUserForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("userFormStatus");
  const payload = Object.fromEntries(new FormData(e.target).entries());
  status.textContent = "Saving...";
  const res = await fetch("/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (data.ok) {
    window.location.reload();
  } else {
    status.textContent = data.message || "Could not add user";
  }
});
"""


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    users = auth.list_usernames()
    current = getattr(request.state, "username", "")
    rows = "\n".join(
        f"""<tr>
          <td>{u}{' <span style="color:var(--text-faint);font-size:11.5px;">(you)</span>' if u == current else ''}</td>
          <td style="text-align:right;"><button class="remove-btn" onclick="removeUser('{u}')">Remove</button></td>
        </tr>"""
        for u in users
    )
    return f"""<!doctype html>
<html><head><title>Team Accounts — EvolveIQ Ops</title><style>{PAGE_CSS}{ADMIN_USERS_CSS}</style></head>
<body>
  {NAV_HTML}
  <h1>Team Accounts</h1>
  <div class="sub">Everyone who can sign in to this tool. Each account is separate from client-facing logins.</div>

  <table class="users-table">
    <tbody>{rows or '<tr><td colspan="2" class="no-rows">No accounts yet — add one below.</td></tr>'}</tbody>
  </table>

  <h3 style="font-family:var(--font-display); font-size:16px; margin-bottom:14px;">Add someone</h3>
  <form id="addUserForm" class="add-user-form">
    <div>
      <label>Username</label>
      <input name="username" required autocomplete="off" />
    </div>
    <div>
      <label>Password</label>
      <input name="password" type="password" required autocomplete="new-password" />
    </div>
    <button type="submit">Add</button>
  </form>
  <div id="userFormStatus"></div>

  <script>{ADMIN_USERS_JS}</script>
</body></html>"""


@app.post("/admin/users")
async def admin_add_user(request: Request):
    body = await request.json()
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    if not username or not password:
        return JSONResponse({"ok": False, "message": "Username and password are both required"}, status_code=400)
    if len(password) < 8:
        return JSONResponse({"ok": False, "message": "Password must be at least 8 characters"}, status_code=400)
    auth.add_user(username, password)
    return {"ok": True}


@app.delete("/admin/users/{username}")
def admin_remove_user(username: str, request: Request):
    current = getattr(request.state, "username", "")
    if username.strip().lower() == current:
        return JSONResponse({"ok": False, "message": "You can't remove your own account while signed in as it"}, status_code=400)
    if len(auth.list_usernames()) <= 1:
        return JSONResponse({"ok": False, "message": "Can't remove the last remaining account — you'd lock everyone out"}, status_code=400)
    auth.remove_user(username)
    return {"ok": True}


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
        # Inherit this launcher's own environment (ANTHROPIC_API_KEY, RESEND_API_KEY, etc. —
        # on the droplet these come from evolveiq-ops.service's own EnvironmentFile) rather
        # than a hand-picked minimal dict. The old minimal env silently gave every demo/
        # prospect instance started this way (anything not run via the systemd-templated
        # evolveiq-client@.service real clients use) no API key at all — chat "worked" in
        # the sense of not crashing, just always returned the same not-configured message.
        env={**os.environ, "LEADGUARD_DATA_DIR": client["data_dir"]},
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        # Detach into its own session so it survives independently of this launcher
        # process — without this, every client backend it spawns shares the launcher's
        # process group and dies right along with it on every restart (needed for every
        # code deploy), which is exactly what happened locally after the last few fixes.
        start_new_session=True,
    )
    for _ in range(30):
        time.sleep(0.3)
        if is_running(client["port"]):
            if client.get("type") == "demo":
                _touch_last_started(client["id"])
            return {"ok": True, "message": f"{client['name']} started on :{client['port']}"}
    return {"ok": False, "message": f"{client['name']} did not start — check {log_path}"}


def _touch_last_started(client_id: str) -> None:
    """Records when a demo was most recently (re)started, so the auto-stop policy
    below can tell a fresh restart (7-day cap) from the original creation-time
    start (30-day cap) — see _auto_stop_expired_demos()."""
    clients = load_clients()
    now = datetime.now(timezone.utc).isoformat()
    changed = False
    for c in clients:
        if c["id"] == client_id:
            c["last_started_at"] = now
            c.setdefault("created_at", now)
            changed = True
            break
    if changed:
        save_clients(clients)


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


# A demo left running indefinitely burns memory and (on the cloud) real hosting cost
# for no reason once a sales conversation has gone cold — per Larry's call: 30 days
# from its original creation, or just 7 days if someone's manually restarted it since
# (a restart usually means "let me check on this one," not "keep it live for a month").
AUTO_STOP_CHECK_INTERVAL_SECONDS = 1800
DEMO_FIRST_RUN_MAX_DAYS = 30
DEMO_RESTART_MAX_DAYS = 7


async def _auto_stop_expired_demos():
    while True:
        await asyncio.sleep(AUTO_STOP_CHECK_INTERVAL_SECONDS)
        try:
            clients = load_clients()
            now = datetime.now(timezone.utc)
            backfilled = False
            for c in clients:
                if c.get("type") != "demo":
                    continue
                # Older demos (created before this feature existed) have no timestamps —
                # give them a fresh clock starting now rather than treating "unknown" as
                # "already expired."
                if not c.get("created_at"):
                    c["created_at"] = now.isoformat()
                    c["last_started_at"] = now.isoformat()
                    backfilled = True
            if backfilled:
                save_clients(clients)
                clients = load_clients()

            for c in clients:
                if c.get("type") != "demo" or not is_running(c["port"]):
                    continue
                last_started = c.get("last_started_at") or c.get("created_at")
                if not last_started:
                    continue
                started_dt = datetime.fromisoformat(last_started)
                is_first_run = last_started == c.get("created_at")
                cap_days = DEMO_FIRST_RUN_MAX_DAYS if is_first_run else DEMO_RESTART_MAX_DAYS
                if (now - started_dt).days >= cap_days:
                    stop_client(c)
        except Exception:
            pass  # a bad run shouldn't kill the loop — just try again next interval


@app.on_event("startup")
async def _start_background_tasks():
    asyncio.create_task(_auto_stop_expired_demos())


def delete_client_data(client: dict):
    """Best-effort removal of a client's data directory. Refuses to touch anything
    outside BACKEND_DIR or the cloud clients-data root (/opt/evolveiq/clients, used
    for demos migrated to the droplet, which store data_dir as an absolute path
    rather than relative to BACKEND_DIR) — data_dir comes from clients.json, a
    trusted local file, but this stays defensive since the operation is irreversible."""
    data_path = (BACKEND_DIR / client["data_dir"]).resolve()
    allowed_roots = [BACKEND_DIR.resolve(), pathlib.Path("/opt/evolveiq/clients")]
    allowed = False
    for root in allowed_roots:
        try:
            data_path.relative_to(root)
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        return  # outside every allowed root — refuse to touch it
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

    demo_meta_html = ""
    if c.get("type") == "demo" and c.get("created_at"):
        created_dt = datetime.fromisoformat(c["created_at"])
        demo_meta_html = f' &middot; created {created_dt.strftime("%b %-d, %Y")}'
        if running:
            last_started = c.get("last_started_at") or c["created_at"]
            is_first_run = last_started == c["created_at"]
            cap_days = DEMO_FIRST_RUN_MAX_DAYS if is_first_run else DEMO_RESTART_MAX_DAYS
            expires = datetime.fromisoformat(last_started) + timedelta(days=cap_days)
            demo_meta_html += f' &middot; auto-stops {expires.strftime("%b %-d")}'

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
    <div class="card" data-name="{html.escape(c['name'].lower())}">
      <div class="card-head">
        <h3>{c['name']}</h3>
        {status_html}
      </div>
      <div class="card-actions">
        {start_pause_html}
        <a class="btn btn-visitor {'btn-disabled' if not running else ''}" href="{visitor_href}" target="_blank" {disabled}>🌐 Visitor view</a>
        <a class="btn btn-record {'btn-disabled' if not running else ''}" href="{visitor_href}?record=1" target="_blank" {disabled} title="Hides suggested-question bubbles, turns on Option/Alt+1-3 typing hotkeys">🎥 Recording view</a>
        <a class="btn btn-admin {'btn-disabled' if not running else ''}" href="{admin_href}" target="_blank" {disabled}>🔑 Admin view</a>
        <a class="btn btn-client {'btn-disabled' if not running else ''}" href="{client_href}" target="_blank" {disabled}>🗂 Client view</a>
        {promote_html}
        <button class="btn btn-delete" onclick="deleteClient('{c['id']}', '{c['name']}')">🗑 Delete</button>
      </div>
      <div class="card-meta">port :{c['port']} &middot; {visitor_target or "no demo generated yet"} {kb_html}{demo_meta_html}</div>
    </div>"""


PAGE_CSS = """
  :root {
    --bg: #ffffff;
    --surface: #f5f5f7;
    --surface-2: #ebebee;
    --border: rgba(28, 22, 12, 0.12);
    --border-strong: rgba(28, 22, 12, 0.22);
    --text: #1c160c;
    --text-dim: #5b5342;
    --text-faint: #8c8471;
    --accent: #2f5fe0;
    --accent-soft: rgba(47, 95, 224, 0.10);
    --accent-strong: #1b3fae;
    --teal: #4f7a44;
    --teal-soft: rgba(79, 122, 68, 0.12);
    --gold: #a6790a;
    --danger: #c23b3b;
    --ok: #4f7a44;
    --on-accent: #ffffff;
    --font-display: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Helvetica, Arial, sans-serif;
    --font-body: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Helvetica, Arial, sans-serif;
    --font-mono: ui-monospace, 'SF Mono', 'IBM Plex Mono', Menlo, monospace;
    --radius: 12px;
  }

  * { box-sizing: border-box; }
  body {
    font-family: var(--font-body);
    background: var(--bg);
    margin: 0; padding: 32px; color: var(--text); min-height: 100vh;
    -webkit-font-smoothing: antialiased;
  }
  h1 { font-family: var(--font-display); font-weight: 700; margin: 0 0 4px; font-size: 28px; letter-spacing: -0.015em; color: var(--text); animation: rise .5s ease both; }
  .sub { color: var(--text-dim); font-size: 13.5px; margin-bottom: 28px; animation: rise .5s ease both; animation-delay: .05s; }
  .topnav { display: flex; gap: 22px; margin-bottom: 30px; animation: rise .4s ease both; }
  .topnav a { color: var(--text-dim); font-weight: 600; font-size: 12.5px; text-decoration: none; text-transform: uppercase; letter-spacing: .08em; padding-bottom: 4px; border-bottom: 2px solid transparent; transition: color .15s, border-color .15s; }
  .topnav a:hover { color: var(--accent-strong); border-color: var(--accent); }
  .topnav-signout { margin-left: auto; color: var(--text-faint) !important; }
  .filters { display: flex; gap: 12px; margin-bottom: 18px; }
  .filters select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: var(--surface); color: var(--text); font-family: var(--font-body); }
  .search-input { display: block; width: 100%; max-width: 340px; padding: 9px 13px; margin-bottom: 18px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: var(--surface); color: var(--text); font-family: var(--font-body); box-sizing: border-box; }
  .search-input:focus { outline: none; border-color: var(--accent); }
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
  .btn-record { background: #fde68a; color: #92400e; }
  .btn-admin { background: var(--accent-soft); color: var(--accent-strong); }
  .btn-client { background: var(--surface-2); color: var(--text-dim); }
  .btn-disabled { opacity: .4; pointer-events: none; }
  .card-meta { margin-top: 10px; font-size: 11.5px; color: var(--text-faint); font-family: var(--font-mono); }
  .btn-pause { background: rgba(147,112,31,0.16); color: var(--gold); }
  .btn-promote { background: var(--teal-soft); color: var(--teal); }
  .btn-delete { background: var(--accent-soft); color: var(--accent-strong); }
  .stats-strip { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 22px; }
  .stat-tile { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; min-width: 110px; }
  .stat-tile-accent { border-color: var(--accent); background: var(--accent-soft); }
  .stat-value { font-size: 19px; font-weight: 700; color: var(--text); font-family: var(--font-display, var(--font-body)); font-variant-numeric: tabular-nums; }
  .stat-tile-accent .stat-value { color: var(--accent-strong); }
  .stat-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .04em; margin-top: 3px; }
  .stats-compact .stat-tile { min-width: 130px; }
  .view-toggle { display: flex; gap: 4px; margin-bottom: 16px; }
  .view-toggle-btn { background: var(--surface); border: 1px solid var(--border); padding: 7px 14px; font-size: 13px; font-weight: 600; color: var(--text-dim); cursor: pointer; border-radius: 7px; font-family: var(--font-body); }
  .view-toggle-btn.active { color: var(--on-accent); background: var(--accent); border-color: var(--accent); }
  th.sortable { cursor: pointer; user-select: none; }
  th.sortable:hover { color: var(--accent-strong); }
  th.sortable .sort-arrow { opacity: .5; font-size: 10px; margin-left: 3px; }
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

function filterCards(query) {
  const q = query.trim().toLowerCase();
  document.querySelectorAll(".card[data-name]").forEach((card) => {
    card.style.display = !q || card.dataset.name.includes(q) ? "" : "none";
  });
}

"""


NAV_HTML = """
<div class="topnav">
  <a href="/">Clients</a>
  <a href="/outreach">Outreach</a>
  <a href="/support-requests">Support requests</a>
  <a href="/bip-import">BIP import</a>
  <a href="/admin/users">Team accounts</a>
  <a href="/logout" class="topnav-signout">Sign out</a>
</div>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    clients = load_clients()
    client_cards = "\n".join(client_card_html(c) for c in clients if c.get("type") == "client") \
        or '<p class="sub">No clients yet.</p>'
    stats_html = stats_strip_html(compute_sales_stats(), compact=True)
    return f"""<!doctype html>
<html><head><title>LeadGuard Launcher</title><style>{PAGE_CSS}</style></head>
<body>
  {NAV_HTML}
  <h1>Clients</h1>
  <div class="sub">Local control panel — no terminal needed. Bookmark this page. Prospecting and demo generation live under Outreach now.</div>

  <h2 style="font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-faint);margin-bottom:10px;">Sales snapshot</h2>
  {stats_html}
  <a href="/outreach" style="display:inline-block;margin-bottom:24px;color:var(--teal);font-size:12.5px;font-weight:600;text-decoration:underline;">Full sales stats on Outreach →</a>

  <input id="cardSearch" class="search-input" placeholder="Search by name..." oninput="filterCards(this.value)" />

  <div class="grid">{client_cards}</div>

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
    # A deleted demo's Outreach prospect (if any) previously kept pointing at the now-gone
    # instance — client_id referenced nothing and demo_url silently went dead, both easy to
    # miss since nothing about the prospect's own view changed to reflect the deletion.
    if client.get("type") == "demo":
        with outreach_db.db_session() as conn:
            conn.execute(
                "UPDATE prospects SET client_id = NULL, demo_url = NULL, updated_at = ? WHERE client_id = ?",
                (datetime.now(timezone.utc).isoformat(), client_id),
            )
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


@app.api_route("/proxy/{port}/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy_to_client(port: int, path: str, request: Request):
    """Forward a request to a client/demo instance's own backend, so a demo page's
    live widget (loaded from a public demo link, opened by anyone, not just this
    machine) can actually reach it — the instance itself only listens on
    127.0.0.1 and was never meant to be reached directly. Deliberately public (see
    PUBLIC_PATH_PREFIXES) since real prospects hit this when they chat with a demo.

    Restricted to ports this launcher actually knows about via clients.json, not an
    arbitrary port number — this is a scoped relay to registered instances only,
    not an open proxy to anything on localhost."""
    known_ports = {c["port"] for c in load_clients()}
    if port not in known_ports:
        return JSONResponse({"ok": False, "message": "unknown instance"}, status_code=404)

    target = f"http://127.0.0.1:{port}/{path}"
    query = request.url.query
    if query:
        target += f"?{query}"
    body = await request.body()

    req = urllib.request.Request(
        target,
        data=body if body else None,
        method=request.method,
        headers={
            "Content-Type": request.headers.get("content-type", "application/octet-stream"),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            status = resp.status
    except urllib.error.HTTPError as e:
        content = e.read()
        content_type = e.headers.get("Content-Type", "application/octet-stream") if e.headers else "text/plain"
        status = e.code
    except urllib.error.URLError:
        return JSONResponse({"ok": False, "message": "instance not reachable — is it running?"}, status_code=502)

    from fastapi import Response
    return Response(content=content, status_code=status, media_type=content_type)


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
def open_visitor(client_id: str, record: str = ""):
    from fastapi.responses import RedirectResponse
    clients = load_clients()
    client = next((c for c in clients if c["id"] == client_id), None)
    if not client:
        return JSONResponse({"ok": False, "message": "unknown client"}, status_code=404)
    target = client.get("sales_demo") or client.get("widget_demo")
    if not target:
        return JSONResponse({"ok": False, "message": "no demo generated for this client yet"}, status_code=404)
    # record=1 is forwarded straight through to the demo page itself — see
    # demo_template.html's RECORD_MODE flag: hides the suggested-question bubbles and
    # turns on the Option/Alt+1-3 typing hotkeys, for solo screen recording.
    record_suffix = "&record=1" if record == "1" else ""
    # New-style prospect demos (Phase 1, docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md) are
    # written into the prospect's own data_dir and served by that instance's own GET
    # /demo route — recognizable by the "backend/data_..." path generate-demo writes.
    # Clients that predate that architecture (LMTLSS, Evolve) still carry a path under
    # the shared widget/ directory instead; those never get a GET /demo on their own
    # instance, so redirecting there 404s — serve them via the old /file route instead.
    if target.startswith("widget/"):
        return RedirectResponse(f"/file?path={target}{record_suffix}")
    # public_base_for() resolves to the scoped /proxy/{port} relay when EVOLVEIQ_PUBLIC_BASE_URL
    # is set (cloud), localhost otherwise (local dev) — a literal "localhost:{port}" here would
    # redirect the VISITOR'S OWN machine to that port, not the server that generated the link.
    return RedirectResponse(f"{public_base_for(client['port'])}/demo{('?record=1' if record == '1' else '')}")


def _generate_demo(url: str, name: str, client_id: str, industry: str = "", booking_link: str = "", video_source_path: Optional[pathlib.Path] = None, demo_questions: Optional[list] = None) -> dict:
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
        # A stopped template used to be a hard failure with nothing saved anywhere —
        # easy to trigger from a dropdown that gives no hint which entries are running,
        # and easy to miss since the only sign was inline form text. Auto-start it
        # instead, same as the "regenerating an existing prospect" path below already does.
        started = start_client(template)
        if not started["ok"]:
            return {"ok": False, "message": f"{template['name']}'s backend couldn't be started to use as a config template: {started['message']}"}

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
        created_now = datetime.now(timezone.utc).isoformat()
        prospect = {
            "id": prospect_id,
            "name": name,
            "port": next_free_port(clients),
            "data_dir": f"./data_{prospect_id}",
            "accent_color": template.get("accent_color", "#4f46e5"),
            "widget_demo": None,
            "sales_demo": None,
            "type": "demo",
            "created_at": created_now,
            "last_started_at": created_now,
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
                # Powers both the visible suggested-question bubbles and the Option/Alt+1-3
                # recording hotkeys — previously always seeded empty here even when the
                # prospect already had curated questions sitting in demo_questions, which
                # silently left every auto-generated demo's hotkeys with nothing to fire.
                "demo_suggested_questions": (demo_questions or [])[:3],
                "demo_expires_at": (datetime.now(timezone.utc) + timedelta(days=DEMO_LINK_LIFETIME_DAYS)).isoformat(),
                "booking_link": booking_link,
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
            current["booking_link"] = booking_link
            if demo_questions:
                current["demo_suggested_questions"] = demo_questions[:3]
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
            "--api-base", public_base_for(prospect["port"]),
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

    if video_source_path and video_source_path.exists():
        shutil.copy(video_source_path, out_path.parent / "demo_video.mp4")

    rel_path = out_path.relative_to(PROJECT_ROOT)
    prospect["sales_demo"] = str(rel_path)
    clients = [prospect if c["id"] == prospect_id else c for c in load_clients()]
    if not any(c["id"] == prospect_id for c in clients):
        clients.append(prospect)
    save_clients(clients)

    return {
        "ok": True,
        "client_id": prospect_id,
        "open_url": f"{public_base_for(prospect['port'])}/demo",
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


# Research-caveat text the import process sometimes writes directly into
# decision_maker_name when it couldn't confirm a real one (e.g. "Not publicly
# verified in quick scan") — this isn't a name and must never be spoken as one.
_UNVERIFIED_NAME_MARKERS = ("not publicly verified", "not verified")


def _first_name(decision_maker_name: str) -> str:
    """First name only, for scripts ("Hi Tom" not "Hi Tom Crosley") — and for a
    multi-person field ("Tim Tate; Claire Tate Rehmet") just the first person
    listed. Returns "" (caller falls back to "there") for blank or caveat text."""
    if not decision_maker_name:
        return ""
    if any(marker in decision_maker_name.strip().lower() for marker in _UNVERIFIED_NAME_MARKERS):
        return ""
    first_person = decision_maker_name.split(";")[0].strip()
    return first_person.split()[0] if first_person else ""


def _merge_fields(prospect: dict, rep_name: str) -> dict:
    questions = prospect.get("demo_questions") or []
    vertical_code = prospect.get("vertical") or ""
    return {
        "company": prospect.get("company_name") or "",
        "name": _first_name(prospect.get("decision_maker_name") or "") or "there",
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
    rating: Optional[str] = None
    product: Optional[str] = None
    mrr_value: Optional[float] = None
    setup_amount: Optional[float] = None
    lost: Optional[bool] = None
    lost_reason: Optional[str] = None


class ProspectCreate(BaseModel):
    company_name: str
    vertical: str = ""
    city_metro: str = ""
    website: str = ""
    decision_maker_name: str = ""
    decision_maker_role: str = ""
    phone: str = ""
    email_or_contact_url: str = ""
    assigned_rep: str = ""
    notes: str = ""


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


def compute_sales_stats() -> dict:
    with outreach_db.db_session() as conn:
        rows = conn.execute("SELECT status, rating, lost, mrr_value, setup_amount FROM prospects").fetchall()
    open_mrr = closed_mrr = closed_setup = 0.0
    hot_count = lost_count = 0
    by_stage = {s: 0 for s in outreach_db.STAGES}
    for r in rows:
        if r["status"] in by_stage:
            by_stage[r["status"]] += 1
        if r["lost"]:
            lost_count += 1
        if r["rating"] == "hot":
            hot_count += 1
        mrr = r["mrr_value"] or 0
        setup = r["setup_amount"] or 0
        if r["status"] == "Closed":
            closed_mrr += mrr
            closed_setup += setup
        elif not r["lost"]:
            open_mrr += mrr
    return {
        "open_mrr": open_mrr,
        "closed_mrr": closed_mrr,
        "closed_setup": closed_setup,
        "hot_count": hot_count,
        "lost_count": lost_count,
        "by_stage": by_stage,
        "total": len(rows),
    }


def stats_strip_html(stats: dict, compact: bool = False) -> str:
    def money(v):
        return f"${v:,.0f}"
    if compact:
        return f"""<div class="stats-strip stats-compact">
          <div class="stat-tile"><div class="stat-value">{money(stats['open_mrr'])}/mo</div><div class="stat-label">Open pipeline</div></div>
          <div class="stat-tile"><div class="stat-value">{money(stats['closed_mrr'])}/mo</div><div class="stat-label">Closed MRR</div></div>
          <div class="stat-tile"><div class="stat-value">{money(stats['closed_setup'])}</div><div class="stat-label">Setup fees collected</div></div>
          <div class="stat-tile"><div class="stat-value">{stats['hot_count']}</div><div class="stat-label">🔥 Hot leads</div></div>
        </div>"""
    stage_tiles = "".join(
        f'<div class="stat-tile"><div class="stat-value">{stats["by_stage"].get(s, 0)}</div><div class="stat-label">{s}</div></div>'
        for s in outreach_db.STAGES
    )
    return f"""<div class="stats-strip">
      <div class="stat-tile stat-tile-accent"><div class="stat-value">{money(stats['open_mrr'])}/mo</div><div class="stat-label">Open pipeline value</div></div>
      <div class="stat-tile stat-tile-accent"><div class="stat-value">{money(stats['closed_mrr'])}/mo</div><div class="stat-label">Closed MRR</div></div>
      <div class="stat-tile stat-tile-accent"><div class="stat-value">{money(stats['closed_setup'])}</div><div class="stat-label">Setup fees collected</div></div>
      {stage_tiles}
      <div class="stat-tile"><div class="stat-value">{stats['hot_count']}</div><div class="stat-label">🔥 Hot</div></div>
      <div class="stat-tile"><div class="stat-value">{stats['lost_count']}</div><div class="stat-label">Lost</div></div>
    </div>"""


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


@app.post("/api/outreach/prospects")
def create_prospect(prospect: ProspectCreate):
    """Hand-add a single potential-client lead — someone you met, a referral — outside
    the usual bulk-imported list. Starts life in the 'Lead' stage like every other
    prospect; everything the research pipeline would normally fill in (reviews,
    personalization hook, etc.) just starts blank and can be added later."""
    if not prospect.company_name.strip():
        raise HTTPException(400, "Company name is required")
    now = datetime.now(timezone.utc).isoformat()
    with outreach_db.db_session() as conn:
        cursor = conn.execute(
            """INSERT INTO prospects
               (company_name, vertical, city_metro, website, decision_maker_name,
                decision_maker_role, phone, email_or_contact_url, assigned_rep, notes,
                status, cadence_step, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Lead', 1, ?, ?)""",
            (
                prospect.company_name.strip(), prospect.vertical.strip(), prospect.city_metro.strip(),
                prospect.website.strip(), prospect.decision_maker_name.strip(), prospect.decision_maker_role.strip(),
                prospect.phone.strip(), prospect.email_or_contact_url.strip(), prospect.assigned_rep.strip(),
                prospect.notes, now, now,
            ),
        )
        row = conn.execute("SELECT * FROM prospects WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _prospect_row_to_dict(row)


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
    with outreach_db.db_session() as conn:
        rep_row = conn.execute("SELECT booking_link FROM reps WHERE name = ?", (row["assigned_rep"],)).fetchone()
    booking_link = (rep_row["booking_link"] if rep_row else "") or ""
    video_path = PROSPECT_VIDEOS_DIR / f"{prospect_id}.mp4"
    try:
        demo_questions = json.loads(row["demo_questions"] or "[]")
    except json.JSONDecodeError:
        demo_questions = []
    result = _generate_demo(
        url, name, body.client_id, industry=industry,
        booking_link=booking_link,
        video_source_path=video_path if video_path.exists() else None,
        demo_questions=demo_questions,
    )
    if result.get("ok"):
        with outreach_db.db_session() as conn:
            conn.execute(
                "UPDATE prospects SET client_id = ?, demo_url = ?, updated_at = ? WHERE id = ?",
                (result.get("client_id"), result.get("open_url"), datetime.now(timezone.utc).isoformat(), prospect_id),
            )
    return result


MAX_VIDEO_UPLOAD_BYTES = 300 * 1024 * 1024  # generous for a short pitch video; droplet has 42GB free


@app.post("/api/outreach/prospects/{prospect_id}/video")
async def upload_prospect_video(prospect_id: int, file: UploadFile = File(...)):
    with outreach_db.db_session() as conn:
        row = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    if not row:
        return JSONResponse({"ok": False, "message": "unknown prospect"}, status_code=404)
    if file.content_type not in ("video/mp4", "video/quicktime"):
        return JSONResponse({"ok": False, "message": "please upload an MP4 (or MOV) file"}, status_code=400)

    PROSPECT_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROSPECT_VIDEOS_DIR / f"{prospect_id}.mp4"
    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_VIDEO_UPLOAD_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                return JSONResponse({"ok": False, "message": "video is too large (300MB max)"}, status_code=400)
            f.write(chunk)

    with outreach_db.db_session() as conn:
        conn.execute(
            "UPDATE prospects SET has_video = 1, updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), prospect_id),
        )

    # If a demo already exists for this prospect, drop the video straight into its own
    # data dir too — otherwise it'd only show up the next time someone regenerates the
    # demo, which is easy to forget and would silently leave a stale/missing video.
    if row["client_id"]:
        client = next((c for c in load_clients() if c["id"] == row["client_id"]), None)
        if client:
            data_dir = (BACKEND_DIR / client["data_dir"]).resolve()
            if data_dir.exists():
                shutil.copy(dest, data_dir / "demo_video.mp4")

    return {"ok": True, "size": size}


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
    name: Optional[str] = None
    booking_link: Optional[str] = None


@app.get("/api/outreach/template-clients")
def list_template_clients():
    """Real client instances usable as a demo-generation config template — the 'Template
    client id' field used to be free text (easy to typo/mis-case, since it must match
    clients.json's id exactly, not a display name), which is exactly the kind of thing a
    dropdown fixes."""
    return [{"id": c["id"], "name": c["name"]} for c in load_clients() if c.get("type") == "client"]


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
def update_rep(rep_id: int, update: RepUpdate):
    with outreach_db.db_session() as conn:
        existing = conn.execute("SELECT * FROM reps WHERE id = ?", (rep_id,)).fetchone()
        if not existing:
            return JSONResponse({"ok": False, "message": "unknown rep"}, status_code=404)

        if update.name is not None:
            new_name = update.name.strip()
            if not new_name:
                return JSONResponse({"ok": False, "message": "name can't be empty"}, status_code=400)
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

        new_booking_link = None
        if update.booking_link is not None:
            new_booking_link = update.booking_link.strip()
            conn.execute("UPDATE reps SET booking_link = ? WHERE id = ?", (new_booking_link, rep_id))

        row = conn.execute("SELECT * FROM reps WHERE id = ?", (rep_id,)).fetchone()

    if new_booking_link is not None:
        # Push straight into every already-generated demo for this rep's prospects —
        # otherwise a rep updating their link later would leave every existing demo
        # pointing at the old one until someone happens to regenerate it.
        with outreach_db.db_session() as conn:
            assigned = conn.execute(
                "SELECT client_id FROM prospects WHERE assigned_rep = ? AND client_id IS NOT NULL", (row["name"],)
            ).fetchall()
        clients_by_id = {c["id"]: c for c in load_clients()}
        for a in assigned:
            client = clients_by_id.get(a["client_id"])
            if not client or not is_running(client["port"]):
                continue
            try:
                current = fetch_business(client["port"])
                current["booking_link"] = new_booking_link
                put_business(client["port"], current)
            except Exception:
                pass  # non-fatal — link still updates for the next regenerate

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
  .outreach-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(720px, 880px); gap: 20px; align-items: start; }
  .outreach-layout-list { min-width: 0; }
  .table-scroll { overflow-x: auto; }
  .outreach-layout-detail { position: sticky; top: 20px; max-height: calc(100vh - 40px); overflow-y: auto; }
  /* Two-class selector beats .detail-panel's single-class rule regardless of source
     order. Needed because .detail-panel's "rise" keyframe ends on transform:translateY(0)
     — a non-"none" transform makes the element its own containing block, which silently
     breaks position:sticky (it stops tracking the viewport and scrolls away with the
     page instead of staying put). */
  .detail-panel.outreach-layout-detail { animation: none; }
  /* Maximize toggle — same shape as the mobile fallback below: single column, detail
     drops full-width beneath the list instead of sitting sticky alongside it. */
  .outreach-layout.detail-maximized { grid-template-columns: 1fr; }
  .outreach-layout.detail-maximized .outreach-layout-detail { position: static; max-height: none; }
  /* 1200px, not 900px: the detail column's 720px floor plus gap needs ~1040px of
     room before the list column has anything usable left. iPad landscape (up to
     1194pt on 13" Pro) was falling between 900 and that real threshold, squeezing
     the list into an unreadable sliver instead of stacking. */
  @media (max-width: 1200px) {
    .outreach-layout { grid-template-columns: 1fr; }
    .outreach-layout-detail { position: static; max-height: none; }
  }
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
  .video-panel { background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; margin-top: 12px; }
  .video-panel input[type="file"] { display: block; font-size: 12.5px; margin: 8px 0; color: var(--text-dim); }
  .video-panel button { background: var(--accent); color: var(--on-accent); border: none; padding: 8px 14px; border-radius: 7px; font-weight: 700; cursor: pointer; font-family: var(--font-body); font-size: 12.5px; }
  .touch-history { font-size: 12px; color: var(--text-dim); font-family: var(--font-mono); padding-left: 18px; }
  .touch-history li { margin-bottom: 4px; }
  .link-btn { background: none; border: none; color: var(--teal); font-size: 12.5px; font-weight: 600; cursor: pointer; text-decoration: underline; font-family: var(--font-body); padding: 0; margin-left: 4px; }
  .manage-team-panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; margin-bottom: 18px; max-width: 620px; }
  .manage-team-panel h4 { margin: 0 0 10px; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--text-faint); font-weight: 700; }
  .rep-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .rep-name-input { flex: 0 0 130px; padding: 6px 9px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; background: var(--surface-2); color: var(--text); font-family: var(--font-body); }
  .rep-booking-input { flex: 1; padding: 6px 9px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; background: var(--surface-2); color: var(--text); font-family: var(--font-body); }
  .rep-remove-btn { background: var(--accent-soft); color: var(--accent-strong); border: none; border-radius: 6px; padding: 5px 10px; font-size: 11.5px; font-weight: 700; cursor: pointer; }
  .add-rep-form { display: flex; gap: 8px; margin-top: 10px; }
  .add-rep-form input { flex: 1; padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; background: var(--surface-2); color: var(--text); font-family: var(--font-body); }
  .add-rep-form button { background: var(--teal-soft); color: var(--teal); border: none; border-radius: 6px; padding: 7px 14px; font-size: 12.5px; font-weight: 700; cursor: pointer; }
  .outreach-search { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: var(--surface); color: var(--text); font-family: var(--font-body); min-width: 220px; }
  .outreach-board { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(230px, 1fr); gap: 12px; align-items: start; overflow-x: auto; padding-bottom: 8px; }
  .outreach-board[hidden] { display: none; }
  .outreach-col { background: var(--surface-2); border-radius: 10px; padding: 10px; min-height: 120px; }
  .outreach-col h3 { margin: 4px 6px 10px; font-size: 12.5px; color: var(--text-dim); display: flex; justify-content: space-between; font-family: var(--font-body); white-space: nowrap; }
  .outreach-col h3 .count { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1px 8px; font-size: 11px; }
  .outreach-col-cards { display: flex; flex-direction: column; gap: 8px; min-height: 60px; }
  .prospect-card { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px; cursor: grab; font-size: 12.5px; }
  .prospect-card.dragging { opacity: .4; }
  .prospect-card .pc-name { font-weight: 600; color: var(--text); }
  .prospect-card .pc-vertical { color: var(--text-faint); font-size: 11px; }
  .prospect-card .pc-touch { margin-top: 6px; font-size: 11px; color: var(--text-dim); font-family: var(--font-mono); }
  .prospect-card .pc-touch.overdue { color: var(--accent-strong); font-weight: 700; }
  .prospect-card .pc-deal { margin-top: 4px; font-size: 11px; color: var(--teal); font-weight: 600; }
  .prospect-card.lost { opacity: .55; }
  .lost-badge { display: inline-block; font-size: 10px; font-weight: 700; color: #b91c1c; background: #fee2e2; border-radius: 10px; padding: 1px 7px; margin-left: 4px; }
  .deal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; }
  .deal-grid label { font-size: 11px; font-weight: 600; color: var(--text-faint); text-transform: uppercase; letter-spacing: .04em; display: flex; flex-direction: column; gap: 4px; }
  .deal-grid select, .deal-grid input { padding: 8px 10px; border: 1px solid var(--border); border-radius: 7px; font-size: 13px; background: var(--surface-2); color: var(--text); font-family: var(--font-body); text-transform: none; letter-spacing: normal; font-weight: 400; }
  .checkbox-label { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-dim); }
  .add-prospect-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin: 10px 0 16px; }
  .add-prospect-form[hidden] { display: none; }
  .add-prospect-form label { display: block; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; color: var(--text-faint); margin-bottom: 4px; }
  .add-prospect-form input, .add-prospect-form select, .add-prospect-form textarea { width: 100%; padding: 9px 11px; border: 1px solid var(--border); border-radius: 8px; font-size: 13.5px; background: var(--surface); color: var(--text); font-family: var(--font-body); }
  .add-prospect-form textarea { resize: vertical; }
  .add-prospect-form button[type="submit"] { padding: 9px 18px; background: var(--accent); color: var(--on-accent); border: none; border-radius: 8px; font-weight: 700; cursor: pointer; white-space: nowrap; }
"""

OUTREACH_JS = """
let outreachProspects = [];
let selectedProspectId = null;
let OUTREACH_REPS = [];
let outreachSortKey = null;
let outreachSortDir = 1;
document.querySelectorAll("table.prospects th.sortable").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    outreachSortDir = outreachSortKey === key ? -outreachSortDir : 1;
    outreachSortKey = key;
    document.querySelectorAll("table.prospects th.sortable .sort-arrow").forEach((a) => a.remove());
    const arrow = document.createElement("span");
    arrow.className = "sort-arrow";
    arrow.textContent = outreachSortDir === 1 ? "▲" : "▼";
    th.appendChild(arrow);
    renderProspectList();
  });
});

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
  const addRepSel = document.getElementById("addProspectRep");
  if (addRepSel) {
    addRepSel.innerHTML = OUTREACH_REPS.map((r) => `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join("");
    if (saved) addRepSel.value = saved;
  }
}

function toggleAddProspectForm(show) {
  const form = document.getElementById("addProspectForm");
  form.hidden = show === false ? true : !form.hidden ? true : false;
  if (!form.hidden) form.querySelector('[name="company_name"]').focus();
}

document.getElementById("addProspectForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("addProspectStatus");
  const payload = Object.fromEntries(new FormData(e.target).entries());
  status.textContent = "Adding...";
  const res = await fetch("/api/outreach/prospects", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    status.textContent = "Error: " + (data.detail || "could not add lead");
    return;
  }
  e.target.reset();
  toggleAddProspectForm(false);
  status.textContent = "";
  await loadProspects();
  selectProspect(data.id);
});

function renderRepList() {
  const box = document.getElementById("repList");
  if (!box) return;
  box.innerHTML = OUTREACH_REPS.map((r) => `
    <div class="rep-row" data-id="${r.id}">
      <input class="rep-name-input" value="${esc(r.name)}" onblur="renameRep(${r.id}, this.value)" />
      <input class="rep-booking-input" value="${esc(r.booking_link || "")}" placeholder="Booking link (Calendly, etc.)" onblur="updateRepBookingLink(${r.id}, this.value)" />
      <button type="button" class="rep-remove-btn" data-id="${r.id}" data-name="${esc(r.name)}">Remove</button>
    </div>`).join("");
  box.querySelectorAll(".rep-remove-btn").forEach((btn) => {
    btn.addEventListener("click", () => removeRep(Number(btn.dataset.id), btn.dataset.name));
  });
}

async function updateRepBookingLink(id, valueRaw) {
  const value = valueRaw.trim();
  const rep = OUTREACH_REPS.find((r) => r.id === id);
  if (!rep || (rep.booking_link || "") === value) return;
  const res = await fetch(`/api/outreach/reps/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ booking_link: value }),
  });
  const data = await res.json();
  const status = document.getElementById("repFormStatus");
  if (data.ok === false) {
    status.textContent = data.message;
    renderRepList();
    return;
  }
  status.textContent = `Booking link updated for ${data.name}.`;
  await loadReps();
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
  const vSel = document.getElementById("filterVertical");
  if (vSel) {
    const current = vSel.value;
    const verticals = Array.from(new Set(outreachProspects.map((p) => p.vertical).filter(Boolean))).sort();
    vSel.innerHTML = '<option value="">All verticals</option>' + verticals.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
    if (verticals.includes(current)) vSel.value = current;
  }
  renderProspectList();
  renderProspectBoard();
}

function filteredProspects() {
  const q = (document.getElementById("outreachSearch")?.value || "").trim().toLowerCase();
  const vertical = document.getElementById("filterVertical")?.value || "";
  return outreachProspects.filter((p) => {
    const verticalMatch = !vertical || p.vertical === vertical;
    const searchMatch = !q || [p.company_name, p.vertical, p.decision_maker_name, p.city_metro].some((v) => (v || "").toLowerCase().includes(q));
    return verticalMatch && searchMatch;
  });
}
document.getElementById("outreachSearch")?.addEventListener("input", () => {
  renderProspectList();
  renderProspectBoard();
});
document.getElementById("filterVertical")?.addEventListener("change", () => {
  renderProspectList();
  renderProspectBoard();
});

function showOutreachView(view) {
  document.querySelectorAll(".outreach-view-toggle .view-toggle-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.getElementById("outreachListView").hidden = view !== "list";
  document.getElementById("outreachBoardView").hidden = view !== "board";
}

function renderProspectList() {
  const tbody = document.getElementById("prospectListBody");
  let rows = filteredProspects();
  if (outreachSortKey) {
    rows = rows.slice().sort((a, b) => {
      const av = (a[outreachSortKey] || "").toString().toLowerCase();
      const bv = (b[outreachSortKey] || "").toString().toLowerCase();
      return av < bv ? -outreachSortDir : av > bv ? outreachSortDir : 0;
    });
  }
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="no-rows">No prospects match this filter.</td></tr>';
    return;
  }
  const now = new Date();
  tbody.innerHTML = rows.map((p, i) => {
    const overdue = p.next_touch_at && new Date(p.next_touch_at) < now;
    const delay = Math.min(i * 0.025, 0.4);
    return `<tr class="${p.id === selectedProspectId ? 'selected' : ''}" style="animation-delay:${delay}s" onclick="selectProspect(${p.id})">
      <td><strong>${esc(p.company_name)}</strong></td>
      <td>${esc(p.vertical) || "—"}</td>
      <td>${p.rating ? esc(RATING_LABELS[p.rating] || p.rating) : "—"}</td>
      <td>${p.product ? esc(p.product) : "—"}${p.mrr_value ? ` · $${p.mrr_value}/mo` : ""}${p.setup_amount ? ` · $${p.setup_amount} setup` : ""}</td>
      <td><span class="cadence-badge">Day ${p.cadence_step}</span></td>
      <td><span class="next-touch ${overdue ? 'overdue' : ''}">${fmtDate(p.next_touch_at)}</span></td>
      <td>${esc(p.status)}${p.lost ? ' <span class="lost-badge">Lost</span>' : ""}</td>
    </tr>`;
  }).join("");
}

const OUTREACH_STAGES = ["Lead", "Prospect", "Demo Performed", "Client Agreement", "Closed"];
const RATING_LABELS = { "": "Not rated", not_interested: "Not interested", interested: "Interested", hot: "🔥 Hot" };
const PRODUCT_OPTIONS = ["", "Core", "Lead Launch", "Website Only", "Other"];
// Starting-point pricing per docs/LEAD_LAUNCH_STRATEGY.md and the published pricing
// card — Core defaults to its published floor ($99/$399); Lead Launch is $0 MRR for
// the free 60-day trial with a $375 build fee; Website Only is the post-trial
// hosting-only path ($50/mo, same $375 build). All editable after prefill — this is
// just a starting point, not a locked price.
const PRODUCT_DEFAULTS = {
  "Core": { mrr: 99, setup: 399 },
  "Lead Launch": { mrr: 0, setup: 375 },
  "Website Only": { mrr: 50, setup: 375 },
};

const RATING_DOT = { not_interested: "⚪", interested: "🟡", hot: "🔥" };

function prospectCardHtml(p) {
  const overdue = p.next_touch_at && new Date(p.next_touch_at) < new Date();
  const deal = [p.product, p.mrr_value ? `$${p.mrr_value}/mo` : "", p.setup_amount ? `$${p.setup_amount} setup` : ""]
    .filter(Boolean).join(" · ");
  return `
    <div class="prospect-card ${p.lost ? 'lost' : ''}" draggable="true" data-id="${p.id}" onclick="selectProspect(${p.id})">
      <div class="pc-name">${RATING_DOT[p.rating] || ""} ${esc(p.company_name)} ${p.lost ? '<span class="lost-badge">Lost</span>' : ""}</div>
      <div class="pc-vertical">${esc(p.vertical)}${p.city_metro ? " · " + esc(p.city_metro) : ""}</div>
      ${deal ? `<div class="pc-deal">${esc(deal)}</div>` : ""}
      <div class="pc-touch ${overdue ? 'overdue' : ''}">Day ${p.cadence_step} · next ${fmtDate(p.next_touch_at)}</div>
    </div>`;
}

function renderProspectBoard() {
  const board = document.getElementById("outreachBoardView");
  if (!board) return;
  const rows = filteredProspects();
  board.innerHTML = OUTREACH_STAGES.map((stage) => {
    const inCol = rows.filter((p) => p.status === stage);
    return `<div class="outreach-col" data-status="${esc(stage)}">
      <h3>${esc(stage)} <span class="count">${inCol.length}</span></h3>
      <div class="outreach-col-cards" data-status="${esc(stage)}">
        ${inCol.map(prospectCardHtml).join("") || '<p class="muted board-empty">Nothing here.</p>'}
      </div>
    </div>`;
  }).join("");

  board.querySelectorAll(".prospect-card").forEach((card) => {
    card.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", card.dataset.id);
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
  });
  board.querySelectorAll(".outreach-col-cards").forEach((col) => {
    col.addEventListener("dragover", (e) => e.preventDefault());
    col.addEventListener("drop", async (e) => {
      e.preventDefault();
      const id = e.dataTransfer.getData("text/plain");
      if (!id) return;
      await updateStatus(Number(id), col.dataset.status);
    });
  });
}

async function selectProspect(id) {
  selectedProspectId = id;
  renderProspectList();
  const res = await fetch(`/api/outreach/prospects/${id}`);
  const p = await res.json();
  renderProspectDetail(p);
}

let detailMaximized = false;
function toggleDetailMaximized() {
  detailMaximized = !detailMaximized;
  document.querySelector(".outreach-layout")?.classList.toggle("detail-maximized", detailMaximized);
  const btn = document.getElementById("detailMaximizeBtn");
  if (btn) btn.textContent = detailMaximized ? "⤡ Restore" : "⛶ Maximize";
}

function renderProspectDetail(p) {
  const panel = document.getElementById("prospectDetail");
  panel.className = "detail-panel outreach-layout-detail";
  document.querySelector(".outreach-layout")?.classList.toggle("detail-maximized", detailMaximized);
  const questions = (p.demo_questions || []).map((q) => `<li>${esc(q)}</li>`).join("");
  const scripts = (p.scripts || []).map((s, i) => `
    <div class="script-card" style="animation-delay:${i * 0.06}s">
      <div class="script-head">
        <span class="script-title">${esc(s.title)}</span>
        <button class="copy-btn" onclick="copyScript(this)">Copy</button>
      </div>
      <pre>${esc(s.body)}</pre>
    </div>`).join("") || '<div class="sub">No script for this step yet.</div>';
  const videoSection = `<div class="video-panel">
      <div class="sub">${p.has_video ? "✅ Video uploaded — shows on the demo page automatically." : "No pitch video yet — optional."}</div>
      <input type="file" id="videoFileInput" accept="video/mp4,video/quicktime" />
      <button type="button" onclick="uploadProspectVideo(${p.id})">${p.has_video ? "Replace video" : "Upload video"}</button>
      <div id="videoUploadStatus" class="sub" style="margin-top:6px;"></div>
    </div>`;
  const demoForm = `<div class="demo-panel" id="demoForm" ${p.demo_url ? "hidden" : ""}>
        <label style="font-size:11px;font-weight:600;color:var(--text-faint);text-transform:uppercase;letter-spacing:.04em;">Website to demo</label>
        <input id="demoUrl" value="${esc(p.website)}" />
        <label style="font-size:11px;font-weight:600;color:var(--text-faint);text-transform:uppercase;letter-spacing:.04em;">Business name</label>
        <input id="demoName" value="${esc(p.company_name)}" />
        <label style="font-size:11px;font-weight:600;color:var(--text-faint);text-transform:uppercase;letter-spacing:.04em;">Template client (config to start from)</label>
        <select id="demoClientId"><option value="">Loading…</option></select>
        <button onclick="createDemo(${p.id})">${p.demo_url ? "Regenerate demo" : "Create demo"}</button>
        <div id="demoStatus" class="sub" style="margin-top:6px;"></div>
      </div>`;
  const demoSection = p.demo_url
    ? `<div class="demo-link-box">Live demo: <a href="${p.demo_url}" target="_blank">${p.demo_url}</a>
        &nbsp;<button class="copy-btn" onclick="copyPlain('${p.demo_url}')">Copy link</button>
        &nbsp;<button type="button" class="link-btn" onclick="document.getElementById('demoForm').hidden = !document.getElementById('demoForm').hidden">🔄 Regenerate (picks up the latest template)</button>
      </div>${demoForm}`
    : demoForm;
  const touches = (p.touches || []).map((t) =>
    `<li>${fmtDate(t.created_at)} — ${esc(t.channel)}${t.outcome ? ': ' + esc(t.outcome) : ''}</li>`
  ).join("") || "<li>No touches logged yet.</li>";

  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
      <div>
        <h2>${esc(p.company_name)}</h2>
        <div class="sub">${esc(p.vertical)} · ${esc(p.city_metro)} · Score ${p.score ?? "—"} · Priority #${p.priority_rank ?? "—"}</div>
      </div>
      <button type="button" id="detailMaximizeBtn" class="link-btn" style="white-space:nowrap;" onclick="toggleDetailMaximized()">${detailMaximized ? "⤡ Restore" : "⛶ Maximize"}</button>
    </div>

    <div class="detail-section">
      <select class="status-select-lg" id="statusSelect" onchange="updateStatus(${p.id}, this.value)">
        ${OUTREACH_STAGES.map(
          (s) => `<option value="${s}" ${s === p.status ? "selected" : ""}>${s}</option>`
        ).join("")}
      </select>
      &nbsp;assigned to
      <select class="status-select-lg" id="repAssignSelect" onchange="updateAssignedRep(${p.id}, this.value)">
        ${OUTREACH_REPS.map((r) => `<option value="${esc(r.name)}" ${r.name === p.assigned_rep ? "selected" : ""}>${esc(r.name)}</option>`).join("")}
      </select>
      &nbsp;
      <select class="status-select-lg" id="ratingSelect" onchange="updateProspectField(${p.id}, 'rating', this.value)">
        ${Object.entries(RATING_LABELS).map(([v, l]) => `<option value="${v}" ${v === (p.rating || "") ? "selected" : ""}>${l}</option>`).join("")}
      </select>
    </div>

    <div class="detail-section">
      <h4>Deal</h4>
      <div class="deal-grid">
        <label>Product
          <select id="productSelect" onchange="onProductSelectChange(${p.id}, this.value)">
            ${PRODUCT_OPTIONS.map((o) => `<option value="${esc(o)}" ${o === (PRODUCT_OPTIONS.includes(p.product) ? p.product : "Other") ? "selected" : ""}>${o || "— choose —"}</option>`).join("")}
          </select>
        </label>
        <label id="productCustomLabel" ${PRODUCT_OPTIONS.includes(p.product) && p.product !== "Other" ? 'hidden' : ''}>Custom product name
          <input id="productCustomInput" value="${PRODUCT_OPTIONS.includes(p.product) ? '' : esc(p.product)}" onblur="updateProspectField(${p.id}, 'product', this.value)" />
        </label>
        <label>MRR ($/mo)
          <input id="mrrInput" type="number" step="1" min="0" value="${p.mrr_value ?? ''}" onblur="updateProspectField(${p.id}, 'mrr_value', this.value === '' ? null : Number(this.value))" />
        </label>
        <label>Setup fee ($)
          <input id="setupInput" type="number" step="1" min="0" value="${p.setup_amount ?? ''}" onblur="updateProspectField(${p.id}, 'setup_amount', this.value === '' ? null : Number(this.value))" />
        </label>
      </div>
      <label class="checkbox-label" style="margin-top:10px;">
        <input type="checkbox" ${p.lost ? "checked" : ""} onchange="updateProspectField(${p.id}, 'lost', this.checked)" /> Marked lost
      </label>
      ${p.lost ? `<textarea class="notes-box" placeholder="Why was this lost?" onblur="updateProspectField(${p.id}, 'lost_reason', this.value)">${esc(p.lost_reason)}</textarea>` : ""}
      ${p.status === "Closed" && p.client_id ? `<button type="button" style="margin-top:10px;" onclick="pushToClient('${p.client_id}', '${esc(p.company_name)}')">Push to Client →</button>` : ""}
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
      ${videoSection}
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

  const demoClientSelect = document.getElementById("demoClientId");
  if (demoClientSelect) loadTemplateClients(demoClientSelect);
}

let TEMPLATE_CLIENTS_CACHE = null;
async function loadTemplateClients(select) {
  if (!TEMPLATE_CLIENTS_CACHE) {
    const res = await fetch("/api/outreach/template-clients");
    TEMPLATE_CLIENTS_CACHE = await res.json();
  }
  select.innerHTML = TEMPLATE_CLIENTS_CACHE.length
    ? TEMPLATE_CLIENTS_CACHE.map((c) => `<option value="${esc(c.id)}">${esc(c.name)} (${esc(c.id)})</option>`).join("")
    : '<option value="">No running clients yet</option>';
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
  if (status === "Closed") {
    const p = outreachProspects.find((x) => x.id === id);
    if (p && p.client_id) {
      if (confirm(`Push ${p.company_name}'s demo to a real client now?`)) {
        await pushToClient(p.client_id, p.company_name);
      }
    }
  }
  loadProspects();
}

async function pushToClient(clientId, name) {
  const res = await fetch(`/promote/${clientId}`, { method: "POST" });
  const data = await res.json();
  if (!data.ok) alert(data.message || `Could not push ${name} to client status`);
}

async function onProductSelectChange(id, value) {
  const customLabel = document.getElementById("productCustomLabel");
  if (value === "Other") {
    if (customLabel) customLabel.hidden = false;
    document.getElementById("productCustomInput")?.focus();
    return;
  }
  if (customLabel) customLabel.hidden = true;
  await updateProspectField(id, "product", value, { skipReload: true, skipDetailReload: true });
  const defaults = PRODUCT_DEFAULTS[value];
  if (defaults) {
    const mrrInput = document.getElementById("mrrInput");
    const setupInput = document.getElementById("setupInput");
    if (mrrInput) mrrInput.value = defaults.mrr;
    if (setupInput) setupInput.value = defaults.setup;
    await updateProspectField(id, "mrr_value", defaults.mrr, { skipReload: true, skipDetailReload: true });
    await updateProspectField(id, "setup_amount", defaults.setup);
  } else {
    loadProspects();
  }
}

async function updateProspectField(id, field, value, opts) {
  opts = opts || {};
  await fetch(`/api/outreach/prospects/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [field]: value }),
  });
  if (!opts.skipReload) loadProspects();
  if (selectedProspectId === id && !opts.skipDetailReload) selectProspect(id);
}

async function updateAssignedRep(id, assigned_rep) {
  const p = outreachProspects.find((x) => x.id === id);
  const priorRep = p?.assigned_rep;
  const patch = { assigned_rep };
  if (priorRep && assigned_rep && priorRep !== assigned_rep) {
    const stamp = new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" });
    const line = `— Reassigned from ${priorRep} to ${assigned_rep} (${stamp}) —`;
    patch.notes = p.notes ? `${p.notes}\n${line}` : line;
  }
  await fetch(`/api/outreach/prospects/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
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

async function uploadProspectVideo(id) {
  const input = document.getElementById("videoFileInput");
  const status = document.getElementById("videoUploadStatus");
  if (!input.files.length) {
    status.textContent = "Choose a file first.";
    return;
  }
  status.textContent = "Uploading...";
  const formData = new FormData();
  formData.append("file", input.files[0]);
  const res = await fetch(`/api/outreach/prospects/${id}/video`, { method: "POST", body: formData });
  const data = await res.json();
  if (data.ok) {
    selectProspect(id);
  } else {
    status.textContent = "Error: " + data.message;
  }
}

document.getElementById("repSelect")?.addEventListener("change", loadProspects);
document.getElementById("statusFilter")?.addEventListener("change", loadProspects);
"""


@app.get("/outreach", response_class=HTMLResponse)
def outreach_page():
    status_options = "".join(f'<option value="{s}">{s}</option>' for s in outreach_db.STAGES)
    demo_clients = [c for c in load_clients() if c.get("type") == "demo"]
    demo_cards = "\n".join(client_card_html(c) for c in demo_clients) \
        or '<p class="sub">No demo instances yet — create one from a prospect below.</p>'
    stats_html = stats_strip_html(compute_sales_stats())
    return f"""<!doctype html>
<html><head><title>Outreach — LeadGuard Launcher</title><style>{PAGE_CSS}</style><style>{OUTREACH_CSS}</style></head>
<body>
  {NAV_HTML}
  <h1>Outreach</h1>
  <div class="sub">Work your assigned prospects — scripts, cadence, and demo creation in one place.</div>

  {stats_html}

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

  <div class="view-toggle outreach-view-toggle">
    <button type="button" class="view-toggle-btn active" data-view="list" onclick="showOutreachView('list')">☰ List</button>
    <button type="button" class="view-toggle-btn" data-view="board" onclick="showOutreachView('board')">▦ Board (by stage)</button>
    <button type="button" class="view-toggle-btn" onclick="toggleAddProspectForm()">+ Add lead</button>
  </div>
  <div class="filters">
    <input id="outreachSearch" class="outreach-search" placeholder="Search prospects by name, vertical, metro, decision-maker..." />
    <select id="filterVertical"><option value="">All verticals</option></select>
  </div>

  <form id="addProspectForm" class="add-prospect-form" hidden>
    <div><label>Company name</label><input name="company_name" required /></div>
    <div><label>Vertical</label><input name="vertical" placeholder="e.g. HVAC" /></div>
    <div><label>City / metro</label><input name="city_metro" /></div>
    <div><label>Website</label><input name="website" placeholder="https://" /></div>
    <div><label>Decision-maker name</label><input name="decision_maker_name" /></div>
    <div><label>Decision-maker role</label><input name="decision_maker_role" /></div>
    <div><label>Phone</label><input name="phone" /></div>
    <div><label>Email / contact URL</label><input name="email_or_contact_url" /></div>
    <div><label>Assign to</label>
      <select name="assigned_rep" id="addProspectRep"></select>
    </div>
    <div style="flex:1 1 100%;"><label>Notes</label><textarea name="notes" rows="2" placeholder="How you met them, context so far..."></textarea></div>
    <div style="display:flex;gap:8px;align-items:center;">
      <button type="submit">Add lead</button>
      <button type="button" class="link-btn" onclick="toggleAddProspectForm(false)">Cancel</button>
      <span id="addProspectStatus" class="sub"></span>
    </div>
  </form>

  <div class="outreach-layout">
    <div class="outreach-layout-list">
      <div id="outreachListView" class="table-scroll">
        <table class="prospects">
          <thead><tr>
            <th class="sortable" data-sort="company_name">Company</th>
            <th class="sortable" data-sort="vertical">Vertical</th>
            <th class="sortable" data-sort="rating">Rating</th>
            <th>Deal</th>
            <th>Cadence</th><th>Next touch</th><th>Status</th>
          </tr></thead>
          <tbody id="prospectListBody"><tr><td colspan="7" class="no-rows">Loading...</td></tr></tbody>
        </table>
      </div>
      <div id="outreachBoardView" class="outreach-board" hidden></div>
    </div>

    <div id="prospectDetail" class="detail-empty outreach-layout-detail">Select a prospect to see their script and log a touch.</div>
  </div>

  <h2 style="margin-top:40px;">Demo instances</h2>
  <div class="sub">Every demo generated from a prospect above — start, pause, delete, or promote to a real client.</div>
  <input id="demoSearch" class="search-input" placeholder="Search demos by name..." oninput="filterCards(this.value)" />
  <div class="grid">{demo_cards}</div>

  <script>{PAGE_JS}</script>
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
