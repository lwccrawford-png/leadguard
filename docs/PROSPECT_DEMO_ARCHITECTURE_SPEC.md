# EvolveIQ / LeadGuard — Prospect Demo Link Architecture: Pre-DigitalOcean Handoff

Received 2026-08-10. Declared a **blocking milestone before DigitalOcean
migration/deployment** — see `ops/DEPLOYMENT_PLAN.md` for the deployment plan
this gates.

## Adaptation note (read before implementing)

The data-model SQL below is written in Postgres/UUID/JSONB shorthand for
portability across projects. This codebase is SQLite, single-tenant
(one SQLite file per client instance, per `CLAUDE.md`), and already has an
established convention — most recently used end-to-end in the intelligence
routing branch (`backend/app/services/intelligence.py`):

- `UUID PRIMARY KEY` → `INTEGER PRIMARY KEY AUTOINCREMENT`
- `JSONB` columns → `TEXT` columns holding `json.dumps(...)` / parsed back
  with `json.loads(...)` (see `_loads()` / `scoring_rules_json` etc. in
  `intelligence.py` for the exact pattern)
- `TIMESTAMPTZ NOT NULL DEFAULT NOW()` → `TEXT NOT NULL`, populated with
  `datetime.now(timezone.utc).isoformat()` (see `_now()` in `intelligence.py`)
- New tables should go through the same `ensure_schema()` /
  `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN` (wrapped in
  `try/except sqlite3.OperationalError: pass`) migration pattern already
  used by both `backend/app/db.py` and `intelligence.py`, not a separate
  migrations framework.

Everything else below (routes, entities, UX, acceptance criteria) is
architecture-level and applies as written.

---

## Purpose

Build prospect-specific public demo links before moving LeadGuard/EvolveIQ to DigitalOcean.

The outbound sales motion depends on sending each target business a unique, personalized demo URL such as:

- `https://demo.example.com/coolcare`
- `https://try.example.com/coolcare`
- `https://example.com/demo/coolcare`

These are examples only. Do not hardcode an unavailable or unowned domain. The implementation must work on localhost/staging now and support custom domains/subdomains cleanly after DigitalOcean deployment.

This is a blocking milestone before DigitalOcean migration or production deployment.

## Business Rationale

The goal is to turn outbound outreach into a demo-first sales engine.

Instead of asking a prospect to imagine the value of LeadGuard, the sales workflow should let Larry create a lightweight public demo for that exact business, send the prospect a unique link, monitor engagement, and use observed activity to prioritize follow-up.

Initial target market:

- Texas HVAC companies

Later target markets:

- Legal
- Other BIPs and verticals supported by the EvolveIQ intelligence framework

This must remain cross-industry. Do not create HVAC-only architecture, schema, routing, prompts, or analytics assumptions. HVAC should be treated as one vertical template.

## Outbound Workflow Enabled

1. Find visible leak
   - Identify a target company with a weak website conversion path, unclear service intake, missed replacement opportunities, poor FAQ handling, weak after-hours capture, or other public-facing customer-intelligence gap.

2. Create company demo
   - Create a `prospect_demo` using a reusable vertical template.
   - Add company name, slug, public website source, vertical/BIP, region/jurisdiction if relevant, suggested questions, logo/brand fields, disclosure, expiration date, owner, and notes.

3. Personalized outreach
   - Phone, text, email, and/or short personalized video.
   - The first CTA is not a purchase. The CTA is: "look at the demo."

4. Send unique demo URL
   - Example: `https://demo.example.com/coolcare`
   - The link opens a minimal public demo page with the assistant immediately usable.

5. Monitor engagement
   - Track page opens, unique sessions, conversations started, messages, suggested-question clicks, CTA actions, repeat visits where privacy-appropriate, last activity, and broad intent topics.

6. 15-minute intelligence walkthrough
   - If the prospect engages, book a short call to show what the assistant learned and how it would plug into their real intake process.

7. POC
   - Convert the prospect demo into a real client configuration without rebuilding everything from scratch.

## Current vs Roadmap Functionality

### Build Now: Pre-DigitalOcean Requirement

