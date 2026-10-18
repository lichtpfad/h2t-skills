"""Every secrets surface reads the path #432 made canonical (#448).

#432 added ~/.h2t/config/secrets/secrets.env to h2t_ops.core.secrets and stopped there.
The research connector and the setup skill each carried their own candidate list, so a key
written to the documented location was invisible to `h2t-ops research` and reported MISSING
by `setup doctor` — while `h2t-ops notion` found it.

Each side's own tests stayed green throughout: the defect lived in the seam. This is the
round trip — one key, written only to the documented location, read by all three.

In 4.0 the documented location is a 3.x fallback read through core.secrets, whose paths
resolve at call time: a tmp HOME is the whole isolation (#548).
"""
import pytest

from h2t_ops.connectors.research import client
from h2t_ops.core import paths
from h2t_ops.core import secrets as core_secrets
from h2t_ops.setup import legacy as setup_h2t

KEY = "EXA_API_KEY"
VALUE = "fake-documented-path-value"


def _home(tmp_path, monkeypatch):
    for name in (KEY, "H2T_SECRETS_FILE", "H2T_PATH_ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


@pytest.fixture
def documented_only(tmp_path, monkeypatch):
    """A home whose ONLY secrets file is the documented one."""
    _home(tmp_path, monkeypatch)
    documented = paths.legacy("secrets.h2t") / "secrets.env"
    documented.parent.mkdir(parents=True)
    documented.write_text(f"{KEY}={VALUE}\n", encoding="utf-8")
    yield tmp_path
    import os
    os.environ.pop(KEY, None)


def test_core_reads_documented_path(documented_only, monkeypatch):
    core_secrets.load_secrets()
    import os
    assert os.environ.get(KEY) == VALUE


def test_research_reads_documented_path(documented_only):
    assert client.resolve_secret(KEY) == VALUE


def test_setup_sees_documented_path(documented_only):
    assert setup_h2t._secret_present(KEY, documented_only) is True


def test_research_hint_names_documented_path(tmp_path, monkeypatch):
    """A miss must point at the location every other message names."""
    _home(tmp_path, monkeypatch)

    with pytest.raises(client.ConfigError) as ei:
        client.resolve_secret(KEY)

    assert "~/.h2t/config/secrets/secrets.env" in (ei.value.hint or "")


def test_research_does_not_read_the_secrets_file_variable(tmp_path, monkeypatch):
    """3.x read H2T_SECRETS_FILE (expanding ~, #448 review); 4.0 does not read it (R5)."""
    _home(tmp_path, monkeypatch)
    (tmp_path / "tilde-secrets.env").write_text(f"{KEY}=fake-tilde\n", encoding="utf-8")
    monkeypatch.setenv("H2T_SECRETS_FILE", "~/tilde-secrets.env")

    with pytest.raises(client.ConfigError):
        client.resolve_secret(KEY)
    assert all(p.name != "tilde-secrets.env" for p in core_secrets.candidate_secret_files())


@pytest.fixture
def provider_file_only(tmp_path, monkeypatch):
    """A home whose ONLY secret sits in a per-provider file of the documented directory (#483)."""
    _home(tmp_path, monkeypatch)
    directory = paths.legacy("secrets.h2t")
    directory.mkdir(parents=True)
    (directory / "exa.env").write_text(f"{KEY}={VALUE}\n", encoding="utf-8")
    yield tmp_path
    import os
    os.environ.pop(KEY, None)


def test_core_reads_a_per_provider_file(provider_file_only):
    core_secrets.load_secrets()
    import os
    assert os.environ.get(KEY) == VALUE


def test_research_reads_a_per_provider_file(provider_file_only):
    assert client.resolve_secret(KEY) == VALUE


def test_setup_sees_a_per_provider_file(provider_file_only):
    assert setup_h2t._secret_present(KEY, provider_file_only) is True
