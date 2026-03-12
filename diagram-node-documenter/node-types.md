# Node Type Templates

Reference for Step 4 (DRAFT) of the diagram-node-documenter skill.

## Annotation Rules (enforced)

1. **One annotation per node** — never group multiple nodes into one annotation cell
2. **6 lines max** — каждая строка = одна смысловая единица
3. **Narrative first** — Line 1 = `<b>Name — What it does</b>` (declarative, not imperative)
4. **Source citations** — ссылаться на spec/config если есть числа (thresholds, timeouts)
5. **⚠️ flags** — использовать для gotchas, известных рисков, MVP ограничений
6. **Line 6 = research doc + Page N** — для complex нод оба: `→ docs/research/layers/X.md | Page N: detail`
   - Simple ноды: Line 6 = `Phase: MVP` или `See: ADR-XXX`
   - Complex ноды (ML, pipelines): Line 6 = и research doc, и Page ссылка

---

## TYPE_SOURCE — API / Data Source

```html
<b>[API Name] — [Short Description]</b><br/>
Plan: [tier] [price] | [credits/mo] | [req/min] | [N endpoints]<br/>
Data: [key data categories]<br/>
Freq: [update frequency per data type]<br/>
⚠️  [what's unavailable and why → alternative]<br/>
→ Page 9: endpoints &amp; metrics table
```

**Validated example (CMC):**
```html
<b>CMC — CoinMarketCap API</b><br/>
Plan: Hobbyist $35/mo | 110k credits | 30 req/min | 21 endpoints<br/>
Data: listings, metadata, categories, exchange map<br/>
Freq: listings real-time; metadata/categories 1d; history 12mo<br/>
⚠️  OHLCV unavailable on Hobbyist → use CCXT<br/>
→ Page 9: endpoints &amp; metrics table
```

---

## TYPE_ML — ML Model / Algorithm

```html
<b>[Node Name] — [Purpose]</b><br/>
Algorithm: [name + library], [N states/params]<br/>
Input:&nbsp; [feature vector / context]<br/>
Output: [classification / weights / reward] → [downstream]<br/>
Train:&nbsp; [cadence + window + init method]<br/>
⚠️  [key known risk] → [mitigation]
```

**Validated example (HMM):**
```html
<b>HMM Classifier — Regime Detection</b><br/>
Algorithm: Gaussian HMM, 4 states (hmmlearn), EM-trained<br/>
Input:&nbsp; feature_matrix_1d [ADX, MA_slope, Hurst, TAIL, funding_z]<br/>
Output: regime_label + state_probs[4] → G1 Gate<br/>
Train:&nbsp; monthly refit, 730d window, rule-based warm-start<br/>
⚠️  label-swap on refit → centroid-matching required
```

---

## TYPE_PROCESS — Transformation / ETL

```html
<b>[Node Name] — [Short technical title]</b><br/>
[Plain-language sentence: what this node does and why it exists in the system.]<br/>
Input/Output: [data in] → [data out / consumer]<br/>
Logic:&nbsp; [key rules / formula / threshold]<br/>
⚠️  [gotcha or key constraint, if any]<br/>
Phase: MVP  [→ docs/research/layers/X.md if complex]
```

**Note:** Line 2 must be readable by someone unfamiliar with the system — no abbreviations, no arrow notation. Explain the *role*, not just the data flow.

---

## TYPE_GATE — FSM / Filter / Safeguard

```html
<b>[Gate Name] — [What it guards]</b><br/>
States: [A] → [B] → [C]<br/>
Trigger: [formula / threshold]<br/>
Action:&nbsp; [what it blocks / activates]<br/>
Recovery: [how to exit state]<br/>
See: ADR-XXX  [→ docs/research/layers/X.md if complex]
```

---

## TYPE_SCHEMA — Database Table

```html
<b>[table_name]</b> ([db: TimescaleDB | ClickHouse])<br/>
Layer:&nbsp; [Bronze | Entity DB | Silver | Gold]<br/>
Key:&nbsp;&nbsp;&nbsp; [primary key / hypertable column]<br/>
Writers: [ingestor / process]<br/>
Readers: [downstream process]<br/>
See: docs/schema/sources/[source].md
```

---

## TYPE_CONTRACT — Data Contract

```html
<b>[Contract Name]</b><br/>
Fields: [key fields with types]<br/>
Invariants: [что всегда true]<br/>
Writers: [who produces]<br/>
Readers: [who consumes]<br/>
Idempotency: [client_order_id / request_id]
```

---

## TYPE_STORAGE — Storage / DB / Queue

```html
<b>[Storage Name]</b><br/>
Tech:&nbsp;&nbsp;&nbsp;&nbsp; [S3 | ClickHouse | Redis | TimescaleDB]<br/>
Schema:&nbsp;&nbsp; [key fields summary]<br/>
Pattern: [append-only | ReplacingMergeTree | SCD]<br/>
Retention: [7d hot | 2yr cold | forever]<br/>
Phase:&nbsp;&nbsp;&nbsp; MVP
```

---

## TYPE_PIPELINE — Complex Internal Pipeline

```html
<b>[Pipeline Name]</b><br/>
Contains: [N sub-modules]<br/>
Input:&nbsp; [data in]<br/>
Output: [data out]<br/>
→ Page [N]: [full pipeline detail]
```

---

## Annotation Size Reference

| TYPE | Width | Height |
|---|---|---|
| TYPE_SOURCE | 190 | 95 |
| TYPE_ML | 200 | 115 |
| TYPE_PROCESS | 170 | 90 |
| TYPE_GATE | 170 | 90 |
| TYPE_SCHEMA | 170 | 85 |
| TYPE_CONTRACT | 170 | 90 |
| TYPE_STORAGE | 170 | 85 |
| TYPE_PIPELINE | 170 | 80 |
