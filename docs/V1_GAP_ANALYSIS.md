# V1 Gap Analysis — Current Codebase vs. V1 Update Spec

Audit date: 2026-07-29. Verified directly against the current code (not from
memory) — `backend/app/db.py`, `services/chat_service.py`, `services/retrieval.py`,
`services/ingestion.py`, `routers/business.py`, `widget/widget.js`.

## Phase 1 status update (2026-07-29, later same day)

Approved per `BIA_structured_knowledge_layer.md` and implemented:

- **§2A SQL structured layer** — `business_facts` (key/value, always included in
  every prompt, no matching needed) and `faqs` (question/answer/category/priority)
  tables added. **Was Missing → now Partial** (Services/Policies/Qualification/CTA
  modules remain deferred, per the phased plan).
- **§2A Source priority routing** — a dedicated FAQ-matching index is checked
  before general retrieval; a confident match skips the TF-IDF chunk pass
  entirely. **Was Missing → now Partial** (client-context and full priority
  chain from §4.3 still not implemented — only the FAQ-vs-general-KB priority
  exists so far).
- **§7.2 Unnecessary-research prevention** — confirmed via test and live
  measurement: FAQ-matched questions use ~1,800 input tokens vs. ~2,900 for the
  same conversation falling through to general retrieval. **Was Partial → now
  Partial-but-measured** (real numbers now exist; full §7 tool-threshold logic
  still doesn't gate the general retrieval call itself, only FAQ vs. general).
- **§10 Performance targets/logging** — `latency_ms`, `input_tokens`,
  `output_tokens` now captured on every assistant message, summed across
  tool-use rounds. **Was Missing → now Implemented** (response-duration
  logging; no per-tool-call breakdown yet).
- **§17 Logging/analytics** — a Usage & Performance dashboard view surfaces
  monthly tokens/latency, knowledge coverage (FAQ/fact/source counts), and a
  live list of `unresolved_question` leads as knowledge gaps. **Was Missing →
  now Partial** (this is a live dashboard view, not the fuller report set
  §17 describes — most-common-questions, tool failure rates, etc. still absent).
- **Testing** — a pytest suite now covers source-priority routing,
  unnecessary-research prevention, client-context retention, callback/human
  handoff, and tool-failure handling, per the update spec's own testing
  requirement (§22). 23 tests, no live API calls, ~1.2s runtime.

Still open from the original audit: Services catalog, Qualification rules,
CTA definitions, conflict detection, confidence-scored approval workflow, a
true vector database, and the fuller admin review interface (§16). Deferred
intentionally per the Phase 1 scoping in the Business Impact Analysis.

## Phase 2 status update (2026-07-30) — verified live, not just in code

- **Clickable handoff links** — `widget.js` now renders replies via
  `linkify(escHtml(text))` instead of plain `textContent`. URLs and phone
  numbers become clickable `<a>` tags (`tel:`/`sms:` chosen by nearby "text"
  keyword detection). **Was Missing → now Implemented.** Verified live: a
  phone number typed by the visitor and a scheduling URL returned by the
  assistant both rendered as underlined clickable links in a real browser
  session against the Evolve Credit Repair demo instance.
- **Mobile-friendly widget UI** — audited and fixed: 16px input font (avoids
  iOS auto-zoom), 44×44px touch targets on input/send, 36×36px close button.
  **Not yet audited → now Implemented.** Verified live via
  `getComputedStyle`/`getBoundingClientRect` at a 375×812 viewport — exact
  values confirmed, not just visually plausible.
- **AI-search discoverability** — `seo.py` generates FAQPage JSON-LD schema
  from approved FAQs and checks robots.txt access for 9 named AI crawlers.
  **Not yet audited → now Implemented** as a dashboard card (Knowledge tab).
  Not yet folded into the external sales pitch/features doc — that's a
  marketing task, not an engineering gap.
- **Client discovery phases** — `leads.discovery_phase` (5 fixed presets:
  fact_finding, price_shopping, comparing_providers, evaluating_fit,
  ready_to_book) added to `capture_lead`, the system prompt, and the Kanban
  lead cards. **Missing → now Implemented** as a deliberately-scoped
  simplification of §14's generic funnel-stage concept — not the full
  situation/goal/obstacle/timeline client profile §13 still calls for.
  Verified live: a booking-intent conversation was correctly tagged
  `ready_to_book` and shows on its Kanban card.
- **§6.14 Talk now / callback / scheduling** — scheduling is no longer a bare
  static link. A `get_scheduling_link` tool builds a URL with the visitor's
  known name/email/phone merged into the query string (covering
  Calendly/Cal.com and Acuity-style param conventions), only offered when a
  business has a scheduling link configured. **Partial → still Partial, but
  materially better**: this closes the "cut and paste" friction the update
  spec explicitly calls out, without a full calendar-availability API
  integration (deliberately deferred — see README "Notes"). Verified live
  end-to-end: a real chat captured name/email/phone and the assistant
  returned a correctly pre-filled Calendly-style URL, which rendered as a
  clickable link.

Still open after Phase 2: full source-priority routing across all knowledge
types (only FAQ-vs-general-KB priority exists), Services/Policies/
Qualification/CTA as structured modules, a real client profile
(situation/goal/obstacle/funnel_stage/lead_score) beyond the 5-preset
discovery phase, conflict detection and a confidence-scored knowledge
approval workflow, and deeper analytics (most-common-unanswered-questions,
tool failure rates) beyond the current Usage dashboard.

## Section 22 Audit Answers

1. **How is website content crawled?** `services/ingestion.py::crawl_site()` —
   BeautifulSoup, robots.txt-aware, strips nav/footer/script, same-domain only,
   capped at 40 pages.
2. **How is crawl data stored?** SQLite `sources` (site page or manual doc) +
   `chunks` (raw text only, ~180 words with overlap, tagged with a source
   label). No structured fields — text blobs only.
3. **Chunked, embedded, or indexed?** Chunked, yes. **Not embedded** — no
   vector database. Indexed via `TfidfVectorizer` + cosine similarity
   (keyword-statistical, not semantic).
4. **How is retrieval triggered?** Unconditionally, every message —
   `chat_service.py:230`, `retrieval.retrieve(user_message, top_k=5)` runs
   before every single Claude call with no gating.
5. **Does every message trigger retrieval?** **Yes, confirmed.** This is
   exactly the inefficiency the spec calls out in §4.1.
6. **Does a structured business profile exist?** Partial. The `business`
   table has real structured fields (name, website_url, scheduling_link,
   handoff_webhook_url, handoff_email, flow_script, accent_color,
   assistant_name, assistant_image_url, monthly_message_limit) — but nothing
   close to the spec's modules 3.2–3.11 (no Services, Policies, FAQ,
   Qualification Rules, or CTA tables; `flow_script` is one free-text field
   standing in for all of brand voice + policies + qualification logic).
