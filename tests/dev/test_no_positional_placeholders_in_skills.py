"""No SKILL.md may contain `$` followed by a digit (#484).

When a skill is invoked with arguments, the harness expands `$0`, `$1`, ... inside the
skill text. The research cost table wrote prices as `$0.02`, so a live invocation with a
query rendered `~BMAD-METHOD.02` in place of every price — at the point where an agent
reads them before spending money.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLACEHOLDER = re.compile(r"\$\d")


def test_no_skill_text_collides_with_argument_placeholders():
    hits = [
        f"{path.relative_to(REPO)}:{lineno}: {line.strip()}"
        for path in sorted((REPO / "plugins").rglob("SKILL.md"))
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if PLACEHOLDER.search(line)
    ]
    assert not hits, "write amounts as '0.02 USD', not '$0.02':\n" + "\n".join(hits)
