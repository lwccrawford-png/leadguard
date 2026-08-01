# Ideal Client & Workflow

Confirmed 2026-07-30. This is the reference point for evaluating future
product/UX decisions — a proposed feature or flow should be checked against
this profile before being built, rather than each decision re-litigating who
the product is for. Synthesized from decisions already made this session
(Model A managed service, claim-not-assign, the Pipeline board's motivation),
not invented separately from them.

## The client

A small, local or community-based organization or business — a solo
operator or a team of roughly 1-10 people, where usually just 1-3 people
actually touch customer/member follow-up. Concretely: independent service
businesses (contractors, salons, small professional-services firms like
Evolve Credit Repair), or community organizations (churches, ministries,
clubs, small nonprofits like LMTLSS). Not a tech company, no IT person, not
already running a real CRM or help desk.

### What makes them the right fit

- **Non-technical, relationship-based.** They don't want to log into
  anything or configure anything themselves — this is why the managed
  service model (no client login) is a fit, not a compromise.
- **Small enough that "claim" is enough.** A handful of people glancing at
  one shared board doesn't need roles, assignment, or access control. The
  moment that stops being true is the moment this client has outgrown the
  ideal profile.
- **Budget-conscious, single decision-maker.** ~$99/month plus a one-time
  setup fee has to read as an obvious yes to one person — not a line item
  needing committee approval. Rules out anything requiring procurement.
- **Currently loses track of follow-ups in email, texts, or memory.** No
  formal system exists today. The Leads board and Pipeline add-on replace
  sticky notes, not an existing CRM.
- **Often has a "next step" that isn't just close-the-deal.** Either a short
  sales cycle (quote → book → close) or a longer relationship (visitor →
  orientation → member). This is why Pipeline needs configurable stages
  instead of one fixed funnel.

### Who this explicitly rules out

Multi-location businesses needing real role-based access; anyone wanting
API access or deep self-service configuration; anyone already running a
real CRM; anything requiring procurement or compliance sign-off beyond what
a solo owner can decide alone. If a prospective client looks like this,
they're not the target — don't shape the core product around their needs.

## Their ideal day-to-day workflow

1. A visitor chats with the widget on their site — gets answered, booked
   (via the prefilled scheduling link), or captured as a lead.
2. A notification lands wherever they already look — Slack or email, via
   the handoff webhook — not a new tool they have to remember to check.
3. They (or their 1-2 people) glance at the Leads board periodically, claim
   what they're personally working, jot a note.
4. If it's a relationship that takes a while (membership steps, a longer
   sales cycle), they promote a claimed lead into Pipeline and move it
   through whatever stages make sense to them.
5. When something needs to change — a scheduling link, an FAQ, a policy —
   they use the support-request form or contact the agency directly. They
   never touch Settings.
6. Occasionally (a monthly gut-check, or during a check-in call) they look
   at the Dashboard tab to see whether it's actually working for them.

## Demo instances referenced in this document

Real clients, with real domains and the running demo instance for each:

- **LMTLSS** — real site: [www.wearelmtlss.com](https://www.wearelmtlss.com) (the bare domain has a cert issue — `www.` is required). Demo dashboard: `http://localhost:8000/dashboard/`. Demo widget page: `widget/demo.html`. The pilot client, a men's ministry/community organization.
- **Evolve Credit Repair** — real site: [evolvecreditrepair.org](https://evolvecreditrepair.org). Demo dashboard: `http://localhost:8001/dashboard/`. Demo widget page: `widget/demo_evolve.html`. The side-by-side demo instance used to prove the product isn't LMTLSS-specific; a professional/financial-services example.

Fictional examples, no real domain — used only in mockups and test walkthroughs to illustrate other business types the ideal-client profile covers (not real prospects or clients):

- Riverside Auto Detailing (local service business)
- Riverside Fitness Club / Northgate Fitness Studio (membership-pipeline example)
- Cedar Grove Fellowship (community/nonprofit)
- Summit Tax & Bookkeeping (professional services)

## How to use this

Before building a new feature or access model, ask: would this client
actually want to do this themselves, or would they want it done for them?
If a proposal only makes sense for a larger team, a technical user, or
someone willing to self-configure, it's probably solving for the wrong
persona — either scope it down to fit this client, or flag explicitly that
it's meant for a different tier/segment than the core product targets.
