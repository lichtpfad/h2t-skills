# Claim Verification Checklist

Use this before a finding goes into a report: it turns a raw claim ("X causes Y") into a
judged, gradeable statement. It governs judgment; the citation format itself (source URL +
verbatim quote + confidence label) is fixed by `traceability-policy.md` — this file does not
repeat that rule, only what to check before you accept or downgrade a claim.

## 1. Identify what is actually being asserted

- State the exact claim in one sentence.
- Classify it: causal ("X causes Y"), associational ("X is linked to Y"), or descriptive
  ("X happened").
- Note how strong the wording is ("proven" vs "suggests" vs "may").

## 2. Check the evidence behind it

- Is the evidence direct (measures the claim itself) or indirect (a proxy)?
- Is it sufficient for the strength of wording used? A single study never earns "proven."
- Have obvious alternative explanations been ruled out, or just not mentioned?

## 3. Check the logic

Does the conclusion actually follow from the data? Common failure modes to scan for:

| Trap | What it looks like |
|---|---|
| Correlation → causation | Association reported as if a causal mechanism were shown |
| Extrapolation beyond the sample | Animal data applied to humans, healthy-population data applied to a sick one, one country's data applied globally |
| Appeal to authority | "Expert X says so" cited instead of the underlying evidence |
| Hasty generalization | One study/trial treated as if it "proves" the point |
| Ecological fallacy | A population-level pattern applied to predict an individual case |

## 4. Check proportionality

- Is confidence proportional to the strength of the evidence, or inflated?
- Are limitations stated plainly, not buried or softened?
- Is speculation clearly labeled as speculation, not blended into established fact?

## 5. Check for overgeneralization

- Does the claim extend past the population, market, or sample actually studied?
- Are those restrictions (age, geography, company size, time period) acknowledged?
- Is context-dependency (works here, not there) called out?

## 6. Bias sweep

Scan the claim's source material for five categories of bias. For each one you find, note
which claim it affects and how severe it is (critical / moderate / minor):

| Category | Watch for |
|---|---|
| Cognitive | Confirmation bias, cherry-picking supportive examples, HARKing (presenting a post-hoc explanation as if it were the original hypothesis) |
| Selection | Survivorship bias (only counting the ones that made it), volunteer bias, "healthy user" bias |
| Measurement | Recall bias, socially-desirable answers, a measuring instrument that skews results |
| Analysis | P-hacking (trying analyses until one is significant), outcome switching, fishing through subgroups until one looks significant |
| Confounding | An unmeasured third factor explains both sides of the association; reverse causation (Y actually causes X) |

## 7. Hidden-assumption check

For any claim that a whole line of argument rests on, ask: what is being assumed here that is
never tested or even stated out loud? For each assumption found:

- State it as a plain declarative sentence.
- Rate the risk if it turns out false: low (revise the conclusion a bit) / medium (the key
  finding is invalidated) / high (the whole argument collapses).

## 8. Red flags — downgrade or reject on sight

- Causal language drawn from a correlational-only source.
- "Proven" or absolute certainty with no evidence trail behind it.
- A citation list that is 100% confirmatory — nothing contradictory even considered.
- Contradictory evidence that is known to exist but goes unmentioned.
- A conclusion extrapolated well past what the underlying data actually covers.

## 9. Recording the result

Once judged, log each claim in a simple table so corrections are traceable:

| # | Claim | Source | Verified? | Correction (if any) | Confidence |
|---|---|---|---|---|---|

"Verified" here means you personally checked the source says what the claim says — not that
the source itself is correct. If you cannot find a URL and a verbatim quote for a claim, it
does not belong in Key Findings; see `traceability-policy.md`.

## Related references

- `traceability-policy.md` — mandatory citation shape for every finding
- `evidence-quality-checklists.md` — domain-specific source tiers and anti-patterns
- `search-technique-toolkit.md` — how to go find the missing/contradicting evidence this checklist surfaces
