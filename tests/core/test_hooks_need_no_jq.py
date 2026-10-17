"""No hook may need jq (D1, #541).

Measured 2026-10-15 on Windows: Git Bash ships no jq, so `gather-on-prompt` failed on every
message (`line 19: jq: command not found`) and the slash path to a session skill never
gathered. The other hook tests skip on Windows, and a POSIX runner has jq, so nothing saw it.

Since Task 12a a hook is `hooks/run` (bash) in front of a module in h2t_ops/hooks
(Python). Both are read here: a jq call in the wrapper, and `jq` as an argv element in a
handler's subprocess.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPERS = sorted(REPO_ROOT.glob("plugins/*/hooks/run"))
MODULES = sorted((REPO_ROOT / "h2t_ops" / "hooks").glob("*.py"))

# A command position: start of line, after a pipe, `$(`, `;`, `&&`, `||`. Mentions in
# comments and `gh … --jq` (gh's own built-in) are not calls to the jq binary.
JQ_CALL = re.compile(r"(^|[|;(&]\s*|\$\(\s*)jq(\s|$)")
# `["jq", ...]` / `"jq"` as a list element; `"--jq"` is gh's flag, not the binary.
JQ_ARGV = re.compile(r"""[\[,(]\s*["']jq["']""")


def test_no_wrapper_calls_jq():
    found = []
    for path in WRAPPERS:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0] if not line.lstrip().startswith("#") else ""
            if JQ_CALL.search(code):
                found.append(f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}")
    assert WRAPPERS, "found no wrappers — the walk, not the tree"
    assert not found, "jq is not on Windows (Git Bash):\n  " + "\n  ".join(found)


def test_no_handler_runs_jq():
    found = [f"{p.name}:{n}" for p in MODULES
             for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
             if JQ_ARGV.search(line)]
    assert len(MODULES) >= 14, "found too few handler modules — the walk, not the tree"
    assert not found, found


def test_the_argv_pattern_sees_a_call_and_ignores_the_gh_flag():
    """Control: a pattern that matches nothing would make the test above vacuous."""
    assert JQ_ARGV.search('subprocess.run(["jq", "-r", ".x"])')
    assert not JQ_ARGV.search('["gh", "repo", "view", "--jq", ".nameWithOwner"]')
