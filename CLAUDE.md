# LeadGuard — Project Context

AI front-desk/lead-qualification plugin for small business websites, sold as a
service. Configured per client through four inputs: knowledge base (site scan
+ manual content), scheduling link, handoff webhook/email, and a free-form
conversational script. See `README.md` and `SPEC.md` for the v1 architecture
as originally built.

## Governing specs (read these before making product/architecture decisions)

- **`docs/V1_ARCHITECTURE_SPEC.md`** — how we build: engineering philosophy,
  cost awareness, and the **Business Impact Gate**. Pricing changes, new
  recurring costs, schema/infrastructure changes, and major refactors require
  a Business Impact Analysis and explicit approval before implementation —
  this gate stays active even when working autonomously otherwise.
- **`docs/V1_UPDATE_SPEC.md`** — what we're building toward: three-layer
  knowledge architecture (structured SQL / vector knowledge base / action
  tools), source-priority routing, client profiling, human handoff, admin
  review workflow. Current implementation status is tracked in
  `docs/V1_GAP_ANALYSIS.md`.
- **`docs/PRODUCT_STRATEGY_HANDOFF.md`** — how we talk about it: this is a
  Business Intelligence Platform, not an AI chatbot/agency — AI is the
  interface, the product is the customer's captured business knowledge.
  Governs all marketing/positioning copy (site, pitch decks, outreach) and
  the vocabulary to use/avoid. Its 5-layer architecture is the long-term
  vision, not current state — v1 implements Layer 1 (structured knowledge)
  and one Layer 5 channel (website widget) only; don't let marketing copy
  claim the rest (voice, SMS, CRM writeback, multi-role "digital workforce")
  before it's built.

## Operating mode

Routine implementation work (audits, incremental refactors, tests, docs,
low-risk fixes clearly within existing scope) proceeds without stopping to
ask for permission at each step. Anything that trips the Business Impact Gate
above still pauses for approval — that gate is a standing safeguard the user
and their business partner asked for, not a default caution to relax without
being told to.

## Current business context

- Pricing target: $99/month recurring + ~$399 one-time setup fee (see
  `../business-plan/`), not yet validated with a paying customer.
- One live pilot: LMTLSS (wearelmtlss.com). One side-by-side demo instance:
  Evolve Credit Repair — proves the product is business-agnostic, not
  LMTLSS-specific.
- Architecture is single-tenant today (one hosted instance per client). A
  multi-tenant rebuild is a known future step, not yet started — would itself
  trip the Business Impact Gate (database redesign / new infrastructure).
