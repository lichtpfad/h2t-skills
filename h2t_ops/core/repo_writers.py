"""What each command may write into the user's repository (#548 §7.1, table «repo»).

Globs are fnmatch on the POSIX path relative to the repository root; `*` crosses `/`.
Task 17 replaces the starting set below with the measured one and pins it with a test that
runs every command in a scratch repository.
"""
REPO_WRITERS: dict[str, dict[str, tuple[str, ...]]] = {
    # §7.1: .claude/project-id — "create if absent"; an existing file is kept (plan R32).
    "init-project": {"create": (".claude/project-id",)},
    "h2t-project-register": {"create": (".claude/project-id",)},
}
