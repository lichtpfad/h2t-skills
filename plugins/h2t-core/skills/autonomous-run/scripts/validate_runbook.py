"""Sealed post-generation validator. Splits the artifact into H2 sections and reports
every missing required section, every safety marker absent FROM ITS OWN SECTION, and any
unresolved <<TOKEN>>. Run after generation AND after model weaving, so weaving cannot
silently gut a section or drop safety text (spec § Architecture step 3; codex-plan-gate-1 P1)."""
from __future__ import annotations
import re
import sys
import runbook_schema as S


class RunbookInvalid(Exception):
    pass


_H2 = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def split_sections(text: str) -> dict[str, str]:
    """Map each '## Heading' -> body text up to the next H2 (or EOF)."""
    out: dict[str, str] = {}
    matches = list(_H2.finditer(text))
    for i, m in enumerate(matches):
        heading = "## " + m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[heading] = text[start:end]
    return out


def validate(text: str) -> list[str]:
    """Return human-readable problems; empty list == valid."""
    problems: list[str] = []
    secs = split_sections(text)
    for h in S.REQUIRED_SECTIONS:
        if h not in secs:
            problems.append(f"missing required section: {h}")
    for marker, section in S.MARKER_SECTION.items():
        if marker not in secs.get(section, ""):
            problems.append(f"safety marker {marker!r} missing from section {section}")
    if "<<" in text or ">>" in text:
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
