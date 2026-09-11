# Evidence Quality Checklists by Domain

Use this to grade sources and catch known failure patterns before they enter a report. Pick
the section matching the topic's domain; each has its own source-quality tiers, the mistakes
that recur in that domain, and questions to stress-test a finding before you trust it.

## Health / nutrition / pharmacology

**Source tiers**

| Grade | Source type | Examples |
|---|---|---|
| A | Cochrane reviews, high-confidence meta-analyses, landmark randomized trials | NEJM, Lancet, JAMA, BMJ |
| B | Well-powered randomized trials, large prospective cohorts (n>1000) | Specialty journals with high impact factor (Blood, Circulation, Gut) |
| C | Observational studies, small randomized trials, expert-consensus guidelines | ACC/AHA, ESC, WHO guidelines |
| D | Case reports, mechanistic/animal studies, preprints | Preclinical journals, bioRxiv |

Formal scoring tools this field uses, if you need to go deeper than the tiers above: GRADE
(rates confidence per outcome), Cochrane ROB 2.0 (bias in randomized trials), Newcastle-Ottawa
Scale (bias in observational studies), AMSTAR 2 (quality of systematic reviews).

**Typical anti-patterns**

| Anti-pattern | Why it's wrong | Fix |
|---|---|---|
| Citing animal/mouse studies as human evidence | Different pharmacokinetics, doses don't scale linearly | Label "preclinical only," keep separate from human evidence |
| Relative risk without absolute risk | "50% reduction" from 0.002 to 0.001 is a NNT (number needed to treat) of 1000 | Always report both, plus NNT |
| "Studies show" with no named study | Unfalsifiable hand-waving | Name author, year, sample size, design for every claim |
| Extrapolating from healthy young men to everyone | Most trials use 20-30-year-old men | Flag the studied population, note who it may not apply to |
| Treating a guideline as if it were evidence | A guideline is an expert's summary of evidence, not evidence itself | Cite the underlying trials/meta-analyses instead |
| "Safe and well-tolerated" with no dose/duration given | Safety is dose- and duration-specific | State the dose range and duration actually tested |

**Stress-test questions** (ask at least two per finding)

1. Under what conditions could this become harmful for someone with a different profile (genetics, existing condition, current medication)?
2. Strip away relative risk — looking only at absolute risk reduction, is this still worth doing?
3. What is the single most likely confounder that explains this result without the proposed mechanism?
4. Does the evidence support long-term benefit (>5 years), or only short-term?
5. How different is the studied population from the person/case this applies to, and what adjustment does that require?
6. What happens when this meets something already in use (another drug, supplement, condition) — is there evidence, or just silence?
7. Where does benefit plateau, and where does it turn to harm?

## Macro / economics / sector trends

**Source tiers**

| Grade | Source type | Examples |
|---|---|---|
| A | Official statistics, government/central-bank data | IEA, EIA, BLS, Eurostat, Fed, ECB, OECD, World Bank |
| B | Industry bodies, company filings | IRENA, SEMI, WSTS, OPEC, 10-K/10-Q filings, earnings transcripts |
| C | Consulting and sell-side research | McKinsey, Goldman Sachs, Morgan Stanley, BCG, Gartner |
| D | Expert blogs, podcasts, social media | Substacks, conference talks, social threads |

Treat grade C as an upper bound for projections, not a neutral estimate — sell-side and
consulting forecasts skew toward the bullish/newsworthy case.

**Typical anti-patterns**

| Anti-pattern | Why it's wrong | Fix |
|---|---|---|
| Extrapolating a 3-year trend as permanent | Ignores mean reversion, S-curves, policy shifts | Test against historical analogues; add a case where the trend breaks |
| Using a consulting firm's market-size number uncritically | Sell-side sizing skews bullish | Cross-validate bottom-up (units × price), note the source's grade |
| "Demand will require X" with no supply mechanism shown | A demand projection is not a supply guarantee | Trace the supply pathway (permits → construction → commissioning) |
| Treating announced capacity as if it were built | Announced ≠ funded ≠ permitted ≠ built ≠ operating | Apply a realistic conversion rate; state which stage a number refers to |
| Mixing nominal and real dollars | Inflation distorts multi-year comparisons | State and hold to one basis throughout |
| A "global" number that hides regional concentration | 80% of a "global" figure can sit in one country | Break the number down by geography |

**Stress-test questions**

1. What single event (geopolitical, technological, regulatory) would make this whole thesis irrelevant within 18 months?
2. Has a market grown at this projected rate for this long before? What happened to the cases that didn't sustain it?
3. Does the supply/demand math actually close — if not, who or what absorbs the gap?
4. If everyone already agrees with this thesis, why isn't it priced in already?
5. What happens to the sector if the key subsidy or regulation disappears?
6. If this trend plays out, what breaks elsewhere (a sector, a commodity, a currency)?
7. Double the consensus timeline — does the thesis still hold at twice the expected pace?

