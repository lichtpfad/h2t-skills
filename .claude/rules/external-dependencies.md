# External Dependencies

A skill in this pack may need something the pack does not ship. Two obligations follow, and
neither is optional: **declare it in `compatibility`, and check for it before acting.**

Skipping either produces the same failure: the skill appears in the listing, looks reachable,
and dies on its first command. That costs the agent a turn and the reader their trust — and it
is indistinguishable, from the outside, from a skill that is simply broken.

## Inventory

Measured 2026-08-28 across the 29 shipped `SKILL.md`.

| dependency | needed by | how it is obtained |
|---|---|---|
| `uv` | 10 skills | the one hard prerequisite of the pack; supplies every interpreter |
| `gh` | 7 skills | GitHub CLI, authenticated |
| `h2t-snap` | `h2t-core:snap`, `h2t-core:project-audit` | prebuilt, free, both platforms — see below |
| `drawio`, `node` | `h2t-arch:drawio` | draw.io desktop app + Node runtime |
| `npx` | `h2t-dev:pre-merge-check` | ships with Node |
| `llm-kb-engine` | `h2t-ops:kb` | `uv tool install`; KB location from `H2T_KB_ROOT` |
| `h2t-tools:playwright-agent` | `h2t-creative:landing`, `:deck` | **not in the pack, not installed** — #460 |
| `h2t-tools:screenshot` | `h2t-ops:research` | not in the pack; optional there, unlike the above |
| `mcp__anysite` | `h2t-ops:research` | MCP server, alternative path |

Environment variables that gate behaviour: `H2T_KB_ROOT`, `H2T_SESSION_ROOT`,
`H2T_ACTIVITY_SPOOL`, `H2T_SECRETS_FILE`.

## h2t-snap

Free, and prebuilt binaries exist for both macOS and Windows in `lichtpfad/h2t-snap`. Building
from source with a Swift toolchain — which `snap/SKILL.md` still describes first — is the
fallback, not the path.

```bash
h2t-snap --version          # is it already here?
```

If absent: take the release binary for the platform, put it on PATH. macOS additionally needs
Screen Recording (capture) and Accessibility (click/type), granted through the system dialog on
first run. **Exit code 5 means permission denied, not a missing window** — the two look alike in
a transcript and are fixed in completely different places.

## Writing a skill that needs one

Declare the requirement where the agent reads it before running anything — the `compatibility`
field, not prose in the body. `h2t-ops:kb` is the model:

```yaml
compatibility: "Requires the installed llm-kb-engine tool (uv tool install), a data-only KB whose
  location is given by H2T_KB_ROOT, and the h2t-ops research connector for ingest harvest."
```

Then check, and fail with the remedy rather than the symptom:

```bash
command -v h2t-ops >/dev/null || { echo "ERROR: h2t-ops not on PATH. Run /h2t-core:setup"; exit 1; }
```

`h2t-ops:daily-brief`, `h2t-core:snap` and `h2t-core:project-audit` do this. Most skills do not,
and simply assume.

## Degradation

Missing a dependency is not automatically fatal, and treating it as fatal has its own cost.
`h2t-creative:landing` halts delivery outright when `h2t-tools:playwright-agent` is absent — a
plugin that is in nobody's install — which makes the skill unexecutable as written rather than
merely unverified. Prefer marking the result unverified and saying so; reserve the stop for the
case where continuing would produce something harmful.
