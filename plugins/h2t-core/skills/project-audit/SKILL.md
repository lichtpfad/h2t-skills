---
name: project-audit
description: "Automated per-project audit pipeline: scan repo → positioning → readiness eval → generate docs → update registry. Usage: /project-audit [repo-id-or-path] [--tier product] [--dry-run]"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# /project-audit — Per-Project Audit Pipeline

5-stage pipeline: **SCAN → COUNCIL → JUDGE → DOCS → REPORT**

## Variables

```bash
command -v h2t-project-audit-scan >/dev/null 2>&1 || {
  echo "ERROR: h2t-project-audit-scan not found. Run /h2t-core:setup"
  exit 1
}

TEMPLATES_DIR="C:/dev/h2t-landings/templates"
PROJECTS_YAML="C:/dev/h2t-landings/projects.yaml"
```

## Argument Parsing

Parse the user's command arguments:

| Pattern | Meaning |
|---------|---------|
| No args | Audit current working directory |
| `h2t-snap` | Audit `C:/dev/h2t-snap` |
| `/path/to/repo` | Audit that path directly |
| `--tier product` | Batch: audit all projects with `product_potential: high` from projects.yaml |
| `--dry-run` | Show what would be generated, don't write files |

**Repo path resolution:**
1. If argument is an absolute path → use it
2. If argument is a repo id → try `C:/dev/{id}`
3. If `C:/dev/{id}` doesn't exist → error: "Repo not found. Specify full path."
4. No argument → use current working directory

## Stage 1: SCAN (Python script, no LLM)

Run the scan script:

```bash
h2t-project-audit-scan "<repo_path>" --projects-yaml "$PROJECTS_YAML"
```

The script outputs JSON to stdout. Read it and present a **brief summary** to the user:

```
## SCAN — {project_id}

Path: {path}
Language: {primary_language} | Commits: {commit_count} | Last: {last_commit_date}
Issues: {open_issue_count} open

| Check        | Status |
|--------------|--------|
| CLAUDE.md    | {yes/no} |
| README.md    | {yes/no} |
| Tests        | {yes/no} |
| Docs dir     | {yes/no} |
| Examples     | {yes/no} |
| License      | {yes/no} |
| Landing      | {yes/no} |
| CI           | {yes/no} |
| Releases     | {count, latest tag + asset names} |

Recent: {last 3 commit messages}
File tree: {top-level dirs and key files from file_tree}
```

If `existing_card` is present in scan result, also show the current projects.yaml card fields.
If `releases` is non-empty, show release tags and asset names (important for platform support detection).
If `landing_head` is non-empty, note that landing content is available for JUDGE analysis.

**Remote branches alert:** If any `remote_branches` entry has `ahead_of_local > 0`, this means **work was done on another machine** that hasn't been merged locally. Show a warning:

```
⚠ REMOTE WORK DETECTED:
  {branch_name}: {ahead_count} commits ahead (last: {date} — {message})
  This work is NOT reflected in local files. Pipeline will use remote data where possible.
```

This is critical for accurate assessment — the project may be more complete than local state suggests.

**Do NOT stop here.** Proceed immediately to Stage 2.

## Stage 2: COUNCIL (LLM — use model: sonnet)

Generate product positioning from scan data. This is NOT an interactive workshop — it's automated positioning from facts. But it must be MARKETING positioning, not a tech spec.

**Launch an Agent** with `model: sonnet`:

