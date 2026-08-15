#!/usr/bin/env python3
"""Generate a one-call-close sales demo: a screenshot of a prospect's real
homepage with a live LeadGuard widget embedded on top.

Usage:
    python3 generate_site_demo.py \
        --url https://prospectsite.com \
        --name "Prospect Business Name" \
        --api-base http://localhost:8006 \
        --color "#4f46e5" \
        --out ../widget/prospect_demo.html

The generated file is fully self-contained (the screenshot is embedded as a
base64 data URI) — safe to send/copy anywhere. It still needs the backend at
--api-base actually running for the widget to respond live; this script only
builds the demo page, it doesn't start any server.
"""
import argparse
import base64
import json
import pathlib
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

def _find_chrome_path() -> str:
    """Locate a Chrome/Chromium binary across macOS (local dev) and Linux (the
    production droplet) — this script needs to run in both places unchanged."""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        # Real Google Chrome (Google's own apt repo) is checked before any snap
        # path — snap-packaged Chromium run as root hits AppArmor/DBus sandbox
        # denials on this droplet and the render pipeline falls apart (confirmed
        # directly: ListActivatableNames AccessDenied, then cascading mojo/zygote
        # errors, then a silent hang with no screenshot produced). Google's .deb
        # package isn't snap-confined and doesn't have this problem.
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        # These are checked last and mostly won't be hit on this droplet, but
        # stay here for other Linux setups where snap isn't the install method
        # (e.g. a plain `apt install chromium` on Debian, not Ubuntu-snap).
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return path
    raise RuntimeError(
        "No Chrome/Chromium binary found. On macOS, install Google Chrome. "
        "On Linux, install real Google Chrome (not the Ubuntu snap, which hits "
        "AppArmor sandbox denials as root) via Google's own apt repo. If it's "
        "installed somewhere not listed here, add its path to _find_chrome_path()."
    )


CHROME_PATH = _find_chrome_path()
# Headless Chromium refuses to start as root (the normal user on the production
# droplet) without this — Chrome's sandbox needs a setuid helper binary that isn't
# set up in that environment. Harmless to always include, including on macOS.
CHROME_SERVER_FLAGS = ["--no-sandbox", "--disable-dev-shm-usage"]
TEMPLATE_PATH = pathlib.Path(__file__).parent / "demo_template.html"
BACKEND_DIR = pathlib.Path(__file__).parent.parent / "backend"

