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
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
fi

TEMPLATES_DIR="C:/dev/h2t-landings/templates"
PROJECTS_YAML="C:/dev/h2t-landings/projects.yaml"
SCAN_SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/project-audit/scripts/scan.py"
REPORT_SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/project-audit/scripts/report.py"
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
$H2T_PYTHON "$SCAN_SCRIPT" "<repo_path>" --projects-yaml "$PROJECTS_YAML"
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

Recent: {last 3 commit messages}
```

If `existing_card` is present in scan result, also show the current projects.yaml card fields.

**Do NOT stop here.** Proceed immediately to Stage 2.

## Stage 2: COUNCIL (LLM — use model: haiku)

Generate lightweight positioning from scan data. This is NOT an interactive workshop — it's automated positioning from facts.

**Launch an Agent** with `model: haiku`:

```
Prompt for the agent:

You are a product positioning analyst. Based on the scan data below, generate a positioning document.

SCAN DATA:
{paste full scan_result JSON}

TEMPLATE (fill every section):
{read and paste contents of $TEMPLATES_DIR/positioning.md.template}

RULES:
- One-Liner: max 10 words, must be concrete (not "AI-powered tool for X")
- For Whom: specific role + context, not "developers"
- Problem/Solution: grounded in what the repo ACTUALLY does (check README head, commits)
- If existing_card has product_vision, use it as guidance
- If existing_card has one_liner, improve it or keep if already good
- Competitive Landscape: if you don't know real competitors, say "No direct competitors identified — niche/internal tool"
- MVP Scope: derive from open issues and recent commits
- Definition of Done: 3-5 concrete criteria
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
{paste full scan_result JSON}

POSITIONING:
{positioning_draft}

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

### Architecture (0-3)
- 0: Monolith, no clear API, tangled dependencies
- 1: Some modularity, unclear boundaries
- 2: Clear modules, defined API surface, reasonable deps
- 3: Clean API, modular, minimal deps, easy to extend

OUTPUT FORMAT (exactly):

## Readiness Score: {total}/12

| Area | Score | Evidence |
|------|-------|----------|
| Code Quality | {n}/3 | {one-line justification with specific evidence} |
| Documentation | {n}/3 | {one-line justification} |
| Product Readiness | {n}/3 | {one-line justification} |
| Architecture | {n}/3 | {one-line justification} |

### Strengths
- {2-3 bullet points, be specific}

### Critical Gaps
- {2-3 bullet points, ordered by impact}

### Recommendations (priority order)
1. {most impactful action}
2. {second}
3. {third}
```

Save agent's output as `eval_report`. Show to user:

```
## JUDGE — Readiness Evaluation

{eval_report}
```

**Do NOT stop here.** Proceed to Stage 4.

## Stage 4: DOCS (LLM — use model: sonnet)

Generate standardized documentation from templates.

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
$H2T_PYTHON "$REPORT_SCRIPT" "{project_id}" \
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
| Using sonnet for JUDGE | Use opus — evaluation needs strong reasoning |
| Using opus for COUNCIL | Use haiku — positioning from facts doesn't need deep reasoning |
| Skipping REPORT after dry-run | Still update projects.yaml if scan found existing docs |