```
Prompt for the agent:

You are a product marketing strategist (not a technical writer). Based on the scan data below, generate a MARKETING positioning document.

SCAN DATA:
{paste full scan_result JSON — includes readme_head, releases, landing_head, file_tree, existing_card}

TEMPLATE (fill every section):
{read and paste contents of $TEMPLATES_DIR/positioning.md.template}

RULES:
- This is MARKETING positioning, not a tech spec. Write for someone deciding whether to use/buy this.
- One-Liner: max 10 words. Lead with the user benefit, not the technology.
- For Whom: specific role + pain point + context. Not "developers" — who exactly, in what situation?
- Problem: the PAIN the user feels, not the technical gap. Use their language.
- Solution: lead with the outcome, then explain the mechanism briefly.
- Why Now: market timing, competitive window, technology readiness. Be specific.
- Competitive Landscape: name real alternatives if known. If niche/internal, explain WHY no competitors exist (market gap or too early?)
- Key Metrics: business metrics (adoption, retention, time saved), not just technical metrics
- Use releases data to understand platform support (e.g. if .exe AND .dmg exist → cross-platform)
- Use landing_head to understand current messaging — improve on it, don't just repeat
- If existing_card has product_vision, use it but make it sharper
- MVP Scope: what's shipped (from releases) vs what's planned (from issues/commits)
- Definition of Done: 3-5 criteria mixing product AND marketing readiness
- Total output: under 400 words
```

Save agent's output as `positioning_draft` (in context, not to disk yet).

Show the positioning to the user:
```
## COUNCIL — Positioning Draft

{positioning_draft}
```

**Do NOT stop here.** Proceed immediately to Stage 3.

## Stage 3: JUDGE (LLM — use model: opus)

Evaluate project readiness with a calibrated rubric.

**Launch an Agent** with `model: opus`:

```
Prompt for the agent:

You are a senior engineering manager evaluating project readiness for public release.
Be calibrated and honest. A score of 3/3 means genuinely excellent, not "has the file."

SCAN DATA:
{paste full scan_result JSON — includes releases, landing_head, file_tree}

POSITIONING:
{positioning_draft}

IMPORTANT: Use ALL scan data fields for evidence:
- releases: check what platforms are supported (asset names like .exe, .dmg, .AppImage)
- landing_head: read and evaluate the landing page quality (messaging, CTA, design intent)
- file_tree: understand actual project structure
- Do NOT assume facts not in the data. If releases show only .exe, it's Windows-only.

RUBRIC — score each area 0-3:

### Code Quality (0-3)
- 0: No tests, no structure
- 1: Some structure OR some tests, not both
- 2: Tests + clear structure + reasonable coverage
- 3: Tests + CI + types/linting + good coverage

### Documentation (0-3)
- 0: No README or useless README
- 1: Basic README only
- 2: Good README + CLAUDE.md or agent docs
- 3: README + CLAUDE.md + examples + API docs

### Product Readiness (0-3)
- 0: No positioning, no landing, unclear purpose
- 1: Has one of: positioning, landing, clear README pitch
- 2: Has positioning + landing OR very clear product narrative
- 3: Positioning + landing + marketing docs + clear onboarding
- NOTE: If landing page exists, evaluate its quality: is the messaging clear? Is there a CTA? Does it convey value proposition in 5 seconds?

### Architecture (0-3)
- 0: Monolith, no clear API, tangled dependencies
- 1: Some modularity, unclear boundaries
- 2: Clear modules, defined API surface, reasonable deps
- 3: Clean API, modular, minimal deps, easy to extend

PART 2 — POSITIONING QUALITY EVAL

Also evaluate the POSITIONING document quality. Score each section 1-5:

### Positioning Sections (1-5 each):

| Section | What 5/5 looks like |
|---------|---------------------|
| Audience | Named persona with role, pain, context. Can find on LinkedIn in 30 sec |
| Problem | Described in user's language, not technical jargon. Specific pain, not abstract gap |
| Messaging | One-liner lands in 3 seconds. Clear benefit, not feature |
| Competitive | Named alternatives with specific gaps. Honest about own weaknesses |
| MVP Scope | Concrete, matches actual releases. In/Out is a real decision, not obvious |

If ANY positioning section scores below 3/5, list it in a `positioning_weaknesses` block with:
- Which section failed
- Why it failed (specific critique)
- What would make it pass (actionable fix instruction for COUNCIL)

OUTPUT FORMAT (exactly):

## Readiness Score: {total}/12

| Area | Score | Evidence |
|------|-------|----------|
| Code Quality | {n}/3 | {one-line justification with specific evidence} |
| Documentation | {n}/3 | {one-line justification} |
| Product Readiness | {n}/3 | {one-line justification} |
| Architecture | {n}/3 | {one-line justification} |

## Positioning Quality

| Section | Score | Note |
|---------|-------|------|
| Audience | {n}/5 | {one-line} |
| Problem | {n}/5 | {one-line} |
| Messaging | {n}/5 | {one-line} |
| Competitive | {n}/5 | {one-line} |
| MVP Scope | {n}/5 | {one-line} |

{IF any section < 3/5:}
### Positioning Weaknesses (for COUNCIL retry)
- **{section}**: {why it failed}. FIX: {what to do differently}

### Strengths
- {2-3 bullet points, be specific}

### Critical Gaps
- {2-3 bullet points, ordered by impact}

### Recommendations (priority order)
1. {most impactful action}
2. {second}
3. {third}
```

