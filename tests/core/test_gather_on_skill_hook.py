"""`gather-on-skill` must produce INIT_DATA for init-project (#378).

SKILL.md step 1 tells the agent to read `INIT_DATA:` from hook output, and lists running
detect_project.py by hand as an anti-pattern — but nothing ever emitted INIT_DATA. The
hook matched `*init-project*` and ran gather, so the documented path could not work and
the only working path was the forbidden one.

The hook is the executor on purpose: 672249e moved gathering out of the model's hands
because the model skipped it ("Closes #12 — gather.py can no longer be ignored").
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "plugins" / "h2t-core" / "hooks-handlers" / "gather-on-skill"

pytestmark = pytest.mark.skipif(os.name == "nt", reason="bash wrapper; POSIX only")


@pytest.fixture
def hook_env(tmp_path):
    """A deterministic interpreter and a private TMPDIR so the 30s dedup lock is fresh.

    The interpreter only has to satisfy what the plugin scripts import; requiring the
    root-only `lib.cli` package is the defect under test.
    """
    for candidate in (REPO_ROOT / ".venv" / "bin" / "python", Path(sys.executable)):
        if candidate.is_file() and subprocess.run(
            [str(candidate), "-c", "import yaml"], capture_output=True
        ).returncode == 0:
            interpreter = candidate
            break
    else:
        pytest.skip("no interpreter with PyYAML available")

    env = dict(os.environ)
    env["H2T_PYTHON"] = str(interpreter)
    env["TMPDIR"] = str(tmp_path / "tmp")
    Path(env["TMPDIR"]).mkdir(parents=True)
    return env


def _run_hook(env, skill, cwd):
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(HOOK)],
        input=json.dumps({"tool_input": {"skill": skill}, "cwd": str(cwd)}),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


def _system_message(result):
    assert result.returncode == 0, f"rc={result.returncode} stderr={result.stderr!r}"
    assert result.stdout.strip(), f"no stdout; stderr={result.stderr!r}"
    return json.loads(result.stdout)["systemMessage"]


def test_init_project_skill_receives_init_data(hook_env, tmp_path):
    """The skill's documented input must actually arrive."""
    project = tmp_path / "some-project"
    project.mkdir()

    message = _system_message(_run_hook(hook_env, "h2t-core:init-project", project))

    assert message.startswith("INIT_DATA:"), message[:200]
    payload = json.loads(message[len("INIT_DATA:"):])
    assert "detected" in payload
    assert "already_registered" in payload
    assert payload["detected"]["id"] == "some-project"


def test_init_project_does_not_receive_a_briefing(hook_env, tmp_path):
    """Detection, not gather: a briefing answers a different question."""
    project = tmp_path / "some-project"
    project.mkdir()

    message = _system_message(_run_hook(hook_env, "h2t-core:init-project", project))

    assert "BRIEFING:" not in message
    assert "GATHER_META:" not in message


def test_session_start_receives_a_briefing(hook_env):
    """#12 regression: the context must arrive without the model fetching it.

    The hook cd's into the plugin root and probed `import lib.cli.main`, but the plugin
    has never vendored `lib/cli` — so this returned GATHER_ERROR in every layout, dev and
    marketplace cache alike, from 14e2b42 (2026-04-25) onward.
    """
    message = _system_message(_run_hook(hook_env, "h2t-core:session-start", REPO_ROOT))

    assert "INIT_DATA:" not in message
    assert message.startswith("BRIEFING:"), message[:200]
    assert "GATHER_META:" in message


