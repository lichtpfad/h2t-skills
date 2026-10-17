"""git pre-commit: nothing but dated Markdown enters docs/superpowers/plans|specs.

Third layer of the same rule (structure-guard catches Claude's writes, the CI layout job
catches what is already committed); this one catches files written by scripts — the
_gc_capture_*.jsonl dumps in h2t-transcription came from a Python script, and no
PreToolUse hook ever saw them. Install once per machine:

  mkdir -p ~/.h2t/git-hooks
  printf '#!/usr/bin/env bash\\nexec h2t-hook layout-precommit "$@"\\n' > ~/.h2t/git-hooks/pre-commit
  chmod +x ~/.h2t/git-hooks/pre-commit
  git config --global core.hooksPath ~/.h2t/git-hooks

A repo with its own core.hooksPath (h2t-skills: scripts/hooks) overrides the global one —
chain `h2t-hook layout-precommit` from that hook. Exit 1 blocks the commit.

Port of the 3.x bash handler of the same name. A git hook, not a Claude hook: no event on
stdin, arguments ignored, the exit code is the answer.
"""
from __future__ import annotations

import re
import subprocess

from h2t_ops.hooks.emit import to_stderr

PATTERN = re.compile(r"^docs/superpowers/(plans|specs)/"
                     r"([0-9]{4}-[0-9]{2}-[0-9]{2}-[^/]+\.md|README\.md|index\.md|\.gitkeep)$")


def main(argv: list[str]) -> int:
    # `|| true` in 3.x: a git failure here is "nothing staged", never a refusal.
    done = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=AR", "--",
                           "docs/superpowers/plans", "docs/superpowers/specs"],
                          capture_output=True, check=False)
    names = done.stdout.decode("utf-8", "replace").splitlines()
    bad = [name for name in names if not PATTERN.search(name)]
    if not bad:
        return 0
    lines = ["h2t layout-precommit: not a plan, refused in docs/superpowers/{plans,specs}/:"]
    lines += [f"  {name}" for name in bad]
    lines.append("  scripts → scripts/; run output → docs/.artifacts/<run>/; "
                 "drafts stay outside the repo.")
    to_stderr("\n".join(lines) + "\n")
    return 1