7. **How are system prompt/routing assembled?** `chat_service._system_prompt()`
   builds one flat prompt per message: persona + safety rules + `flow_script`
   + scheduling link + retrieved TF-IDF chunks + formatting rules + a few-shot
   example. There is no routing layer that decides *whether* to retrieve —
   retrieval output is always included.
8. **What tools exist?** One: `capture_lead`. No calendar/availability tool,
   no live-booking tool, no distinct "talk now" or "callback" tool, no CRM
   integration beyond the built-in `leads` table.
9. **How are tool calls selected?** Entirely by Claude's own judgment from
   the system prompt (LLM-native tool-use), not a deterministic pre-filter.
10. **Is client context stored?** Partial. `conversations`/`messages` hold
    full raw transcripts; `leads` holds name/email/phone/intent/notes/
    status/claimed_by/outcome/good_to_know. There is **no structured client
    profile** (situation / goals / obstacles / timeline / funnel_stage /
    lead_score per spec §13) and no cross-session `visitor_id` — everything
    is scoped to one `session_id`'s conversation.
11. **Can a CRM lead be created or updated?** Yes, but it's an internal
    lightweight CRM, not an external integration: `capture_lead` creates a
    lead row; `PATCH /api/leads/{id}` updates status/claimed_by/notes/
    good_to_know/outcome (dashboard Kanban board). No AI-callable "update
    existing lead" tool mid-conversation.
