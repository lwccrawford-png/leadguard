# Team Onboarding & Sales Process — EvolveIQ / Lead Launch

Written 2026-08-13, for onboarding the first teammate into client acquisition.
This is the reconciling document — where other strategy docs in this folder
disagree or go stale, this one wins until updated. Read `V1_GAP_ANALYSIS.md`
alongside this before running any live demo — it tells you what NOT to promise.

---

## 1. The Product, In One Paragraph (for demoing)

EvolveIQ is a managed AI front desk for small, local service businesses.
It sits on a client's website, answers visitor questions from that
business's own approved knowledge (not generic AI guessing), qualifies
who's worth following up with, and captures a name/email/phone the moment
someone's ready to talk — then notifies the business by email or Slack so a
real lead never just evaporates into an unanswered chat window. It is
**not** a chatbot builder and **not** a website builder — websites (Lead
Launch) are the on-ramp for businesses that don't have one yet, not the
product itself.

**What it actually does today** (safe to demo, all verified live):
- Answers from structured facts + FAQs, not open-ended generation
- Captures leads and notifies the business in real time
- Hands off a scheduling link pre-filled with the visitor's info (no
  copy-paste)
- Says "I don't know" honestly instead of guessing, and escalates safety-
  critical questions (verified live against a gas-leak scenario)
- Mobile-friendly, works after hours, logs every conversation

**What it does NOT do yet — never promise these in a demo:**
- No live calendar booking (scheduling is a pre-filled link, not real
  availability)
- No phone answering — website only
- No true CRM integration beyond the internal lead board
- No client self-service — this is a *managed* service; clients never log
  into Settings themselves (see `IDEAL_CLIENT_AND_WORKFLOW.md`)
- No vertical beyond **HVAC** has a real, tested knowledge pack yet (Legal
  is next — see §3)

---

## 2. Sales Goal Right Now: 3–5 Paying Customers, Not Volume

Per `GTM_AND_BIP_PRIORITY.md`, Phase 1's explicit goal is converting **3-5
paying customers** — not maximizing outreach volume. Nobody has ever paid
for this product yet. That is the actual current state, and it should shape
how a new teammate is deployed: prove the sales motion and the pricing
before scaling either.

Do not have a new teammate run the full 100-business / 10-industry list
from `LEAD_LAUNCH_STRATEGY.md` on day one. Scope their initial work to the
two verticals with real product behind them (§3), chasing a small number of
real conversations, not maximum coverage.

---

## 3. Target Verticals (reconciled — this supersedes conflicting priority
lists elsewhere in `docs/`)

| Priority | Vertical | Why | Status |
|---|---|---|---|
| 1 | **HVAC / Home Comfort** | Real BIP exists (`onboarding/bips/hvac.md`), high ticket, urgent-need pain is obvious, real demo proof already built | Ready |
| 2 | **Personal Injury Legal** | Already promised on the live marketing site ("Business-tier intelligence"); Mousavi & Associates is already a real prospect in the pipeline | **BIP does not exist yet — build before running more legal demos** |

Everything else in `LEAD_LAUNCH_STRATEGY.md`'s 10-industry list (electricians,
plumbers, roofing, concrete, tree service, mobile mechanics, restoration,
etc.) and `GTM_AND_BIP_PRIORITY.md`'s next-3 (roofing, med spa, auto repair)
is real future work, not a lie — just not yet, and not what a first
teammate should be sent after. Expand only after HVAC + Legal produce real
paying conversations.

---

## 4. Revenue Potential (what to actually say in the room)

