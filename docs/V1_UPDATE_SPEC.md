# V1 Website AI Assistant — Efficiency and Knowledge Architecture Update Spec

Received 2026-07-29. Reorganized per its own instruction: "2A" is placed under
section 2 (Core Design Principle), where it belongs, rather than left dangling
at the end of the original document.

## Operating instruction that ships with this spec

> Review the existing repository against this spec. First, review the document
> and put all additions at the bottom under the correct category. Then map the
> current architecture and identify which requirements are complete, partial,
> or missing. Then implement the highest-priority gaps using the smallest
> maintainable changes. Do not rebuild working features unnecessarily. Separate
> structured business knowledge, approved retrieval content, raw scan content,
> and action tools. Add tests for source-priority routing, unnecessary-research
> prevention, client-context retention, recommendation behavior, callback
> requests, human handoff, and tool-failure handling. Document all schema
> changes, migrations, environment variables, and remaining gaps.

Additional standing notes from the user:

- Live handoff to a human should never be blocked by a 3rd-party dependency.
  Where a live transfer isn't feasible, use simple guaranteed fallbacks —
  e.g. a `tel:` link that's clickable directly in the chat. If scheduling is
  offered, the visitor should never have to copy/paste a link manually — if
  the assistant can complete the booking, it should; if not, the link itself
  must be a clickable element, not plain text requiring copy/paste.
- The architecture should make client sites more discoverable to AI-powered
  search/inquiry surfaces (Google SGE, Gemini, ChatGPT, Claude browsing/plugins).
- The visitor-facing experience must perform well and look good on mobile.

---

## 1. Objective

Update the existing V1 website AI assistant so it:

- Responds quickly to common questions.
- Relies less on searching the raw website scan for every response.
- Converts scanned website content into structured, reusable business knowledge.
- Understands the visitor's situation, goals, and obstacles.
- Retains relevant conversation context.
- Provides preliminary guidance.
- Recommends a personalized next step that moves the visitor into the sales funnel.
- Uses external tools only when live information or an action is actually required.
- Offers immediate human contact, a callback, or scheduled contact when appropriate.

The assistant should behave like a capable digital business representative — not
a search box layered over a website crawl.

## 2. Core Design Principle

Use three separate information and action layers:

**Layer 1: Structured Business Knowledge** — stable, frequently requested
information (business name, phone, email, locations, hours, services, pricing,
policies, processes, qualification criteria, calls to action, human-contact
options). This layer should provide the fastest responses.

**Layer 2: Searchable Knowledge Base** — deeper or less frequently requested
information (educational articles, detailed service pages, long-form FAQs,
guides, case studies, explanations, terms and conditions, supporting
documents). May use retrieval, but searches approved indexed content — not a
live rescan of the website per question.

**Layer 3: Action and Live-Data Tools** — used only when the assistant must
retrieve current data or perform an action (check calendar availability,
schedule an appointment, request a callback, start a live conversation,
create/update a CRM lead, send an email or text, retrieve a customer record,
generate a quote, check order/application status).

### 2A. Data Architecture

**Objective.** Separate structured business data, searchable knowledge, client
data, and action tools into distinct layers. The website scan populates these
layers — it is not the primary source used to answer every question. This
prioritizes fast responses, consistent answers, lower token usage, reduced
retrieval latency, easier administration, better scalability, and cleaner AI
reasoning.

**Data Layer 1 — Structured Business Database (SQL).** Retrieved directly
without semantic search whenever possible: business details, services,
policies, FAQ (question, approved answer, category, related service, priority,
last verified, approval status), qualification rules, calls to action.

*SQL Response Rule:* whenever a question can be answered from structured
business information, retrieve it directly from SQL. Do not perform semantic
retrieval or website research. ("What are your hours?", "Do you serve Texas?",
"What is your cancellation policy?" → SQL lookups.)

**Data Layer 2 — Knowledge Base (Vector Database).** Longer-form content:
blog articles, educational content, guides, white papers, PDFs, long FAQs,
service explanations, case studies, help articles. Exists for semantic
retrieval when structured data is insufficient.

*Vector Search Rule:* only for educational questions, finding information
inside long documents, locating detailed explanations, comparing multiple
knowledge sources, retrieving supporting context. Not for simple business facts.

