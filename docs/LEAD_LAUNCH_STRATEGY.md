# Lead Launch by EvolveIQ — Strategy

Source: `EvolveIQ_Lead_Launch_Claude_Handoff.md` (Larry, 2026-08-13), vetted against
what already existed on the marketing site and in `ops/` before implementation.
This doc keeps the strategic content from that handoff and adapts the
implementation notes to match what's actually built — see "What already
existed" below before extending this further.

## What already existed (don't rebuild these)

- **Nav CTA and Lead Launch section** — `marketing/index.html` already had a
  "Need a site?" nav badge (`#website`) and a website-offer section. Both were
  renamed/repositioned to "Lead Launch by EvolveIQ" with opportunity-capture
  copy (2026-08-13) rather than built from scratch.
- **One unified form, not two** — `#demoForm` already handles both "get a demo"
  and "I just need a website" (via the `needs_website` checkbox), posting to
  `POST /api/demo-request`. The handoff's proposed separate 8-field Lead Launch
  form was **not** built — it would have fragmented an already-consolidated
  funnel. The Lead Launch section's CTA now points to `#demo` instead of a bare
  `mailto:`, so both paths flow through the one form.
- **Basic submission tagging already exists** — `backend/app/routers/business.py`
  `submit_demo_request()` already branches on `needs_website` and writes a
  distinguishing `notes` string on the lead row (now reads "Interested in: Lead
  Launch by EvolveIQ (no site yet)"). There's no dedicated `source`/`tag`
  column — filtering means searching `notes`, not querying a field. Adding a
  real column is a schema change and trips the Business Impact Gate in
  `docs/V1_ARCHITECTURE_SPEC.md`; flagged as an open decision below, not done.
- **A full Outreach CRM already exists** — `ops/outreach_db.py` (the
  `prospects` table), `ops/import_outreach_prospects.py`, and a live UI at
  `/outreach` (see `ops/launcher_server.py`). The `prospects` table already
  covers nearly every column the handoff's prospect-list spec (section 9 below)
  asks for: company, vertical, city/metro, website, review signal, size
  signal, primary service, lead-leakage/gap, evidence, personalization hook,
  demo scenario/questions, decision-maker name/role, phone, email, socials,
  preferred channel, outreach angle, status, cadence step, assigned rep, score,
  priority rank. **Use this system for the Lead Launch prospect list — do not
  build a second one.**

## Open decision (not resolved — needs a call before building)

The `prospects` table has no field to distinguish which list/campaign a row
belongs to (Lead Launch vs. the main EvolveIQ list vs. the original LeadGuard
list — see "List distinction" in section 9). Two options, neither implemented
yet:

1. **No schema change**: convention-tag rows via `notes` or `outreach_angle`
   (e.g. prefix `[Lead Launch]`) and filter by search. Zero technical risk,
   works today with the existing importer and CRM UI.
2. **Add a `list_name` or `campaign` column**: cleaner filtering/reporting,
   but it's a schema change — needs a Business Impact Analysis per the
   Architecture Gate before implementation.

Recommend starting with option 1 (tag via `notes`/`outreach_angle`) since the
Lead Launch list is starting at ~100 rows — small enough that search-based
filtering is fine — and revisiting a schema change only if that becomes
unwieldy.

## Pricing (revised 2026-08-13 — supersedes the original handoff numbers)

The handoff proposed folding Lead Launch fully into Core at $499 setup +
$149/mo. The site originally had a two-tier bundled/standalone split ($100 +
$20/mo for Core subscribers, $499 + $50/mo standalone). Both were replaced
with a single, simpler structure after working through the tradeoffs with
Larry:

- **$375 one-time build** — the only option, no bundled/standalone fork.
- **First 60 days: Evie and hosting free.**
- **After 60 days**, the customer's choice:
  - Keep Evie → rolls onto **standard Core pricing** ($99–149/mo) — hosting
    stays included free.
  - Drop Evie → **$50/mo**, hosting and maintenance only, no AI.

**Why no permanent discount on the recurring rate:** an earlier draft of this
model had Lead Launch customers rolling onto a discounted $79/mo instead of
standard Core pricing. That created a real inconsistency — the customer doing
*more work* (a full site build, not just AI added to an existing site) would
end up paying *less* than someone who already has a website and pays standard
Core rates for setup + monthly. That's backwards, and it would incentivize an
existing-site prospect to falsely claim they have no website just to get the
cheaper deal and a free rebuild. Converging both paths to the same standard
Core monthly rate closes that hole. The $375 one-time build fee stays below
standard Core's $399–799 setup range, which is defensible on its own — it's a
simpler, templated single-page build, not full custom Core onboarding — and
the 60-day free trial plus included hosting are already a strong, bounded
incentive without needing a second permanent discount stacked on top.

Site copy and pricing card updated to match (2026-08-13).

---

*Below this line is the strategic content from the original handoff, kept
close to verbatim since it's genuinely new prospecting/positioning guidance,
not yet reflected anywhere else in `docs/`.*

## 1. Executive Direction

Lead Launch is a deliberately narrow client-acquisition pathway — it captures
incremental business from legitimate small companies that need a new or
substantially better website, but EvolveIQ must not become positioned as a
website builder or web-design agency.

> A website gives people somewhere to go. Lead Launch gives them a reason and
> a way to move forward.

Lead Launch is an **opportunity-capture and conversion offer**, not
fundamentally a website offer. The website is the digital location where
prospects from Google, referrals, advertising, social media, and word of
mouth often arrive — and then fail to receive the answer, offer, or next step
needed to begin a business conversation. Lead Launch closes that gap.

**Primary business outcome:** help businesses turn more of the attention
they're already earning into qualified inquiries, calls/callbacks, estimates,
appointments/consultations, planned visits, identified sales opportunities,
and new customers/revenue. Do not imply Lead Launch creates new traffic —
the defensible promise is converting more existing attention into measurable
opportunities.

## 2. Brand and Product Architecture

Lead Launch must not compete with the current EvolveIQ offer hierarchy:

| Role | Name | Purpose |
|---|---|---|
| Platform and product family | **EvolveIQ** | The business-intelligence and AI engagement ecosystem |
| Website-needs entry pathway | **Lead Launch by EvolveIQ** | Adds the digital foundation needed to capture and advance customer interest |
| Entry subscription | **Core** | Practical AI assistance, business intelligence, essential opportunity capture |
| Primary growth tier | **Business** | Greater value, routing, tuning, insight, workflow, lead-management capability |
| Complex organization tier | **Enterprise** | Multi-location, multi-team, higher-volume, custom-workflow needs |
| Government/civic tier | **Public Sector** | Governed, accessible, public-facing knowledge and engagement use cases |

Intended customer progression: **Lead Launch → Core → Business → Enterprise**
when appropriate.

**Do not:** create a fifth pricing card beside Core/Business/Enterprise/Public
Sector; create Bronze/Silver/Gold website packages; create page-count or
design-feature comparison tables; make web design a primary nav category;
describe EvolveIQ as an AI website builder; market rapid/five-minute website
creation; let Lead Launch dominate the main EvolveIQ value proposition; imply
every EvolveIQ customer needs a new website.

## 3. The Customer Problem Lead Launch Solves

The prospect doesn't wake up wanting a website — they want more business.
Viable local businesses already generate attention through Google Business
Profiles, reviews, referrals, branded vehicles/jobsite signs, ads, social
media, community reputation, and word of mouth. That attention frequently
reaches the website, where it dies: no specific answer to the visitor's
question, no offer/service path, no low-friction next step, no after-hours
contact path, no reason to identify themselves before leaving. Anonymous
abandonment — the business paid for or earned the attention but never
received the opportunity.

**Customer journey:** prospect hears about/searches for the business → reaches
the website with a question/need/buying intent → Lead Launch surfaces
relevant info instead of forcing a hunt through generic pages → the AI
assistant answers approved questions and guides toward the right offer/next
step → prospect requests a call/estimate/appointment/consultation/visit → the
business gets an actionable opportunity instead of losing an anonymous
visitor.

**Core positioning line:** *Your business is getting attention. Lead Launch
helps turn more of it into business.*

**Supporting positioning:** Prospects visit your website with questions,
needs, and buying intent. Lead Launch helps them find the right information,
understand the right offer, and take the next step — whether that means
requesting an estimate, scheduling a consultation, planning a visit, or
starting a conversation.

## 4. Lead Launch Offer Definition

Should feel like: a revenue opportunity, a missing conversion layer, an
always-available guide for prospective customers, a bridge from interest to
conversation, a flexible solution filling the client's most important
engagement gaps.

Should **not** feel like: a cheap website, a rigid starter package, a
collection of pages/technical features, an à la carte design service, a
scope-limitation exercise.

**Delivery components** (translate each into a customer outcome in
public-facing copy, don't list as raw features): a focused mobile-first site
when the client lacks an effective foundation; a basic EvolveIQ AI assistant;
an approved industry Business Intelligence Pack; business info/services/hours/
FAQs/approved pricing language; lead capture and preliminary qualification;
estimate/callback/consultation/appointment/visit requests as appropriate;
scheduling-link integration; owner/team notifications; basic reporting; a
clear upgrade path into Business.

**Adaptability message:** don't suggest every client gets an unlimited custom
implementation, but communicate that the team identifies where a business is
losing opportunities and configures the right starting pathway. Target
reaction: *"They understand where I am losing opportunities, and they can
help me create a better path."* Avoid: *"This is a small, fixed package that
probably won't handle what I need."*

## 5. Pricing Posture (strategic reasoning — see "Pricing" above for the actual decision made)

Do not publish multiple website packages. The reason to avoid public website
packages is strategic: Lead Launch exists to acquire the right EvolveIQ
clients, not to create a separate low-margin web-production company. If a
prospect needs substantially more pages, advanced content, custom design,
multiple locations, custom routing, integrations, or significant ongoing
strategy, route them to Business or a scoped custom engagement rather than
stretching Lead Launch indefinitely.

## 6. Dedicated Prospect Strategy

Lead Launch needs its own prospect inventory because the strongest candidates
aren't necessarily the same companies targeted for full Business/Enterprise
implementations.

**Prospect category: Hidden Operators** — credible, active businesses whose
online presence is materially weaker than the quality of their actual
operation. Indicators: active Google Business Profile, working phone number,
recent reviews showing current operations (ideally 10+ reviews, 4.0+ rating),
no website/Facebook-only/outdated/passive website, services with enough
customer value to justify investment, owner-operated or small-team, no
franchise/corporate marketing department. The ideal prospect is a real,
active business failing to convert enough of the attention it earns — not a
failing or imaginary one.

**Three prospect segments:**

| Segment | Qualification | Primary sales angle |
|---|---|---|
| **No Website** | Active business with a Google profile but no credible website | "Customers are finding evidence that you exist, but they do not have a clear place to understand your value or take the next step." |
| **Weak Website** | Outdated, broken, low-credibility, or poor mobile experience | "Your reputation and actual work are stronger than the digital experience representing your company." |
| **Passive Website** | Visually acceptable site with weak answers, no guided next step, no after-hours engagement, or poor lead capture | "Your website presents information, but it is not doing enough to turn interested visitors into conversations." |

The Passive Website group may be the most valuable — they've already shown
willingness to invest in an online presence, so the sale isn't "you need a
website," it's "your current site is underperforming as a conversion asset."

## 7. Best Initial Industries

Prioritize industries where one recovered customer can reasonably justify a
meaningful portion of the annual subscription:

1. Electricians
2. HVAC contractors
3. Plumbers
4. Fence and gate contractors
5. Concrete and foundation companies
6. Tree-service companies
7. Roofing companies
8. Mobile mechanics and independent repair shops
9. Restoration and remediation companies
10. Small law firms

**Deprioritize:** restaurants, general retail, low-ticket personal services,
nonprofits without a defined economic use case, pre-revenue/idea-stage
businesses, franchises or corporate-marketing-controlled organizations. May
contain exceptions, but the default economics are less attractive initially.

**Vertical pack priority:** electrical, HVAC, small law firms — reuse the
existing electrical/HVAC strategy work (`onboarding/bips/hvac.md`,
`onboarding/bips/hvac_json/`) rather than rebuilding. Each vertical pack
should eventually contain: approved website structure, standard service
pathways, Business Intelligence Pack, FAQ/knowledge foundation, qualification
flow, lead-routing rules, realistic demo questions, outreach script,
onboarding form, upgrade pathway.

## 8. Prospect Scoring Model

Score each prospect out of 10:

| Signal | Points |
|---|---:|
| No website or Facebook-only website | 2 |
| At least 15 Google reviews | 2 |
| Rating of 4.0 or higher | 1 |
| Review posted within the last 60 days | 1 |
| Likely customer value exceeds $500 | 1 |
| Owner-operated or locally owned | 1 |
| Current website lacks meaningful lead capture or guided conversion | 1 |
| Business serves multiple nearby cities | 1 |

Prioritize prospects scoring **7–10**. Treat this as a starting point, not a
substitute for human judgment — a company with strong reputation, visible
demand, and a high-value service may deserve priority even with one signal
missing.

*Note: this is a separate, purpose-built qualification score for Lead Launch
prospecting — not the same thing as the existing `prospects.score` field in
`ops/outreach_db.py` (imported rows use a "Prospect Score /100" column, per
`import_outreach_prospects.py`), which serves the general EvolveIQ/LeadGuard
CRM scoring purpose. Don't rescale or merge the two — store this /10 Lead
Launch qualification score in `notes` alongside the `[Lead Launch]` tag,
leaving `prospects.score` for its existing purpose untouched.*

## 9. Initial Prospect List Structure

Build the list **inside the existing Outreach CRM** (`ops/outreach_db.py`,
`/outreach` UI) — see "What already existed" above. Target composition:

- 100 DFW businesses, 10 industries, ~10 prospects per industry
- ~50 no-site/weak-site prospects, ~50 passive-site prospects

**Columns needed** (cross-referenced against the existing `prospects` table —
✓ = already a column, tag = fold into `notes`/`outreach_angle` per the open
decision above):

- Business name ✓ (`company_name`) · Industry ✓ (`vertical`) · City/service
  area ✓ (`city_metro`) · Website URL ✓ (`website`) · Google rating / review
  count / recency ✓ (`review_signal`) · Evidence business is active ✓
  (`evidence`) · Estimated customer value band ✓ (`size_signal`) ·
  Locally-owned indicator ✓ (`size_signal` or `evidence`) · Primary
  conversion gap ✓ (`lead_leakage`) · Personalization hook ✓
  (`personalization_hook`) · Decision-maker name/email/phone ✓
  (`decision_maker_name`, `email_or_contact_url`, `phone`) · Lead score ✓
  (`score` — see scale note above) · Demo/outreach status ✓ (`status`,
  `cadence_step`) · Follow-up date ✓ (`next_touch_at`) · Outcome ✓ (`notes` /
  `touches` table)
- **Not a native column, tag instead:** Google Business Profile URL (fold
  into `source_urls`) · Website segment: No/Weak/Passive (tag in `notes` or
  `outreach_angle`, e.g. `[Lead Launch: No Website]`) · AI-assistant
  opportunity / missing answer-offer-next-step (fold into `lead_leakage` or
  `demo_scenario`) · Best Lead Launch use case (fold into `outreach_angle`)

Keep this inventory logically distinct from the main EvolveIQ prospect list
and the original LeadGuard list via the `[Lead Launch]` tag convention:

- **EvolveIQ prospect list:** organizations needing sophisticated engagement,
  intelligence, workflow, or integration.
- **Lead Guard prospect list:** businesses visibly losing inquiries or
  failing to respond.
- **Lead Launch prospect list:** good businesses whose digital front door is
  below the quality of their real operation or fails to advance customer
  intent.

The existing daily 25+25 execution model can run against this larger Lead
Launch inventory.

## 10. Demo-First Acquisition Workflow

1. Select a highly qualified business from the Lead Launch prospect list.
2. Review its Google profile, reviews, website, services, likely customer
   journey.
3. Identify the exact conversion gap — not merely an unattractive design.
4. Generate a private preview from the approved vertical structure.
5. Load the appropriate basic Business Intelligence Pack and approved
   business info.
6. Demonstrate a realistic customer question.
7. Show how Lead Launch provides the missing answer or service path.
8. Submit a sample callback/estimate/appointment/consultation request.
9. Show the business notification or captured opportunity.
10. Record a concise 60–90 second personalized video.
11. Send the preview with an outcome-led message.
12. Offer activation through Lead Launch into Core.
13. Identify Business-tier upgrade opportunities after value/usage are
    established.

**Demo video structure:** Recognition ("Your customers clearly value your
work") → Gap (the specific place an interested prospect lacks information or
a next step) → Experience (demonstrate the improved customer journey) →
Opportunity (show the submitted inquiry and business notification) →
Invitation (ask whether the owner wants to review the private preview).

Don't lead by insulting the current website — lead with the mismatch between
the business's strong reputation and the customer journey currently
representing it.

## 11. Three-Person Execution Model

| Role | Daily responsibility |
|---|---|
| **Research VA** | Find and qualify 15–20 businesses; document reviews, activity, website quality, conversion gaps, contact data, lead score |
| **Demo VA** | Build approved previews, load verified business details, test the assistant, create 60–90 second personalized demos |
| **Sales/Closer** | Conduct calls and outreach, send demos, follow up, qualify fit, close activation, collect onboarding information |

Larry stays focused on offer refinement, higher-value sales conversations,
strategic partnerships, and upgrading appropriate clients into Business or
higher tiers.

## 12. Outreach Messaging

**No Website:** Customers can already find evidence that your business is
active and trusted, but they do not have a strong place to understand what
you do or take the next step. We created a private preview showing how Lead
Launch could turn more of that existing attention into calls, estimates, and
real conversations.

**Weak Website:** Your reviews and reputation say more about the quality of
your business than your current website does. We created a private Lead
Launch preview that gives interested prospects clearer answers and a direct
path to contact you.

**Passive Website:** Your website looks credible, but interested prospects
still have to search, wait, or call to get the answer they need. Lead Launch
adds a guided path that helps turn more visitors into conversations,
appointments, and opportunities.

**Primary sales positioning:** *We install a 24/7 opportunity-capture system
for your business and include the digital foundation it needs to work.*

**Avoid:** "We build AI websites in minutes." / "We noticed your website is
bad." / "Would you like a new website?" / "We sell affordable web-design
packages."

## 17. Final Strategic Standard

The website is not the product story. It is the location where customer
intent repeatedly appears. Lead Launch should communicate that EvolveIQ helps
a business stop wasting that intent by providing the missing information,
relevant offer, guided next step, and connection to a real conversation.

> You do not need another website that waits for customers to figure out
> what to do. You need a better path from interest to business. That is Lead
> Launch.
