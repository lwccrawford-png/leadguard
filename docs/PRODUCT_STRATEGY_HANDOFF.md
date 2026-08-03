# Product Strategy Handoff Specification

Project: Business Intelligence Platform (Working Vision)

## Executive Summary

This project is not an AI company.
It is not a chatbot.
It is not an AI agency.

It is a SaaS platform whose purpose is to capture, organize, amplify, and continuously
improve the unique knowledge that makes every business successful.

Artificial Intelligence is simply the interface. The true product is the customer's
Business Intelligence.

## Core Philosophy

Every successful business has accumulated years of knowledge. That knowledge exists
inside:

- Owners
- Employees
- SOPs
- Training
- CRM notes
- Emails
- Estimates
- Customer conversations
- Documents
- Policies
- Websites
- Sales processes

Unfortunately, that knowledge is fragmented.

When employees leave, knowledge leaves. When customers ask questions, only part of the
business is represented. When AI searches the website, it sees only a fraction of what
the company actually knows.

Our platform solves this problem. We transform a company's knowledge into a living
intelligence layer that powers every customer interaction.

## Vision Statement

Every business is built on knowledge. We give that knowledge a bigger voice.

## Mission

Transform business knowledge into an intelligent operating platform that learns
continuously and improves every customer interaction.

## Positioning

Do NOT position this product as:

- AI Chatbot
- AI Website Assistant
- AI Receptionist
- AI Agency
- AI Automation Company

Instead position it as: **A Business Intelligence Platform**, or **A Living Business
Knowledge Platform**. The AI is merely the interface into that intelligence.

## The Customer Problem

Businesses evolve every day. Their websites do not.

Their employees learn. Their websites don't. Their processes improve. Their websites
don't. Their services expand. Their websites don't. Their expertise compounds. Their
websites stay static.

Customers interact with an outdated version of the business. This platform fixes that.

## Core Promise

Your business shouldn't just have a website. It should have a voice.

## Primary Value Proposition

Our platform captures your business knowledge and transforms it into an intelligent
digital experience that can:

- Answer questions
- Educate customers
- Qualify leads
- Schedule appointments
- Support employees
- Guide buyers
- Recover missed opportunities
- Preserve institutional knowledge
- Improve continuously

## Strategic Differentiator

Competitors automate conversations. We amplify business intelligence.

Competitors deploy chatbots. We deploy a living representation of the business.

Competitors create AI assistants. We create an intelligent operating layer.

## Platform Architecture

**Layer 1 — Business Knowledge:** company information, policies, processes, FAQs,
products, services, pricing rules, documents, training, sales processes, compliance,
brand voice, customer history, institutional knowledge.

**Layer 2 — Business Intelligence Engine:** normalizes, organizes, indexes, learns,
searches, connects relationships, maintains context, improves continuously.

**Layer 3 — Business DNA:** unique workflows, company terminology, decision
frameworks, escalation rules, culture, best practices, operational logic, competitive
advantages.

**Layer 4 — Digital Workforce:** receptionist, sales advisor, customer success,
dispatcher, knowledge expert, operations assistant, executive assistant, trainer,
estimator, future AI roles. Each role operates from the same Business Intelligence
Engine.

**Layer 5 — Channels:** website, voice, SMS, email, CRM, internal portal, future
agent-to-agent, future APIs, future mobile applications. Every channel shares the same
intelligence.

*Status note: LeadGuard v1 today implements Layer 1 (structured facts/FAQs + site
crawl) and a single Layer 5 channel (website widget). Layers 2-4 and the rest of Layer
5 are the working vision this document describes, not yet built — see
`V1_GAP_ANALYSIS.md` for current implementation status. Marketing and product copy
should be honest about this distinction: position today's product as the first
chapter of this platform vision, not claim capabilities (voice, SMS, CRM writeback,
multi-role "digital workforce") that don't exist yet.*

## Product Principles

Every feature must satisfy at least one of the following:

- Capture knowledge.
- Organize knowledge.
- Improve knowledge.
- Deliver knowledge.
- Protect knowledge.
- Measure knowledge.

Never build features simply because competitors have them.

## Business Intelligence Packs (BIPs)

Every industry receives a Business Intelligence Pack. Each BIP contains: industry
ontology, business vocabulary, customer journeys, conversation library, intent
catalog, knowledge graph, operational playbooks, compliance boundaries, KPIs,
automation recipes, CRM mappings, reporting, prompt templates, testing scenarios,
deployment configuration.

The BIP should represent years of industry expertise.

*Status note: `onboarding/bips/hvac_json/` is exactly this richer vision, already
scaffolded for HVAC as reference material. `onboarding/bips/hvac.md` is the
v1-compatible subset actually wired into the product today (flow script + facts +
FAQs) via the Fast BIP Import tool. See `docs/CLAUDE_CODE_HANDOFF_HVAC_BIP.md`.*

## Company Intelligence

Each customer extends the industry pack with: business-specific terminology, policies,
services, pricing philosophy, documents, processes, FAQs, CRM history, employee
knowledge, operational procedures.

This becomes that company's Business DNA.

## Continuous Learning

Every interaction should strengthen the platform.

New questions → new knowledge → better answers → better customer experience → more
business intelligence → better future conversations.

The system compounds in value over time.

## Website Messaging Direction

Avoid technology-first messaging. Lead with transformation.

Primary headline direction:

> Your Business Is Built On Knowledge.
> It's Time To Give It A Bigger Voice.

Supporting message:

> Your business evolves every day. Your website shouldn't be left behind. Transform
> everything your business knows into an intelligent experience that serves
> customers, supports employees, and grows with your business.

## Language Guidelines

**Preferred:** Business Intelligence, Knowledge, Experience, Expertise, Voice, Growth,
Learning, Operational Intelligence, Business DNA, Living Platform.

**Avoid:** Bot, Chatbot, Prompt, LLM, GPT, Automation, AI-first messaging, Model,
Tokens — unless speaking to technical buyers.

## Success Metrics

The platform should help customers measure outcomes, not activity. Examples: revenue
influenced, appointments booked, missed opportunities recovered, response time,
knowledge growth, customer satisfaction, employee time saved, estimate recovery,
membership growth, review generation, referral generation, business knowledge
expansion.

## Long-Term Vision

The website is only the beginning. The Business Intelligence Engine should become the
foundation for every future customer interaction, every digital employee, every
workflow, every automation, and every AI-to-AI transaction.

The goal is not to build the best chatbot. The goal is to become the operating
intelligence behind modern service businesses.

## Engineering Directive

Every architectural decision should answer one question: **Does this make it easier
for a business to capture, organize, amplify, and continuously improve its unique
knowledge?**

If the answer is no, reconsider whether the feature belongs in the core platform.

This principle should guide product design, engineering priorities, UX, integrations,
data architecture, and future roadmap decisions.
