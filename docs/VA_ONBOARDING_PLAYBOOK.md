# VA Onboarding Playbook — Track B Outreach

Written 2026-08-16, before any VA has been hired. Purpose: everything a VA
needs is ready before day one, so hiring one is "plug and play" instead of a
scramble. Read `TEAM_ONBOARDING_AND_SALES_PROCESS.md` first — this doc is the
day-to-day operating manual that sits underneath it, specific to the
automated-email-plus-VA play for Core / the LeadGuard package.

---

## 1. The product, in the words a VA actually needs

EvolveIQ is a managed AI front desk for small, local service businesses. It
sits on a client's website, answers visitor questions from that business's
own approved knowledge, qualifies who's worth following up with, and
captures a lead the moment someone's ready to talk — then notifies the
business so a real lead never evaporates into an unanswered chat window.
Full version: `TEAM_ONBOARDING_AND_SALES_PROCESS.md` §1.

**The one framing that matters on every call:** it supports the business's
current team, it does not replace anyone. Lead with that if it comes up —
don't wait for the objection.

---

## 2. Before a VA's first day — Larry's setup checklist

Nothing below is the VA's job to arrange. Have this ready before they start:

- [ ] Telnyx number provisioned and assigned to the existing compliant
      messaging campaign (local area code matching the target market —
      local numbers get answered; unfamiliar/out-of-area ones often don't)
- [ ] A branded email address (`firstname@justaskevolveiq.com`), not a
      personal Gmail
- [ ] CRM login — access to the Outreach tab in the launcher
      (`team.justaskevolveiq.com`), where the prospect list, cadence, and
      script library (§4 below) all live
- [ ] View access to the booking calendar (TidyCal) so they can see
      upcoming booked calls
- [ ] TidyCal SMS reminders enabled (Agency plan — already active) on the
      booking type reps use
- [ ] The Zapier "new booking → notify VA" automation connected (Slack,
      email, or text — whichever the VA will actually check in real time)
- [ ] A consistent name/identity the VA introduces themselves with — same
      name on the email signature, the caller ID, and the calendar invite
      for a given prospect, not a different name per channel

---

## 3. The daily routine

Four buckets, roughly in priority order:

1. **Confirm tomorrow's booked calls first, every day.** Check the booking
   calendar (or the Zapier notification if it fired overnight). Call each
   one using the `call_confirmation` script (§4). If no answer, leave a
   voicemail and send the `text_confirmation` script. This is the single
   highest-leverage task of the day — a no-show costs a real, already-won
   call slot.
2. **Handle warm replies.** Anyone who replied to the automated email
   sequence or clicked their demo link gets a phone follow-up the same day
   if possible — that interest decays fast. Use the existing cadence
   scripts (`email`, `day7_followup`, etc.) as the basis, adjusted to what
   they actually said.
3. **Research and personalize new prospects.** Add them to the Outreach
   CRM with a real personalization hook and evidence (not just a company
   name and phone number pulled from a list) — the whole reason this
   channel outperforms generic cold email is that each one is specific.
   Run the pre-send checklist (§5) on the generated demo before it queues
   to send.
4. **Log every touch.** Every call, text, and outcome goes into the CRM
   against that prospect — not a personal notebook, not memory. Larry sees
   what's working in real time only if this is done consistently.

---

## 4. Scripts

Live, editable versions of all of these are in the CRM's script library
(`GET /api/outreach/scripts` in the launcher's Outreach tab) — treat that as
the source of truth, not this doc, since scripts get tuned over time. As of
this writing:

**Cold-cadence scripts** (`ops/outreach_db.py`, `DEFAULT_SCRIPTS`):
`call_owner`, `call_gatekeeper`, `voicemail`, `text_after_voicemail`,
`email`, `video_outline`, `day7_followup`, `day12_closeloop`.

**Booked-call confirmation scripts** (new, added alongside this doc):
`call_confirmation` (day-before phone call) and `text_confirmation`
(text/voicemail follow-up). These aren't part of the cold cadence — they
fire off a booked call date, not days-since-first-touch, so they won't show
up on a prospect's cadence view. Pull them from the full script library.

All scripts use the same merge-field style: `{{name}}`, `{{company}}`,
`{{rep}}`, `{{vertical}}`, `{{hook}}`, `{{demo_link}}`, `{{time}}`.

---

## 5. Pre-send checklist (mandatory, every demo, no exceptions)

Copied in full from `TEAM_ONBOARDING_AND_SALES_PROCESS.md` §5 — repeated
here because this is the step most likely to get skipped under volume
pressure. A personal injury law firm once had HVAC questions shown on its
demo because this got skipped. Never again:

- [ ] Suggested questions match the prospect's actual industry
- [ ] The BIP loaded matches the vertical (only HVAC has a real one today —
      say so honestly if the prospect isn't HVAC, don't imply intelligence
      that isn't loaded)
- [ ] Ask the assistant 2-3 realistic questions yourself before sending
- [ ] The disclosure text shows the correct business name
- [ ] The scheduling link is real and points to a live calendar, not a
      placeholder

---

## 6. Objection handling

Real answers, not deflections — the product's actual boundaries matter more
than sounding smooth. Never promise past what's true (§7).

**"Is this going to replace my staff / take jobs?"**
No — it's built to support your current team, not replace them. It catches
the calls and messages that are currently going unanswered after hours or
during a rush, and hands your team a clean lead instead of a missed
opportunity. Nobody's job changes; you just stop losing the ones you're
losing today.

**"How much does this cost?"**
[Give the real Core number, not a vague range.] The way to think about it:
one missed call in your business is usually worth more than a year of this.
Try the demo first — the ROI conversation only makes sense once you've seen
what it actually catches.

**"How did you get my information / is this legit?"**
Fair question. The demo was built from information that's already public on
your own website — nothing scraped that wasn't already visible to anyone.
It's not live on your site and we're not affiliated with your business
unless you say so — that's stated right on the demo page itself.

**"We already have [a chatbot / answering service / something like this]."**
Good — that means you already know the value of not missing a lead. Worth
two minutes to see how this compares? If it's not better than what you have,
no hard feelings.

**"Not interested."**
No pressure — mind if I leave the link in case it's useful later? [If firm
no:] Understood, I'll take you off the list.

**"Send me more information by email instead."**
Happy to — but the fastest way to actually evaluate this is the live demo,
not a deck. [Send the email script (§4) with the demo link front and
center, not a generic brochure.]

**"What happens to the data / conversations it captures?"**
Every conversation is logged for the business's own review — it's not
shared, sold, or used to train anything outside this deployment.

---

## 7. Hard boundaries — never promise these

Copied from `TEAM_ONBOARDING_AND_SALES_PROCESS.md` §1. If a prospect asks
about any of these, be honest that it's not there yet rather than implying
otherwise to close the call:

- No live calendar booking — it's a pre-filled scheduling link, not real
  real-time availability
- No phone answering — website only
- No true CRM integration beyond the internal lead board
- No client self-service — this is a managed service; clients never get
  Settings access themselves
- No vertical beyond HVAC has a real, tested knowledge pack yet

---

## 8. CRM discipline

Every prospect's status, cadence step, and touch history lives in the
Outreach CRM (`ops/outreach_db.py`, surfaced in the launcher's Outreach
tab) — not a spreadsheet, not memory, not a personal note. This is what
lets the cost-per-lead and cost-per-booked-call numbers stay real instead
of guessed, and it's what a second VA (or Larry) needs to pick up a
prospect's history without starting over.
