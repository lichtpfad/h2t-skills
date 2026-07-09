"""Post-generation drift-guard for the runbook artifact. Splits into H2 sections and
reports missing/duplicate/empty required sections, safety markers absent FROM THEIR OWN
SECTION, missing pipeline steps, and unresolved <<TOKEN>>. Run after generation AND after
model weaving (spec § Architecture step 3).

SCOPE (honest, codex-gate-M1): this defends against *accidental drift* — a weaving model
silently gutting or dropping a safety section. It is NOT an adversarial sandbox: a
malicious agent could bypass by never calling the validator. Duplicate-heading and
empty-body checks close the realistic accidental-bypass paths; line-scoped marker matching
reduces (does not eliminate) unrelated-prose false-accepts."""
from __future__ import annotations
import re
import sys
import runbook_schema as S


class RunbookInvalid(Exception):
    pass


_H2 = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def _headings(text: str) -> list[str]:
    return ["## " + m.group(1).strip() for m in _H2.finditer(text)]


def split_sections(text: str) -> dict[str, str]:
    """Map each '## Heading' -> body text up to the next H2 (or EOF). On duplicate
    headings the last body wins; `validate` rejects duplicates so that never certifies."""
    out: dict[str, str] = {}
    matches = list(_H2.finditer(text))
    for i, m in enumerate(matches):
        heading = "## " + m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[heading] = text[start:end]
    return out


def _marker_on_a_line(marker: str, body: str) -> bool:
    return any(marker in line for line in body.splitlines())


def validate(text: str) -> list[str]:
    """Return human-readable problems; empty list == valid."""
    problems: list[str] = []
    headings = _headings(text)
    secs = split_sections(text)
    for h in S.REQUIRED_SECTIONS:
        n = headings.count(h)
        if n == 0:
            problems.append(f"missing required section: {h}")
        elif n > 1:
            problems.append(f"duplicate required section (bypass risk): {h}")
        elif not secs.get(h, "").strip():
            problems.append(f"empty body in required section: {h}")
    for marker, section in S.MARKER_SECTION.items():
        if not _marker_on_a_line(marker, secs.get(section, "")):
            problems.append(f"safety marker {marker!r} missing from section {section}")
    pipe = secs.get("## Pipeline steps", "")
    for step in S.PIPELINE_STEPS:
        # require the checkbox+bold form the resume parser reads, not a bare substring
        if not re.search(r"(?m)^- \[[ xX]\] \*\*" + re.escape(step) + r"\*\*", pipe):
            problems.append(f"pipeline step missing/malformed in Pipeline steps: {step}")
    if re.search(r"<<\w+>>", text):  # only real unresolved tokens, not a stray `>>` redirect
        problems.append("unresolved <<TOKEN>> placeholder remains")
    return problems


def validate_or_raise(text: str) -> None:
    problems = validate(text)
    if problems:
        raise RunbookInvalid("; ".join(problems))


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_runbook.py <runbook.md>", file=sys.stderr)
        return 2
    problems = validate(open(argv[1], encoding="utf-8").read())
    if problems:
        for p in problems:
            print(f"INVALID: {p}", file=sys.stderr)
        return 1
    print("OK: runbook valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
