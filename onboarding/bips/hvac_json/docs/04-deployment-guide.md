# HVAC BIP Deployment Guide

## Deployment Phases

### Phase 1: Readiness

Collect:

- Business profile
- Service area
- Hours and after-hours policy
- Booking rules
- Emergency transfer numbers
- CRM access
- Calendar/dispatch access
- Membership plans
- Financing provider language
- Diagnostic/trip fee disclosure policy
- Review link
- Consent policy
- Existing scripts and FAQs

Deliverables:

- Completed `schemas/config_template.json`
- Integration access validated
- Human escalation targets confirmed
- Compliance scripts approved

### Phase 2: Configuration

Configure:

- Tenant identity and tone.
- Service segments.
- Allowed services.
- Booking availability and appointment types.
- Emergency and after-hours rules.
- CRM object mappings.
- SMS/email templates.
- KPI assumptions.
- Suppression rules.

### Phase 3: Dry Run

Test:

- No cooling.
- No heat.
- Gas smell.
- Replacement quote.
- Financing inquiry.
- Membership question.
- Estimate follow-up.
- Commercial request.
- Complaint.
- Opt-out.
- CRM outage.

Acceptance:

- Critical cases escalate.
- Bookings create correct CRM jobs.
- Consent rules work.
- AI does not provide unsafe repair instructions.
- Reports separate estimated and actual revenue.

### Phase 4: Pilot

Recommended pilot scope:

- Web chat.
- Missed-call SMS recovery.
- Appointment request qualification.
- CRM notes.
- Human approval before booking if the company is operationally immature.

Pilot length:

- 14-30 days.

Daily review:

- Conversations.
- Escalations.
- Bookings.
- Integration errors.
- Customer complaints.

### Phase 5: Production

Enable:

- AI booking.
- After-hours triage.
- Estimate follow-up.
- Membership campaigns.
- Review requests.
- Owner reports.

Monitor:

- Safety escalations.
- Opt-outs.
- Booking errors.
- Over-promising.
- Missed fields.
- Revenue attribution accuracy.

## Rollback Plan

If critical errors occur:

1. Disable autonomous booking.
2. Keep AI in capture-and-route mode.
3. Disable outbound campaigns.
4. Route all emergency and complaint flows to humans.
5. Review transcripts and patch configuration.
6. Re-test affected scenarios.

## Production Acceptance Checklist

- Tenant configuration complete.
- CRM mapping tested.
- Calendar booking tested.
- Escalation phone numbers tested.
- Emergency scripts approved.
- Pricing language approved.
- Financing language approved.
- Warranty language approved.
- Consent policy approved.
- Test scenarios passed.
- Owner dashboard validated.
- Human team trained on handoff notes.

