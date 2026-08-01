# Client → Agency Support/Change Request Channel

Under the managed-service model (you run every instance; clients never log
in), there's no dashboard to embed a "request support" button into — so this
has to be a channel that exists outside the product, not inside it.

## Recommendation: a simple form, not a feature

A Google Form/Typeform, the same pattern as `INTAKE_FORM.md`, given to every
client during onboarding as their one channel for "please change X" or
"something's wrong." Zero engineering, and it gives you a written record of
requests instead of scattered texts/calls/emails.

Suggested fields:

1. **Business name** (so you know whose instance to open).
2. **What do you need?** — dropdown: "Update something (scheduling link,
   hours, pricing, etc.)" / "Something seems broken" / "Add a new
   FAQ/policy" / "Other."
3. **Details** — free text.
4. **How urgent is this?** — dropdown: "Whenever you get a chance" / "This
   week" / "Urgent — affecting customers now."
5. **Best way to reach you if I have questions** — phone/email/text.

Route form responses to your own email or a Slack channel (Google
Forms/Typeform both support this natively) — same notification pattern
already used for the `handoff.notify()` webhook, just pointed at you instead
of the client.

## Where the client gets this link

Hand it to them once, during onboarding — alongside the embed snippet, in
whatever welcome message/email accompanies going live. Worth adding as a
line item to the onboarding workflow in `README.md` once this exists: "share
the support-request form link" sits naturally right next to "embed the
widget snippet."

## When this stops being enough

If request volume grows past what a form-plus-manual-triage can handle
comfortably, or if you want clients to see the status of a request they
submitted, that's the point where it's worth building a real in-product
version — but that likely means Model B (client login) has also become
worth it by then, since a status-visible request needs somewhere for the
client to check it. Not a reason to build either one now.