**Data Layer 3 — Client Data (SQL).** Visitor (name, email, phone, company),
conversation (situation, goals, obstacles, timeline, services discussed,
questions asked, recommendation, summary), lead (funnel stage, lead score,
assigned rep, callback/appointment requested, CRM status) — stored separately
from business knowledge.

*Client Context Rule:* retrieve client context from SQL instead of
reconstructing it from conversation history when practical. Prefer
conversation summaries over replaying long histories.

**Data Layer 4 — Action Layer.** Calendar, CRM, phone system, email, SMS,
payment gateway, quote generation, scheduling, forms, workflow automation.
Never used merely to answer static questions.

**Website Scan Workflow:** Crawl → Content Extraction → Duplicate Removal →
Classification → Populate SQL Business Tables → Populate Vector Knowledge Base
→ Detect Conflicts → Generate Review Queue → Administrator Approval → Publish
Approved Knowledge.

**Source Priority:**
1. Client Context (SQL)
2. Structured Business Database (SQL)
3. Approved FAQ
4. Approved Business Knowledge (Vector Search)
5. Raw Website Scan
6. General Model Knowledge
7. Human Escalation

Higher-priority sources always override lower-priority sources.

**Retrieval Decision Tree:** Can the question be answered from client data? →
SQL. Else, from structured business data? → SQL. Else, is this
educational/long-form? → Vector Search. Else, does it require live info or an
action? → Tool/API. Else, answer from approved business knowledge or general
model reasoning.

**Website Scan Requirements:** don't just embed every page — extract structured
business information, populate normalized SQL tables, generate embeddings only
for long-form content, detect conflicting/outdated information, flag uncertain
data for admin approval, preserve source URLs for every extracted record.

**Performance Optimization Rules:** minimize unnecessary retrieval. Preferred
order: SQL lookup (fastest) → cached knowledge → vector search → tool/API →
raw website retrieval. Never search the website if the answer already exists
in SQL.

**Knowledge Compiler (user-proposed addition, flagged as a potential
competitive advantage):** rather than simply indexing the website, a service
that transforms the scan into a business model — normalizes extracted data,
removes duplicates, resolves entity names, detects relationships between
services/audiences/policies/CTAs, populates SQL tables, generates embeddings,
builds a lightweight business knowledge graph, generates an admin review
report, produces confidence scores per record.

## 3. Required Knowledge Modules

The website scan should produce a draft version of the following standardized
modules.

### 3.1 Business Details
Legal/public business name, brand name, business description, primary phone,
primary email, website URL, physical locations, service areas, hours of
operation, time zone, social links, primary contact methods, talk-now
availability, callback availability, appointment availability.

### 3.2 Products and Services
Per service: name, short description, detailed description, customer problem
addressed, primary benefits, features, eligibility requirements, exclusions,
limitations, price/pricing model, typical timeline, recommended customer type,
related services, primary call to action.

### 3.3 Policies
Refund, cancellation, rescheduling, payment terms, warranty/guarantee
language, privacy practices, service restrictions, customer responsibilities,
required disclaimers, compliance language.

### 3.4 Processes and Customer Journey
What happens before/after purchase, consultation process, assessment process,
onboarding steps, expected timelines, required customer actions, internal
handoff points, follow-up process, completion/delivery process.

### 3.5 Frequently Asked Questions
Each FAQ: question, approved answer, related topic, related service, source
URL, last verified date, confidence level. Approved FAQs are answered directly
without entering research mode.

### 3.6 General Education
Definitions, common misconceptions, basic industry explanations, best-practice
guidance, educational responses, approved examples/analogies, important
limitations/disclaimers. Answered from this module or the approved knowledge
base without unnecessary live research.

### 3.7 Audience and Use Cases
Primary customer types, common situations/goals/frustrations/obstacles,
typical urgency indicators, relevant service per use case, situations the
business does not serve.

### 3.8 Sales and Qualification
Discovery questions, qualification questions, fit criteria, disqualifying
conditions, urgency/timeline/budget criteria (where appropriate),
decision-maker criteria (where appropriate), lead scoring rules, routing
rules, recommended next step by customer type.

