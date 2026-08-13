# BIP Authoring Guide — Handoff for Codex

Written 2026-08-13, after fixing the first Codex-authored BIP
(`personal_injury_premium.md`) to work with the live import tool. This is the
format spec to write against going forward — follow it and a new BIP should
work in `/bip-import` immediately, no fix-up round-trip needed.

## What a BIP actually is

A single markdown file in `onboarding/bips/*.md` in the `leadguard` repo.
It gets parsed by `ops/bip_parser.py` and rendered in a fill-in-the-blanks
form at `/bip-import` (part of `ops/launcher_server.py`, the local admin
tool). An operator picks a BIP, fills in `{{PLACEHOLDER}}` values from a
real client's intake info, previews the result, and applies it — writing
the flow script, facts, and FAQs straight into that client's live
assistant config.

**The parser is intentionally narrow.** It only extracts a few specific
sections by exact heading text. Everything else in the file is fine to
include for human readers (and it should be — rich context is good) but
won't be pulled into the product. The sections below are the ones that
matter mechanically.

## Required structure

```markdown
# BIP: <Human-Readable Title>

Version: <x.y>
Use with: <free text, informational only>
Primary template family: <free text, informational only>

## Flow Script

​```text
<the actual system-prompt-style flow script the assistant will run on.
Use {{PLACEHOLDER}} tokens (all-caps, underscores) for anything that
varies per client — {{BUSINESS_NAME}}, {{SERVICE_AREA}}, {{TONE}}, etc.>
​```

## Facts

| Label | Value |
|---|---|
| Business type | <a real default, or {{PLACEHOLDER}}> |
| Business name | {{BUSINESS_NAME}} |

## FAQs

| Question | Answer | Category | Priority |
|---|---|---:|---:|
| <question a real visitor would ask> | <a real, complete answer, using {{PLACEHOLDER}} where it varies> | <short category label> | <integer, higher = more important> |
```

**Exact rules that will silently break if not followed:**
- The `# BIP:` title line and `Version:` line must be at the very top,
  each on their own line, matching that exact prefix text.
- `## Flow Script` must contain a fenced code block (` ```text ` or plain
  ` ``` `) — the parser only reads what's inside the fence.
- Table header rows must read exactly `| Label | Value |` and
  `| Question | Answer | Category | Priority |` — the parser matches on
  the first column header's text.
- `Priority` must be a plain integer (e.g. `95`, not `"high"`).
- Placeholders must be `{{ALL_CAPS_WITH_UNDERSCORES}}` — same token used
  in the Flow Script, Facts, and FAQs all get filled from one shared form,
  so reuse the same name everywhere it means the same thing.

## Optional section: `## Required Configuration`

For a BIP whose real value is a rich flow script and behavior logic rather
than a static Facts/FAQ list — an intake/routing-style BIP like Personal
Injury Premium is the working example — it's completely fine to have an
empty or near-empty Facts/FAQ table. Add this section instead:

```markdown
## Required Configuration

- Primary jurisdiction and any additional jurisdictions
- Accepted and excluded matter types
- Standard and urgent handoff destinations
```

This renders as a visible checklist in the admin preview UI so whoever
applies the BIP knows what still needs a human decision — instead of the
tool silently showing "0 facts, 0 FAQs" and looking broken. Use a flat
list of plain bullet points (`- item`), one decision per line.

## Everything else is free-form and welcome

Purpose, a Universal Signal Vocabulary, Structured Attribute Vocabulary,
Recommended Routing Rules (JSON blocks), Demo Scenarios, an Operating
Principle — all of this is genuinely useful context and reference material
for whoever configures and demos the BIP later, even though the parser
doesn't ingest it mechanically today. Keep writing it. The
`personal_injury_premium.md` file is a good example of this working well —
its signal vocabulary and demo scenarios didn't get lost, they're just not
auto-applied yet (that's a separate, bigger feature — the "intelligence
routing" backend — not part of this format).

## Where this goes and how it becomes live

1. Write the file as `onboarding/bips/<short_name>.md` (lowercase,
   underscores — matches `hvac.md`, `personal_injury_premium.md`).
2. Commit and push to the `leadguard` repo — a branch is fine, doesn't need
   to be `main` directly.
3. Tell Larry (or Claude Code) it's ready. The Facts/FAQ table gets
   test-parsed against the live `bip_parser.py` and verified end-to-end in
   `/bip-import` before anyone applies it to a real client — that
   verification step catches format mistakes Codex can't check itself
   (no access to run the actual parser), so don't skip it even if the file
   looks right.

## Reference: a fully working example

`onboarding/bips/hvac.md` in this repo is the canonical example of the
minimum viable BIP — title/version header, a complete flow script, 21
facts, 8 FAQs, no Required Configuration section needed because its
knowledge genuinely fits the Facts/FAQ model. Read it before writing a new
BIP from scratch.