- Public prospect demo URLs by slug.
- Minimal public demo page.
- Prospect-specific assistant configuration.
- Configurable suggested questions.
- Required non-affiliation disclosure.
- Basic prospect-level analytics.
- Admin create/edit/disable workflow.
- Reusable vertical templates.
- Share/copy-link action.
- Disabled, expired, and missing-slug behavior.
- Rate limiting and abuse controls.
- Isolation from production client accounts and analytics.
- Clean conversion path from prospect demo to real client/account.
- Localhost/staging QA support.
- `noindex,nofollow` SEO controls.

### Roadmap: After Initial Deployment

- Advanced engagement scoring.
- Deeper intent topic classification.
- Personalized video landing page blocks.
- A/B tests for suggested questions.
- Sales-owner notifications.
- CRM integrations.
- Approved live handoff/scheduling per prospect.
- Custom domain management UI if domains become multi-tenant.

## UX Requirements

### Public Demo Page

Route pattern should support one or both of:

- Subdomain style after deployment: `https://demo.<configured-domain>/<prospect-slug>` or `https://try.<configured-domain>/<prospect-slug>`
- Path style for localhost/staging: `http://localhost:<port>/demo/<prospect-slug>`

The page should be intentionally minimal:

- Prospect company name.
- Company logo only if legally and technically appropriate.
- Heading similar to: `Experience your AI assistant`
- Embedded assistant immediately usable on page load.
- Three configurable suggested questions.
- No pricing.
- No signup wall.
- No admin navigation.
- No internal dashboard links.
- No client-only settings visible.
- Clear disclosure:
  - `Demonstration created for [Company] using publicly available website information — not currently affiliated with or deployed by [Company].`

The disclosure must be visible without requiring interaction. It can appear near the assistant or in the footer, but it must not be hidden behind a tooltip, modal, or collapsed panel.

### Suggested Questions

Each demo should support exactly three primary suggested questions in the first version.

Examples for an HVAC demo:

- `My AC is running but not cooling. What should I check first?`
- `How do I know whether I need a repair or replacement?`
- `Do you offer emergency service or financing options?`

These must be configurable per prospect and defaultable from the selected vertical template.

### Simulated vs Live Actions

The demo may safely showcase scheduling, service handoff, lead capture, or routing behavior, but it must clearly distinguish simulation from live action unless explicitly enabled and approved.

Default behavior:

- Do not book real appointments.
- Do not send real customer leads to the prospect.
- Do not call or text the prospect's business.
- Do not trigger production routing destinations.
- Do not write demo leads into production client lead queues.

If a lead or scheduling demo is captured, label it as simulated/demo data in the admin view and in any stored record.

## Architecture Requirements

### Core Principle

Prospect demos are separate from production client accounts.

They may reuse the same BIP/intelligence framework, assistant runtime, and template system, but demo records must be isolated so they do not pollute production client analytics, lead reporting, routing, billing, or account configuration.

### Recommended Model

Use generic entities:

- `prospect_demos`
- `demo_events`
- `demo_conversations` or a demo-scoped conversation flag/table
- `demo_templates` or equivalent reusable vertical template records

Avoid HVAC-specific table names, enum names, prompt code paths, and UI labels unless they are template content.

### Relationship Model

A prospect demo should reference or copy from reusable configuration without leaking production data:

- `prospect_demo` may reference `demo_template`.
- `prospect_demo` may reference a BIP/vertical.
- `prospect_demo` may reference a demo profile/scenario.
- `prospect_demo` should not reference production client private configuration unless conversion has occurred.
- Production `client_account` conversion should create or link a new real account/config intentionally.

## Recommended Data Model

Adapt names and types to the existing database conventions — see the
Adaptation Note at the top of this document.

### `prospect_demos`

Recommended fields:

