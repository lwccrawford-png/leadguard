"""Parse a v1-compatible BIP markdown file (onboarding/bips/*.md) into structured
data the Fast BIP Import tool can render as a fill-in form and write to a client.

Deliberately only understands the sections a BIP actually needs for LeadGuard v1 —
Flow Script, Facts, FAQs — per docs/CLAUDE_CODE_HANDOFF_HVAC_BIP.md's guardrail that
the richer hvac_json/ reference packs are NOT meant to be ingested by this tool.
"""
import re


def parse_bip(path) -> dict:
    text = open(path, encoding="utf-8").read()

    title_match = re.search(r"^#\s*BIP:\s*(.+)$", text, re.MULTILINE)
    version_match = re.search(r"^Version:\s*(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem
    version = version_match.group(1).strip() if version_match else "1.0"

    flow_script = _extract_flow_script(text)
    facts = _extract_table(text, "## Facts", ["label", "value"])
    faqs = _extract_table(text, "## FAQs", ["question", "answer", "category", "priority"])
    for f in faqs:
        try:
            f["priority"] = int(f["priority"])
        except (ValueError, TypeError):
            f["priority"] = 0

    placeholder_text = flow_script + " ".join(
        v for row in facts for v in row.values()
    ) + " ".join(v for row in faqs for v in (row.get("question", ""), row.get("answer", "")))
    placeholders = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", placeholder_text)))

    return {
        "title": title,
        "version": version,
        "flow_script": flow_script,
        "facts": facts,
        "faqs": faqs,
        "placeholders": placeholders,
    }


def _section(text: str, heading: str) -> str:
    """Return the text between `heading` and the next '## ' heading (or EOF)."""
    start = text.find(heading)
    if start == -1:
        return ""
    start += len(heading)
    next_heading = text.find("\n## ", start)
    return text[start:next_heading if next_heading != -1 else len(text)]


def _extract_flow_script(text: str) -> str:
    section = _section(text, "## Flow Script")
    match = re.search(r"```(?:text)?\n(.*?)```", section, re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_table(text: str, heading: str, columns: list) -> list:
    section = _section(text, heading)
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or set(cells[0]) <= {"-", ":"}:
            continue  # header separator row like |---|---|
        if len(cells) >= 1 and cells[0].lower() == columns[0]:
            continue  # header row itself
        row = {columns[i]: cells[i] if i < len(cells) else "" for i in range(len(columns))}
        rows.append(row)
    return rows


def substitute(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def list_bips(bips_dir) -> list:
    """List available v1-compatible BIPs (top-level *.md files only — hvac_json/ and
    similar reference-pack directories are explicitly out of scope, per the handoff doc)."""
    out = []
    for path in sorted(bips_dir.glob("*.md")):
        try:
            parsed = parse_bip(path)
            out.append({"id": path.stem, "title": parsed["title"], "version": parsed["version"]})
        except Exception:
            continue
    return out
