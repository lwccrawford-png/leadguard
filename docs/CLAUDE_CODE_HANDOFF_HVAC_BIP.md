# Claude Code Handoff — HVAC BIP And LeadGuard Fit

Created: 2026-08-01

## Context

LeadGuard is a managed AI front-desk and lead-qualification widget for small business websites.

Current v1 configuration model:

1. Knowledge base: site crawl + manual sources.
2. Scheduling link.
3. Lead handoff destination: webhook/email.
4. Free-form conversational script.

Current structured knowledge layer:

- `business_facts`: label/value rows, always included in the prompt.
- `faqs`: question/answer/category/priority rows, matched before general retrieval.

Do not redesign the product around the BIP. Treat BIPs as onboarding/setup accelerators that make v1 faster to configure and easier to sell.

## What Was Added

### GTM / Packaging

See:

- `docs/GTM_AND_BIP_PRIORITY.md`

Key decisions:

- Keep the $99/month Core tier focused on answering, qualifying, capturing, notifying, and basic lead visibility.
- Do not bundle Pipeline into the $99 Core tier.
- Keep Pipeline as a paid add-on for longer follow-up, sales, membership, onboarding, or post-lead workflows.
- Use BIPs to make vertical setup faster without changing the product architecture.

### First V1-Compatible BIP

See:

- `onboarding/bips/hvac.md`

This is the drop-in LeadGuard version of the HVAC BIP. It matches the current product shape:

- Flow script using `{{PLACEHOLDER}}` variables.
- Facts table rows.
- FAQ table rows.
- Implementation notes.
- Suggested Pipeline stages only if the add-on is enabled.
- Demo scenario.

This file is the primary version to use for near-term onboarding and demos.

### Full HVAC BIP Reference Package

See:

- `onboarding/bips/hvac_json/`

This folder contains the larger production-style HVAC BIP reference package:

- `manifest.json`
- `knowledge/`
- `workflows/`
- `schemas/`
- `conversation/`
- `analytics/`
- `docs/`
- `onboarding/`
- `testing/`

These files are not meant to be ingested directly by LeadGuard v1 yet. They are source material for:

- Better future BIP templates.
- Future structured modules.
- Future qualification logic.
- Future reporting/KPI definitions.
- Future prompt and escalation improvements.

## How The HVAC BIP Should Fit Into The Build

### Now: No Product Rebuild

For v1, use `onboarding/bips/hvac.md` manually during client setup:

1. Paste the Flow Script into Settings -> conversational script.
2. Add the Facts rows to Knowledge -> Facts.
3. Add the FAQs rows to Knowledge -> FAQs.
4. Fill placeholders from `onboarding/INTAKE_FORM.md` and the onboarding call.
5. Crawl the client site as usual.
6. Add any client-specific policies, pricing, services, and exceptions manually.

This gives LeadGuard a vertical-aware HVAC setup without changing database schema, chat tools, retrieval, or dashboard architecture.

### Near-Term Improvement: BIP Import Helper

The best product upgrade is a small admin/operator feature, not a rebuild:

- Add a "Load BIP Template" operator workflow that reads a BIP source file and pre-populates:
  - flow script draft,
  - facts,
  - FAQs.

This can be implemented as an internal helper script or dashboard operator button later. It should not require changing the visitor widget or the chat engine.

Suggested first implementation shape:

- Store v1-compatible BIPs in `onboarding/bips/*.md` or a future `onboarding/bips/*.json`.
- Parse only the v1-compatible sections:
  - Flow Script
  - Facts
  - FAQs
- Leave placeholders intact until a real intake form supplies values.
- Require human review before writing to a client instance.

### Later: Structured BIP Modules

Only after enough paying-client evidence exists, consider promoting selected BIP concepts into product data modules:

- Services catalog.
- Qualification rules.
- Escalation rules.
- CTA definitions.
- KPI/reporting templates.
- Vertical-specific prompt fragments.

Do not implement those now unless explicitly approved. They would expand schema and product scope.

## Product Tier Guidance

### $99 Core Tier

Should feel like a no-brainer for average small businesses.

Include:

- Website chat widget.
- Site crawl and manual knowledge.
- Facts and FAQs.
- One vertical BIP starter template during setup.
- Scheduling link.
- Email/webhook lead handoff.
- Basic Leads board: New / Claimed / Done.
- Conversation history.
- Basic support request channel.

Do not include:

- Full configurable Pipeline board.
- Deep CRM replacement behavior.
- Live booking API.
- Live dispatching.
- External CRM writeback.
- Phone answering.

### Pipeline Add-On

Pipeline remains the upsell.

Use it for:

- Longer sales process.
- Membership/onboarding process.
- Multi-step follow-up.
- Won/lost tracking.
- Custom stages.
- Lead promotion from Leads board.

Positioning:

Core captures and organizes new opportunities. Pipeline manages what happens after the lead is claimed.

## First 5 BIPs To Build

Priority order:

1. HVAC / Home Comfort
2. Roofing / Exterior Contractors
3. Med Spa / Aesthetic Clinics
4. Auto Repair / Specialty Automotive Service
5. Credit Repair / Professional Financial Services

The next BIP should follow the same structure as `onboarding/bips/hvac.md` before any code changes are considered.

## Guardrails

Do not read or reference:

- `ops/CLIENT_DIRECTORY.md`
- `ops/clients.json`
- `backend/.env`

Do not overstate maturity:

- LeadGuard v1 does not do live booking.
- LeadGuard v1 does not answer phone calls.
- LeadGuard v1 does not push directly into external CRMs except through generic webhook/email handoff.
- LeadGuard v1 does not ingest the full JSON BIP as structured runtime logic.

Do not hardcode HVAC behavior into the product.

BIPs should remain configuration assets until there is enough customer evidence to justify structured product modules.

