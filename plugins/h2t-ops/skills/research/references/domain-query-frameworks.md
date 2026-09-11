# Domain Query Frameworks

Use this to shape the actual search queries for a topic, and to check you've covered the
whole domain rather than just its most interesting corners. Pick the framework matching the
topic's domain.

## Picking the domain

| Domain | Trigger keywords |
|---|---|
| Health | medical, nutrition, pharmacology, supplement, dosage, biomarker, clinical |
| Macro | market, sector, energy, macro, TAM, supply, demand, geopolitics, infrastructure, commodity, investment theme, industry, regulatory, policy, trade, capex |
| Company | company, competitor, niche, business model, unit economics, moat, market share, startup, revenue, margin, funding, valuation, go-to-market |
| Science | paper, architecture, algorithm, model, benchmark, cognitive, neural, physics, biology, mechanism, theory, hypothesis, experiment, reproducibility, preprint |

Grey zones: a topic about a specific company operating in a broad market is Company, not
Macro, even if it also touches sector trends. A topic about the market for a technology is
Macro; the same technology's underlying mechanism is Science. If a request could go two ways,
ask one clarifying question rather than guessing.

## Query-shaping frameworks

**PICO — health / medical / nutrition**
- **P**opulation: who? (age, sex, condition)
- **I**ntervention: what? (substance, dosage, protocol)
- **C**omparison: versus what? (placebo, alternative protocol, no treatment)
- **O**utcome: which outcome? (biomarker, endpoint, patient-reported outcome)

**STEEP — macro / sector / market trends**
- **S**ocial: demographic shifts, consumer behavior, labor trends
- **T**echnological: innovation cycles, technology readiness, scaling curves
- **E**conomic: growth, interest rates, capital-spending cycles, unit economics
- **E**nvironmental: resource constraints, climate policy, sustainability mandates
- **P**olitical: regulation, trade policy, sanctions, industrial policy

**PROFIT — company / niche / business opportunity**
- **P**roduct: what is sold? what problem does it solve? how differentiated is it?
- **R**evenue: business model, pricing, unit economics, scalability
- **O**pportunity: market size, growth, timing
- **F**orces: competitive dynamics, barriers to entry, moats, threats
- **I**nfrastructure: technology stack, dependencies, build-vs-buy
- **T**eam & traction: founders, key hires, growth metrics, customer signal

**CREAM — science / technical / academic**
- **C**laim: what is the central claim or phenomenon under study?
- **R**esults: what are the key experimental or empirical results?
- **E**vidence: how good is the evidence? (replication, benchmarks, controls)
- **A**lternatives: what competing explanations exist?
- **M**echanisms: how does it work — a causal chain, not just a correlation?

## Coverage checklists per domain

Use these alongside the general coverage-check method in `search-technique-toolkit.md` — they
name the categories that are easy to skip because they're unglamorous, not because they're
unimportant.

**Health**
- Food groups: vegetables, fruits, nuts/seeds, legumes, dairy, meat/poultry, fish/seafood, eggs, oils, grains, fermented foods, beverages, spices
- Supplement categories: vitamins, minerals, amino acids, herbals, probiotics
- Lifestyle: exercise modalities, sleep, stress, circadian factors
- Interactions: drug × nutrient, nutrient × nutrient, condition-specific factors
- "Boring staples" check: yogurt, turkey, rice, potatoes, oats — high-evidence, low-novelty, easy to skip

**Macro**
- Sectors: energy, tech, agriculture, water/utilities, manufacturing, finance, healthcare, real estate, transport, defense
- Dimensions: supply, demand, pricing, regulation, geopolitics, demographics, technology disruption
- Geographies: US, EU, China, emerging markets, commodity exporters
- Time horizons: near-term (1-2yr), medium (3-5yr), long (10+yr)
- "Boring infrastructure" check: utilities, ports, rail, water treatment — low-novelty but high-impact

**Company**
- Value chain: R&D, operations/back-office, sales, marketing, support, compliance/legal, HR/talent
- Stakeholders: customers, competitors, suppliers, regulators, investors, employees
- Business model: revenue streams, cost structure, unit economics, churn/retention
- Market: total/serviceable/obtainable market size, growth drivers, adjacent markets, substitutes
- Risk: regulatory, competitive, execution, talent/hiring, macro exposure
- "Boring but decisive" check: compliance costs, integration friction, hiring timelines, support burden — these often decide the winner

**Science**
- Theory levels: foundational principles, current state of the art, emerging/speculative work
- Evidence types: controlled experiments, observational studies, simulations, null findings, replication attempts
- Methodology: the dominant paradigm, alternative approaches, measurement tools
- Applications: near-term, long-term, adjacent fields that draw on this knowledge
- Meta-science: reproducibility track record, prevalence of p-hacking, pre-registration, funding structure
- "Boring fundamentals" check: textbook constraints on the exciting claims, calibration/measurement-validation studies

## Extra techniques for company/customer research

**Preserve customer language verbatim.** When a source is a review, forum post, earnings-call
Q&A, or support ticket, keep the exact wording rather than paraphrasing — raw customer
language carries signal your summary would flatten. (The source-URL-plus-quote requirement
itself is the general rule in `traceability-policy.md`; this adds a domain-specific tagging
scheme on top of it.) Tag each quote `[pain]`, `[delight]`, `[churn_risk]`, or
`[feature_request]`, aiming for at least a handful of raw quotes per topic covered this way.

**Score problems before prioritizing them.** For each candidate pain point or opportunity,
score four dimensions 1-5 and rank by the weighted sum:

| Dimension | 1 | 5 |
|---|---|---|
| Urgency | nice-to-have | customers need it solved now |
| Willingness-to-pay signal | none | customers already pay a competitor for this |
| Trend | declining | rapidly increasing |
| Complaint frequency | rare mention | dominant theme across reviews/forums/calls |

Score = Urgency×0.3 + WTP×0.3 + Trend×0.2 + Complaints×0.2. Above 4.0 = top priority;
3.0-3.9 = worth investigating; below 3.0 = monitor only.

## Related references

- `search-technique-toolkit.md` — general expansion and citation-chaining techniques
- `evidence-quality-checklists.md` — source tiers and anti-patterns once you have results
