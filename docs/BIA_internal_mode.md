# Business Impact Analysis — Internal Mode

Prepared 2026-08-04, per the Business Impact Gate in `V1_ARCHITECTURE_SPEC.md`
(new tables + a new recurring-cost driver + a new pricing tier — explicitly gated).
Not yet approved; no code changes have been made.

## What's being proposed

A second, employee-facing use of the same underlying platform: a knowledge
assistant for onboarding, training, and daily recall — "what's our policy on
X," "where's the install checklist," "how do we handle a warranty claim" —
answered from the business's own internal documentation, the same way the
public widget answers customer questions from the business's public-facing
knowledge.

This is explicitly **not** a mode toggle on the existing public widget. The
public widget has no authentication — anyone on the business's website can
open it. Internal content (HR policy, negotiation floors, vendor contacts,
training material) must never sit behind that same unauthenticated door. The
real design question isn't "should this exist," it's "how do we build it
without creating a path for internal content to leak to a customer, or
customer-facing content-management workflows to silently start touching
internal data."

### Concrete scope

1. **Separate internal knowledge tables** — `internal_facts`,
   `internal_faqs`, `internal_sources`, `internal_chunks` — structurally
   identical in shape to the existing `business_facts` / `faqs` / `sources` /
   `chunks`, but a fully separate pool. Deliberately not a `visibility` flag
   bolted onto the existing tables (see Architectural Review, #10) — a
   structural separation is much harder to accidentally cross-contaminate
   than a shared table every future code path has to remember to filter
   correctly. One missed filter on the shared-table approach means internal
   pricing guidance shown to a real customer; that failure mode doesn't
   exist if the pools are separate tables entirely.
2. **Reuses the existing chat engine's retrieval and Claude-call pattern**,
   pointed at the internal pool instead of the customer-facing one, with its
   own system prompt (no `capture_lead` / `get_scheduling_link` tools — those
   are meaningless internally) and no lead/conversation records created.

   **Content-first, not links-only.** The assistant answers directly from
   ingested content — reusing the existing `add_manual_document` pattern
   (paste text, it gets chunked and retrieved) against the internal tables
   — because that's the actual value prop: "here's the answer," not "here's
   a document, go read it." A links-only system is barely better than a
   file list with a search bar.

   `internal_sources` also carries an optional `reference_url` field, and
   **the answer format is "here's the answer — here's where to find it,"
   not one or the other.** When a source has a `reference_url`, every
   answer drawn from it includes the link, not just as a fallback for
   content that isn't fully ingested. This does two things at once: meets
   the immediate need (a direct answer, no digging required) and trains
   the employee for next time (they learn where the source document
   actually lives, building real familiarity with company resources
   instead of permanent dependency on asking the assistant). It's also
   the natural fix for content that shouldn't be duplicated and kept in
   sync by hand — a Google Doc HR updates weekly, a shared drive folder, a
   training video — where the link is the only way to stay current.

   **Explicitly not in scope:** file upload or parsing (PDF/Word
   extraction, OCR). Text paste plus an optional link covers training
   content, policies, and process docs without that added complexity —
   consistent with how customer-facing manual documents already work.
3. **Auth via the already-built Team Access Links** (`docs/BIA_team_access_links.md`)
   rather than a new auth system. Any valid, non-revoked Team Access token
   (Principal, Admin, or Staff) can *query* Internal Mode — the whole point
   is new/tenured employees getting answers without asking a person. Only
   Principal/Admin can *add or edit* internal content, mirroring the
   existing split where Staff gets working access and Principal/Admin
   configure.
4. **A new authenticated route** (e.g. `/internal`, gated the same way
   dashboard routes already are) rendering a chat interface reusing the
   widget's existing rendering code, not the public `/widget` mount.
5. **Its own usage cap**, separate from `monthly_message_limit` — internal
   usage scales with employee headcount and habit, not website traffic, so
   it needs a cost lever independent of the customer-facing cap.

## Architectural Review (per the spec's own required questions)

1. **Does this already exist?** No — nothing employee-facing exists today;
   every piece of the product is either customer-facing (widget) or
   agency-facing (dashboard, launcher).
2. **Can an existing component be extended?** Substantially yes for the
   *plumbing* — same chat-call pattern, same retrieval approach, same
   manual-document ingestion function (parameterized by which pool it writes
   to), same Team Access auth already built. What's genuinely new is the
   *content store* (deliberately separate, see below) and a second
   dashboard-style management surface for it.
3. **Technical debt created?** Moderate. A second, parallel
   content-management surface means two places that need to stay in sync if
   future features touch "how knowledge is structured" — a real risk if
   only one side gets updated. Mitigated by sharing the underlying
   ingestion/retrieval functions across both pools (parameterized, not
   forked) rather than duplicating logic.
4. **Duplicate functionality?** Yes, deliberately — a second knowledge store
   that mirrors the shape of the first. This is a safety-motivated
   duplication (see the leak-risk reasoning above), not accidental
   redundancy, and it's the one place in this BIA where "less code" would
   mean "less safe."
5. **Increases infrastructure?** No new external services — same SQLite
   database (more tables), same FastAPI app, same Claude API. No new vendor.
6. **Increases token usage?** Yes, meaningfully. Every internal Q&A
   interaction is a new Claude call, and volume scales with employee
   headcount and habit — a materially different, harder-to-predict cost
   driver than customer-widget traffic, which is naturally capped by actual
   website visitors.
7. **Increases operating cost?** Yes, per #6 — a new recurring cost that
   scales with adoption, not with leads. This is exactly the kind of cost
   the Business Impact Gate exists to flag before it's built, not after.
8. **Increases implementation complexity?** Yes, moderately-to-substantially
   — four new tables, a new authenticated route, a new chat variant/system
   prompt, a new dashboard-style management UI for internal content, and
   real care spent verifying there is zero code path where internal content
   reaches the customer-facing endpoint. Comparable in size to the Pipeline
   board BIA, and a notch larger given the security stakes need actual
   verification, not just a feature check.
9. **Does it justify the complexity with customer value?** Yes, if
   positioned as a distinct value prop rather than a bolt-on. Onboarding
   new hires and not losing institutional knowledge when someone
   experienced leaves are real, different pains from "capture more website
   leads" — and it extends the product's own "give your business's
   knowledge a voice" story to an internal audience, which is a genuine,
   differentiated upsell, not scope creep on Core.
10. **Is there a simpler solution?**
    - A `visibility` flag on the existing tables instead of separate ones —
      rejected. Cheaper to build, but every future retrieval code path has
      to remember to filter by visibility correctly forever; one miss is a
      real data leak to a real customer. Not worth the savings.
    - Point businesses at a plain wiki/Google Doc for this — rejected; it
      throws away the actual differentiator (same AI voice, same platform,
      no second tool for the business to manage and keep updated).
    - Build it as a fully separate product — rejected; throws away real,
      working plumbing (auth, chat engine, ingestion pattern) that makes
      this cheap to build *well* rather than cheap to build *badly*.

## Cost / Pricing / Feature-Scope Impact

- **Pricing:** Distinct paid add-on, not bundled into the $99 Core tier and
  not folded into the Pipeline add-on — different value prop (employee
  productivity/training) with a different cost driver (headcount-scaled
  token usage) than either.

  **Proposed: $49/month flat**, decided 2026-08-04. Reasoning:
  - *Bottom-up cost*: a typical internal Q&A turn (system prompt + retrieved
    knowledge context + a few conversational turns) runs roughly 2,000
    input / 300 output tokens at current Sonnet-tier pricing — a few cents
    per conversation. A small team (10-20 employees) asking occasional
    questions lands around **$10-20/month in raw API cost**; a larger team
    with a heavy daily habit could run meaningfully higher, which is what
    the usage cap below exists to bound.
  - *Market comparable, rejected*: internal-knowledge-assistant tools
    (Guru, Tettra, Glean) mostly charge per-seat, $8-20/employee/month —
    the wrong shape here, since Core and Pipeline are both flat pricing
    with no seat-counting, and per-seat billing reintroduces the CRM-like
    complexity the GTM doc already says to avoid.
  - Flat pricing keeps it consistent with how the rest of the product is
    sold and administered.
- **Profitability:** New recurring cost, directly proportional to adoption
  and usage habits. Needs its own usage cap — **proposed default: 250-300
  internal conversations/month included**, comfortable for a small team
  with healthy margin over the typical $10-20 cost. On hitting the cap,
  mirror the existing customer-widget behavior (stops auto-answering,
  points the employee to ask a person, resets next cycle) rather than
  surprise metered overage billing. A business that regularly blows past
  the cap is a real signal to introduce a second tier later, not something
  to solve preemptively now.
- **Setup effort:** A real onboarding step per business that opts in —
  someone has to populate the internal knowledge pool (facts, FAQs, and any
  documents), separately from the customer-facing knowledge base. Not
  automatic, not reusable from the customer-facing crawl.
- **Support burden:** New surface area for "why doesn't it know X" support
  requests, scoped to whichever businesses opt into the add-on — contained,
  not a Core-wide support cost increase.

## Effort Estimate

Comparable to or slightly larger than the Pipeline board BIA. Pipeline was
three tables with a fairly self-contained Kanban UI; this is roughly four
tables (facts/FAQs/sources/chunks equivalents) plus a new authenticated
route, a new chat-engine variant, and — the part that actually deserves
care, not just time — verifying there is no code path by which internal
content reaches the public widget's retrieval. That verification is a
correctness requirement, not a nice-to-have; it should be tested explicitly
before this ships, the same way the HVAC BIP's safety-escalation behavior
was tested against real scenarios rather than assumed correct.

## Recommendation

Approve as scoped: $49/month flat add-on, 250-300 internal
conversations/month included by default, cap behavior mirrors the existing
customer-widget cap (stops auto-answering and points to a person, resets
next cycle — no surprise metered billing). Both numbers are proposed, not
yet confirmed — flag if either should change before this gets built.

Everything else in the concrete scope above (separate tables, reused
plumbing, Team Access auth, Principal/Admin-only content management,
Staff-and-above query access) is a considered recommendation ready to build
once pricing is confirmed.
