# HVAC Business Intelligence Pack

Version: 1.0.0
Audience: AI SaaS platform teams, implementation partners, RevOps, customer success, and HVAC operators
Status: Production-ready foundation pack
Last reviewed: 2026-08-01

## Purpose

This Business Intelligence Pack (BIP) gives an AI SaaS platform the operating knowledge required to support HVAC service businesses. It is designed for ingestion into a platform that provides AI employees such as receptionist, dispatcher, CSR, sales advisor, customer success assistant, technician assistant, and owner analyst.

The pack includes structured ontology, service catalog, entities, intent library, qualification flows, SOPs, automations, CRM schema, KPI definitions, reporting, integration mappings, compliance boundaries, prompt templates, onboarding requirements, testing scenarios, and deployment guidance.

## Recommended Ingestion Order

1. `manifest.json`
2. `knowledge/taxonomy.json`
3. `knowledge/ontology.json`
4. `knowledge/entities.json`
5. `knowledge/services.json`
6. `workflows/customer_journeys.json`
7. `workflows/intents.json`
8. `workflows/qualification_flows.json`
9. `workflows/escalation_rules.json`
10. `workflows/sops.json`
11. `workflows/troubleshooting_trees.json`
12. `workflows/automations.json`
13. `schemas/data_model.json`
14. `schemas/crm_schema.json`
15. `schemas/api_mappings.json`
16. `schemas/config_template.json`
17. `conversation/conversation_library.json`
18. `conversation/objections.json`
19. `analytics/kpis.json`
20. `analytics/reports.json`
21. `knowledge/knowledge_graph.json`
22. `knowledge/compliance.json`
23. `testing/testing_scenarios.json`

## Module Map

| Module | Purpose |
|---|---|
| `knowledge/` | Domain concepts, services, entities, compliance, graph relationships |
| `workflows/` | Intents, journeys, qualification, SOPs, automations, escalation, troubleshooting |
| `schemas/` | Canonical SaaS data model, CRM fields, API mappings, tenant configuration |
| `conversation/` | Example conversations, language patterns, objections, rebuttals |
| `analytics/` | KPI formulas, report structures, owner/manager dashboards |
| `docs/` | Operating manual, prompt templates, sales playbooks, deployment guide |
| `onboarding/` | Implementation checklist |
| `testing/` | Acceptance scenarios and edge-case test suite |

## Pack Design Principles

- Sell business outcomes, not AI features.
- Treat every customer interaction as a stage in an operating workflow.
- Prefer safe triage and escalation over technical diagnosis.
- Never provide guaranteed pricing, warranty coverage, financing approval, tax advice, legal advice, or unsafe repair instructions.
- Configure company-specific facts before production use.
- Record provenance for all compliance-sensitive claims.
- Use human review for emergencies, complaints, payments, financing applications, warranty disputes, and any safety-sensitive condition.

## Supported HVAC Segments

- Residential service
- Residential replacement
- Residential maintenance
- Light commercial service
- Light commercial replacement
- Commercial rooftop units
- Ductless mini-splits
- Heat pumps
- Furnaces
- Boilers
- Indoor air quality
- Ductwork
- Refrigeration service
- Maintenance agreements

## Sources To Keep Current

Compliance and incentive items change. Review these before each production release:

- EPA HFC Technology Transitions Program
- EPA Section 608 technician certification and refrigerant management
- ENERGY STAR and DOE efficiency/tax-credit guidance
- FTC Cooling-Off Rule for in-home sales
- FCC/TCPA and state consent rules for calls/texts
- State HVAC licensing boards
- Local permit authorities

