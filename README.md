# LeadGuard

A simple, cross-industry AI front-desk plugin for business websites. One codebase; each
business is configured through four things: a knowledge base (site scan + your own pasted
content), a scheduling link, a handoff webhook, and a plain-English script describing how the
agent should behave. See [SPEC.md](SPEC.md) for the full design.

## Setup

```bash
cd leadguard/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Open the dashboard: **http://localhost:8000/dashboard/**

1. **Settings** — business name, (optional) website URL, scheduling link, handoff webhook URL,
   and your conversational script (write it like you're briefing a new front-desk hire).
2. **Knowledge** — click "Crawl Site Now" if you set a website URL, and/or paste in FAQs,
   pricing, policies — anything you want the agent to know that isn't on the public site.
3. **Leads** — every captured lead, and whether the handoff webhook succeeded.
4. **Conversations** — full transcript of every chat.

Copy the embed snippet from the bottom of Settings into the client's site, before `</body>`.

Try it locally first: open `widget/demo.html` in a browser — it's wired to `localhost:8000`.

## Handoff webhook

Paste a Slack **Incoming Webhook** URL to get a direct Slack message per lead. Paste a
Zapier/Make/n8n "catch webhook" URL instead if you want to fan a lead out to SMS, email, or a
CRM — LeadGuard POSTs `{"text": ..., "business": ..., "lead": {...}}`; Slack reads `text`
natively, and Zapier/Make can map any field from `lead`.

## Notes
- One config per running instance (single business) — the same as v1. Multi-tenant (many
  clients from one deployment) is a documented next step in SPEC.md, not built yet.
- Retrieval is TF-IDF (keyword-based) — works well for a single business's knowledge base;
  revisit if a client's content is huge or very heterogeneous.
