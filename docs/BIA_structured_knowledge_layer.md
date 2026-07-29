# Business Impact Analysis — Structured Knowledge Layer (V1 Update Spec Priority 1)

Prepared 2026-07-29, per the Business Impact Gate in `V1_ARCHITECTURE_SPEC.md`
(this is a database redesign — explicitly gated). Not yet approved; no code
changes have been made.

## What's being proposed

**Not** the full 11-module structured schema from `V1_UPDATE_SPEC.md` §3
(Business Details / Services / Policies / Processes / FAQ / Education /
Audience / Qualification / Offers / Brand Voice / Human Handoff) built all at
once. That's a large lift with real onboarding-effort cost, and we have no
usage data yet from LMTLSS or Evolve Credit Repair to say it's needed at that
scope.

Instead, a smaller Phase 1 that directly targets the two biggest problems the
gap analysis found — retrieval running on every message, and no fast path for
the handful of questions that make up most real traffic (hours, phone,
pricing, common FAQs):

1. **`business_facts` table** — flexible key/value structured facts (hours,
   phone, address, short policy summaries). No rigid per-fact-type schema, so
   adding a new fact later doesn't need a migration — matches the spec's own
   "configuration over hardcoding" principle. Short enough to include directly
   in every system prompt at near-zero token cost — no retrieval call needed
   for these at all.
2. **`faqs` table** — question / approved answer / category / priority.
   Directly implements spec §3.5. This is the single highest-value module:
   FAQs are literally what most visitor questions already map to.
3. **A routing check in `chat_service`** — before assembling the general
   retrieval context, check the FAQ table for a high-confidence match. If
   found, ground the reply strictly in that approved answer instead of the
   general TF-IDF pass over all site content.

**Deferred, not built in Phase 1:** Services catalog, Qualification/scoring
rules, CTA definitions, conflict detection, confidence-scored admin approval
workflow, and a true vector database. Revisit once Phase 1 is live and we
have real usage signal on whether that additional structure earns its cost.

## Architectural Review (per the spec's own required questions)

1. **Does this already exist?** Partial — `business` table already holds
   some structured fields; the TF-IDF `chunks`/`retrieval` layer already
   serves as a rough stand-in for "Layer 2." Nothing structured exists for
   FAQs or quick facts specifically.
2. **Can an existing component be extended?** Yes — this follows the exact
   pattern already used for the `business` table (typed SQL columns, dashboard
   form to edit them). Two sibling tables, not a new subsystem.
3. **Technical debt created?** Low, if scoped this way. The main risk is
   scope creep back toward the full 11-module schema — Phase 1 deliberately
   avoids that.
4. **Duplicate functionality?** Minor overlap: FAQ-shaped content pasted into
   the existing "manual document" knowledge box today would, after this
   change, belong in the FAQ table instead. No functional conflict — the
   manual-document path stays for genuinely long-form content (guides,
   policies, articles) that isn't FAQ-shaped.
5. **Increases infrastructure?** No. Same SQLite database, two new tables.
   No new services, no vector database, no new AI provider.
6. **Increases token usage?** **Decreases it** for the questions this
   targets — a matched FAQ answer or the always-available facts block is far
   smaller than today's 5-chunk TF-IDF dump on every single message.
7. **Increases operating cost?** Net **decrease** expected on Claude API
   spend for common-question traffic (shorter prompts). One-time dev cost,
   no new recurring cost.
8. **Increases implementation complexity?** Yes, moderately — two new
   tables + migrations, a small admin UI addition (FAQ editor, facts editor),
   and a routing change in `chat_service.handle_message`/`_system_prompt`.
   Comparable in size to the Kanban board build already shipped this
   session — a contained feature, not a rewrite.
9. **Does it justify the complexity with customer experience gains?** Yes —
   faster, more consistent answers on exactly the questions visitors ask
   most (hours, pricing, policies, common FAQs), with zero risk of the LLM
   paraphrasing a wrong number or date, which matters for a product being
   sold on trustworthiness.
10. **Is there a simpler solution?** Considered and rejected: doing nothing
    and just tuning the prompt further. Already tried something like this
    (the few-shot example added earlier for `unresolved_question`) — it
    helps behavior but doesn't fix that every message still pays for a full
    retrieval call, which is the actual inefficiency named in the spec.

## Cost / Pricing / Feature-Scope Impact

- **Pricing:** No change. This doesn't touch tiers, limits, or billing.
- **Profitability:** Net positive — lower average tokens per conversation on
  fact/FAQ-heavy traffic; no new infrastructure or subscription cost.
- **Setup effort:** Slightly higher per client — someone needs to fill in
  FAQs and quick facts during onboarding. Mitigated by being **additive, not
  required**: a client with nothing filled in behaves exactly as today (site
  scan + free-text script), so this doesn't block onboarding or break
  existing clients (LMTLSS, Evolve Credit Repair) — it's a Phase 2 quality
  pass on top of what already works for them.
- **Admin workflow:** New — a simple FAQ list editor and a facts editor in
  the dashboard's Knowledge tab. Not the full conflict-detection/approval
  workflow from spec §16; that's still deferred.

## Effort Estimate

Roughly comparable to one of the larger features already shipped this
session (the Kanban board, or the handoff-intent expansion) — two new
tables with migrations, dashboard CRUD for both, and a routing change in the
chat engine, plus tests for the new SQL-first-vs-retrieval-fallback
behavior per the spec's own testing requirement.

## Recommendation

Approve Phase 1 as scoped above (facts + FAQs + routing only). Explicitly
hold off on Services/Qualification/CTA/vector-DB/admin-approval-workflow
until Phase 1 is live on at least one real client and we can see whether the
added structure actually earns its onboarding cost.
