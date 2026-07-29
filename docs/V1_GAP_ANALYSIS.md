# V1 Gap Analysis — Current Codebase vs. V1 Update Spec

Audit date: 2026-07-29. Verified directly against the current code (not from
memory) — `backend/app/db.py`, `services/chat_service.py`, `services/retrieval.py`,
`services/ingestion.py`, `routers/business.py`, `widget/widget.js`.

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

## Extra finding not in the Section 22 checklist

**`widget/widget.js:113`** renders every assistant reply via
`el.textContent = text` — plain text only. Any URL or phone number in a
reply is **not clickable**. This directly contradicts the user's explicit
standing instruction: scheduling links must be clickable (no copy/paste
friction) and phone handoff should use a clickable `tel:` link when a live
transfer isn't feasible. This is confirmed as a real, currently-shipping gap.

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
| §6.14 Talk now / callback / scheduling | **Partial** | Callback ≈ `capture_lead`; scheduling = static link, not a booking action; talk-now not distinct |
| §7 Tool/research usage policy | **Partial** | Prompt instructs "answer from KB when possible," but there's no code-level gate — retrieval always runs regardless |
| §8 Routing decision tree | **Missing** | No SQL-first / retrieval-second / tool-third decision code |
| §9 Response style | **Implemented** | Prompt enforces short, plain-text, non-markdown replies |
| §10 Performance targets/logging | **Missing** | No latency measurement of any kind |
| §11 Conflict/missing-info flags | **Missing** | No conflict detection exists |
| §12 Confidence thresholds | **Missing** | Score computed, then discarded |
| §13 Client profile schema | **Missing** | No matching table/fields |
| §14 Funnel stages | **Missing** | No funnel_stage tracking |
| §15 Human handoff summary | **Partial** | `notes` field carries some context to the webhook; not the full structured summary (goal/obstacle/timeline/etc.) |
| §16 Admin review interface | **Missing** | Dashboard lets you edit config + view/claim leads; no knowledge-approval workflow, no rescan-diff/approve UI |
| §17 Logging/analytics | **Missing** | No analytics beyond raw conversation/lead storage |
| §18 Error/fallback behavior | **Partial** | Tool-failure/API-error fallback exists (`chat_service.py:244`); confidence-based fallback doesn't |
| Safety guardrails (crisis, injection resistance) | **Implemented** | Tested directly this session — holds up well |
| Usage caps (monthly limit, burst limit) | **Implemented** | Built and tested this session |
| Clickable handoff links (`tel:`, scheduling) | **Missing** | Confirmed — plain-text rendering only |
| Mobile-friendly widget UI | **Not yet audited** | Needs a dedicated pass — not covered in this audit |
| AI-search discoverability (SGE/Gemini/ChatGPT browsing) | **Not yet audited** | Needs a dedicated pass — separate concern from the knowledge-architecture work |

## What this means, plainly

The current product does the job for a single small business with a modest
knowledge base — it's a working, tested, real MVP. But structurally, it's
still "a chatbot with retrieval bolted on," exactly what the spec is asking
to move past: every message pays for a retrieval call whether it needs one
or not, there's no SQL fast-path for the 80% of questions that are simple
facts (hours, phone number, policies), and there's no structured client
profile or funnel tracking — just a transcript and a lead record.

The spec's own priority order (§19) is the right sequence to close this in
phases rather than one large rewrite: Structured Knowledge first, then
Routing Efficiency, then Client Discovery, then Funnel Actions, then Knowledge
Review, then Analytics.