### 3.9 Offers and Calls to Action
Free/paid consultation, assessment, demo, quote request, trial, application,
appointment, callback, talk-now option, downloadable resource,
purchase/checkout action. Each offer: eligibility, destination, required
information, priority, funnel stage, when the assistant should present it.

### 3.10 Brand Voice and Response Boundaries
Desired tone, formality, words/phrases to use or avoid, approved/prohibited
claims, topics requiring disclaimers or human escalation, maximum recommended
response length, whether humor is appropriate, whether faith/culture/other
brand elements should be included.

### 3.11 Human Handoff
Talk-now method, callback method, scheduling method, department routing,
availability rules, escalation triggers, emergency/urgent routing, required
summary fields for handoff, CRM destination, notification recipients.

## 4. Website Scan Processing

### 4.1 Current Problem
The assistant appears to rely too heavily on retrieving information from the
raw site scan during live conversations. This can cause slower responses,
inconsistent answers, duplicate information, retrieval of outdated pages,
confusion from conflicting website content, overly long responses, poor
qualification behavior, weak sales-funnel movement.

### 4.2 Required Updated Process
1. Crawl approved public pages.
2. Extract visible page content and metadata.
3. Remove navigation clutter, repeated footers, cookie text, duplicate content.
4. Classify information into the standard knowledge modules.
5. Create structured fields for high-frequency business information.
6. Break long content into retrieval-friendly knowledge chunks.
7. Attach the source URL to every extracted record.
8. Assign a confidence score.
9. Detect conflicts between pages.
10. Detect missing fields.
11. Flag time-sensitive or outdated information.
12. Present the generated business profile for review.
13. Mark approved information as trusted.
14. Use raw scan content only as a fallback, not the default response source.

### 4.3 Source Priority
1. Human-approved structured knowledge
2. Human-approved FAQ and educational content
3. Approved searchable knowledge-base content
4. Unreviewed structured content with a high confidence score
5. Raw website scan retrieval
6. Human escalation

When sources conflict, the higher-priority source wins. The assistant should
not combine conflicting answers without acknowledging the conflict.

## 5. Knowledge Record Requirements

Every stored knowledge record should support:

```json
{
  "id": "unique-record-id",
  "module": "business_details",
  "topic": "business_hours",
  "content": "Monday through Friday, 9:00 AM to 6:00 PM",
  "structured_value": {
    "monday": "09:00-18:00",
    "tuesday": "09:00-18:00",
    "wednesday": "09:00-18:00",
    "thursday": "09:00-18:00",
    "friday": "09:00-18:00",
    "saturday": "closed",
    "sunday": "closed"
  },
  "source_url": "https://example.com/contact",
  "source_page_title": "Contact Us",
  "confidence": 0.96,
  "approval_status": "approved",
  "last_scanned_at": "ISO-8601 timestamp",
  "last_verified_at": "ISO-8601 timestamp",
  "expires_at": null,
  "is_time_sensitive": false
}
```

## 6. Assistant Conversation Functions

Industry-neutral functions the assistant should support:

- **6.1 Welcome and Personalize** — greet naturally, detect likely reason for
  visit, avoid generic menus when a direct answer is possible, personalize
  based on known context.
- **6.2 Discover Current Situation** — concise relevant questions, avoid
  re-asking known info, one or two questions at a time.
- **6.3 Identify Goal** — desired outcome, timing, priority, definition of success.
- **6.4 Identify Obstacles** — frustrations, previous attempts, constraints,
  risks, missing resources, reasons visitor hasn't acted yet.
- **6.5 Build and Retain a Client Profile** — name, contact preferences,
  situation, goals, timeline, obstacles, services discussed, questions asked,
  preliminary recommendation, funnel stage, requested follow-up. Distinguish
  temporary conversation context / session-level context / persistent
  CRM-customer-profile data. Don't silently store sensitive/unnecessary info.
  Follow applicable privacy/consent requirements.
- **6.6 Analyze the Situation** — using structured knowledge, qualification
  rules, approved education, known client context, business-defined logic.
  Identify likely needs, relevant options, missing information, risks,
  appropriate next actions.
- **6.7 Provide Preliminary Guidance** — explain likely issue, describe
  options, clarify tradeoffs, give nonbinding preliminary direction. Never
  present as a guaranteed diagnosis or final outcome.
