"""PostToolUse hook: a merged PR closes the plans and specs it carried.

Retrospectively this link cannot be recovered. Measured on h2t-skills: a plan
slug appears in 7 of 60 merged PR bodies, and commit counts cannot separate
"done and never updated" from "abandoned" — which is why `docs-lint retire`
leaves the judgement to a person. At the moment of the merge nothing has to be
inferred: `gh pr view` lists the PR's own files.

That is where this hook first went wrong. "The PR listed the document" was read
as "the document is finished", and the two are not the same claim: a PR may
carry a plan because it implemented it, or because it edited it. Measured
2026-08-27 in one repository — PRs #58, #59 and #60, three documentation edits in
a row, each stamping `done` on a 2300-line decision map with four open questions
in section A alone.

What separates the two is on the same `gh pr view` output, and costs nothing to
read: a pull request that changed no code implemented nothing. That check is
`_implements_something`. A document that has no finished state says so for
itself with `lifecycle: living` in its frontmatter, and is never stamped.

Exit code is always 0. This is bookkeeping after the fact — a failure here must
never look like a failed merge.

Port of the 3.x hooks-handlers/plan_closer.py, deleted in Task 12a: the functions are the original's (AST-compared until the deletion);
`main()` became `handle()`, and the reply goes out through `h2t_ops.hooks.emit`.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.core.errors import H2TError
from h2t_ops.hooks.emit import Reply

# Only these carry a lifecycle. A report records a moment and is done when
# written; an ADR is a permanent record whose status means something else.
_LIFECYCLE_DIRS = ("docs/superpowers/plans/", "docs/superpowers/specs/")

_CLOSED = {
    "done", "complete", "completed", "accepted", "approved",
    "superseded", "deprecated", "rejected", "archived",
}

# `gh pr merge 408 ...` — the number is the first bare argument after `merge`.
# `env` is a run of VAR=value assignments that prefix the command (GH_REPO=o/r gh ...).
_MERGE = re.compile(r"(?:^|[;&|]\s*)(?P<env>(?:\w+=\S*\s+)*)(?P<gh>gh\s+pr\s+merge\b)"
                    r"(?P<rest>[^;&|]*)")
# Flags of `gh pr merge` that take a value (gh pr merge --help): the value is never the
# number, and `--repo` names the repository the merge went to.
_VALUE_FLAGS = {"-A", "--author-email", "-b", "--body", "-F", "--body-file",
                "--match-head-commit", "-t", "--subject", "-R", "--repo"}
_STATUS_LINE = re.compile(r"^status:\s*.*$", re.MULTILINE)
# A document whose author declared it has no finished state. A decision map is the
# case that forced this: it lives exactly as long as its open questions do, so every
# merge that touched it was stamping a lifecycle it does not have.
_LIVING = re.compile(r"^lifecycle:\s*[\"\']?living[\"\']?\s*$", re.MULTILINE | re.IGNORECASE)
# Suffixes a change can carry without implementing anything.
_DOC_SUFFIXES = (".md", ".mdx", ".rst", ".txt", ".adoc")
_PR_LINE = re.compile(r"^pr:\s*.*$\n?", re.MULTILINE)


def extract_pr_number(command: str) -> int | None:
    """The PR number in a `gh pr merge` command, or None if there is none.

    None also covers `gh pr merge` with no number (the current branch's PR):
    resolving that after the merge is a guess, and the branch may already be
    deleted. A guess here would stamp `status: done` on the wrong plan.
    """
    target = merge_target(command)
    return target[0] if target else None


def merge_target(command: str) -> tuple[int, str | None, str | None] | None:
    """(PR number, --repo value, directory of a leading `cd`) of a `gh pr merge`, or None.

    gh resolves the PR in the repository of its working directory unless `--repo`, `-R`
    or GH_REPO names another (#662). None whenever the repository is not certain: no
    number, a URL or branch, an unparseable line, more than one `cd`, `cd -`, `pushd`,
    a subshell. Each of those would make the hook stamp documents of a repository the
    merge never touched.
    """
    m = _MERGE.search(command)
    if not m:
        return None
    try:
        tokens = shlex.split(m.group("rest"))
    except ValueError:
        return None
    number: int | None = None
    repo: str | None = None
    it = iter(tokens)
    for token in it:
        if token.startswith("--repo="):
            repo = token.split("=", 1)[1]
        elif token.startswith("-R") and len(token) > 2:
            repo = token[2:]
        elif token in _VALUE_FLAGS:
            value = next(it, None)
            if token in ("-R", "--repo"):
                repo = value
        elif token.startswith("-"):
            continue
        elif number is None and token.isdigit():
            number = int(token)
        else:
            return None  # a URL, a branch, or a second positional: no guess
    if number is None:
        return None
    try:
        assignments = shlex.split(m.group("env"))  # GH_REPO="o/r" is shell-quoted too
    except ValueError:
        return None
    for assignment in assignments:
        name, _, value = assignment.partition("=")
        if name == "GH_REPO" and repo is None:
            repo = value

    prefix = command[: m.start("gh")]
    if any(mark in prefix for mark in ("(", "`", "$(")):
        return None
    cd_dir: str | None = None
    for part in re.split(r"&&|\|\||[;|]", prefix):
        try:
            words = shlex.split(part)
        except ValueError:
            return None
        if not words or words[0] not in ("cd", "pushd", "popd"):
            continue
        if words[0] != "cd" or cd_dir is not None or len(words) != 2 or words[1] == "-":
            return None
        cd_dir = words[1]
    return number, repo, cd_dir


def _slug(ref: str) -> str:
    """owner/repo, lowercased, from [HOST/]OWNER/REPO, an https URL or a git@host:o/r remote."""
    ref = ref.strip().removesuffix("/").removesuffix(".git")
    parts = re.split(r"[/:]", ref)
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else ""


def _remote_slugs(root: Path) -> set[str]:
    try:
        out = subprocess.run(["git", "-C", str(root), "remote", "-v"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return set()
    if out.returncode != 0:
        return set()
    return {_slug(line.split()[1]) for line in out.stdout.splitlines() if len(line.split()) > 1}


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    close = text.find("\n", end + 1)
    return text[: close + 1], text[close + 1 :]


def _implements_something(view: dict) -> bool:
    """Did this pull request change anything but documentation?

    The discriminator the hook was missing. A documentation-only PR cannot have
    implemented the plan it carries — it edited it. Read off the same `gh pr view`
    output, so it costs nothing and cannot be wrong about what the PR contained.

    A PR with no file list at all counts as implementing nothing: an empty answer
    from `gh` must not read as permission to stamp.
    """
    files = view.get("files") or []
    for entry in files:
        rel = entry.get("path") if isinstance(entry, dict) else str(entry)
        if rel and not rel.lower().endswith(_DOC_SUFFIXES):
            return True
    return False


def close_plans_for_pr(repo_root: Path, pr_number: int, view: dict,
                       failed: list[dict] | None = None) -> list[dict]:
    """Stamp `status: done` and `pr: N` on every plan/spec the PR carried.

    failed, when given, collects {"path", "error"} for every stamp the write refused or
    could not make: the hook says so instead of dropping it.

    Returns what actually changed. An unmerged PR, a file the PR deleted, a doc
    with no frontmatter, and a doc already closed all yield nothing — this runs
    unattended, so every uncertain case must be a no-op rather than a guess.
    """
    if str(view.get("state", "")).upper() != "MERGED":
        return []
    if not _implements_something(view):
        return []

    changed: list[dict] = []
    for entry in view.get("files") or []:
        rel = entry.get("path") if isinstance(entry, dict) else str(entry)
        if not rel or not rel.startswith(_LIFECYCLE_DIRS):
            continue
        path = repo_root / rel
        if not path.is_file():
            continue  # the PR deleted or moved it — e.g. retired into archive
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        parts = _split_frontmatter(text)
        if not parts:
            continue
        fm, body = parts

        if _LIVING.search(fm):
            continue

        m = _STATUS_LINE.search(fm)
        if not m:
            continue
        current = m.group(0).split(":", 1)[1].strip().strip('"').strip("'").lower()
        if current in _CLOSED:
            continue

        fm = _STATUS_LINE.sub('status: "done"', fm, count=1)
        fm = _PR_LINE.sub("", fm)
        fm = fm.replace('status: "done"', f'status: "done"\npr: {pr_number}', 1)
        try:
            store.repo(repo_root, "plan-closer").replace(rel, fm + body)
        except (OSError, H2TError) as exc:
            if failed is not None:
                failed.append({"path": rel, "error": str(exc)})
            continue
        changed.append({"path": rel, "was": current})
    return changed


def _pr_view(repo_root: Path, pr_number: int, repo: str | None = None) -> dict:
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "state,files",
             *(["--repo", repo] if repo else [])],
            capture_output=True, text=True, timeout=30, cwd=str(repo_root),
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {}


def handle(event: dict) -> Reply:
    if event.get("tool_name") != "Bash":
        return Reply()

    command = (event.get("tool_input") or {}).get("command", "")
    target = merge_target(command)
    if target is None:
        return Reply()
    pr_number, repo, cd_dir = target

    repo_root = Path.cwd().resolve()
    if cd_dir is not None:
        repo_root = paths.expand_user_dest(cd_dir).resolve()  # relative to the same cwd
        if not repo_root.is_dir():
            return Reply()
    slug = None
    if repo is not None:
        slug = _slug(repo)
        # the merge went to a named repository: act only on a clone of that one
        if not slug or slug not in _remote_slugs(repo_root):
            return Reply()
    failed: list[dict] = []
    changed = close_plans_for_pr(repo_root, pr_number,
                                 _pr_view(repo_root, pr_number, repo=slug), failed)
    if not changed and not failed:
        return Reply()
    text, notice = "", ""
    if changed:
        # Last two segments, not the basename: a plan and its spec share a stem,
        # so basenames alone print the same name twice.
        names = ", ".join("/".join(Path(c["path"]).parts[-2:]) for c in changed)
        lines = [f"  {c['path']}: {c['was']} → done" for c in changed]
        text = (f"PR #{pr_number} merged. Статус проставлен автоматически:\n"
                + "\n".join(lines)
                + "\nФайлы изменены локально и не закоммичены — включите их в "
                  "следующий коммит или закоммитьте отдельно.")
        notice = (f"PR #{pr_number}: проставлен status: done в {len(changed)} документ(ах): "
                  f"{names}. Изменения не закоммичены.")
    if failed:
        # A refused write is said, not dropped (hooks.md: a silent hook is a failure).
        text += ("\n" if text else "") + (
            f"PR #{pr_number}: статус не проставлен — запись не прошла:\n"
            + "\n".join(f"  {f['path']}: {f['error']}" for f in failed))
        notice += (" " if notice else "") + (
            f"PR #{pr_number}: не удалось проставить status: done в "
            + ", ".join(f["path"] for f in failed) + ".")
    # Two channels, two readers: `text` (additionalContext) reaches the model, `notice`
    # (systemMessage) is the line the user sees in the TUI.
    return Reply(text=text, notice=notice)