## Company / market / competitive intelligence

**Source tiers**

| Grade | Source type | Examples |
|---|---|---|
| A | Filed, audited financials | 10-K, 10-Q, S-1, proxy statements, annual reports |
| B | Earnings calls, official investor materials | Call transcripts, investor-relations decks, official press releases |
| C | Analyst and industry research | Sell-side banks, CB Insights, PitchBook, Gartner |
| D | Trade press, expert blogs, user reviews | TechCrunch, Substacks, Glassdoor, G2, Product Hunt, social media |

Never let a revenue or margin figure rest solely on grade C-D sourcing.

**Typical anti-patterns**

| Anti-pattern | Why it's wrong | Fix |
|---|---|---|
| Treating a top-down TAM as achievable | "10% of a $500B market" is a slogan, not a plan | Build the market size bottom-up (units × price × segment); cross-validate |
| Ignoring private/stealth competitors | Public companies are the visible tip; startups are the rest of the iceberg | Check startup databases for unlisted competition |
| "Best product wins" | Distribution and switching costs often beat product quality | Analyze distribution and lock-in, not just features |
| Management's own growth claim taken at face value | "We're growing 50%" is a narrative until it matches the filings | Verify every financial claim against filed financials |
| Confusing forward-looking revenue with recognized revenue | One predicts, the other reports | Specify which metric is being used, and the churn/retention behind it |
| Leaving out "do nothing" as a competitor | Customers' biggest alternative is often staying with the status quo | Include inaction/manual process as a competing option |
| Assuming a pattern in successful companies caused their success | Failed companies often did the same thing | Check whether the pattern also appears among the failures |

**Stress-test questions**

1. What does every successful player in this market understand that customers never say out loud?
2. What single assumption is this whole market built on, and what event would break it?
3. If an experienced investor wanted to kill this thesis with one question, what would they ask?
4. Give a specific, plausible scenario where the current leader's advantage erodes within three years.
5. What would make the best customers switch — including switching to "build it ourselves" or "do nothing"?
6. Is this genuinely early, or genuinely too late — what specific trigger turns interest into revenue at scale?
7. What does a second mover learn from the first that lets it win — is first-mover advantage real here?

## Science / technical / academic

**Source tiers**

| Grade | Source type | Examples |
|---|---|---|
| A | Peer-reviewed, top-tier, independently replicated | Nature, Science, Cell, top conferences in the field |
| B | Peer-reviewed specialized journals/conferences | Established journals or venues in the subfield |
| C | Preprints with significant traction (many citations, or from a well-known lab) | arXiv from major research labs or universities |
| D | Blog posts, technical reports, talks with no accompanying paper | Company blogs, Substacks, social threads |

Never let a core claim rest solely on grade C-D sourcing. Track, for each key result: was
code/data released, and has anyone outside the original group replicated it?

**Typical anti-patterns**

| Anti-pattern | Why it's wrong | Fix |
|---|---|---|
| Treating a preprint as if it were peer-reviewed | No review means no quality gate has been passed | Label the source grade; keep separate from peer-reviewed claims |
| "State of the art" with no benchmark, date, or metric given | SOTA is only meaningful relative to a specific benchmark at a specific time | Always state: on which benchmark, as of when, by which metric |
| Treating correlation as causation in observational data | Observation shows association only | State explicitly whether it's correlational or causal (from an actual intervention) |
| Citing only positive results | Publication bias inflates the reported effect | Actively look for negative/null results and systematic reviews |
| Drawing an analogy between two fields without checking it holds | A superficial resemblance is not evidence of shared mechanism | Flag the analogy's limits; check whether a testable prediction actually transfers |
| Treating one lab's result as settled science | A single lab's finding is preliminary even in a top journal | Note replication status: single-lab vs independently replicated |
| Quoting a result while omitting the resources it took | "State of the art" performance can hide an unstated, unreproducible cost | Note compute/data/expertise required |

**Stress-test questions**

1. What specific replication failure would collapse this finding — has anyone tried and failed?
2. Is this "state of the art" claim meaningful in practice, or does it overfit a benchmark that doesn't reflect real use?
3. Does the result hold at a much larger scale, or was it extrapolated from just two data points?
4. What is the simplest alternative explanation that fits the same data without the proposed mechanism?
5. If this principle holds in one field, what testable prediction does it make in another — has anyone tested it?
6. What promising approach in this field was abandoned in the last few years, and why?
7. Strip away the framing: is this a genuine shift, or a small improvement with good marketing?

## Related references

- `claim-verification-checklist.md` — the general judgment process these tiers and anti-patterns feed into
- `domain-query-frameworks.md` — how to shape searches and check topic coverage per domain