Save agent's output as `eval_report`.

### Stage 3b: COUNCIL RETRY (conditional, max 1 retry)

**Check eval_report for `Positioning Weaknesses` section.**

If **no weaknesses** (all positioning sections ≥ 3/5): proceed to Stage 4.

If **weaknesses found** AND this is the **first pass** (no retry yet):

1. Show the JUDGE evaluation to the user:
```
## JUDGE — Positioning needs improvement

{eval_report positioning quality table + weaknesses}

Retrying COUNCIL with JUDGE feedback (1 of 1 allowed retries)...
```

2. **Re-launch COUNCIL Agent** (model: sonnet) with the ORIGINAL prompt PLUS this addition:
```
JUDGE FEEDBACK — fix these specific issues:
{paste Positioning Weaknesses section from eval_report}

Keep sections that scored ≥ 3/5 unchanged. Only rewrite the weak sections.
```

3. **Re-launch JUDGE Agent** (model: opus) with the new positioning.

If **weaknesses found** AND this is already a **retry** (second pass):
- Show results to user: "Positioning still has weak spots after retry. Proceeding with current version."
- Continue to Stage 4.

Show final eval to user:

```
## JUDGE — Readiness Evaluation {" (after retry)" if retried}

{eval_report}
```

**Proceed to Stage 4.**

## Stage 4: DOCS (LLM — use model: sonnet)

Generate standardized documentation from templates.

### 4-pre: Structural health check

Gate is based on **machine-readable fields from `scan_result.docs_lint_health`** — not prose from JUDGE.

Check `scan_result.docs_lint_health`:

| Condition | Action |
|-----------|--------|
| `docs_lint_health` is null | docs-lint unavailable — skip gate, proceed |
| `status == "ok"` | proceed |
| `total_findings > 0` | show findings, ask user |

If findings exist:

```
⚠ STRUCTURAL ISSUES: {total_findings} findings (docs-lint doctor)

{list up to 10 findings from docs_lint_health.findings}

Generating docs for a structurally broken project may produce misleading documentation.
Proceed anyway? (yes / skip-docs)
```

Wait for user response. On `skip-docs` → jump to Stage 5 with `files_written = []`.

### 4a: Determine what to generate

Based on scan_result:
- If `has_claude_md` is false → generate CLAUDE.md
- If `has_readme` is false OR `readme_head` is minimal (<5 lines of real content) → generate README.md
- `positioning.md` → always generate (from COUNCIL output)
- `eval-report.md` → always generate (from JUDGE output)

### 4b: Generate docs

For each doc that needs generation, **launch an Agent** with `model: sonnet`:

**CLAUDE.md generation:**
```
Generate a CLAUDE.md for this project.

SCAN DATA: {scan_result JSON}
POSITIONING: {positioning_draft}
EVAL: {eval_report}
TEMPLATE: {read $TEMPLATES_DIR/CLAUDE.md.template}

RULES:
- Fill every template section with real data from scan
- Architecture section: derive from file structure and README
- Key Files: list actual files, not placeholders
- CLI/API: derive from README or pyproject.toml entry points
- Current Focus: derive from recent commits and open issues
- Keep total under 60 lines

CRITICAL: Return ONLY the file content as plain text in your response.
DO NOT use the Write tool. DO NOT create files on disk.
Stage 4c handles writing after human confirmation.
```

**README.md generation:**
```
Generate a README.md for this project.

SCAN DATA: {scan_result JSON}
POSITIONING: {positioning_draft}
TEMPLATE: {read $TEMPLATES_DIR/README.md.template}

RULES:
- What section: 3-5 sentences, concrete
- Features: derive from actual code/README, not aspirational
- Quick Start: real install + usage commands from pyproject.toml or README
- Status table: use scan data for real statuses
- Related Projects: use existing_card.serves/depends_on/enables
- Keep total under 80 lines

CRITICAL: Return ONLY the file content as plain text in your response.
DO NOT use the Write tool. DO NOT create files on disk.
Stage 4c handles writing after human confirmation.
```

### 4c: Human gate

**STOP. Show all generated docs to the user and ask for confirmation.**

```
## DOCS — Generated Files

### {filename_1}
{content}

---
### {filename_2}
{content}

---

**Target locations:**
- `{repo_path}/CLAUDE.md` {new/overwrite}
- `{repo_path}/README.md` {new/overwrite}
- `{repo_path}/docs/product/positioning.md` {new}
- `{repo_path}/docs/product/eval-report.md` {new}

Write these files? (yes / edit / skip)
```

**Wait for user response:**
- **yes** → write all files
- **edit** → user specifies changes, regenerate affected docs
- **skip** → skip writing, proceed to REPORT with dry-run note

**If --dry-run:** show docs but do NOT write. Print "(dry-run: no files written)"

### 4d: Write files

Create target directories if needed:
```bash
mkdir -p "{repo_path}/docs/product"
```

Write each file using the Write tool. For existing files (overwrite), confirm which sections changed.

## Stage 5: REPORT (Python script)

Update projects.yaml with new doc statuses:

```bash
h2t-project-audit-report "{project_id}" \
  --field claude_md=true \
  --field readme=true \
  --field marketing_docs=true \
  --projects-yaml "$PROJECTS_YAML"
```

Only pass `=true` for fields that were actually written (or already existed).

Show final summary:

```
## REPORT — Audit Complete

Project: {project_id}
Score: {total}/12
Files written: {list}
projects.yaml updated: {fields}

### Next Steps
{recommendations from JUDGE, top 3}
```

## Batch Mode

When `--tier product` is specified:

1. Read projects.yaml
2. Filter projects where `product_potential: high`
3. For each project:
   a. Run the full pipeline (SCAN → COUNCIL → JUDGE → DOCS → REPORT)
   b. Show summary
   c. Ask: "Continue to next project ({name})? (yes / skip / stop)"
4. After all projects: show aggregate summary table

## Error Handling

| Error | Action |
|-------|--------|
| Repo path not found | Stop with clear error message |
| scan.py fails | Show error, suggest checking path and git status |
| gh not available | Skip issues, note in scan result |
| Agent timeout | Retry once, then show partial results |
| User cancels at gate | Skip DOCS writing, still run REPORT with current state |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running scan manually (file reads) | Use scan.py script — faster, structured output |
| Writing docs without human gate | ALWAYS show and wait for confirmation at Stage 4c |
| Gating Stage 4 on JUDGE prose | Use `scan_result.docs_lint_health.total_findings` — a number, not substring match |
| Using sonnet for JUDGE | Use opus — evaluation needs strong reasoning |
| Using opus for COUNCIL | Use haiku — positioning from facts doesn't need deep reasoning |
| Skipping REPORT after dry-run | Still update projects.yaml if scan found existing docs |