12. **Do talk-now/callback/scheduling actions exist?** Partial/mostly missing.
    Scheduling = sharing a **static link only** — no availability check, no
    actual booking (directly contradicts the user's "we should book it, not
    make them cut and paste" requirement). No explicit "talk now" tool (only
    implicit language in `capture_lead`'s human_request intent). No `tel:`
    link generation — see #13.
13. **How is latency measured?** **Not at all.** No response-duration or
    tool-duration logging anywhere in the codebase.
14. **How are failed retrievals / unanswered questions logged?** Partial —
    the `unresolved_question` lead intent captures cases where Claude
    *decides* it can't answer (behavioral, prompt-enforced), not a
    systematic confidence-score or failed-retrieval log. `retrieval.retrieve()`
    computes a similarity `score` per chunk but **it's discarded** —
    `chat_service.py` never reads it, so there's no confidence-threshold
    logic per spec §12.
15. **Which requirements are already implemented?** See the matrix below.

## Extra finding not in the Section 22 checklist (resolved in Phase 2)

**`widget/widget.js`** previously rendered every assistant reply via
`el.textContent = text` — plain text only, so URLs and phone numbers weren't
clickable. This has been fixed (see Phase 2 status update above) and
verified live in a real browser session — kept here as a record of a real
gap that was found and closed, not removed silently.

## Status Matrix

| Spec Area | Status | Notes |
|---|---|---|
| §2 Layer 1: Structured business knowledge | **Partial** | Business-level fields exist; no Services/Policies/FAQ/Qualification/CTA structure |
| §2 Layer 2: Approved searchable KB (not live rescan) | **Partial** | Content is indexed, not "live rescanned" per message — but it's TF-IDF text, not curated/approved records with confidence & approval workflow |
| §2 Layer 3: Action/live-data tools | **Missing** | Only `capture_lead`; no calendar, no live booking, no CRM push |
| §2A SQL structured layer + SQL Response Rule | **Missing** | No dedicated SQL lookup path; everything goes through the LLM + one flat retrieval call |
| §2A Vector knowledge base | **Missing** | TF-IDF, not embeddings — works, but not what's specified |
| §2A Client data layer (situation/goals/obstacles/funnel) | **Missing** | Only lead + raw transcript, no structured client profile |
| §2A Source priority routing | **Missing** | No priority chain; retrieval always runs, no SQL-first short-circuit |
| §3 Knowledge modules (3.1–3.11) | **Partial (3.1 only)** | Only business details are structured; services/policies/FAQ/qualification/CTA/brand-voice/handoff modules don't exist as data |
| §4 Scan processing (conflict/confidence/review) | **Missing** | Crawl → chunk → index only; no classification, confidence scoring, conflict detection, or review queue |
| §5 Knowledge record schema | **Missing** | Chunks store raw text + source label only |
| §6 Conversation functions (situation/goal/obstacles/funnel) | **Partial** | Handled implicitly by prompt instructions + Claude's judgment; no structured tracking or funnel-stage field |
| §6.14 Talk now / callback / scheduling | **Partial (improved)** | Callback ≈ `capture_lead`; scheduling now returns a contact-info-prefilled link via `get_scheduling_link` (no cut-and-paste), but still not a true booking action with live availability; talk-now not distinct |
| §7 Tool/research usage policy | **Partial** | Prompt instructs "answer from KB when possible," but there's no code-level gate — retrieval always runs regardless |
| §8 Routing decision tree | **Missing** | No SQL-first / retrieval-second / tool-third decision code |
| §9 Response style | **Implemented** | Prompt enforces short, plain-text, non-markdown replies |
| §10 Performance targets/logging | **Missing** | No latency measurement of any kind |
| §11 Conflict/missing-info flags | **Missing** | No conflict detection exists |
| §12 Confidence thresholds | **Missing** | Score computed, then discarded |
| §13 Client profile schema | **Missing** | No matching table/fields |
| §14 Funnel stages | **Partial** | `leads.discovery_phase` (5 fixed presets) is a deliberately-simplified stand-in for the spec's generic funnel-stage concept — not situation/goal/obstacle tracking |
| §15 Human handoff summary | **Partial** | `notes` field carries some context to the webhook; not the full structured summary (goal/obstacle/timeline/etc.) |
| §16 Admin review interface | **Missing** | Dashboard lets you edit config + view/claim leads; no knowledge-approval workflow, no rescan-diff/approve UI |
| §17 Logging/analytics | **Missing** | No analytics beyond raw conversation/lead storage |
| §18 Error/fallback behavior | **Partial** | Tool-failure/API-error fallback exists (`chat_service.py:244`); confidence-based fallback doesn't |
| Safety guardrails (crisis, injection resistance) | **Implemented** | Tested directly this session — holds up well |
| Usage caps (monthly limit, burst limit) | **Implemented** | Built and tested this session |
| Clickable handoff links (`tel:`/`sms:`, scheduling) | **Implemented** | `linkify()` in widget.js; verified live in-browser Phase 2 |
| Mobile-friendly widget UI | **Implemented** | 16px input font, 44px touch targets, 36px close button; verified via computed-style inspection at 375×812 |
| AI-search discoverability (SGE/Gemini/ChatGPT browsing) | **Implemented** | FAQPage JSON-LD + AI-crawler robots.txt check, surfaced in dashboard; not yet folded into the external pitch doc |

## What this means, plainly (updated 2026-07-30)

The product now handles the user-facing gaps that were most visible in a
live demo — clickable links, mobile usability, a pre-filled booking link,
and rough discovery-phase tracking. Structurally, it's still closer to "a
chatbot with retrieval bolted on" than the spec's target: FAQ lookups skip
general retrieval, but general-knowledge questions still pay for a TF-IDF
pass every message with no SQL fast-path for simple facts beyond the small
`business_facts` table, and there's still no structured client profile or
real funnel tracking — a 5-preset discovery phase plus a lead record, not
the situation/goal/obstacle/timeline schema §13 describes.

The spec's own priority order (§19) is the right sequence to close this in
phases rather than one large rewrite: Structured Knowledge first, then
Routing Efficiency, then Client Discovery, then Funnel Actions, then Knowledge
Review, then Analytics.
