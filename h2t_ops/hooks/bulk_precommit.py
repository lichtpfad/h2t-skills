"""git pre-commit: a bulk staging that swept in scratch is refused.

`git add -A` / `git add .` / `commit -am` are written down as forbidden in three repos'
rules and still happen — a rule without a mechanism. The signature of a sweep is not the
count alone (a refactor stages 50 files legitimately) but count plus debris: logs, dumps,
backups, editor leftovers. Both together → refuse and name the debris. Exit 1 blocks the
commit.

Port of the 3.x bash handler of the same name. A git hook, not a Claude hook: no event on
stdin, arguments ignored, the exit code is the answer.
"""
from __future__ import annotations

import os
import re
import subprocess

from h2t_ops.hooks.emit import to_stderr

DEFAULT_THRESHOLD = 20
DEBRIS = re.compile(r"\.(log|jsonl|bak|bak[0-9]*|tmp|orig|rej|swp)$"
                    r"|(^|/)(null|nul|tmp_[^/]*|diag_[^/]*|debug_[^/]*)$", re.IGNORECASE)


def _raw() -> str:
    """`${H2T_BULK_THRESHOLD:-20}`: unset and empty both mean the default."""
    return os.environ.get("H2T_BULK_THRESHOLD") or str(DEFAULT_THRESHOLD)


def _threshold() -> int:
    # 3.x compared with `[ -le ]`, which errors on a non-number and so fell through to the
    # debris check: a value that is not a number checks every staging for debris.
    try:
        return int(_raw())
    except ValueError:
        return -1


def main(argv: list[str]) -> int:
    threshold = _threshold()
    done = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
                          capture_output=True, check=False)
    if done.returncode != 0:
        # `set -e` in 3.x: a failed git exits with git's code and its message.
        to_stderr(done.stderr.decode("utf-8", "replace"))
        return done.returncode
    staged = [name for name in done.stdout.decode("utf-8", "replace").splitlines() if name]
    if len(staged) <= threshold:
        return 0
    debris = [name for name in staged if DEBRIS.search(name)]
    if not debris:
        return 0
    lines = [f"h2t bulk-precommit: {len(staged)} files staged and among them scratch — "
             "looks like git add -A. Refused."]
    lines += [f"  {name}" for name in debris]
    lines.append("  Stage files by name; scratch goes to docs/.artifacts/<run>/ or outside "
                 f"the repo. (H2T_BULK_THRESHOLD={_raw()})")
    to_stderr("\n".join(lines) + "\n")
    return 1