```sql
id UUID PRIMARY KEY,
slug TEXT NOT NULL UNIQUE,
status TEXT NOT NULL DEFAULT 'draft',
company_name TEXT NOT NULL,
website_url TEXT,
vertical TEXT NOT NULL,
bip_type TEXT,
region TEXT,
jurisdiction TEXT,
demo_template_id UUID NULL,
demo_profile JSONB NOT NULL DEFAULT '{}',
assistant_config JSONB NOT NULL DEFAULT '{}',
suggested_questions JSONB NOT NULL DEFAULT '[]',
logo_url TEXT,
brand_name TEXT,
brand_colors JSONB NOT NULL DEFAULT '{}',
disclosure_text TEXT NOT NULL,
expires_at TIMESTAMPTZ NULL,
sales_owner_id UUID NULL,
sales_owner_name TEXT,
sales_notes TEXT,
public_page_title TEXT,
seo_noindex BOOLEAN NOT NULL DEFAULT TRUE,
created_by UUID NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
disabled_at TIMESTAMPTZ NULL,
converted_client_id UUID NULL,
converted_at TIMESTAMPTZ NULL
```

Status values:

- `draft`
- `active`
- `disabled`
- `expired`
- `converted`

Required behavior:

- Slugs are unique.
- Slugs are URL-safe.
- Slug collisions are handled with a clear validation error or generated suffix.
- Disabled and expired demos are not publicly accessible.
- Converted demos can remain accessible only if intentionally allowed.

### `demo_templates`

Recommended fields:

```sql
id UUID PRIMARY KEY,
name TEXT NOT NULL,
vertical TEXT NOT NULL,
bip_type TEXT,
region TEXT,
default_suggested_questions JSONB NOT NULL DEFAULT '[]',
default_demo_profile JSONB NOT NULL DEFAULT '{}',
default_assistant_config JSONB NOT NULL DEFAULT '{}',
default_disclosure_template TEXT NOT NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

Purpose:

- Allow fast creation of 20-25 personalized HVAC demos.
- Later support legal and other BIP demos.
- Prevent manual cloning.

### `demo_events`

Recommended fields:

```sql
id UUID PRIMARY KEY,
prospect_demo_id UUID NOT NULL REFERENCES prospect_demos(id),
event_type TEXT NOT NULL,
session_id TEXT,
conversation_id UUID NULL,
metadata JSONB NOT NULL DEFAULT '{}',
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

Recommended event types:

- `demo_page_opened`
- `demo_unique_session_started`
- `suggested_question_clicked`
- `conversation_started`
- `message_sent`
- `assistant_response_generated`
- `lead_cta_clicked`
- `demo_lead_submitted`
- `schedule_simulation_started`
- `schedule_simulation_completed`
- `repeat_visit_detected`
- `demo_disabled_view_attempted`
- `demo_expired_view_attempted`

Analytics should avoid invasive fingerprinting. Use privacy-appropriate session identifiers, standard cookies/local storage where acceptable, and aggregate metrics. Do not build hidden device fingerprinting.

### `demo_conversations`

If the current app has a conversations table, use either:

- a separate `demo_conversations` table, or
- a strong `scope = 'prospect_demo'` / `prospect_demo_id` field that isolates demo data from production clients.

Recommended fields:

```sql
id UUID PRIMARY KEY,
prospect_demo_id UUID NOT NULL REFERENCES prospect_demos(id),
session_id TEXT,
started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
last_message_at TIMESTAMPTZ NULL,
message_count INTEGER NOT NULL DEFAULT 0,
intent_topics JSONB NOT NULL DEFAULT '[]',
lead_action_taken BOOLEAN NOT NULL DEFAULT FALSE,
is_simulated BOOLEAN NOT NULL DEFAULT TRUE
```

## Backend/API Requirements

Use the repository's existing backend conventions. Do not introduce a new framework just for demos.

### Public Routes

Required:

- `GET /demo/:slug`
  - Loads the public demo shell.
  - Returns 404 for unknown, disabled, expired, or non-public demos.
  - Adds `noindex,nofollow` metadata.

- `GET /api/public/demo/:slug`
  - Returns only public-safe demo config.
  - Must not return admin notes, internal scores, secrets, routing destinations, private prompts, API keys, other prospect data, or production client configuration.

- `POST /api/public/demo/:slug/events`
  - Records allowed demo events.
  - Rate limited.
  - Validates event type and metadata shape.

- `POST /api/public/demo/:slug/conversations`
  - Starts a demo-scoped conversation.
  - Creates or resumes a privacy-appropriate session.
  - Does not create a production lead or production client conversation.

