"""A skill's record must be written before it can ask the user anything.

These skills run at the end of a session, when the user has often already left. A question
before the write costs the whole record: on 2026-08-23 the meetgeek session composed a full
summary, asked for a session name at handoff Step 1, and got no answer — nothing reached
~/.h2t/sessions. Renaming a written file is cheap; an unwritten one is gone.

An audit of every shipped SKILL.md found seven interactive gates. Six guard an outward or
irreversible action and are correct: session naming at session-start (the user is present by
definition), project-audit before generating docs for a structurally broken repo and again
before writing files into the repo, setup waiting for pasted secrets, docs-lint on a dirty
worktree, and handoff's rule-promotion gate — which stands after the write, so it can only
cost rule promotion. The seventh was the only one of its class. See .claude/rules/gates.md.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# skill directory -> the command that persists work the session already produced.
#
# One member, and that is the finding rather than a shortfall. init-project was the other
# candidate and does not belong: widening the scan window did surface a gate before its
# write ("If `needs_input` is false — wait for «ок» or corrections", SKILL.md:45), but its
# write IS the outward action — entries in ~/.h2t/config/repo-mapping.yaml and domains.yaml,
# and .claude/project-id inside the user's repo. Confirming before that is what the rule
# permits. Handoff is different: its record is the work, and the gate stood between the two.
WRITERS = {
    "h2t-core/skills/handoff": "h2t-handoff write",
}

BLOCKING = (
    re.compile(r"\bwait for\b", re.IGNORECASE),
    re.compile(r"⛔\s*GATE"),
)


def _text_before_the_write(manifest, write_call):
    """Everything preceding the LAST mention of the write command.

    The name also appears in the `command -v` install check and inside the ERROR message
    beside it — init-project mentions it four times, and the first two sit in the first 900
    characters. Filtering those by what precedes them was not enough: a mutation test put a
    ⛔ GATE just before the real invocation and the tripwire stayed green, because the window
    had already collapsed onto the error string. The last mention is the invocation in every
    skill measured (handoff 1 of 1 at char 6922 of 8505; init-project 4 of 4 at 2225 of
    3220), and taking it makes the window as large as it can honestly be.

    A gate that legitimately follows the write stays outside the window, which is why
    handoff's Step 6b rule-promotion gate does not trip this.
    """
    text = manifest.read_text(encoding="utf-8")
    matches = [m.start() for m in re.finditer(re.escape(write_call), text)]
    if not matches:
        pytest.fail(f"{manifest} no longer mentions `{write_call}` — the writer moved")
    if not _inside_a_bash_block(text, matches[-1]):
        pytest.fail(
            f"{manifest} last mentions `{write_call}` in prose, not in a runnable block — "
            "the scan would then anchor on an explanation while the real write moved."
        )
    return text[:matches[-1]]


def _inside_a_bash_block(text, index):
    """Is this position inside a ```bash fence?

    Anchoring on any mention leaves a vacuity path: the skill could stop invoking the
    writer while keeping a late explanatory mention of its name, and both tests would still
    pass. Requiring the anchor to sit in an executable block closes that.
    """
    open_bash = False
    position = 0
    for line in text.splitlines(keepends=True):
        if position > index:
            break
        stripped = line.strip()
        if stripped.startswith("```"):
            open_bash = stripped.startswith("```bash") if not open_bash else False
        elif open_bash and position <= index < position + len(line):
            return True
        position += len(line)
    return False


@pytest.mark.parametrize(("skill", "write_call"), sorted(WRITERS.items()))
def test_the_scan_window_covers_the_pipeline(skill, write_call):
    """Control: a window collapsed to the header would make the next test vacuous."""
    manifest = ROOT / "plugins" / skill / "SKILL.md"
    window = _text_before_the_write(manifest, write_call)
    # Two thirds of the file, measured: handoff 6922/8505, init-project 2225/3220. A window
    # that collapses onto a header or an error string is how this scan goes quietly vacuous.
    assert len(window) > 0.6 * len(manifest.read_text(encoding="utf-8")), (skill, len(window))


@pytest.mark.parametrize(("skill", "write_call"), sorted(WRITERS.items()))
def test_nothing_blocks_before_the_write(skill, write_call):
    """A textual tripwire, not a proof.

    It catches the two phrasings that have appeared — "wait for" and a ⛔ GATE marker — in
    the text preceding the write call. It cannot see a gate phrased a third way, one reached
    through a variable, or one in a referenced file. The rule in .claude/rules/gates.md is
    the invariant; widen BLOCKING when a third phrasing shows up, and do not claim the
    invariant is mechanically enforced.
    """
    manifest = ROOT / "plugins" / skill / "SKILL.md"
    offenders = [p.pattern for p in BLOCKING
                 if p.search(_text_before_the_write(manifest, write_call))]
    assert not offenders, (
        f"{manifest} blocks on the user before `{write_call}`: {offenders}. "
        "Every value the writer needs must be derived, not asked."
    )