**Per-client economic value claim** (already live on the marketing site,
verified consistent with the ROI calculator's math): for an ideal-fit
client, EvolveIQ is designed to produce or protect **$3,000–$15,000/month**
in economic value — by capturing more high-intent opportunities, preserving
paid ad traffic, and catching after-hours inquiries that would otherwise go
to voicemail or a competitor.

**Pricing ladder** (from `GTM_AND_BIP_PRIORITY.md` — do not publish beyond
what's already live; these upper tiers are for sales conversations, not
public rate cards yet):

| Tier | Monthly | Setup | Fit |
|---|---:|---:|---|
| Starter Pilot | $99 | $399 | Early proof, friendly local businesses |
| Vertical Front Desk | $149–199 | $599–799 | HVAC, legal, auto, credit repair — once trust is established |
| Priority Setup | $249–299 | $999–1,299 | Higher-value verticals, stronger lead economics |
| Business tier (published) | $797–997/mo | $1,500–2,500 | Companies where one lead/case/job justifies the subscription outright |

**The framing that matters**: don't defend a price point. Find the highest
number that still reads as an easy yes next to the cost of *one missed
opportunity* in that business's own numbers. A single missed HVAC emergency
call or a single missed PI legal case inquiry is worth more than a year of
the Starter tier — that comparison is the actual pitch, not the software's
feature list.

**Lead Launch** (the website on-ramp, for prospects who need a site too):
$375 one-time build, Evie and hosting free for 60 days, then standard Core
pricing if they keep it or $50/month hosting-only if they don't. This is an
acquisition pathway into Core, not a separate business — see
`LEAD_LAUNCH_STRATEGY.md` §1–2 for the full reasoning.

---

## 5. The Demo-First Acquisition Workflow

Full detail in `LEAD_LAUNCH_STRATEGY.md` §10–12. Summary for a new teammate:

1. Pick a qualified prospect from the Outreach CRM (`/outreach` — see
   `ops/outreach_db.py`), scored per §6 there. Prioritize scores 7–10.
2. Review their Google profile, reviews, current website, and services —
   find the *specific* conversion gap (not just "the site looks old").
3. Generate a private demo: `ops/generate_site_demo.py` builds a real
   screenshot of their homepage with a live widget on top.
4. **Run the pre-send checklist below before anyone outside the company
   sees it.**
5. Send the preview with an outcome-led message (scripts in
   `LEAD_LAUNCH_STRATEGY.md` §12), not a generic "check out our AI tool"
   pitch.
6. Offer activation into Core (or Lead Launch, if they need a site too).

### Pre-send checklist (new — written after the 2026-08-13 Mousavi incident)

A personal injury law firm's demo went out showing HVAC suggested
questions ("My AC is running but not cooling?"). The assistant itself
handled it gracefully by rejecting the mismatch, but it should never have
shipped — this checklist exists so it doesn't happen again, especially once
someone other than the person who built the system is generating demos.

Before sending any demo link to a real prospect:

- [ ] **Suggested questions match the prospect's actual industry** — open
      the generated demo page and read the three starter bubbles out loud.
      If they don't make sense for this business, fix them in that
      instance's Settings before sending. (As of 2026-08-13, new demos
      default to *zero* suggested questions rather than a wrong-industry
      guess — if you see HVAC questions on a non-HVAC demo, something
      regressed; flag it immediately.)
- [ ] **The BIP loaded matches the vertical.** Only HVAC has a real BIP
      today. If the prospect isn't HVAC, the demo is running on generic
      facts/FAQs only — say so honestly in the pitch, don't imply deeper
      vertical intelligence than what's actually loaded.
- [ ] **Ask the assistant 2-3 realistic questions yourself** before sending
      — the exact ones a real visitor from that industry would ask. Confirm
      it answers sensibly or escalates honestly; never sends a fabricated
      answer.
- [ ] **The disclosure text is correct** — every prospect demo must show the
      non-affiliation disclosure (`DEFAULT_DEMO_DISCLOSURE` in
      `ops/launcher_server.py`) with the *correct business name* in it.
- [ ] **The scheduling link (if any) is real and points to a live
      calendar** — not a placeholder.

---

## 6. Roles (once a teammate is in place)

Per `LEAD_LAUNCH_STRATEGY.md` §11, scoped to a 2-person version for now
(Larry + one teammate) rather than the full 3-role model until volume
justifies a third person:

- **Research + Demo**: find and qualify prospects, generate demos, run the
  pre-send checklist. This is the natural first role for a new teammate.
- **Sales/Closer**: outreach, calls, follow-up, closing. Larry, at least
  until the motion is proven — the founder-led sales GTM doc explicitly
  frames the first 3-5 conversions as hands-on, not delegated.

---

## 7. What "Done" Looks Like for This Phase

Per `GTM_AND_BIP_PRIORITY.md` Phase 1, success is **3–5 paying customers**,
tracked manually (conversations, leads captured, bookings clicked,
unresolved questions, owner feedback) — not a dashboard metric yet. Once
that's real, the next phase is verticalizing further (§3's "everything
else" list) and formalizing pricing at whatever tier proved to be an easy
yes in real conversations, not the current provisional numbers.
