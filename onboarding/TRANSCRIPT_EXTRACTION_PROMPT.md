# Zoom Transcript → Client Config Extraction Prompt

After a Zoom onboarding call, paste the transcript into a Claude conversation along with the
prompt below. It returns Part B of the intake form (see `INTAKE_FORM.md`) pre-filled from what
was actually said, plus a first-draft flow_script — ready to review and paste into the
dashboard, not authored from a blank page.

This is a manual step (you run it, you review the output before it goes live) — nothing here
calls the LeadGuard app or touches its database.

---

## Prompt to use

```
Below is a transcript of an onboarding call with a new LeadGuard client. Extract the
following, using only what was actually said — don't invent or assume anything not in the
transcript, and mark anything not covered as "NOT MENTIONED — ask separately":

1. BUSINESS DESCRIPTION: one or two sentences describing what they do, in language close to
   how they described it themselves.

2. PRICING GUIDANCE: how they want the assistant to handle pricing questions — a range they're
   comfortable sharing, a starting price, or "always defer to a call."

3. FAQS: every question-and-answer pair the client mentioned that customers commonly ask,
   even if it came up informally rather than as a direct "here's our FAQ" moment. Format as
   Q/A pairs.

4. BUSINESS FACTS: any standalone facts mentioned that the assistant should always know and
   state exactly as given — phone number, address, certifications, guarantees, specific
   policies (refund/cancellation/etc.), years in business, service area details.

5. NEVER SAY / BOUNDARIES: anything the client said the assistant should avoid — specific
   promises not to make, competitors not to mention or disparage, compliance/legal lines not
   to cross, topics to redirect to a human.

6. TONE: 2-3 words capturing how they want to come across, inferred from how they talk about
   their own business and any explicit preferences they stated (e.g. "we're pretty casual,"
   "we need to sound professional because of compliance").

7. HANDOFF PREFERENCE: how they said they want to be looped in when the assistant can't
   help — phone, text, email, or just capture-and-follow-up.

8. DRAFT FLOW SCRIPT: using items 1, 2, 5, and 6 above, write a first-draft conversational
   script in the voice of a business owner briefing a new front-desk hire (2-4 short
   paragraphs) — the kind that would go in LeadGuard's Settings → conversational script
   field. Flag it clearly as a draft for human review, not a final version.

Output each section with its own header so it's easy to copy pieces into separate places.

Transcript:
[PASTE TRANSCRIPT HERE]
```

---

## After running it

- Copy the FAQS section straight into the Knowledge tab's FAQ entries.
- Copy BUSINESS FACTS into Business Facts entries.
- Review DRAFT FLOW SCRIPT against the closest template in `flow_script_templates/` — often
  faster to merge the two than to use either alone: template for structure, draft for the
  client's actual voice and specifics.
- Anything flagged "NOT MENTIONED" — either it wasn't covered on the call (follow up
  directly) or it's a Part A item that's already on the written form.

## If this becomes a recurring bottleneck

Right now this is a copy/paste step you run by hand. If you're doing enough onboardings that
running this manually every time gets old, the next step up is a dashboard button that
uploads a transcript and calls Claude once to pre-fill the Knowledge tab directly — that's a
real feature (new cost per onboarding call, touches the ingestion flow), so it'd need a quick
Business Impact Analysis before building. Not worth it until the manual version is the actual
friction point.