- `POST /api/public/demo/:slug/messages`
  - Sends a message to the demo assistant.
  - Uses prospect-specific public/demo config.
  - Rate limited.
  - Stores conversation data in demo scope.

Optional but useful:

- `POST /api/public/demo/:slug/lead-action`
  - Simulates or records a CTA/lead action.
  - Must default to simulation mode.

### Admin Routes

Required:

- `GET /api/admin/prospect-demos`
- `POST /api/admin/prospect-demos`
- `GET /api/admin/prospect-demos/:id`
- `PATCH /api/admin/prospect-demos/:id`
- `POST /api/admin/prospect-demos/:id/disable`
- `POST /api/admin/prospect-demos/:id/enable`
- `POST /api/admin/prospect-demos/:id/convert`
- `GET /api/admin/prospect-demos/:id/analytics`
- `POST /api/admin/prospect-demos/:id/copy-link` or frontend-only copy action using the generated public URL

Template routes:

- `GET /api/admin/demo-templates`
- `POST /api/admin/demo-templates`
- `PATCH /api/admin/demo-templates/:id`

### Public-Safe Config Contract

The public config response should include only:

```json
{
  "slug": "coolcare",
  "companyName": "Cool Care",
  "websiteUrl": "https://example.com",
  "vertical": "hvac",
  "region": "Texas",
  "heading": "Experience your AI assistant",
  "logoUrl": "https://...",
  "brand": {
    "name": "Cool Care",
    "colors": {}
  },
  "suggestedQuestions": [
    "My AC is running but not cooling. What should I check first?",
    "How do I know whether I need a repair or replacement?",
    "Do you offer emergency service or financing options?"
  ],
  "disclosureText": "Demonstration created for Cool Care using publicly available website information — not currently affiliated with or deployed by Cool Care.",
  "isSimulation": true
}
```

Do not include:

- API keys
- system prompts that reveal internal strategy
- internal priority scores
- admin notes
- sales owner private notes
- routing phone numbers or emails unless explicitly approved for live mode
- production client IDs
- other prospect records
- private firm/client configuration

## Frontend Requirements

### Public Demo Page

Create a route equivalent to:

- `/demo/[slug]`

The page should:

- Fetch public-safe demo config by slug.
- Render company name/logo when appropriate.
- Render heading: `Experience your AI assistant`.
- Render the assistant immediately, without requiring signup.
- Render three suggested question buttons.
- Render disclosure text visibly.
- Render a disabled/expired/not-found state as a clean 404-style page.
- Add `robots` metadata: `noindex,nofollow`.
- Record page-open event once per page load.
- Record suggested-question clicks.
- Record conversation start and message counts through backend events.

### Admin/Dashboard

Add an admin section equivalent to:

- `Prospect Demos`
- `Demo Templates`

Admin list view should show:

- Company name
- Slug/public URL
- Status
- Vertical/BIP
- Website source
- Sales owner
- Opens
- Conversations
- Last activity
- Expiration date
- Converted status

Admin editor should support:

- Create/edit/disable demo
- Set company/prospect name
- Set slug
- Set website source
- Set vertical/BIP
- Set jurisdiction/region where relevant
- Select template
- Edit demo scenario/profile
- Edit suggested questions
- Set logo/brand fields
- Edit disclosure
- Set expiration date
- Set sales owner and notes
- Copy/share link
- Convert to real client/account/config

## Analytics Requirements

Track prospect-level engagement:

- Demo page opens
- Unique sessions
- Conversations started
- Total messages
- Suggested-question clicks
- Lead/CTA actions
- Repeat visits where privacy-appropriate
- Last activity timestamp
- Optional broad intent topics

Do not implement invasive fingerprinting.

Recommended analytics rollup:

```sql
prospect_demo_id
total_opens
unique_sessions
conversations_started
messages_sent
suggested_question_clicks
lead_cta_actions
repeat_visits
last_activity_at
top_intent_topics
```

This can be computed from `demo_events` or maintained as a materialized/summary table if the app already uses that pattern.

## Security, Branding, and Legal Requirements

