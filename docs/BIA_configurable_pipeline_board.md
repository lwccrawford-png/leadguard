# Business Impact Analysis — Configurable Pipeline Board

Prepared 2026-07-30, per the Business Impact Gate in `V1_ARCHITECTURE_SPEC.md`
(new tables + a new dashboard subsystem — explicitly gated). Not yet
approved; no code changes have been made.

## What's being proposed

A second, business-configurable Kanban board — distinct from the existing
Leads board — for tracking claimed leads (or anyone else added directly)
through a longer, ongoing process: sales pipeline, membership/onboarding
steps, orientation classes, whatever the client needs. The motivating case
is organizations (churches, clubs, small nonprofits) that need CRM-like
follow-up tracking and don't have a CRM — but the feature itself must stay
fully generic. Per explicit instruction: the church/nonprofit fork is not
happening now, and building any vertical-specific behavior into this would
make that future fork *more* expensive, not less. Everything here is
configuration, not hardcoded terminology.

### Concrete scope

1. **Custom stages** — a business defines up to 8 stages with their own
   labels and order (e.g., "New Inquiry → Class 1 → Class 2 → Member," or
   "Qualified → Proposal → Won/Lost" — entirely up to the client), configured
   in a new Settings section.
2. **Outcome notes field** — at least 3 stages can be individually flagged
   to show an additional free-text notes field on their cards, for
   won/lost-type detail. Not limited to exactly 3 — any stage can have it
   toggled on.
3. **A single "Won" stage with a configurable dropdown** — exactly one stage
   can be flagged as the terminal positive-outcome stage. Cards sitting in
   that stage only get an extra dropdown field, populated from a
   business-defined list of options (e.g., which product/service/tier was
   chosen). This is separate from the outcome-notes field above and only
   appears on this one stage.
4. **Cards default collapsed** — showing only name, phone number, and the
   claim control. Full detail (notes, outcome notes, dropdown, timestamps)
   revealed by clicking to expand a single card.
5. **Per-column bulk collapse/expand** — a toggle (eye icon) in each column
   header that expands or collapses every card in that column at once, for
   when someone wants to scan a whole column's detail instead of one card at
   a time.
6. **Column header count** — same pattern as the existing Leads board.
7. **Lead promotion** — an action on a claimed lead (existing Leads board)
   that creates a corresponding pipeline card seeded with its name/contact
   info, linked back to the originating lead.
8. **Deferred, explicitly not in this phase**: CSV export. Small, low-risk,
   easy to bolt on once the board is live — no reason to couple it to this
   BIA.

### Decided: two separate boards

Leads and Pipeline stay as two separate boards (new tab for Pipeline),
sharing the same underlying Kanban code (generalized to render configurable
columns instead of hardcoded New/Claimed/Done), rather than merging into one
page. Reasoning: the Leads funnel (New → Claimed → Done) and a multi-step
sales/membership pipeline are genuinely different lifecycles with different
volumes and different card shapes — conflating them risks a page that's
confusing for both use cases. "Reuse the current lead page" is honored at
the *code* level (generalize the existing Kanban renderer, don't build a
second one from scratch) rather than the *page* level.

## Architectural Review (per the spec's own required questions)

1. **Does this already exist?** Partial — the Leads Kanban already has the
   drag-and-drop, claim, count-badge, and notes-field patterns this reuses.
   Nothing configurable exists (columns are hardcoded), and no
   dropdown/collapse/outcome-tracking behavior exists anywhere yet.
2. **Can an existing component be extended?** Yes, and it should be — this
   generalizes the existing Kanban renderer to read its columns from
   business config instead of a fixed enum, rather than building a second,
   parallel board implementation.
3. **Technical debt created?** Low, if the genericness constraint holds.
   The real risk is a future "just hardcode this one church-specific thing"
   shortcut — explicitly ruled out by your own instruction, since that's
   exactly what would make the eventual fork more expensive.
4. **Duplicate functionality?** Some conceptual overlap with the Leads
   `status` field (New/Claimed/Done) — addressed by the recommendation
   above: Pipeline is a separate, downstream board fed by promoted leads,
   not a replacement for the Leads funnel.
