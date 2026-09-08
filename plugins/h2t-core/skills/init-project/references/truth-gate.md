# Truth gate — three answers by command before the first line of code

Origin: cross-repo audit 2026-09 (`C:/dev/docs/research/2026-09-repo-audit/summary.md`).
Root finding: "flag says done, content missing" in 11 of 21 repos; a project that cannot
answer the three questions below by command has not started, whatever its docs say
(crypto-machine: 1541 lines of rules, 0 code).

A rule without a mechanism is a note. This gate is the mechanism: every answer is a
command, every command is run, empty output is red.

## The three questions

| # | Question | Accepted answer | Red when |
|---|----------|-----------------|----------|
| 1 | **Where is the source of truth?** Which file/table/query holds the state everything else is derived from | A command that prints it (e.g. `sqlite3 data/x.db ".tables"`, `ls data/raw/`, `git ls-files docs/adr`) | Command missing, or prints nothing |
| 2 | **Where is the stage-run record?** Which stage ran over which entity, when, with what result | A command that lists runs (e.g. `tail -5 runs/ledger.jsonl`, `ls docs/.artifacts/`) | Command missing, or prints nothing |
| 3 | **What is the data contract?** Shape of what stage N hands to stage N+1 | A command that prints the schema/spec (e.g. `cat docs/contracts/*.md`, `python -c "import x; print(x.Schema)"`) | Command missing, or prints nothing |

Project types: `git` / `git-local` — all three. `directory` / docs-only — question 1 only.

## Procedure

1. Ask the three questions in one prompt. Show the table above verbatim.
2. For each answer run the command with Bash, one command per call. Show output.
3. Empty output or non-zero exit → that row is red. Say so; do not paraphrase it green.
4. Write the result into the project `CLAUDE.md` under a `## Truth gate` heading:

```markdown
## Truth gate (<YYYY-MM-DD>)
| # | question | command | status |
|---|----------|---------|--------|
| 1 | source of truth | `<cmd>` | green / red |
| 2 | stage-run record | `<cmd>` | green / red |
| 3 | data contract | `<cmd>` | green / red |
```

5. A red row is allowed — the project is new. What is not allowed is a missing row or a
   row without a command. The heading stays until all three are green; re-run
   `/h2t-core:init-project` to update.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Accepting a path as the answer | A path is not a command; ask for the command that prints the content |
| Accepting a README sentence as the answer | The audit found 8 rules written and violated; a note is not a mechanism |
| Marking green without running | Run it. Output shown, then status |
| Skipping the gate because "no code yet" | That is exactly when it runs |
