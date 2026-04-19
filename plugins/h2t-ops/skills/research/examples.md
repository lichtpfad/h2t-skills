# Examples — h2t-ops:research

## Valid CLI Invocations

All examples assume `H2T_PYTHON` and `EXA_CLI` are set per SKILL.md Step 0.

### 1. Quick factual lookup (fast mode)

```bash
$EXA_CLI search \
  --query "What is the 2026 EU AI Act enforcement deadline?" \
  --mode fast \
  --num-results 5 \
  --project policy
```

### 2. Generic balanced research (depth=standard)

```bash
$EXA_CLI search \
  --query "Rejuve.bio longevity research DAO governance" \
  --mode generic \
  --depth standard \
  --num-results 10 \
  --project rejuve
```

### 3. News with date + domain filters

```bash
$EXA_CLI search \
  --query "Rejuve.bio Switzerland press coverage" \
  --mode news \
  --start-date 2025-10-01 --end-date 2026-04-18 \
  --include-domains "techcrunch.com,swissbiotech.ch" \
  --num-results 10 \
  --project rejuve
```

### 4. Academic papers

```bash
$EXA_CLI search \
  --query "small-molecule NAD+ precursors aging" \
  --mode academic \
  --start-date 2024-01-01 \
  --num-results 8 \
  --project longevity
```

### 5. Competitor research (company category — no date/domain filters)

```bash
$EXA_CLI search \
  --query "Switzerland-based biotech longevity startups 2026" \
  --mode competitor \
  --country CH \
  --num-results 10 \
  --project rejuve
```

### 6. People research

```bash
$EXA_CLI search \
  --query "Alex Zhavoronkov Insilico Medicine" \
  --mode people \
  --num-results 5 \
  --project rejuve
```

### 7. Deep synthesis with query variations

```bash
$EXA_CLI search \
  --query "quantum computing impact on cryptography 2026" \
  --mode deep \
  --additional-queries "post-quantum cryptography research,NIST PQC standards update" \
  --num-results 10 \
  --project security
```

### 8. Crawl a known URL

```bash
$EXA_CLI crawl \
  --url "https://rejuve.bio/about" \
  --project rejuve
```

## Output Format

Every run produces two files in `--output-dir` (default `~/.h2t/research/`):

- `{project}-{topic-slug}-{YYYY-MM-DD}.partial.md` — script-written Meta + Telemetry
- `{project}-{topic-slug}-{YYYY-MM-DD}.sources.json` — raw Exa response + metadata

The agent reads `.partial.md`, adds Sources / Key Findings / Grounding / Limitations / Follow-up per `REPORT-SPEC.md`, then writes final `{project}-{topic-slug}-{YYYY-MM-DD}.md` and deletes `.partial.md`.

## Sample Output (stdout)

```
## Exa Search: 'Rejuve.bio longevity research DAO governance'
**Mode:** generic | **Results:** 8 | **Cost:** $0.008 | **Latency:** 1040ms

1. [Rejuve.bio — About](https://rejuve.bio/about)
   Rejuve.bio operates as a decentralized autonomous organization (DAO) focused on longevity research...
2. [SingularityNET Longevity Initiative](https://singularitynet.io/longevity)
   Partner organization powering the Rejuve.bio protocol infrastructure...
...

Saved: ~/.h2t/research/rejuve-rejuve-bio-longevity-research-dao-governance-2026-04-18.partial.md
JSON:  ~/.h2t/research/rejuve-rejuve-bio-longevity-research-dao-governance-2026-04-18.sources.json
```

## Cross-Engine Recipe (manual)

Research a company end-to-end requires two skills:

```
User: "Research Rejuve.bio — company + people + news."

Agent plan:
1. /research --mode competitor --query "Rejuve.bio about product team"     (company pages)
2. /research --mode news --query "Rejuve.bio" --start-date 2025-10-01     (recent coverage)
3. /search-leads (Bayram plugin) — "Rejuve.bio founders and core team"    (LinkedIn)

Agent synthesises manually across the three outputs in conversation.
```

There is no automatic cross-engine orchestration in v0.1.
