"""The 3.x names called from outside hooks.json keep their contract under `h2t-hook`.

Two kinds of caller, both committed files that outlive any plugin version:

- git pre-commit (`scripts/hooks/pre-commit`, `~/.h2t/git-hooks/pre-commit`):
  `layout-precommit`, `bulk-precommit`, `secrets-precommit`. No event on stdin; exit 1
  refuses the commit, and the reason is on stderr.
- a project's `.claude/settings.json`, written by scaffold-project: `on-stop`,
  `post-git-commit-docs-lint`. Plain stdout, always exit 0.

Each scenario runs `h2t-hook <name>` in a fresh git repository and must give the recorded
exit code and text. The records were taken from the 3.x handlers, which ran the same
scenarios until they were deleted (Task 12a report).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GIT = shutil.which("git")
POSIX = os.name != "nt"
pytestmark = pytest.mark.skipif(GIT is None, reason="git is not on PATH")


def h2t_hook() -> list[str]:
    bindir = Path(sys.executable).parent
    for candidate in (bindir / "h2t-hook", bindir / "h2t-hook.exe",
                      bindir / "Scripts" / "h2t-hook.exe"):
        if candidate.is_file():
            return [str(candidate)]
    found = shutil.which("h2t-hook")
    return [found] if found else [sys.executable, "-m", "h2t_ops.hook_entry"]


LAYOUT_REFUSED = "h2t layout-precommit: not a plan, refused in docs/superpowers/{plans,specs}/:\n"
LAYOUT_TAIL = ("  scripts → scripts/; run output → docs/.artifacts/<run>/; "
               "drafts stay outside the repo.\n")
BULK_TAIL = ("  Stage files by name; scratch goes to docs/.artifacts/<run>/ or outside the repo. "
             "(H2T_BULK_THRESHOLD={})\n")
SECRETS_ABSENT = ("h2t secrets-precommit: gitleaks not on PATH — staged diff not scanned "
                  "(install: https://github.com/gitleaks/gitleaks/releases)\n")
SECRETS_FOUND = ("h2t secrets-precommit: gitleaks found a secret in the staged diff. Refused.\n"
                 "  see: gitleaks git --staged --redact -v .\n")
MILESTONE = "[h2t] Milestone 'M1' has no open issues -- consider /h2t-dev:milestone-closure\n"
STOP_EVENT = json.dumps({"hook_event_name": "Stop", "session_id": "s1"})
COMMIT_EVENT = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                           "tool_input": {"command": "git commit -m docs"}})
STATUS_EVENT = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                           "tool_input": {"command": "git status"}})


def _files(n: int, *extra: str) -> dict[str, str]:
    files = {f"src/f{i:02d}.py": "x\n" for i in range(n)}
    files.update({name: "x\n" for name in extra})
    return files


# hook, id: committed first, staged, renamed (git mv), env, stdin, fakes, expected.
# `fakes`: gitleaks -> its exit code; gh -> {"slug": rc of `repo view`, "api": stdout}.
SCENARIOS: list[dict] = [
    {"hook": "layout-precommit", "id": "a-dated-plan", "stage": {
        "docs/superpowers/plans/2026-01-01-x.md": "# x\n",
        "docs/superpowers/specs/README.md": "# r\n"}, "rc": 0, "stderr": ""},
    {"hook": "layout-precommit", "id": "nothing-staged", "rc": 0, "stderr": ""},
    {"hook": "layout-precommit", "id": "a-dump-and-a-note", "stage": {
        "docs/superpowers/plans/notes.txt": "n\n",
        "docs/superpowers/specs/_gc_capture_1.jsonl": "{}\n",
        "docs/superpowers/plans/2026-01-01-ok.md": "# ok\n",
        "src/notes.txt": "elsewhere is fine\n"}, "rc": 1,
     "stderr": LAYOUT_REFUSED + "  docs/superpowers/plans/notes.txt\n"
               "  docs/superpowers/specs/_gc_capture_1.jsonl\n" + LAYOUT_TAIL},
    {"hook": "layout-precommit", "id": "renamed-in", "commit": {"draft.txt": "d\n"},
     "mv": [("draft.txt", "docs/superpowers/specs/draft.txt")], "rc": 1,
     "stderr": LAYOUT_REFUSED + "  docs/superpowers/specs/draft.txt\n" + LAYOUT_TAIL},
    # A rename inside the pathspec is R; one from outside it reads as A (renamed-in).
    {"hook": "layout-precommit", "id": "renamed-within",
     "commit": {"docs/superpowers/plans/old.txt": "o\n"},
     "mv": [("docs/superpowers/plans/old.txt", "docs/superpowers/plans/new.txt")], "rc": 1,
     "stderr": LAYOUT_REFUSED + "  docs/superpowers/plans/new.txt\n" + LAYOUT_TAIL},
    {"hook": "layout-precommit", "id": "modified-is-not-added",
     "commit": {"docs/superpowers/plans/old.txt": "1\n"},
     "stage": {"docs/superpowers/plans/old.txt": "2\n"}, "rc": 0, "stderr": ""},

    {"hook": "bulk-precommit", "id": "many-clean-files", "stage": _files(25), "rc": 0,
     "stderr": ""},
    {"hook": "bulk-precommit", "id": "few-files-with-a-log", "stage": _files(3, "run.log"),
     "rc": 0, "stderr": ""},
    {"hook": "bulk-precommit", "id": "at-the-threshold", "stage": _files(19, "run.log"),
     "rc": 0, "stderr": ""},
    {"hook": "bulk-precommit", "id": "a-sweep", "stage": _files(20, "run.log", "out/debug_x",
                                                               "tmp_probe", "keep.md"),
     "rc": 1, "stderr": "h2t bulk-precommit: 24 files staged and among them scratch — looks "
                        "like git add -A. Refused.\n  out/debug_x\n  run.log\n  tmp_probe\n"
                        + BULK_TAIL.format(20)},
    {"hook": "bulk-precommit", "id": "threshold-from-env", "env": {"H2T_BULK_THRESHOLD": "2"},
     "stage": _files(2, "a.ORIG"), "rc": 1,
     "stderr": "h2t bulk-precommit: 3 files staged and among them scratch — looks like git "
               "add -A. Refused.\n  a.ORIG\n" + BULK_TAIL.format(2)},
    {"hook": "bulk-precommit", "id": "threshold-not-a-number",
     "env": {"H2T_BULK_THRESHOLD": "lots"}, "stage": _files(1, "x.bak2"), "rc": 1,
     "stderr": "h2t bulk-precommit: 2 files staged and among them scratch — looks like git "
               "add -A. Refused.\n  x.bak2\n" + BULK_TAIL.format("lots")},
    {"hook": "bulk-precommit", "id": "threshold-empty-is-default",
     "env": {"H2T_BULK_THRESHOLD": ""}, "stage": _files(3, "x.log"), "rc": 0, "stderr": ""},

    {"hook": "secrets-precommit", "id": "no-gitleaks", "stage": {"a.txt": "a\n"},
     "path": "empty", "rc": 0, "stderr": SECRETS_ABSENT},
    {"hook": "secrets-precommit", "id": "gitleaks-clean", "stage": {"a.txt": "a\n"},
     "fakes": {"gitleaks": 0}, "rc": 0, "stderr": ""},
    {"hook": "secrets-precommit", "id": "gitleaks-finds", "stage": {"a.txt": "a\n"},
     "fakes": {"gitleaks": 1}, "rc": 1, "stderr": SECRETS_FOUND},
    {"hook": "secrets-precommit", "id": "gitleaks-errors", "stage": {"a.txt": "a\n"},
     "fakes": {"gitleaks": 3}, "rc": 1, "stderr": SECRETS_FOUND},

    {"hook": "on-stop", "id": "a-ready-milestone", "stdin": STOP_EVENT,
     "fakes": {"gh": {"slug": 0, "api": json.dumps([{"title": "M1", "open_issues": 0},
                                                     {"title": "M2", "open_issues": 3}])}},
     "rc": 0, "stdout": MILESTONE},
    {"hook": "on-stop", "id": "empty-stdin", "stdin": "",
     "fakes": {"gh": {"slug": 0, "api": json.dumps([{"title": "M1", "open_issues": 0}])}},
     "rc": 0, "stdout": MILESTONE},
    {"hook": "on-stop", "id": "not-a-github-repo", "stdin": STOP_EVENT,
     "fakes": {"gh": {"slug": 1, "api": "[]"}}, "rc": 0, "stdout": ""},
    {"hook": "on-stop", "id": "api-answers-garbage", "stdin": STOP_EVENT,
     "fakes": {"gh": {"slug": 0, "api": "<html>"}}, "rc": 0, "stdout": ""},
    {"hook": "on-stop", "id": "no-gh", "stdin": STOP_EVENT, "path": "empty", "rc": 0,
     "stdout": ""},

    {"hook": "post-git-commit-docs-lint", "id": "docs-committed", "stdin": COMMIT_EVENT,
     "commit": {"docs/a.md": "# a\n", "src/b.py": "b\n"}, "lint": '{"status": "ok"}',
     "rc": 0, "stdout": "",
     "report": {"status": "ok", "summary": "docs-lint doctor completed",
                "changed_docs": ["docs/a.md"], "docs_lint": {"status": "ok"}}},
    {"hook": "post-git-commit-docs-lint", "id": "lint-fails", "stdin": COMMIT_EVENT,
     "commit": {"docs/a.md": "# a\n"}, "lint": '{"status": "error"}',
     "rc": 0, "stdout": "",
     "report": {"status": "error", "summary": "docs-lint doctor completed",
                "changed_docs": ["docs/a.md"], "docs_lint": {"status": "error"}}},
    {"hook": "post-git-commit-docs-lint", "id": "no-docs-in-commit", "stdin": "",
     "commit": {"src/b.py": "b\n"}, "lint": '{"status": "ok"}',
     "rc": 0, "stdout": "",
     "report": {"status": "skipped", "summary": "no docs markdown changed in latest commit",
                "changed_docs": [], "docs_lint": None}},
    {"hook": "post-git-commit-docs-lint", "id": "not-a-commit", "stdin": STATUS_EVENT,
     "commit": {"docs/a.md": "# a\n"}, "lint": '{"status": "ok"}',
     "rc": 0, "stdout": "", "report": None},
]


def scenario_id(s: dict) -> str:
    return f"{s['hook']}/{s['id']}"


def _git(repo: Path, *args: str) -> None:
    subprocess.run([GIT, "-C", str(repo), *args], check=True, capture_output=True)


def _write(repo: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _fake(bindir: Path, name: str, body: str) -> None:
    """A POSIX script on PATH. The scenarios that need one are skipped on Windows, where
    `subprocess.run(["gh", ...])` finds only an .exe."""
    script = bindir / name
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    script.chmod(0o755)


def prepare(s: dict, tmp_path: Path) -> tuple[Path, dict]:
    """The repository and the environment for one scenario."""
    if s.get("fakes") and not POSIX:
        pytest.skip("fake gh/gitleaks are POSIX shell scripts")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "t"),
                       ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        _git(repo, "config", key, value)
    _write(repo, {"README.md": "r\n"})
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    if s.get("commit"):
        _write(repo, s["commit"])
        _git(repo, "add", "--", *s["commit"])
        _git(repo, "commit", "-q", "-m", "fixture")
    for src, dst in s.get("mv", []):
        (repo / dst).parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "mv", src, dst)
    if s.get("stage"):
        _write(repo, s["stage"])
        _git(repo, "add", "--", *s["stage"])

    home = tmp_path / "home"
    home.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    env = {k: v for k, v in os.environ.items()
           if k not in ("H2T_BULK_THRESHOLD", "H2T_DOCS_LINT_SCRIPT", "H2T_LINT_HOOK_TIMEOUT")}
    env.update(HOME=str(home), USERPROFILE=str(home))
    fakes = s.get("fakes") or {}
    if "gitleaks" in fakes:
        _fake(bindir, "gitleaks", f'echo "$@" > "{tmp_path / "gitleaks.args"}"\n'
                                  f'exit {fakes["gitleaks"]}\n')
    if "gh" in fakes:
        (tmp_path / "api.out").write_text(fakes["gh"]["api"], encoding="utf-8")
        _fake(bindir, "gh", 'case "$1" in\n'
                            f'  repo) echo o/r; exit {fakes["gh"]["slug"]} ;;\n'
                            f'  api) [ "$2" = "repos/o/r/milestones?state=open" ] || exit 9\n'
                            f'       cat "{tmp_path / "api.out"}" ;;\n'
                            'esac\n')
    # The fakes come first; "empty" is a PATH with nothing but them.
    env["PATH"] = str(bindir) if s.get("path") == "empty" else os.pathsep.join(
        [str(bindir), env.get("PATH", "")])
    if "lint" in s:
        lint = tmp_path / "lint.py"
        lint.write_text(f"print({s['lint']!r})\n", encoding="utf-8")
        env["H2T_DOCS_LINT_SCRIPT"] = str(lint)
    env.update(s.get("env") or {})
    return repo, env


def run(argv: list[str], repo: Path, env: dict, stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=repo, env=env, input=stdin.encode("utf-8"),
                          capture_output=True, timeout=60, check=False)


def check(s: dict, done: subprocess.CompletedProcess, repo: Path, tmp_path: Path) -> None:
    out = done.stdout.decode("utf-8").replace("\r\n", "\n")
    err = done.stderr.decode("utf-8").replace("\r\n", "\n")
    got = {"rc": done.returncode, "stdout": out, "stderr": err}
    assert got == {"rc": s["rc"], "stdout": s.get("stdout", ""), "stderr": s.get("stderr", "")}
    if "gitleaks" in (s.get("fakes") or {}):
        args = (tmp_path / "gitleaks.args").read_text(encoding="utf-8").split()
        assert args == ["git", "--staged", "--redact", "--no-banner", "--exit-code", "1", "."]
    if "report" in s:
        path = repo / ".h2t" / "lifecycle" / "post-git-commit-docs-lint.json"
        if s["report"] is None:
            assert not path.exists()
            return
        report = json.loads(path.read_text(encoding="utf-8"))
        assert report["command"] == "post-git-commit-docs-lint"
        assert report["repo_root"] == str(repo.resolve())
        assert {"status": report["status"], "summary": report["summary"],
                "changed_docs": report["evidence"]["changed_docs"],
                "docs_lint": report["evidence"]["docs_lint"]} == s["report"]


@pytest.mark.parametrize("s", SCENARIOS, ids=[scenario_id(s) for s in SCENARIOS])
def test_h2t_hook_keeps_the_3x_contract(s, tmp_path):
    repo, env = prepare(s, tmp_path)
    done = run([*h2t_hook(), s["hook"]], repo, env, s.get("stdin", ""))
    check(s, done, repo, tmp_path)


def test_every_command_hook_has_scenarios():
    from h2t_ops import hooks
    commands = {name for name, handle in hooks.HANDLERS.items()
                if isinstance(handle, hooks.Command)}
    assert commands == {"layout-precommit", "bulk-precommit", "secrets-precommit", "on-stop",
                        "post-git-commit-docs-lint"}
    assert commands <= {s["hook"] for s in SCENARIOS}


def test_arguments_are_ignored_as_in_3x(tmp_path):
    """The global git hook passes "$@" through (layout_precommit.py docstring)."""
    s = next(s for s in SCENARIOS if s["id"] == "a-dump-and-a-note")
    repo, env = prepare(s, tmp_path)
    done = run([*h2t_hook(), s["hook"], "extra", "--args"], repo, env, "")
    check(s, done, repo, tmp_path)


def test_docs_lint_defaults_to_the_package(tmp_path):
    """3.x looked for a plugin lint.py and reported "not found" without one; the package
    carries docs-lint, so the doctor always runs."""
    s = dict(next(s for s in SCENARIOS if s["id"] == "docs-committed"))
    s.pop("lint")
    repo, env = prepare(s, tmp_path)
    done = run([*h2t_hook(), s["hook"]], repo, env, s["stdin"])
    assert done.returncode == 0 and done.stdout == b""
    report = json.loads((repo / ".h2t/lifecycle/post-git-commit-docs-lint.json")
                        .read_text(encoding="utf-8"))
    assert report["summary"] == "docs-lint doctor completed"
    # doctor's own JSON report, parsed: the package's docs-lint ran on this repository.
    assert report["evidence"]["docs_lint"]["command"] == "docs-lint doctor"


def test_a_crash_is_one_line_exit_1_and_a_log_row(tmp_path, monkeypatch):
    from h2t_ops import hook_entry, hooks

    def boom(argv):
        raise RuntimeError("probe")

    monkeypatch.setattr(sys, "argv", ["h2t-hook", "layout-precommit"])
    monkeypatch.setitem(hooks.HANDLERS, "layout-precommit", hooks.Command("layout_precommit"))
    monkeypatch.setattr(hooks.Command, "__call__", lambda self, argv: boom(argv))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert hook_entry.main() == 1
    rows = (tmp_path / ".h2t/logs/hooks.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(rows[-1])["hook"] == "layout-precommit"
