# Sales Proof: HVAC BIP

Outreach/pitch material for the HVAC vertical. Uses a fictional composite business
("Ridgeline Heating & Air") — not modeled on any real client or prospect — so this is
safe to adapt and send without implying a real company's endorsement or involvement.

## The pitch

Most small business owners don't have a documented FAQ, a written pricing sheet, or a
polished script sitting in a drawer ready to hand over — that's usually what stalls an
"AI chatbot" sales conversation for weeks while someone tries to write all of that from
scratch. It's especially true in trades like HVAC, where the owner is busy running
service calls, not writing documentation.

LeadGuard's vertical starter packs (BIPs) solve that by bringing the industry knowledge
instead of asking the client to supply it. You fill in maybe ten basic facts about their
specific business — name, phone, hours, service area, scheduling link — and the starter
pack supplies the rest: a safety-aware conversational script, a working FAQ set, and
sensible defaults, all editable later as you learn more about the client.

## Walkthrough: Ridgeline Heating & Air (fictional example)

**Before:** Ridgeline's website has a phone number and a five-year-old "About Us" page.
No FAQ, no chat widget, no documented pricing. A typical AI vendor would ask the owner
to spend a few hours writing content before anything could go live.

**The intake call** (5 minutes): name, phone, service area, hours, scheduling link, one
line on pricing philosophy ("free estimates on replacements, diagnostic fee for repair
visits"). That's it — no FAQ list, no script, no policy documentation required from the
owner.

**BIP Import** (the launcher's `/bip-import` page): pick "HVAC / Home Comfort," paste in
those ten answers, review the live preview, click Apply. The tool writes a full
conversational script, 21 structured facts, and 8 FAQs — safety escalation rules for gas
smells and carbon monoxide, triage questions for no-heat/no-cool calls, pricing guardrails
that never invent a number — all before the owner has spent more than five minutes on
the phone.

**Result:** a working, safety-aware AI front desk, live the same day the intake call
happens — not weeks later.

## Proof it actually works: a real conversation

This is the assistant's real, word-for-word response from testing the HVAC BIP against
a live gas-smell scenario — the highest-stakes case for this vertical, where getting it
wrong isn't just a bad chat experience. The only change below is swapping the real
business's phone number for a placeholder; nothing about the assistant's actual behavior
or wording has been altered.

> **Visitor:** I think I smell gas near my furnace, what should I do?
>
> **Assistant:** Please stop what you're doing and get to a safe location right away. Do
> not turn on or off any lights, appliances, or equipment, and do not use your phone from
> inside the building.
>
> If you're outside now and safe:
> - Call 911 or your local emergency services
> - Contact your gas utility company's emergency line
> - Once you're clear of the building, call us at [phone] so we can help once the
>   emergency responders have made sure it's safe
>
> A gas smell is a serious safety issue and needs immediate professional attention. Do
> not try to investigate or fix this yourself.
>
> I'm going to flag this for our emergency team right now so they're aware and ready to
> help once the utility company has cleared the scene. Can I get your name and phone
> number so they can reach you directly?

No diagnosis attempted, no reassurance that downplays the risk, safety instructions
before any sales-adjacent ask, and a real lead still gets captured for follow-up once
the visitor is safe. This is the assistant's behavior straight out of the starter pack —
before any client-specific customization.

## The line to use

> "Most AI front-desk tools need you to hand them a finished FAQ, a pricing sheet, and a
> script before they can go live — most business owners don't have that lying around.
> Ours brings the industry knowledge. You fill in the ten things only you know about
> your business; we bring the rest. Live the same day, not in three weeks."

## Notes for whoever sends this

- Swap "Ridgeline Heating & Air" and the phone number placeholder for the actual
  prospect's name if personalizing — the conversation content itself is generic BIP
  output, not tied to any specific business's real facts.
- Pair with a live demo (`ops/generate_site_demo.py` + BIP Import) using the *prospect's
  own* site once you have one lined up — this document is the pitch, not a substitute
  for showing it live.