5. **Increases infrastructure?** No. Same SQLite database. Three new
   tables (`pipeline_stages`, `pipeline_dropdown_options`,
   `pipeline_cards`), no new services.
6. **Increases token usage?** None. This is a dashboard/CRM feature — the
   chat engine doesn't read from or write to it, aside from the one-time
   lead-promotion action, which is a plain DB write, not a prompt change.
7. **Increases operating cost?** No new recurring cost. No new AI calls, no
   new third-party service — pure app/database feature.
8. **Increases implementation complexity?** Yes, meaningfully — this is
   larger than any single feature shipped so far this session. Three new
   tables (vs. one or two in past changes), roughly 8-10 new endpoints
   (stage CRUD + reorder, dropdown-option CRUD, card CRUD + move + promote),
   a Kanban renderer generalized to be config-driven instead of fixed, a new
   Settings section, and a genuinely new interaction pattern — per-card and
   per-column collapse/expand — that doesn't exist anywhere in the
   dashboard today.
9. **Does it justify the complexity with customer experience gains?** Yes,
   if the underlying thesis holds: this turns the product from "capture a
   lead and notify someone" into "capture, notify, *and* track it all the
   way through" — a real embedded-CRM value prop for exactly the
   under-served customers (small orgs without a CRM) you're targeting, and
   it's configuration-only, so it directly reduces the cost of the
   nonprofit fork later without spending anything on that fork now.
10. **Is there a simpler solution?**
    - Tell clients to keep using a spreadsheet or external CRM — rejected;
      defeats the point for the customers this is aimed at.
    - Ship one fixed generic "extended" pipeline (e.g., 6 hardcoded generic
      stages) instead of true custom labels — rejected; you specifically
      want configurability so the eventual fork is cheap, and a fixed set
      of stages wouldn't serve orientation/class-based tracking well.
    - **Legitimate phasing option**: ship the core configurable board first
      (stages, cards, drag/claim/count, per-card collapse) and add the
      Won-stage dropdown + per-column bulk-collapse toggle in a fast
      follow-up, rather than all at once. Worth considering purely to get
      something testable sooner — not a reason to cut either feature.

## Cost / Pricing / Feature-Scope Impact

- **Pricing:** Decided — the Pipeline board and its supporting features
  (custom stages beyond the base set, outcome-notes field, Won-stage
  dropdown) are a **paid add-on**, not included in the base tier by
  default. This means the feature needs a gate somewhere in the product
  (e.g., a flag on `business` — `pipeline_enabled` or similar) that hides
  the Pipeline tab and its Settings section entirely when not purchased,
  not just a pricing-page distinction with no code enforcement.
- **Profitability:** Positive — no new recurring cost (no new
  infrastructure, no new API usage), and it's now a source of incremental
  revenue per client who buys it, not just a cost center.
- **Setup effort:** Additive, not required. A business that never
  configures any pipeline stages simply doesn't see a populated Pipeline
  tab — doesn't affect onboarding for existing clients (LMTLSS, Evolve
  Credit Repair) or the intake-form/template workflow already built.
- **Admin workflow:** New — a Settings section for defining/reordering
  stages, toggling outcome-notes per stage, flagging the single Won stage,
  and managing its dropdown option list. Needs basic validation (at least
  one stage configured before the tab shows content; at most one stage
  flagged as Won).

## Effort Estimate

Larger than anything shipped so far this session — roughly 1.5-2x the size
of the original Kanban board build. Three new tables instead of one or two,
a Kanban renderer that has to become config-driven instead of fixed, a new
Settings UI, and a genuinely new interaction (collapse/expand at both the
card and column level) with no existing pattern to copy from elsewhere in
the dashboard.

## Recommendation

Approve the core scope as described (configurable stages, cards, generalized
Kanban rendering, Settings config, lead promotion, per-card and per-column
collapse/expand) as a single phase, with CSV export explicitly deferred to
a follow-up. Confirm the "two separate boards, linked by promotion" decision
above before implementation starts, since it affects both the data model and
the dashboard navigation.
