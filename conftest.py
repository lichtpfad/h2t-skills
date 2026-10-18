"""Repo-wide pytest fixtures."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

# The developer's home, taken at import, before any fixture moves HOME (#548 R5).
REAL_HOME = Path.home()


def _uv_cache_dir() -> str | None:
    """The real uv cache, asked of uv while HOME is still the real one (None without uv)."""
    if os.environ.get("UV_CACHE_DIR"):
        return os.environ["UV_CACHE_DIR"]
    uv = shutil.which("uv")
    if uv is None:
        return None
    out = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True, check=False)
    return out.stdout.strip() or None


# A test that runs uv offline needs its cache, not the whole real home (#548 R5).
REAL_UV_CACHE = _uv_cache_dir()


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
    # Through HOME, not H2T_PATH_ROOT: the legacy places are home-relative by design, and a
    # test reaching secrets.get without its own HOME would read the real ~/.dor/secrets.env
    # (#321 again — real pushes to prod from unit tests). R5 retired the old variables.
    home = root / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    # Tests that commit in temp repos need an author once the real ~/.gitconfig is gone.
    gitconfig = root / "gitconfig"
    gitconfig.write_text("[user]\n name = test\n email = test@example.invalid\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    from h2t_ops.core import paths
    # CLAUDE_CONFIG_DIR moves the harness place; set by the developer's shell it would point
    # the suite at the real ~/.claude.
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV or k == "CLAUDE_CONFIG_DIR":
            monkeypatch.delenv(k, raising=False)


def _real_home_artifacts(home: Path | None = None) -> dict[str, tuple[int, ...]]:
    """size+mtime_ns of the home files the suite must never touch.

    Nanoseconds and sizes, not whole seconds: a rewrite within the same second at equal size
    would otherwise read as no change. `home` is injectable so the tripwire can be tested
    against a temporary tree (tests/governance/test_suite_isolation.py)."""
    # Built here, not from h2t_ops.core.paths: pytest_sessionstart runs before any fixture,
    # so Path.home() is still the real one.
    # Every entry of ~/.h2t and ~/.dor, each its own key, so the report names the area.
    # Not ~/.h2t/logs and ~/.h2t/run: the live session's own hooks write there while the
    # suite runs. Task 12 wrote into ~/.h2t/research, which the old short list did not watch.
    home = Path.home() if home is None else home
    watched: list[Path] = []
    for top, skip in ((home / ".h2t", {"logs", "run"}), (home / ".dor", set())):
        try:
            watched += [p for p in top.iterdir() if p.name not in skip]
        except OSError:
            continue
    watched += [home / ".config" / n for n in ("google-calendar-mcp", "gmail", "notion", "telegram")]
    state: dict[str, tuple[int, ...]] = {}
    for path in watched:
        try:
            if path.is_dir():
                stats = []
                for d, _dirs, names in os.walk(path):
                    for n in names:
                        try:
                            stats.append(os.lstat(os.path.join(d, n)))
                        except OSError:
                            continue
                state[str(path)] = (len(stats), sum(st.st_size for st in stats),
                                    max((st.st_mtime_ns for st in stats), default=0))
            elif path.exists():
                st = path.stat()
                state[str(path)] = (st.st_size, st.st_mtime_ns)
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
