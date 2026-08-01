# Client Onboarding Kit

Zero-engineering tools aimed at cutting per-client setup time toward ~1 hour — the technical
spin-up (new instance/process) is already cheap; the real time sink is composing the flow
script and FAQs from scratch each time. Two sources feed setup, split by which is faster in
which format:

- **A written form** for hard facts that are quick and accurate to type (name, hours,
  service area, scheduling link, lead routing).
- **The onboarding call itself** for everything that comes out more naturally in conversation
  than in a form field (tone, real FAQs, edge cases, things to never say) — extracted from
  the Zoom transcript afterward rather than re-asked in writing.

## Workflow

1. Send `INTAKE_FORM.md` Part A to the client before the onboarding call (a Google
   Form/Typeform works well for these 7 questions).
2. Run the onboarding call on Zoom, using Part B of the intake form as your own mental
   checklist to make sure the conversation covers tone, FAQs, pricing guidance, and
   boundaries — don't make the client type long answers to these.
3. After the call, run the transcript through `TRANSCRIPT_EXTRACTION_PROMPT.md` — it drafts
   FAQs, business facts, boundaries, tone, and a first-pass flow script from what was
   actually said.
4. Pick the closest template from `flow_script_templates/`, merge it with the extracted
   draft script (template for structure, draft for the client's actual voice), and paste the
   result into the dashboard's Settings → conversational script field.
5. Copy the extracted FAQs and business facts into the Knowledge tab, crawl the site, set
   the scheduling link/webhook, embed the widget snippet, and test.

If there's no Zoom call for a given client, fall back to asking Part B as form questions too
— the split above is the fast path, not the only path.

## Files

- `INTAKE_FORM.md` — Part A (form) / Part B (call checklist) questions.
- `TRANSCRIPT_EXTRACTION_PROMPT.md` — the prompt to run a Zoom transcript through afterward.
- `flow_script_templates/service_business.md` — contractors, salons, auto shops, fitness
  studios, and similar local service businesses.
- `flow_script_templates/professional_financial_services.md` — credit repair, consulting,
  insurance, and similar categories with real compliance boundaries.
- `flow_script_templates/community_ministry.md` — churches, ministries, membership orgs,
  and other community-first (not sales-first) organizations.

Add a new template file here whenever a client falls outside these three categories clearly
enough that reusing one of the existing ones would require more editing than starting fresh.
