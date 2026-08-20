# Business Impact Analysis — Stripe Billing

Prepared 2026-08-20, per the Business Impact Gate in `V1_ARCHITECTURE_SPEC.md`
(new recurring cost, pricing-adjacent, schema change — explicitly gated).
Not yet approved; no code changes have been made.

## What's being proposed

There is currently no payment collection mechanism anywhere in this
codebase — confirmed by direct search across the repo, `business-plan/`,
and the production server: zero references to Stripe, Authorize.net, or any
other processor. `$99/month + $399 setup` (per `CLAUDE.md`) has never been
charged to anyone. This is the actual blocker between "the product works"
and "the product can take a paying customer."

Two different scopes are on the table, and this BIA recommends starting
with the smaller one:

### Option A — Manual invoicing (recommended starting point)

Create a Stripe account, use Stripe's own hosted Invoicing product to send
each client a real invoice for setup fee + first month, and repeat monthly
by hand (or with Stripe's built-in recurring-invoice option, which doesn't
require any code). No webhook endpoint, no new database table, no
subscription-lifecycle code. A person (Larry, or whoever handles ops)
looks at Stripe's dashboard to see who's paid and who hasn't, exactly the
way the client roster is already managed by hand today (`ops/clients.json`,
tier changes via the launcher UI).

### Option B — Automated Stripe Checkout + subscriptions

Real subscription automation: Stripe Checkout for signup, a webhook
endpoint (naturally hosted on the launcher, `team.justaskevolveiq.com`,
since it's the one always-on central service — each client's own backend
is a separate isolated process, not a natural home for this) receiving
`checkout.session.completed` / `invoice.payment_failed` /
`customer.subscription.deleted`, and a new billing-status field wired into
the *existing* `TIER_FEATURES` / `push_feature_flags` mechanism already
built for tier management — a lapsed subscription would downgrade a
client's features through the same pathway a manual tier change uses
today, not a parallel system.

## Architectural Review (per the spec's own required questions)

1. **Does this already exist?** No — confirmed by direct search, nothing
   payment-related exists anywhere in the codebase or on the server.
2. **Can an existing component be extended?** Partially, for Option B —
   the launcher's `TIER_FEATURES`/`push_feature_flags` system (built for
   manual tier changes) is a natural extension point for billing-driven
   tier changes, rather than a parallel state machine. Option A extends
   nothing — it's a Stripe-dashboard-only workflow, no code touches this
   repo at all.
3. **Technical debt created?** Option A: none — it's outside the codebase
   entirely. Option B: real — webhook delivery isn't guaranteed exactly-once
   (Stripe recommends idempotent handling), and a new external dependency
   (webhook uptime becomes a thing that can silently break billing state).
4. **Duplicate functionality?** None either way.
5. **Increases infrastructure?** Option A: no. Option B: yes — a public
   webhook endpoint (additive to the launcher's existing public domain, not
   a new server) plus a Stripe account either way.
6. **Increases token usage?** No, neither option touches the chat engine.
7. **Increases operating cost?** Yes, for both, and this is the real
   finding to flag plainly: Stripe's standard processing fee is
   approximately **2.9% + $0.30 per successful charge** (confirm the exact
   current rate at signup — Stripe's published pricing changes
   periodically and this number shouldn't be treated as locked-in). On a
   $99/month charge that's roughly $3.17, about 3.2% effective. No
   additional monthly platform fee from Stripe itself for standard
   Checkout/Invoicing usage at this scale (Stripe Billing adds a
   percentage-based fee only above roughly $1M/year processed — not a
   near-term concern).
8. **Increases implementation complexity?** Option A: minimal — account
   setup and an internal habit, not a build. Option B: real complexity —
   webhook signature verification, idempotent event handling, a real
   product decision about what happens to a client's *live, running*
   instance on a failed payment (grace period vs. immediate suspension —
   this is a business call, not an engineering one, and isn't answered by
   this document).
9. **Does it justify the complexity?** Unambiguously yes for *some* payment
   mechanism — there is currently no way to collect revenue at all, full
   stop. Whether that justifies Option B's specific complexity *today* is
   the actual open question this BIA is raising.
10. **Is there a simpler solution?** Yes — Option A, and it's the
    recommendation below. At the current scale (one live pilot, one
    internal demo, **zero paying customers**), building webhook-driven
    subscription-lifecycle automation is solving a volume problem that
    doesn't exist yet. This mirrors the same reasoning
    `BIA_team_access_links.md` used to reject a heavier design in favor of
    "the smallest thing that solves the stated problem."

## Cost / Pricing / Feature-Scope Impact

- **Pricing:** No change to the documented $99/month + $399 setup for
  Core. Flagged separately: **tiers beyond Core (Entrepreneur, Business,
  Enterprise) have feature definitions in `ops/launcher_server.py`'s
  `TIER_FEATURES` but no documented price anywhere I could find** — that's
  a real business decision needed before *any* billing implementation,
  manual or automated, can charge for them correctly.
- **Profitability:** New recurring cost either way — Stripe's ~2.9%+$0.30
  per-transaction fee. No new fixed monthly cost at current volume.
- **Setup effort:** Option A — a few hours (Stripe account, invoicing
  habit). Option B — a real multi-day build (webhook handler, event
  idempotency, tier-system integration, testing failure/retry paths).
- **Admin workflow:** Option A changes nothing about how clients are
  currently managed day to day. Option B adds a new failure mode (a
  billing webhook silently not firing) that would need monitoring —
  compounding the existing gap that no uptime/alerting exists yet either
  (see the earlier go-live audit).

## Effort Estimate

Option A: hours. Option B: several days, most of it in testing webhook
reliability and the tier-downgrade path safely against the two real live
instances (LMTLSS, Evolve Credit Repair) without risking an accidental
service interruption for an actual pilot.

## Recommendation

Start with **Option A — manual Stripe Invoicing** for the first handful of
real customers. It requires no code in this repo, no new schema, and no new
infrastructure — just a Stripe account and a habit. Revisit Option B once
there's proven paying volume where manual invoicing is the actual
bottleneck, not before. Before either option can charge correctly, **the
pricing for Entrepreneur/Business/Enterprise tiers needs to actually be
decided** — that's a business decision this document surfaces but doesn't
make.
