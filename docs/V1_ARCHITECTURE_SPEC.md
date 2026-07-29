# V1 Product & Architecture Specification

Received 2026-07-29. This is the product's governing engineering/decision
philosophy — the "how we build," paired with `V1_UPDATE_SPEC.md` (the "what
we build").

## Clarification of Role

Acting as lead software architect and senior AI engineer responsible for
evolving this product beyond individual coding tasks — decisions should
improve product quality, customer experience, performance, maintainability,
scalability, profitability, and long-term product viability. This
specification is the product's source of truth.

## Mission

Build an AI Business Representative rather than a chatbot: an AI employee
capable of understanding a client's situation, providing contextual guidance,
recommending next steps, executing business workflows, and seamlessly
transitioning customers into the business's sales and service processes.
Every architectural decision should support this mission.

The V1 product is a plugin priced at $79-99/month with a wide profit margin,
while remaining cost-effective to operate. The ultimate goal is a product with
an admin/portal layer that allows moving quickly from client to client to make
updates and perform maintenance efficiently, without being exposed to the risk
of housing sensitive information.

## Development Philosophy

Prioritize, in order:
1. Simple architecture over clever architecture.
2. Fast responses over unnecessary reasoning.
3. Structured knowledge over repeated retrieval.
4. Reusable components over duplicated code.
5. Configuration over hardcoding.
6. Business value over technical novelty.
7. Small incremental improvements over large rewrites.

## Engineering Principles

The existing codebase is an investment. Do not rewrite working systems unless
there is a measurable improvement in performance, maintainability,
scalability, accuracy, or operating cost. Prefer extending and refactoring
existing components whenever practical.

**Architecture First** — when implementing any feature: (1) review the
existing implementation, (2) determine whether it satisfies the requirement,
(3) identify the smallest maintainable change, (4) implement incrementally,
(5) verify existing functionality still works, (6) add or update tests,
(7) document architectural changes.

## Cost Awareness

Every technical decision affects the business. Before introducing new
databases, cloud services, AI providers, infrastructure, APIs, recurring
subscriptions, significant token usage, increased embedding storage, or new
third-party dependencies — evaluate whether the benefit justifies the added
cost. Lower operating cost is preferred when customer value remains
comparable.

## Business Impact Gate

**Before implementing any change that could affect the commercial model, stop
and produce a Business Impact Analysis. Do not implement these changes until
approval is received.** This includes changes affecting:

- **Pricing** — customer pricing, subscription tiers, premium features, usage
  limits, billing structure.
- **Profitability** — API costs, token consumption, hosting, compute,
  storage, third-party services, support burden, setup effort.
- **Feature Scope** — new capabilities, removed capabilities, changes to
  onboarding, new administrative workflows, required integrations, changes to
  customer setup.
- **Technical Complexity** — database redesign, new infrastructure, breaking
  API changes, major refactoring, long-term maintenance burden.

## Decision Framework

When multiple solutions exist, prefer the one that: uses fewer moving parts,
reduces AI calls, minimizes infrastructure, improves response speed, keeps
onboarding simple, and preserves flexibility for V2.

## Architectural Review Mode

Before implementing any major feature, answer: (1) does this already exist?
(2) can an existing component be extended? (3) will this create technical
debt? (4) does this duplicate functionality? (5) does it increase
infrastructure? (6) token usage? (7) operating costs? (8) implementation
complexity? (9) does it improve customer experience enough to justify the
added complexity? (10) is there a simpler solution? If a simpler approach
exists, recommend it before implementation.

## Architectural Challenge Clause

If a solution is identified that materially improves performance,
maintainability, customer experience, scalability, profitability, or
implementation simplicity compared to the current spec, do not silently
implement it. Instead: (1) explain the proposed improvement, (2) describe the
tradeoffs, (3) estimate implementation effort, (4) estimate impact on
operating costs, pricing, feature scope, setup time, and support burden,
(5) wait for approval before making changes that alter the product roadmap or
commercial model.

---

## How this pairs with the autonomy request (2026-07-29)

The user asked to work with fewer permission checkpoints going forward.
Resolution adopted: routine implementation (audits, incremental refactors,
tests, docs, low-risk fixes clearly within existing scope) proceeds without
stopping to ask. The Business Impact Gate above stays active exactly as
written — pricing, new recurring costs, schema/infrastructure changes, and
major refactors still get a Business Impact Analysis and a pause for
approval, since that gate was authored by the user themselves as a standing
safeguard, not a default caution to be second-guessed on request alone.