- **6.8 Recommend the Best Next Step** — every meaningful advisory
  conversation should move toward a next step (talk now, callback, schedule,
  assessment, quote, application, onboarding, purchase, educational resource,
  continue Q&A), based on the visitor's stated situation, not just the
  business's preferred offer.
- **6.9 Explain the Recommendation** — why it fits, how it connects to the
  visitor's goal, what happens next, what to expect, cost/commitment if any.
- **6.10 Answer Questions** — maintain awareness of prior answers, avoid
  repetition, concise by default, more detail on request, prefer approved
  knowledge over general model knowledge for business-specific claims.
- **6.11 Present Relevant Services** — only services connected to stated
  needs; avoid listing everything, hard selling, irrelevant upsells, or
  recommending before enough context exists.
- **6.12 Qualify the Opportunity** — need, fit, urgency, timeline, location,
  eligibility, budget (where appropriate), decision readiness, authority
  (where appropriate), prerequisites — without feeling like an interrogation.
- **6.13 Execute Business Tasks** — create/update CRM lead, schedule
  appointment, submit callback request, route to live support, send
  confirmation, trigger follow-up workflow, direct to approved form/checkout.
- **6.14 Provide Human Connection Options** — Talk Now (live staff available,
  visitor explicitly asks, urgent, commercially valuable, or a policy/expertise
  boundary is reached); Request a Callback (name, phone, preferred time,
  reason, relevant summary — collect only what's necessary); Schedule a
  Conversation (check available times when a calendar tool exists, complete
  scheduling rather than sending the visitor to search for a link, pass the
  summary to the rep); Continue with AI (always allow continued Q&A if no
  human connection is desired).
- **6.15 Follow Up and Nurture** — with permission: appointment/callback
  confirmation, requested information, reminders, approved nurture sequence,
  resuming from retained context.
- **6.16 Learn and Improve** — capture unanswered questions, failed searches,
  low-confidence answers, repeated questions, funnel abandonment points, tool
  failures, escalations, conversions, incorrect/outdated knowledge. Don't let
  the model autonomously rewrite approved business truth without review.

## 7. Tool and Research Usage Policy

**7.1 Default Rule:** answer from structured business knowledge or the
approved knowledge base whenever possible. Don't use research mode merely
because retrieval tools are available.

**7.2 Do Not Use Research Mode For:** approved FAQs, hours, location, contact
info, general service descriptions, approved pricing, general educational
questions, company policies, process explanations, common definitions,
already-answered questions, info available in structured modules.

**7.3 Use Retrieval When:** the answer requires details from a longer approved
document, multiple approved records must be compared, the topic isn't in
structured modules, the user asks a detailed question needing supporting
content, locating a specific policy/clause/article/explanation.

**7.4 Use Action or Live-Data Tools When:** checking current appointment
availability, checking rep availability now, creating/updating a lead,
requesting a callback, sending a message, retrieving customer-specific info,
checking live order/account/application status, generating a personalized
document, processing a transaction, performing a workflow.

**7.5 Tooling Threshold** — before invoking any tool: (1) can this be answered
from structured knowledge? (2) from approved indexed content? (3) does it need
current data? (4) does the visitor want an action completed? (5) will the tool
materially improve the answer? Use a tool only when 3, 4, or 5 justify it.

## 8. Suggested Routing Logic

```
Receive visitor message
        |
Identify intent
        |
Is this a common business-detail or FAQ question?
   Yes -> Answer from structured knowledge
   No  -> Is personalization required?
            Yes -> Use retained conversation/client context
            No  -> Is deeper approved information required?
                     Yes -> Search approved knowledge base
                     No  -> Does the request require live data or an action?
                              Yes -> Invoke the minimum necessary tool
                              No  -> Is confidence sufficient?
                                       Yes -> Answer concisely
                                       No  -> Ask one targeted clarifying
                                              question or offer human handoff
```

## 9. Response Style Requirements

**9.1 Default Response Length:** simple factual = 1-3 sentences; educational =
one short paragraph or a few concise points; personalized guidance = short
summary + recommendation + next action; complex = progressive disclosure,
direct answer first, more detail on request.

**9.2 Do Not:** produce long essays for simple questions, describe internal
research steps, repeat the visitor's full message, show internal reasoning,
list every product by default, ask multiple unnecessary questions, search the
whole site when structured info is available, use generic "contact us" when a
callback/talk-now/scheduling action can be offered instead.

**9.3 Recommended Advisory Response Pattern:** (1) acknowledge the situation,
(2) summarize what's relevant, (3) provide preliminary guidance, (4) recommend
one next step, (5) offer talk now / callback / scheduling / continued AI
support.

## 10. Performance Targets

**10.1 Response-Speed Targets (product targets, not guaranteed network
timings):** structured business details < 2s; FAQ answers < 2s; general
education < 3s; contextual personalized advice < 5s; single tool action < 8s;
multi-step task < 15s when technically possible.

**10.2 Tooling Limits:** zero tools for standard structured-knowledge
responses; prefer one retrieval call over multiple overlapping searches;
prefer one combined action call where supported; avoid repeated searches for
the same topic in a conversation; cache approved high-frequency answers;
cache retrieval results within the active session where appropriate.

**10.3 Perceived Performance:** for actions taking longer than a normal
answer, immediately acknowledge the request and show a concise status
("Checking available times.", "Submitting your callback request.", "Pulling up
your account details.") without exposing internal technical steps.

## 11. Conflict and Missing-Information Handling

During ingestion, generate review flags, e.g.:

```json
{
  "type": "conflict",
  "topic": "business_hours",
  "sources": [
    {"url": "https://example.com/contact", "value": "9:00 AM-5:00 PM"},
    {"url": "https://example.com/footer", "value": "9:00 AM-6:00 PM"}
  ],
  "recommended_action": "Request business-owner verification"
}
```

Other flag types: missing information, conflicting pricing, expired
promotion, unsupported claim, broken link, duplicate service, unclear CTA,
missing callback destination, missing scheduling integration, missing
compliance disclaimer, low-confidence extraction.

## 12. Confidence Rules

- 0.90-1.00: may answer directly if source is trusted.
- 0.75-0.89: may answer with careful wording, or verify against another
  approved source.
- 0.50-0.74: ask a targeted question, or present as unconfirmed.
- Below 0.50: do not present as fact; escalate for review or human assistance.

Human-approved information overrides automated confidence scoring.

## 13. Client Profile Schema

```json
{
  "visitor_id": "unique-id",
  "session_id": "session-id",
  "name": null,
  "email": null,
  "phone": null,
  "contact_permission": false,
  "preferred_contact_method": null,
  "current_situation": [],
  "goals": [],
  "obstacles": [],
  "timeline": null,
  "urgency": null,
  "location": null,
  "services_discussed": [],
  "questions_asked": [],
  "qualification_status": "unknown",
  "lead_score": null,
  "recommended_next_step": null,
  "funnel_stage": "visitor",
  "callback_requested": false,
  "appointment_requested": false,
  "human_handoff_requested": false,
  "conversation_summary": null,
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp"
}
```

Only collect and retain fields relevant to the business and the visitor's request.

## 14. Funnel Stages

1. Visitor
2. Engaged
3. Situation identified
4. Goal identified
5. Qualified
6. Educated
7. Recommendation delivered
8. Action requested
9. Appointment or callback booked
10. Lead handed off
11. Customer
12. Nurture

The assistant should update the funnel stage based on actual interaction events.

## 15. Human Handoff Summary

When transferring or creating a callback, give the representative: visitor
name, contact details, reason for contact, current situation, stated goal,
timeline, main obstacle, relevant service, preliminary guidance already given,
recommended next step, questions requiring human attention, full transcript
link/reference, consent status. The customer should not have to repeat the
entire conversation.

## 16. Administrator Review Interface

The V1 admin experience should let an owner/administrator: review extracted
business details, approve/reject knowledge records, edit structured fields,
resolve conflicts, add missing information, mark sources as trusted, mark
pages as excluded, set expiration dates, configure qualification questions,
CTAs, callback routing, talk-now availability, escalation rules, preview
assistant answers, view unanswered-question reports, trigger a rescan,
compare new scan results to approved knowledge.

A new scan must not automatically overwrite approved information — show
current approved value vs. newly detected value vs. source vs. recommended
update, with approve/reject controls.

## 17. Logging and Analytics

Track: intent, response source, whether structured knowledge was used,
whether retrieval was used, tool called, tool duration, total response
duration, confidence score, handoff/callback/scheduling events, lead
creation, recommended next step, funnel stage movement, user feedback,
unanswered question, knowledge gap, conversion outcome.

Reports: most common questions, questions causing raw-scan retrieval,
slowest response types, most-used tools, tool failure rates, knowledge gaps,
conflicting information, most successful recommended actions, talk-now
requests, callback requests, appointment conversions.

## 18. Error and Fallback Behavior

- **Structured knowledge missing** → search the approved knowledge base.
- **Approved knowledge missing** → search the raw scan only when permitted.
- **Low confidence** → "I want to make sure I give you the correct
  information," then ask one targeted question, offer a callback, offer talk
  now, or route to a human.
- **Tool failure** → never falsely claim the action completed; say "I wasn't
  able to complete that action just now," then retry once, provide the direct
  link, submit a fallback callback request, or offer human assistance.
- **Human staff unavailable** → offer callback, scheduled appointment,
  continued AI assistance, or approved contact information.

## 19. V1 Implementation Priorities

1. **Structured Knowledge** — business details, services, FAQs, policies,
   CTAs, human handoff settings.
2. **Routing Efficiency** — structured answer first, KB retrieval second, raw
   scan last, tools only when needed.
3. **Client Discovery and Recommendation** — situation, goal, obstacles,
   timeline, preliminary guidance, recommended next step.
4. **Funnel Actions** — create lead, request callback, talk now, schedule
   appointment, pass conversation summary.
5. **Knowledge Review** — conflict detection, missing-information flags,
   approval workflow, rescan comparison.
6. **Analytics** — response speed, knowledge source, tool usage, funnel
   progression, knowledge gaps.

## 20. Out of Scope for V1

Unless already supported, avoid expanding V1 into: fully autonomous
multi-agent workflows, unsupervised modification of approved knowledge,
complex long-term memory without consent controls, broad internet research
for ordinary website conversations, high-risk professional determinations,
automatic pricing changes, automatic policy creation, autonomous sales
commitments outside approved boundaries, complex document generation
unrelated to conversion, large numbers of narrowly defined tools.

Keep V1 focused on fast answers, useful consultation, lead conversion, and
clean human handoff.

## 21. Acceptance Criteria

**Knowledge:** scan creates structured business modules; high-frequency info
no longer answered by repeatedly searching raw pages; every record retains
its source; conflicting information is flagged; approved information is
protected from automatic overwriting.

**Speed:** common business-detail questions answered without research mode;
FAQs/general education use approved knowledge; tool calls occur only when
live data or an action is needed; tool and response durations are logged.

**Conversation:** assistant discusses the visitor's current situation;
identifies goal and obstacles; retains relevant context; doesn't repeat
previously answered questions; provides preliminary, appropriately limited
guidance; recommends a relevant next step.

**Sales Funnel:** assistant can create/update a lead; offer talk now; request
a callback; schedule a conversation when integrated; pass a useful
conversation summary to the human rep; track the visitor's funnel stage.

**Safety and Accuracy:** low-confidence information isn't presented as
definite fact; tool failures are disclosed; sensitive information isn't
retained unnecessarily; the assistant stays within approved business and
professional boundaries.

## 22. Initial Codex Audit Tasks

Before implementing changes, inspect the current codebase and document:

1. How website content is currently crawled.
2. How crawl data is stored.
3. Whether content is chunked, embedded, or indexed.
4. How retrieval is triggered.
5. Whether every message currently triggers retrieval.
6. Whether a structured business profile already exists.
7. How system prompts and routing logic are assembled.
8. What tools currently exist.
9. How tool calls are selected.
10. Whether client context is stored.
11. Whether a CRM lead can be created or updated.
12. Whether talk-now, callback, or scheduling actions exist.
13. How latency is measured.
14. How failed retrievals and unanswered questions are logged.
15. Which requirements in this specification are already implemented.

After the audit: preserve working functionality, identify gaps, recommend the
smallest viable architectural changes, implement in phases, add automated
tests, avoid a full rewrite unless the current architecture makes these
requirements impossible.
