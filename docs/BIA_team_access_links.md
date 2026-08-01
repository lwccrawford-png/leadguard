# Business Impact Analysis — Team Access Links

Prepared 2026-07-30, per the Business Impact Gate in `V1_ARCHITECTURE_SPEC.md`
(new table + an access-control change to the dashboard — explicitly gated).
Not yet approved; no code changes have been made.

## What's being proposed

Replace "share one dashboard URL with the whole team" with **named,
individually-revocable access links** — one per person, generated on
demand, killable one at a time without affecting anyone else's access.

This directly answers the gap identified this session: under a single
shared URL, cutting off one departing employee means either leaving their
access live indefinitely, or rotating the link and redistributing it to
everyone else. For a client whose staff turns over normally (a roofing
crew, seasonal hires), that's not acceptable — access has to be revocable
per person, not per business.

### Concrete scope

1. **`team_access_links` table** — id, name, token (long random
   URL-safe string), role (`principal` / `admin` / `staff`, default
   `staff`), created_at, revoked_at (nullable — null means active). No
   password, no username, no email verification flow — just a named,
   roled link.
2. **A token check in front of the dashboard's API** — every dashboard
   management endpoint (Settings, Knowledge, Leads, Pipeline, Conversations,
   Usage) requires a valid, non-revoked token. The public chat endpoint the
   widget calls (`/api/chat`) is untouched — visitors never see or need a
   token. Checked on every request, not just once at page load, so
   revocation takes effect immediately, including in an already-open tab.
3. **A "Team Access" panel, visible only to `principal`/`admin` roles** —
   staff-tier links don't see this panel at all, not even a disabled or
   read-only version of it. Inside: a name field, a role selector
   (Principal / Admin / Staff, defaulting to Staff), and a "Create link"
   button that immediately shows a copyable URL
   (`.../dashboard/?t=<token>`) to text or email to that person. Below
   that, a list of existing names with their role and a "Revoke" button.
   Trust is not assumed by default — regular staff get exactly enough
   access to work leads/pipeline cards, nothing about who else has access
   or the ability to change it.
4. **Hard cap: at most one active Principal and one active Admin at a
   time.** Attempting to create a second Principal or second Admin while
   one is already active is blocked with a clear message ("Only one
   Principal and one Admin allowed — revoke the existing one first to
   reassign"). Staff links are uncapped.
5. **First link at onboarding** — the agency generates the client's
   Principal link (and Admin link, if they have one) as the last
   onboarding step and hands it over; from there, the Principal/Admin adds
   and revokes Staff links themselves, without contacting the agency for
   routine turnover.

### Decision now resolved

Originally proposed a flat model — any valid link could manage the team
list, on the reasoning that a 1-10 person team has baseline mutual trust.
Corrected: in a sales environment, trust isn't the right default — access
to *grant or revoke access* is restricted to exactly the Principal and
Admin, identified by a simple role tag at creation time, not inferred or
left open. Everyone else gets working access to the boards and nothing
more. This is a small addition on top of the original design (one `role`
column, one visibility check, one cap rule) rather than a different
architecture.

This remains a narrow, deliberate exception to the managed-service (Model
A) decision — the Principal/Admin get this one self-service capability,
nothing else in Settings/Knowledge/config. The reasoning: access
revocation is time-sensitive in a way no other config change is — nobody
urgently needs a scheduling link updated the moment they fire someone, but
they do need that person's access gone immediately, not whenever the
agency next responds to a support request.

## Architectural Review (per the spec's own required questions)

1. **Does this already exist?** No — today "access" is a single unguarded
   dashboard URL. Nothing resembling per-person identity or revocation
   exists anywhere in the product.
2. **Can an existing component be extended?** Partially — this reuses the
   existing FastAPI router structure (one new dependency/check applied to
   existing endpoints) rather than a parallel auth system, but it's a
   genuinely new capability, not an extension of something already there.
3. **Technical debt created?** Low, if kept to this scope. The real risk is
   scope creep toward full accounts (passwords, roles, permission tiers) —
   deliberately avoided here in favor of the smallest thing that solves the
   stated problem.
4. **Duplicate functionality?** None — `claimed_by` today is free text;
   this doesn't replace it, though it's worth noting as a nice side effect
   that a claim could later auto-fill from the link's name instead of being
   retyped, if that's wanted.
5. **Increases infrastructure?** No. Same SQLite database, one new table.
   No new services, no external auth provider.
6. **Increases token usage?** None — purely a dashboard access-control
   feature, no interaction with the chat engine or Claude API at all.
7. **Increases operating cost?** No new recurring cost. Pure one-time
   development cost.
8. **Increases implementation complexity?** Yes, moderately — one new
   table (with a role column and a cap rule, not just a flat list), an
   auth dependency added to every protected route, a role check specifically
   on the Team Access endpoints, token read/store/attach logic in the
   dashboard's own `app.js`, and the new Team Access panel with
   role-based visibility. Smaller than the Pipeline board BIA (one table,
   not three; no Kanban generalization, no collapse/expand) but a bit more
   than the leanest possible version of this feature — the role tier is a
   deliberate, requested addition, not scope creep.
9. **Does it justify the complexity with customer experience gains?** Yes
   — this fixes a real trust and liability problem for the client (a
   departed employee retaining access to leads/conversations indefinitely
   is a genuine risk they'd rightly object to once they thought about it),
   and it does so without asking them to manage passwords or learn a login
   system.
10. **Is there a simpler solution?**
    - Rotate one shared link on every departure — rejected per the earlier
      discussion: it punishes the whole team for one person's departure
      and depends on the agency noticing and acting promptly.
    - Full accounts with passwords — rejected as more than this problem
      needs; token-based named links solve per-person revocation without
      the password/login-flow overhead.

## Cost / Pricing / Feature-Scope Impact

- **Pricing:** No change. This is a trust/security fix expected as part of
  the base product, not an upsell — unlike the Pipeline board, this
  shouldn't be gated behind the paid add-on.
- **Profitability:** No new recurring cost — no new infrastructure, no new
  API usage. One-time development cost only.
- **Setup effort:** One additional onboarding step (generate the first
  named link instead of handing out a bare URL) — small, and it replaces a
  step that already existed (sharing dashboard access) rather than adding a
  new one.
- **Admin workflow:** The Team Access panel is new, but it's the smallest
  possible version of "manage who has access" — a name, a link, a revoke
  button.

## Effort Estimate

Smaller than the Pipeline board BIA — one new table instead of three, and
a much simpler UI (a name list with add/revoke, no board, no drag-drop, no
collapse states). Comparable in size to the original Leads Kanban build.
The auth-check-on-every-request piece is the part worth being careful
with — it has to run for every dashboard API call, not just page load, or
revocation won't be immediate.

## Recommendation

Approve as scoped: one new table with a `role` column (`principal` /
`admin` / `staff`), a token check in front of every dashboard route (chat
endpoint untouched), a Team Access panel visible only to Principal/Admin
roles, and a hard cap of one active Principal and one active Admin at a
time. Staff links get working dashboard access only — no visibility into,
or ability to change, who else has access.
