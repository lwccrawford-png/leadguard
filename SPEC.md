# LeadGuard — Spec

A cross-industry, plug-and-play AI front-desk plugin. One codebase, configured per business
through four inputs — nothing industry-specific is hardcoded.

## The four inputs (per business)

1. **Knowledge base** — site scan (crawl a URL) *and* manually pasted content (FAQs, price
   sheets, policies, anything the scan misses or that isn't public). Both feed the same
   retrieval index, so answers can draw on either.
2. **Scheduling** — a single link (Calendly, Acuity, Square Appointments, whatever the business
   already uses). The agent shares it in conversation when it's time to book. No calendar API
   integration, no OAuth, no per-client setup beyond pasting a URL.
3. **Handoff** — a webhook URL. When the agent captures a lead, it POSTs a Slack-compatible
   payload (`{"text": ..., "lead": {...}}`) to that URL. Paste a Slack Incoming Webhook URL for
   a direct Slack alert, or a Zapier/Make/n8n catch-hook URL to fan out to SMS, email, a CRM,
   or anything else — the receiving side decides, LeadGuard just POSTs the data.
4. **Conversational flow** — a free-form script written by the business owner (or whoever's
   configuring the client), dropped into the system prompt verbatim. No fixed template per
   industry: a dental office and a landscaping company each just write their own instructions.

## Why this shape

v1 (AI Front Desk Assistant, see `../ai-frontdesk/SPEC.md`) hardcoded Google Calendar OAuth,
a single fixed prompt template, and no explicit handoff channel — good for proving the concept,
too rigid to sell across different types of businesses. LeadGuard replaces each rigid piece with
one plain, swappable input: a link, a webhook, and free text. That's the whole surface area a
new client needs to fill in.

## Architecture

```
leadguard/
  backend/
    app/
      main.py, config.py, db.py         same shape as v1, trimmed
      routers/chat.py, business.py       chat endpoint; business config + knowledge + leads + conversations
      services/
        ingestion.py    crawl_site() [reused crawl/chunk logic] + add_manual_document() — both
                         write to a single `sources` + `chunks` table pair
        retrieval.py     TF-IDF retrieval over all chunks, regardless of source
        chat_service.py  system prompt = business.flow_script (verbatim) + retrieved context +
                          scheduling_link mention; ONE tool: capture_lead
        handoff.py       POSTs captured leads to business.handoff_webhook_url
  widget/     same embeddable widget.js as v1 (already generic, unchanged)
  dashboard/  Settings (name, site url, scheduling link, handoff webhook, flow script, color),
              Knowledge (crawl + add manual doc + list/remove sources), Leads, Conversations
```

No calendar integration, no OAuth, no booking tables — appointments happen on whatever tool the
business already uses; LeadGuard's job is qualifying the visitor and getting them to that link or
into a human's hands.

## Data model (SQLite, one business per running instance — still single-tenant for now)
- `business` — name, website_url, scheduling_link, handoff_webhook_url, flow_script, accent_color
- `sources` — `source_type` ('site' | 'manual'), url or label, fetched_at
- `chunks` — text chunks tied to a source, used for retrieval regardless of origin
- `conversations` / `messages` — full chat history per widget session
- `leads` — captured contact info + whether the handoff webhook succeeded

## Request flow (chat)
1. Widget POSTs `{session_id, message}`.
2. Top-5 TF-IDF matches retrieved from `chunks` (site-scanned or manual, mixed).
3. System prompt = business's own `flow_script` + scheduling link + retrieved context +
   minimal instructions (answer from knowledge base, call `capture_lead` when you get contact
   info or a booking request).
4. Claude responds, optionally calling `capture_lead` → saved to `leads` + POSTed to the
   handoff webhook.
5. Reply returned to widget; full turn persisted.

## What's intentionally NOT in this version
- No multi-tenant isolation (one config per deployment) — same path forward as v1: add a
  tenant id to every table once you have concurrent clients.
- No dashboard auth.
- No SMS/Slack SDK — the generic webhook is the integration point; use Zapier/Make if a client
  needs the webhook fanned out to a channel that doesn't accept plain JSON POSTs directly.