### Security

Public demos must:

- Be rate limited by IP/session/slug.
- Validate all slug input.
- Validate event metadata.
- Prevent access to admin APIs.
- Prevent exposure of secrets.
- Prevent enumeration of all demos.
- Prevent cross-demo data access.
- Prevent production client data leakage.
- Avoid exposing internal routing destinations.
- Avoid exposing internal priority scores.
- Avoid exposing private firm configuration.

### Branding

Logo usage should be optional.

If using a prospect's logo from public sources, keep it limited to nominative/demo context and allow admin removal. If there is uncertainty, render the company name without logo.

### Disclosure

Every public demo must display a disclosure like:

`Demonstration created for [Company] using publicly available website information — not currently affiliated with or deployed by [Company].`

The exact text may be editable per demo, but the admin should warn or prevent saving if the disclosure becomes materially misleading.

### SEO

Prospect demo pages should use:

- `noindex`
- `nofollow`
- canonical handling that does not encourage indexing
- no sitemap inclusion

## Conversion Path

The admin must support converting a prospect demo into a production client account/config without redoing setup.

Recommended conversion behavior:

1. Admin clicks `Convert`.
2. System creates a production client account/config using selected demo fields.
3. System copies safe configuration:
   - company name
   - website source
   - vertical/BIP
   - region/jurisdiction
   - approved assistant settings
   - suggested intake questions if applicable
4. System does not copy:
   - demo-only analytics into production analytics
   - simulated leads as real leads
   - sales notes into client-visible areas
   - unapproved routing destinations
5. System stores:
   - `converted_client_id`
   - `converted_at`
   - conversion audit metadata

Converted demo analytics may remain visible in sales/admin reporting as pre-client engagement history.

## Localhost and Staging Requirements

Must be testable before DigitalOcean migration.

Local examples:

- `http://localhost:<port>/demo/coolcare`
- `http://localhost:<port>/demo/acme-hvac`

Staging examples:

- `https://staging.example.com/demo/coolcare`
- `https://demo.staging.example.com/coolcare`

Domain handling should be configuration-driven:

- `PUBLIC_DEMO_BASE_URL`
- `PUBLIC_DEMO_HOST`
- or equivalent existing environment/config pattern

Do not hardcode `demo.evolveiq.ai`, `try.evolveiq.ai`, or any other unverified domain as a required value.

## URL and State Handling

### Slug Rules

- Lowercase recommended.
- URL-safe characters only.
- Prefer `a-z`, `0-9`, and hyphens.
- Trim whitespace.
- Reject or normalize duplicate hyphens.
- Enforce max length.
- Enforce uniqueness.

### Collision Handling

When creating from company name:

- Try generated slug, such as `cool-care`.
- If unavailable, suggest `cool-care-2` or prompt admin to choose another slug.
- Never silently overwrite an existing demo.

### Public State Behavior

- Unknown slug: 404-style page.
- Disabled demo: 404-style page or "demo unavailable" page without revealing private status.
- Expired demo: 404-style page or "demo unavailable" page.
- Draft demo: not publicly accessible.
- Converted demo: behavior controlled by admin setting; default can remain accessible or become disabled depending on sales preference.

## Acceptance Tests

### Public Demo

- Visiting an active slug renders the public demo page.
- Visiting an unknown slug returns 404 or equivalent not-found state.
- Visiting a disabled slug does not reveal demo content.
- Visiting an expired slug does not reveal demo content.
- Page contains no pricing or signup wall.
- Page displays company name.
- Page displays logo only when configured.
- Page displays heading similar to `Experience your AI assistant`.
- Page displays exactly three configured suggested questions.
- Page displays the non-affiliation disclosure.
- Page includes `noindex,nofollow`.
- Public config endpoint does not include secrets, admin notes, internal routing, scores, private prompts, or other prospects' data.

### Assistant Behavior

- Demo assistant loads with prospect-specific demo/profile config.
- Suggested-question click sends or stages the configured question.
- Conversation starts in demo scope.
- Messages are stored in demo scope.
- Demo conversation does not appear in production client analytics unless intentionally converted.
- Scheduling/lead behavior defaults to simulation.
- Simulated scheduling/lead action does not send real emails, texts, appointments, or leads.

