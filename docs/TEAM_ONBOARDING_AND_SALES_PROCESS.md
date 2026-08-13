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

## 2. The Actual Goal: Revenue Speed, via Two Parallel Tracks

**Corrected 2026-08-13** — this section previously said "3-5 paying
customers, not volume" and told a new teammate to hold off on outreach
scope. That was too narrow. The real mission, stated plainly: this is a
young company and the first job is getting to revenue as fast as possible.
That means running two tracks at once, not choosing between them.

### Track A — High-ticket vertical intelligence (brand + core offering)

HVAC, Legal, and the rest of the top-ten industry list. Higher ticket,
stronger per-client MRR, but slower and relationship-driven — and gated by
whether a real BIP exists for that vertical (§3). This is the brand the
company is building around long-term, and where the deepest product value
lives.

### Track B — Low-hanging fruit: sole proprietors and 2-3-person operations

Businesses that make real money but leak opportunity because the owner
can't do the work *and* manage leads at the same time — classic Lead Launch
territory (`LEAD_LAUNCH_STRATEGY.md` §6's "Hidden Operators": no site, a
weak site, or a passive site). Lower ticket per client, but the retention
story is strong: get them **one additional client a month** through better
lead capture, and they never leave — especially bundled with the free/cheap
website (Lead Launch's $375 build, 60 days of Evie and hosting free). This
track is **not BIP-gated** the same way Track A is — Lead Launch's assistant
runs off that business's own site content plus basic FAQs, not deep
vertical intelligence, so it can scale across many small-business
categories immediately, without waiting on more BIPs to be built.

### Who works which track

- **Larry and Natalia** work **all three target types personally** —
  high-ticket Track A prospects and Track B low-hanging fruit alike. This
  isn't a segregated org chart; it's where the founders' direct
  relationship-driven selling applies regardless of ticket size.
- **VA teammates get deployed specifically against Track B** to hammer
  volume and push MRR up — Track B's lighter BIP requirements and faster
  sales cycle make it the right fit for scripted, high-volume outreach by
  someone who isn't doing founder-level relationship selling. It is
  completely fine if Track B, run by VAs, is what actually gets this
  company to revenue first while Larry and Natalia are still closing the
  bigger Track A deals.
- **The gate on VA headcount is unit economics, not a calendar date**: as
  long as the profit from the clients a VA closes covers that VA's cost,
  keep deploying them against Track B. If a VA's list stops converting
  profitably, that's the signal to stop or redirect them — not a fixed
  timeline.
- **Open decision, not yet set**: a specific MRR target that defines "we've
  hammered the list enough." Pick a number — this doc will track it in §7
  once set.

---

## 3. Target Segments (reconciled — this supersedes conflicting priority
lists elsewhere in `docs/`)

### Track A — vertical priority (BIP-gated; Larry/Natalia-led)

| Priority | Vertical | Why | Status |
|---|---|---|---|
| 1 | **HVAC / Home Comfort** | Real BIP exists (`onboarding/bips/hvac.md`), high ticket, urgent-need pain is obvious, real demo proof already built | Ready |
| 2 | **Personal Injury Legal** | Already promised on the live marketing site ("Business-tier intelligence"); Mousavi & Associates is already a real prospect in the pipeline | **BIP does not exist yet — build before running more legal demos** |

Everything else in `LEAD_LAUNCH_STRATEGY.md`'s 10-industry list (electricians,
plumbers, roofing, concrete, tree service, mobile mechanics, restoration,
etc.) and `GTM_AND_BIP_PRIORITY.md`'s next-3 (roofing, med spa, auto repair)
is real future work — expand Track A only after HVAC + Legal produce real
paying conversations, and only build/announce a vertical's intelligence
once its BIP is actually real (the pre-send checklist in §5 exists
specifically to stop this line from being crossed by accident).

### Track B — low-hanging fruit (not BIP-gated; VA-suitable)

Any sole-proprietor or 2-3-person operation with real revenue and a
genuine No Website / Weak Website / Passive Website gap, per
`LEAD_LAUNCH_STRATEGY.md` §6. Industry-agnostic — a VA can pull from the
full prospect list here without waiting on a vertical BIP, because the
pitch is "we'll get you an additional client a month and give you a better
website while we're at it," not "we have deep [industry] intelligence."
The three prospect segments and scoring model in `LEAD_LAUNCH_STRATEGY.md`
§6–8 apply directly.

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

**The Track B retention pitch specifically**: for a sole proprietor or
2-3-person operation, the ticket size is smaller, but the story is
stickier — get them **one additional client a month** they wouldn't have
caught otherwise, bundled with a website they needed anyway, and they have
no real reason to ever cancel. Say this plainly in the pitch: "this pays
for itself the first time it catches a lead you'd have otherwise missed
while you were on a job."

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

## 6. Roles

**Corrected 2026-08-13** to match the two-track model in §2, replacing the
earlier single-teammate/single-track version.

- **Larry & Natalia**: relationship-driven selling across *all* target
  types — Track A (HVAC, Legal, top-ten) and Track B (low-hanging fruit)
  alike. Research, demo, and close personally for now on the higher-touch
  Track A deals especially, since those require the most judgment (BIP
  completeness, vertical credibility) and the biggest trust-building.
- **VA teammates (a couple, deployed against Track B)**: research and
  qualify prospects from the low-hanging-fruit segment, generate demos,
  run the pre-send checklist (§5 — applies regardless of track), send
  outreach, and hand off warm responses for Larry/Natalia to close if the
  motion isn't fully delegatable yet. This is volume work by design — the
  point is to hammer the list, not hand-pick a few.
- **Scaling rule for VA headcount**: keep a running tally of (a) what a VA
  costs per month and (b) the profit from clients that VA's list actually
  converts. As long as (b) covers (a), keep going or add another VA. The
  moment a VA's list stops converting profitably, redirect or pause them —
  this is the real gate, not a fixed timeline or a fixed number of VAs.

---

## 7. What "Done" Looks Like for This Phase

Two separate bars, since the two tracks run on different logic:

- **Track A**: per `GTM_AND_BIP_PRIORITY.md` Phase 1, the validation goal
  is **3–5 paying customers** — proving the higher-ticket sales motion and
  pricing works, tracked manually (conversations, leads captured, bookings
  clicked, unresolved questions, owner feedback), not a dashboard metric
  yet.
- **Track B**: a **specific MRR target** — not yet set (see §2). Once
  Larry picks a number, it belongs here, along with the running VA
  cost-vs-profit tally from §6. Track B is "done" (for this phase) when
  that MRR number is hit *and* it was hit profitably, not just hit.

Once both bars are cleared, the next phase is expanding Track A into more
verticals (§3's "everything else" list) and formalizing pricing at
whatever tier proved to be an easy yes in real conversations, not the
current provisional numbers.