def test_unrelated_skill_is_ignored(hook_env, tmp_path):
    result = _run_hook(hook_env, "some-other:skill", tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


DETECT = REPO_ROOT / "plugins" / "h2t-core" / "skills" / "init-project" / "scripts" / "detect_project.py"


@pytest.fixture
def fixture_config(tmp_path):
    """A config root registering one repo under a domain that does not exist at $HOME."""
    root = tmp_path / "config"
    root.mkdir()
    (root / "repo-mapping.yaml").write_text(
        "mappings:\n  probe-repo: fixture-domain/probe-repo\n", encoding="utf-8"
    )
    (root / "domains.yaml").write_text(
        "domains:\n"
        "  fixture-domain:\n"
        "    label: Fixture\n"
        "    projects:\n"
        "    - id: probe-repo\n"
        "      label: Probe Repo\n",
        encoding="utf-8",
    )
    return root


def _git_repo(path):
    """repo_name is only derived for git projects, so detection needs a real one."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    return path


def _detect(env, cwd, *args):
    return subprocess.run(
        [env["H2T_PYTHON"], str(DETECT), "--cwd", str(cwd), *args],
        capture_output=True, text=True, env=env,
    )


def test_detect_honours_config_root_flag(hook_env, fixture_config, tmp_path):
    """Hardcoded `Path.home()/".h2t"/"config"` could not be pointed at a fixture (#378).

    Its two siblings both allow an override: h2t-project-register takes --config-root,
    identify_project() reads H2T_CONFIG_ROOT.
    """
    project = _git_repo(tmp_path / "probe-repo")

    result = _detect(hook_env, project, "--config-root", str(fixture_config))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["already_registered"] is True
    assert payload["current"]["domain"] == "fixture-domain"


def test_detect_honours_config_root_env(hook_env, fixture_config, tmp_path):
    """The env var the rest of gather already respects."""
    project = _git_repo(tmp_path / "probe-repo")

    env = dict(hook_env, H2T_CONFIG_ROOT=str(fixture_config))
    result = _detect(env, project)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["already_registered"] is True


def _fake_script(path, *, stdout="", stderr="", rc=0):
    path.write_text(
        "import sys\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({rc})\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def fake_plugin(tmp_path, hook_env):
    """A plugin tree whose scripts we control, so failure paths are reachable."""
    root = tmp_path / "plugin"
    (root / "hooks-handlers").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "skills" / "session-start" / "scripts").mkdir(parents=True)
    (root / "skills" / "init-project" / "scripts").mkdir(parents=True)

    hook = root / "hooks-handlers" / "gather-on-skill"
    hook.write_text(HOOK.read_text(encoding="utf-8"), encoding="utf-8")
    hook.chmod(0o755)
    resolver = REPO_ROOT / "plugins" / "h2t-core" / "scripts" / "resolve-h2t-python.sh"
    (root / "scripts" / "resolve-h2t-python.sh").write_text(
        resolver.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return root


def _run_fake(env, plugin_root, skill, cwd):
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(plugin_root / "hooks-handlers" / "gather-on-skill")],
        input=json.dumps({"tool_input": {"skill": skill}, "cwd": str(cwd)}),
        capture_output=True, text=True, cwd=cwd, env=env,
    )


def test_a_failing_script_is_reported_not_injected(hook_env, fake_plugin, tmp_path):
    """Partial stdout plus a non-zero exit must not pass for a real briefing."""
    _fake_script(
        fake_plugin / "skills" / "session-start" / "scripts" / "gather.py",
        stdout="BRIEFING:\nhalf a brie", stderr="boom: config unreadable", rc=1,
    )

    result = _run_fake(hook_env, fake_plugin, "h2t-core:session-start", tmp_path)

    message = json.loads(result.stdout)["systemMessage"]
    assert message.startswith("GATHER_ERROR"), message[:200]
    assert "boom: config unreadable" in message
    assert "half a brie" not in message


def test_control_characters_survive_as_valid_json(hook_env, fake_plugin, tmp_path):
    """The injected envelope is JSON; a tab or CR in the payload must not break it."""
    _fake_script(
        fake_plugin / "skills" / "session-start" / "scripts" / "gather.py",
        stdout='BRIEFING:\ncol\tcol\r\nquote " and back\\slash\n\nGATHER_META: {}',
    )

    result = _run_fake(hook_env, fake_plugin, "h2t-core:session-start", tmp_path)

    message = json.loads(result.stdout)["systemMessage"]
    assert "col\tcol" in message
    assert 'quote " and back\\slash' in message


def test_dedup_lock_is_per_directory(hook_env, fake_plugin, tmp_path):
    """A skill run in one repo must not silence the same skill in another."""
    _fake_script(
        fake_plugin / "skills" / "session-start" / "scripts" / "gather.py",
        stdout="BRIEFING:\nfrom the script\n\nGATHER_META: {}",
    )
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    first = _run_fake(hook_env, fake_plugin, "h2t-core:session-start", repo_a)
    second = _run_fake(hook_env, fake_plugin, "h2t-core:session-start", repo_b)

    assert first.stdout.strip(), "first run produced nothing"
    assert second.stdout.strip(), "second run in a different repo was suppressed"


def test_a_failed_run_does_not_suppress_the_retry(hook_env, fake_plugin, tmp_path):
    """The dedup lock must record a success, not an attempt."""
    script = fake_plugin / "skills" / "session-start" / "scripts" / "gather.py"
    _fake_script(script, stderr="transient", rc=1)
    first = _run_fake(hook_env, fake_plugin, "h2t-core:session-start", tmp_path)
    assert json.loads(first.stdout)["systemMessage"].startswith("GATHER_ERROR")

    _fake_script(script, stdout="BRIEFING:\nrecovered\n\nGATHER_META: {}")
    second = _run_fake(hook_env, fake_plugin, "h2t-core:session-start", tmp_path)

    assert second.stdout.strip(), "retry after a failure was suppressed by the lock"
    assert "recovered" in json.loads(second.stdout)["systemMessage"]
