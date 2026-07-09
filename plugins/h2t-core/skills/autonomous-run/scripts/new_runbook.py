"""Render the durable runbook artifact from references/runbook-template.md.

Token substitution uses `<<NAME>>` markers (NOT str.format) so literal braces in bash /
JSON inside the template are safe. The generator is thin; the template holds the safety
prose; validate_runbook is the guard (spec § Generation)."""
from __future__ import annotations
from pathlib import Path
import runbook_schema as S
from validate_runbook import validate_or_raise

_TEMPLATE = Path(__file__).resolve().parents[1] / "references" / "runbook-template.md"

# Per-step contract stamped by the generator (skill/done/failure/re-entry). `input` is
# filled by the model per run. Every step in S.PIPELINE_STEPS MUST have an entry.
PIPELINE_CONTRACT: dict[str, tuple[str, str, str, str]] = {
    "write-spec":          ("superpowers:brainstorming (spec tail)", "spec file exists + frontmatter", "escalate", "idempotent: overwrite spec"),
    "review-spec":         ("codex review (embedded)", "no [P1]", "fix P1 then re-run (<=N)", "idempotent: re-review"),
    "write-plan":          ("superpowers:writing-plans", "plan file exists", "escalate", "idempotent: overwrite plan"),
    "plan-gate":           ("codex review (embedded)", "no [P1]", "fix P1 then re-run (<=N)", "idempotent: re-review"),
    "subagent-driven-dev": ("superpowers:subagent-driven-development", "all tasks green", "per-task gate; escalate on repeated fail", "continue from first unchecked task"),
    "gates":               ("codex + pre-merge-check", "no [P1]; suite green", "fix then re-run (<=N)", "idempotent: re-run gate"),
    "e2e":                 ("real entrypoint run", "DONE / N/A / BLOCKED-DEFERRED", "BLOCKED->handoff; behavioral fail->fix", "idempotent: re-run"),
    "PR":                  ("superpowers:finishing-a-development-branch", "PR opened", "escalate", "continue: reuse branch"),
    "handoff":             ("h2t-core:handoff", "session record written", "n/a (terminal)", "idempotent: re-run handoff"),
}


def _rows() -> str:
    out = []
    for step in S.PIPELINE_STEPS:
        skill, done, fail, reentry = PIPELINE_CONTRACT[step]
        out.append(
            f"- [ ] **{step}** — skill: `{skill}` · input: `<fill>` · "
            f"done: {done} · failure: {fail} · re-entry: {reentry}"
        )
    return "\n".join(out)


def render(*, title: str, today: str, runbook_path: str, branch: str, spec_path: str,
           issue: str, venv_test: str, e2e_state: str) -> str:
    if not e2e_state.strip() or e2e_state.split()[0] not in S.E2E_STATES:
        raise ValueError(f"e2e_state must start with one of {S.E2E_STATES}; got {e2e_state!r}")
    text = _TEMPLATE.read_text(encoding="utf-8")
    subs = {"title": title, "today": today, "runbook_path": runbook_path,
            "branch": branch, "spec_path": spec_path, "issue": issue,
            "venv_test": venv_test, "e2e_state": e2e_state, "pipeline_rows": _rows()}
    for k, v in subs.items():
        text = text.replace(f"<<{k}>>", v)
    validate_or_raise(text)  # sealed: never emit an invalid runbook
    return text


def create_runbook(dest: str, **fields: str) -> Path:
    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(**fields), encoding="utf-8")
    return p