EXTRACT_TOOL = {
    "name": "extract_knowledge",
    "description": "Extract structured facts and FAQs from website content to power a demo AI assistant.",
    "input_schema": {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
                    "required": ["label", "value"],
                },
                "description": "Short standalone facts explicitly stated on the page — phone, hours, "
                "address, certifications, specific numbers/claims. Only include things literally stated "
                "on the page. Never infer, guess, or invent a fact that isn't directly there.",
            },
            "faqs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}, "answer": {"type": "string"}},
                    "required": ["question", "answer"],
                },
                "description": "Common questions a visitor might ask, answered using only what's "
                "actually on the page. If the page doesn't support a good answer, don't invent one — "
                "return fewer FAQs rather than a fabricated one.",
            },
        },
        "required": ["facts", "faqs"],
    },
}


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def screenshot(url: str, width: int, height: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out_path = pathlib.Path(tmp) / "shot.png"
        result = subprocess.run(
            [
                CHROME_PATH,
                "--headless",
                "--disable-gpu",
                *CHROME_SERVER_FLAGS,
                f"--screenshot={out_path}",
                f"--window-size={width},{height}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if not out_path.exists():
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f"Chrome did not produce a screenshot for {url}")
        return out_path.read_bytes()


def render_page_text(url: str) -> str:
    """Render the page with real Chrome (executes JavaScript) and extract the
    visible text — unlike a plain HTTP fetch, this actually sees content on
    JS-rendered sites (React/Vue/Angular-built marketing pages), which a
    simple requests+BeautifulSoup crawl sees as an empty shell.

    --virtual-time-budget doesn't reliably cap wall-clock time on pages with
    third-party embeds that keep making live network calls (a Google Reviews
    widget was observed hanging a render for 3+ minutes at ~4% CPU — waiting
    on network, not doing real work). Chrome's own --timeout flag doesn't
    reliably help either on pages like that; the subprocess timeout below is
    the one mechanism that's actually proven to cut a stuck render short and
    let the pipeline continue non-fatally. Raising it further won't make
    stubborn sites reliable — some will always need the manual BIP fallback
    (see onboarding/bips/), which is the intended v1 workflow, not a last resort."""
    from bs4 import BeautifulSoup

    with tempfile.TemporaryDirectory() as tmp:
        out_path = pathlib.Path(tmp) / "dom.html"
        result = subprocess.run(
            [
                CHROME_PATH, "--headless", "--disable-gpu",
                *CHROME_SERVER_FLAGS,
                "--dump-dom", "--virtual-time-budget=4000",
                url,
            ],
            capture_output=True, text=True, timeout=45,
        )
        if not result.stdout:
            return ""
        soup = BeautifulSoup(result.stdout, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
            tag.decompose()
        lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines() if ln.strip()]
        return "\n".join(lines)


def summarize_to_knowledge(text: str, business_name: str) -> dict:
    """Ask Claude to turn rendered page text into structured facts/FAQs.
    Demo-quality only — deliberately not auto-promoted into a real client's
    permanent knowledge base without human review (see the FAQ 'approved
    answer' model the real product already uses)."""
    import anthropic
    from dotenv import dotenv_values

    env = dotenv_values(BACKEND_DIR / ".env")
    api_key = env.get("ANTHROPIC_API_KEY") or ""
    model = env.get("CLAUDE_MODEL") or "claude-sonnet-4-5"
    if not api_key or not text.strip():
        return {"facts": [], "faqs": []}

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_knowledge"},
        messages=[{
            "role": "user",
            "content": f"Extract structured facts and FAQs from this website content for "
                       f"\"{business_name}\", to power a demo AI assistant. Only use what's "
                       f"explicitly on the page — do not invent or infer anything.\n\n{text[:6000]}",
        }],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    return {"facts": [], "faqs": []}


def populate_knowledge(api_base: str, facts: list, faqs: list) -> tuple:
    facts_added, faqs_added = 0, 0
    for fact in facts:
        try:
            req = urllib.request.Request(
                f"{api_base}/api/knowledge/facts",
                data=json.dumps(fact).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            facts_added += 1
        except Exception:
            pass
    for faq in faqs:
        try:
            req = urllib.request.Request(
                f"{api_base}/api/knowledge/faqs",
                data=json.dumps(faq).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            faqs_added += 1
        except Exception:
            pass
    return facts_added, faqs_added


def fetch_demo_config(api_base: str, business_name_fallback: str) -> dict:
    """Pull the backend's actual configured assistant_name/business name/disclosure/
    suggested questions so the generated demo page matches what's in Settings instead
    of generic fallbacks that never reflect any configuration. disclosure_text and
    demo_suggested_questions are seeded by launcher_server.py's /generate-demo route
    at provisioning time (see docs/PROSPECT_DEMO_ARCHITECTURE_SPEC.md) and editable
    afterward via that instance's own Settings tab."""
    try:
        with urllib.request.urlopen(f"{api_base}/api/business", timeout=5) as resp:
            data = json.loads(resp.read())
    except Exception:
        data = {}

    business_name = data.get("name") or business_name_fallback
    if data.get("assistant_name"):
        greeting = f"Hi! I'm {data['assistant_name']} from {business_name} — ask me anything or book an appointment."
    else:
        greeting = f"Hi! I'm the AI assistant for {business_name} — ask me anything or book an appointment."

    disclosure = data.get("disclosure_text") or (
        f"Demonstration created for {business_name} using publicly available website "
        f"information — not currently affiliated with or deployed by {business_name}."
    )
    questions = data.get("demo_suggested_questions") or []

    return {"greeting": greeting, "disclosure": disclosure, "questions": questions[:3]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="Prospect's real homepage URL to screenshot")
    parser.add_argument("--name", required=True, help="Business name shown in the widget header")
    parser.add_argument("--api-base", required=True, help="Where the LeadGuard backend for this demo is running, e.g. http://localhost:8006")
    parser.add_argument("--color", default="#4f46e5", help="Widget accent color, hex (default: #4f46e5)")
    parser.add_argument("--out", required=True, help="Output HTML file path")
    parser.add_argument("--width", type=int, default=1440, help="Screenshot capture width (default: 1440)")
    parser.add_argument("--height", type=int, default=1400, help="Screenshot capture height (default: 1400)")
    parser.add_argument("--skip-knowledge", action="store_true", help="Skip the AI-generated facts/FAQs step, just do the screenshot+widget")
    args = parser.parse_args()

    print(f"Screenshotting {args.url} ...")
    png_bytes = screenshot(args.url, args.width, args.height)
    data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    if not args.skip_knowledge:
        print("Rendering page and extracting knowledge (demo-quality, not human-reviewed)...")
        try:
            page_text = render_page_text(args.url)
            knowledge = summarize_to_knowledge(page_text, args.name)
            facts_added, faqs_added = populate_knowledge(
                args.api_base, knowledge.get("facts", []), knowledge.get("faqs", [])
            )
            print(f"Added {facts_added} facts and {faqs_added} FAQs to the demo's knowledge base.")
        except Exception as e:
            print(f"Knowledge extraction skipped (non-fatal): {e}", file=sys.stderr)

    demo_config = fetch_demo_config(args.api_base, args.name)

    template = TEMPLATE_PATH.read_text()
    html = (
        template
        .replace("__BUSINESS_NAME__", args.name)
        .replace("__API_BASE__", args.api_base)
        .replace("__ACCENT_COLOR__", args.color)
        .replace("__GREETING__", demo_config["greeting"].replace('"', "&quot;"))
        .replace("__IMAGE_DATA_URI__", data_uri)
        .replace("__DISCLOSURE__", _html_escape(demo_config["disclosure"]))
        .replace("__SUGGESTED_QUESTIONS_JSON__", json.dumps(demo_config["questions"]))
    )

    out_path = pathlib.Path(args.out)
    out_path.write_text(html)
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    print(f"Reminder: the backend at {args.api_base} needs to actually be running for the widget to respond.")


if __name__ == "__main__":
    main()
