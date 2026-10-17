"""git pre-commit: a secret is caught in the staged diff, before it has a commit hash.

The CI gitleaks job scans history and fails the run — after the secret is already in a
pushed commit and must be rotated. h2t-transcription's HuggingFace token
(realtime_subtitles.bat, 2026-07-19) sat there for seven weeks before anything ran. Needs
the gitleaks binary on PATH (brew/winget/scoop, or the release tarball); when it is absent
this prints one line and exits 0 — a missing tool must not block commits, but it must not
be silent either. Exit 1 blocks the commit.

Port of the 3.x bash handler of the same name. A git hook, not a Claude hook: no event on
stdin, arguments ignored, the exit code is the answer. gitleaks' own output never reaches
the terminal: it is the finding, and the finding may be the secret (.claude/rules/secrets.md).
"""
from __future__ import annotations

import shutil
import subprocess

from h2t_ops.hooks.emit import to_stderr


def main(argv: list[str]) -> int:
    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        to_stderr("h2t secrets-precommit: gitleaks not on PATH — staged diff not scanned "
              "(install: https://github.com/gitleaks/gitleaks/releases)\n")
        return 0
    done = subprocess.run([gitleaks, "git", "--staged", "--redact", "--no-banner",
                           "--exit-code", "1", "."],
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, check=False)
    if done.returncode == 0:
        return 0
    to_stderr("h2t secrets-precommit: gitleaks found a secret in the staged diff. Refused.\n"
              "  see: gitleaks git --staged --redact -v .\n")
    return 1
