"""registry.json -> человекочитаемый markdown, сгруппированный по треку."""
from __future__ import annotations
import json
import sys
from pathlib import Path

_COLS = "| practice | recurrence | domain-indep | verdict | source diversity | current location |"
_SEP = "|---|---|---|---|---|---|"


def _rows(findings: list[dict]) -> str:
    lines = []
    for f in sorted(findings, key=lambda x: -x["recurrence"]):
        flag = "⚠ single-lineage" if f["recurrence"] < 2 else "ok"
        lines.append(
            f"| {f['practice']} | {f['recurrence']} | {f['domain_independence']} "
            f"| `{f['lift_verdict']}` | {flag} | {f['current_location']} |"
        )
    return "\n".join(lines)


def render_md(reg: dict) -> str:
    findings = reg["findings"]
    win = reg.get("window", ["", ""])
    out = [f"# Practice harvest registry ({win[0]} … {win[1]})", ""]
    for track, title in [("process", "Process track"), ("technical", "Technical track")]:
        fs = [f for f in findings if f["track"] == track]
        out += [f"## {title}", "", _COLS, _SEP, _rows(fs) if fs else "| — | | | | | |", ""]
    return "\n".join(out)


def main() -> None:
    reg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.write_text(render_md(reg), encoding="utf-8")
    print(f"rendered -> {out}")


if __name__ == "__main__":
    main()