### Admin Workflow

- Admin can create a prospect demo from a template.
- Admin can edit company name, slug, website source, vertical/BIP, region/jurisdiction, demo profile, suggested questions, logo/brand fields, disclosure, expiration date, sales owner, and notes.
- Admin can disable and re-enable a demo.
- Admin can copy/share the public link.
- Admin sees opens, unique sessions, conversations, messages, CTA actions, and last activity.
- Admin can convert a demo to a real client account/config.
- Conversion does not copy demo analytics into production analytics.

### Templates

- Admin can create or edit reusable vertical templates.
- Creating a demo from the HVAC template prepopulates HVAC-appropriate suggested questions and demo profile.
- Template architecture supports Legal or another BIP without schema changes.

### Abuse and Privacy

- Public event and message endpoints are rate limited.
- Invalid slugs are rejected or not found.
- Event metadata is validated.
- Cross-demo access is blocked.
- No invasive fingerprinting is used.

## Localhost QA Scenarios

1. Create HVAC template.
2. Create `coolcare` demo from HVAC template.
3. Open `http://localhost:<port>/demo/coolcare`.
4. Confirm page is minimal and assistant is immediately usable.
5. Click each suggested question.
6. Send a custom message.
7. Trigger simulated lead/schedule CTA.
8. Confirm admin analytics update.
9. Disable the demo.
10. Confirm public route no longer exposes content.
11. Re-enable the demo.
12. Set expiration date in the past.
13. Confirm expired demo no longer exposes content.
14. Attempt duplicate slug creation.
15. Confirm collision handling works.
16. Convert demo to client.
17. Confirm demo config transfers safely.
18. Confirm demo analytics remain separate.

## Recommended Implementation Sequence

1. Add data model and migrations
   - `prospect_demos`
   - `demo_templates`
   - `demo_events`
   - demo-scoped conversation support

2. Add slug/state utilities
   - normalization
   - uniqueness checks
   - collision handling
   - active/disabled/expired checks

3. Add public-safe backend endpoints
   - demo config
   - events
   - conversations
   - messages

4. Add rate limiting and validation
   - public demo endpoints first
   - metadata schema validation
   - abuse-resistant message limits

5. Add public demo frontend route
   - minimal page
   - assistant embed
   - suggested questions
   - disclosure
   - noindex/nofollow
   - disabled/expired/404 behavior

6. Add admin CRUD
   - create/edit/disable demos
   - copy/share link
   - status and expiration management

7. Add reusable demo templates
   - start with Texas HVAC template
   - keep fields generic for Legal and other BIPs

8. Add analytics dashboard
   - event rollups
   - last activity
   - engagement indicators
   - broad intent topics if already supported

9. Add conversion flow
   - prospect demo to real client/account/config
   - audit conversion
   - preserve analytics separation

10. Add automated tests
    - model validation
    - public routes
    - admin routes
    - analytics events
    - conversion flow
    - security redaction

11. Complete localhost QA
    - verify all acceptance tests before DigitalOcean work resumes

## Definition of Done

This milestone is done when:

- A sales/admin user can create a prospect-specific demo with a unique public URL.
- The public URL loads a minimal, branded, prospect-specific assistant demo without admin access.
- The demo includes three configurable suggested questions.
- The non-affiliation disclosure is visible on every demo page.
- Demo engagement is tracked at the prospect level.
- Demo data is isolated from production client accounts, leads, conversations, and analytics.
- Admin can create demos quickly from reusable vertical templates.
- Admin can disable, expire, edit, and copy/share demo links.
- Slug collisions, missing demos, disabled demos, and expired demos are handled cleanly.
- Public endpoints are rate limited and do not expose secrets or private configuration.
- Scheduling/handoff/lead behavior is simulation-only unless explicitly approved for live action.
- A prospect demo can be converted into a real client account/config without rebuilding from scratch.
- Localhost/staging testing works before DigitalOcean migration.
- Automated tests cover the acceptance criteria above.
- DigitalOcean migration/deployment remains blocked until this feature passes QA.
