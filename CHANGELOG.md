# Changelog

Notable changes to LeadGuard, newest first. Dates are when the work was done, not
necessarily a formal release — this is a single-product, continuously-deployed
codebase, not a versioned library.

## Unreleased

- **GTM strategy and BIP (industry-vertical starter pack) system** — `docs/GTM_AND_BIP_PRIORITY.md`
  lays out positioning, a pricing validation ladder, and the first 5 verticals to target
  (HVAC, roofing, med spa, auto repair, credit repair). `onboarding/bips/hvac.md` is the
  first v1-compatible BIP: a drop-in flow script + facts + FAQs matching the existing
  Settings/Knowledge schema exactly, plus implementation notes and a demo scenario.
  `onboarding/bips/hvac_json/` is a larger reference pack scoped explicitly as future
  material, not for direct ingestion into v1.
- Cross-client **Support Requests admin page** in the launcher (`/support-requests`) —
  aggregates every running client's support requests into one table, filterable by
  client and status, with inline status updates proxied back to the originating
  instance.
- First-party, self-hosted **support-request channel** (`/support` on every client
  instance, no login) — replaces the earlier Google Forms plan with a page that posts
  straight into the client's own database and notifies the agency via the existing
  webhook/email mechanism. Supports an optional screenshot attachment.
- **Configurable product name** — `PRODUCT_NAME` env var now drives the FastAPI app
  title, dashboard header/title, and support page title, so a rebrand is a one-line
  config change instead of a codebase-wide find-and-replace.
- **DigitalOcean deployment prep** (`ops/deploy/`) — Caddy reverse-proxy config,
  systemd template unit, per-client env file convention, a provisioning script, and a
  nightly backup script. Companion to `ops/DEPLOYMENT_PLAN.md`; not yet executed
  against a real server.
- **Demo generator** (`ops/generate_site_demo.py`) — given a prospect's URL, renders
  the page with headless Chrome (fixes JS-rendered sites returning empty content),
  summarizes it into knowledge-base facts/FAQs via Claude with an explicit
  non-hallucination instruction, and produces a ready-to-send demo widget — used for
  the Axel Automotive demo.
- **Launcher control panel** (`ops/launcher_server.py`) — a local always-on page for
  starting/stopping client instances and opening their visitor/client/admin views
  without a terminal; also hosts the demo generator UI and the new Support Requests
  page. The only place cross-client views live, since the product itself stays
  single-tenant per client.
- **Configurable Pipeline board** — a second, business-configurable board (up to 8
  stages, custom labels) for tracking claimed leads through an ongoing sales process,
  distinct from the fixed New/Claimed/Done funnel. Gated behind
  `business.pipeline_enabled`.
- Separate **admin vs. client dashboard views** — the client-facing view now hides
  Settings, Knowledge, and Usage tabs that should only be visible to the product
  owner.

## 2026-07-29

- Structured Layer 1 knowledge: `business_facts` and `faqs` tables, with FAQ-priority
  routing checked before falling back to general knowledge-base retrieval.
- Usage & Performance dashboard view — per-message latency and token-usage capture.
- `discovery_phase` on leads, phase-based recommendation logic in the system prompt,
  and a `capture_lead` tool the assistant calls directly.
- `get_scheduling_link` tool for prefilled booking links.
- Click-to-text (`sms:`) support in the widget's link handling.
- AI-search discoverability: FAQPage schema markup, AI-crawler `robots.txt` check.
- Animated typing indicator, replacing the static "..." placeholder.
- Clickable scheduling links and phone numbers in the widget.
- Mobile touch-target and iOS zoom fixes in the widget.
- V1 architecture/update specs and `CLAUDE.md` added — governing docs for
  product/architecture decisions going forward.

## 2026-07-28

- Initial commit: LeadGuard v1 — trimmed-down rebuild of the original AI front-desk
  scaffold into the current script-driven, scheduling-link, webhook-handoff model.
- Kanban board for lead triage (claim, status, notes); outcome tracking and a
  standing-context field on lead cards.
- Conversation retention purge (90-day) and search/date filtering on the
  Conversations tab.
- Notification email, assistant persona name, and avatar image.
- Per-client monthly message cap and per-session burst rate limiting.
- Support for running multiple isolated client instances from one codebase (the
  `LEADGUARD_DATA_DIR` env var) — the foundation the launcher and deploy scripts
  build on.
- Handoff intents for human requests, complaints, leadership inquiries, and
  unresolved questions.
