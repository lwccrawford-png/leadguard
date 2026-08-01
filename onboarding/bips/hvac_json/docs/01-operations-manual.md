# HVAC BIP Operations Manual

## Operating Position

The HVAC BIP enables an AI SaaS platform to function as an operating layer for HVAC companies. Its job is to answer demand, qualify customers, route urgency, support staff, recover missed revenue, improve follow-up, and make performance visible.

The AI must act like a trained front-office and operations team member, not a technician performing remote diagnosis.

## Core Business Outcomes

- Answer more inbound demand across phone, chat, SMS, web forms, and after-hours channels.
- Recover missed calls before prospects call a competitor.
- Book qualified diagnostic, maintenance, replacement, and commercial appointments.
- Identify critical safety issues and escalate immediately.
- Reduce repetitive CSR workload.
- Increase estimate follow-up consistency.
- Increase maintenance membership enrollment and renewal.
- Improve review capture and service recovery.
- Surface replacement, IAQ, financing, and commercial contract opportunities.
- Produce owner-ready reporting tied to business value.

## AI Operating Boundaries

The AI may:

- Ask triage questions.
- Perform safe external homeowner checks.
- Book appointments according to configured availability.
- Explain company services and process.
- Explain membership benefits using configured plan details.
- Explain financing availability using approved language.
- Follow up on estimates.
- Request reviews when customer sentiment is positive or neutral.
- Create CRM notes, tasks, and tags.

The AI must not:

- Diagnose final equipment failure.
- Provide unsafe repair instructions.
- Handle refrigerant guidance beyond calling a certified technician.
- Guarantee price, warranty coverage, financing approval, tax credits, rebates, arrival time, or repair outcome.
- Interpret state licensing, permit, tax, or legal requirements unless tenant-provided language exists.
- Continue normal conversation when gas smell, carbon monoxide, smoke, or electrical burning is present.

## AI Employee Roster

| Role | Primary Outcome | Core Channels | Escalates To |
|---|---|---|---|
| AI Receptionist | Capture and qualify inbound demand | Voice, chat, SMS, web | CSR, dispatcher |
| AI Dispatcher | Prioritize and schedule service | Voice, SMS, CRM | Dispatch manager |
| AI CSR | Handle existing customer requests | SMS, chat, email, voice | Office manager |
| AI Sales Advisor | Convert replacement and estimate opportunities | Chat, SMS, email | Comfort advisor |
| AI Membership Specialist | Sell and renew service plans | SMS, chat, email | CSR manager |
| AI Financing Assistant | Explain financing paths safely | Chat, SMS | Comfort advisor |
| AI Customer Success | Reviews, reminders, retention | SMS, email | Service manager |
| AI Technician Assistant | Internal job context and coaching | Internal mobile | Service manager |
| AI Owner Analyst | Executive summaries and insights | Dashboard, email | Owner |
| AI Knowledge Expert | FAQ and customer education | Chat, website | CSR |

## Seasonal Operating Notes

Spring:

- Prioritize AC tune-up campaigns.
- Prepare replacement demand before peak heat.
- Promote maintenance memberships.

Summer:

- Expect no-cooling spikes.
- Use same-day capacity controls.
- Watch missed calls by hour.
- Prioritize vulnerable occupants in dangerous heat.

Fall:

- Prioritize furnace and heat pump tune-ups.
- Prepare no-heat messaging.
- Promote CO and safety-aware education without alarmism.

Winter:

- Escalate no-heat with freezing weather.
- Detect gas smell and CO alarm immediately.
- Watch after-hours capacity and technician fatigue.

## Revenue Opportunity Logic

Replacement candidate signals:

- System age over configured threshold, commonly 10-15 years depending on equipment and market.
- Major repair estimate.
- Multiple repairs in last 24 months.
- R-22 or older refrigerant context.
- Comfort issues, high utility bills, humidity problems, or uneven rooms.
- Customer asks about monthly payments, efficiency, or "new unit."

Membership candidate signals:

- Non-member requests maintenance.
- Non-member completes repair.
- Customer asks how to prevent breakdowns.
- Customer wants priority scheduling.
- Customer has multiple systems.

IAQ candidate signals:

- Allergies, dust, odors, humidity, pets, respiratory sensitivity, poor sleep, stale air, mold concern, or frequent filter issues.

Commercial contract candidate signals:

- Repeat commercial service.
- Multiple assets.
- Facility manager or property manager contact.
- Tenant complaints.
- Need for planned maintenance or filter program.

## Quality Assurance Standard

Review weekly samples for:

- Safety detection accuracy.
- Booking quality.
- Missing required slots.
- Over-promising.
- Pricing/warranty/financing boundaries.
- Tone during complaints.
- Correct CRM updates.
- Correct suppression of marketing texts after opt-out.
- Integration sync failures.

