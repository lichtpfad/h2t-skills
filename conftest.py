"""Repo-wide pytest fixtures."""
import pytest


@pytest.fixture(autouse=True)
def _neutralize_eval_secrets(monkeypatch, tmp_path_factory):
    """Stop the real ~/.dor/secrets.env from leaking H2T_EVALS_* creds into tests.

    Once #321 creds are configured, SkillEval construction resolves mode=push
    and (in a venv with the h2t_evals SDK) would fire real network pushes to
    prod during unit tests. Point the default secrets file at a nonexistent
    path; tests that need a file pass secrets_path=... or monkeypatch
    session._DEFAULT_SECRETS explicitly.
    """
    try:
        from lib.eval import session as sess
    except Exception:
        return
    missing = tmp_path_factory.mktemp("no-secrets") / "secrets.env"
    monkeypatch.setattr(sess, "_DEFAULT_SECRETS", missing, raising=False)


@pytest.fixture(autouse=True)
def _isolate_home_writes(monkeypatch, tmp_path_factory):
    """Keep the suite out of the user's ~/.h2t (#441).

    The session writers resolve their targets from env vars with home-relative defaults,
    so a test that forgets one writes into the real home. That is how 94% of the author's
    live activity spool came to be pytest fixtures: two tests redirected H2T_SESSION_ROOT
    and neither redirected H2T_ACTIVITY_SPOOL, and nothing noticed, because the spool has
    no reader (#442).

    Redirecting here rather than per-test is the point — the next writer added under a new
    variable is the one nobody remembers to isolate. Its default still lands in the real
    home, which is what _real_home_artifacts below is for.
    """
    root = tmp_path_factory.mktemp("isolated-home")
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(root / "activity" / "spool.jsonl"))
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root / "sessions"))


def _real_home_artifacts() -> dict[str, tuple[int, int]]:
    """size+mtime of the home files the suite must never touch."""
    from pathlib import Path

    watched = [
        Path.home() / ".h2t" / "activity" / "spool.jsonl",
        Path.home() / ".h2t" / "sessions",
    ]
    state: dict[str, tuple[int, int]] = {}
    for path in watched:
        try:
            if path.is_dir():
                files = sorted(str(p) for p in path.rglob("*") if p.is_file())
                state[str(path)] = (len(files), int(max((p.stat().st_mtime for p in path.rglob("*") if p.is_file()), default=0)))
            elif path.is_file():
                st = path.stat()
                state[str(path)] = (st.st_size, int(st.st_mtime))
        except OSError:
            continue
    return state


def pytest_sessionstart(session):
    session.stash_h2t_home_before = _real_home_artifacts()


def pytest_sessionfinish(session, exitstatus):
    """Fail the run if the suite changed anything in the real ~/.h2t.

    A tripwire, not a redirect: it catches the variable nobody thought to isolate,
    including ones added after this file was written.
    """
    before = getattr(session, "stash_h2t_home_before", None)
    if before is None:
        return
    after = _real_home_artifacts()
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    if changed:
        print("\nERROR: the suite wrote into the real home (#441):")
        for key in sorted(changed):
            print(f"  {key}: {before.get(key)} -> {after.get(key)}")
        print("  Redirect the writer's env var in conftest._isolate_home_writes.")
        session.exitstatus = 1
