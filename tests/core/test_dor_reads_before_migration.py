"""Runtime code reads the 3.x ~/.dor places only on a machine that has not migrated (#581).
Migration code keeps reading them; the vault default is the stated exception."""
import json

import pytest

from h2t_ops.connectors.meetgeek import recovery
from h2t_ops.core import lake, paths, secrets
from h2t_ops.lifecycle.gather import sessions_legacy

KEY = "ZZ_DOR_ONLY_KEY"


@pytest.fixture(autouse=True)
def _home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    monkeypatch.delenv(KEY, raising=False)
    dor = tmp_path / ".dor"
    (dor / "secrets").mkdir(parents=True)
    (dor / "secrets" / "secrets.env").write_text(f"{KEY}=from-dor\n", encoding="utf-8")
    (dor / "secrets.env").write_text("H2T_EVALS_X=old\n", encoding="utf-8")
    (dor / "google-credentials.json").write_text("{}", encoding="utf-8")
    (dor / "lake" / "_cursors").mkdir(parents=True)
    (dor / "lake" / "_cursors" / "granola.json").write_text(json.dumps({"c": 1}), encoding="utf-8")
    (dor / "lake" / "meetgeek" / "uploads-staging").mkdir(parents=True)
    (dor / "sessions" / "m").mkdir(parents=True)


def _migrate(layout):
    f = paths.layout_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(layout, encoding="utf-8")


def _secret():
    return secrets.get(KEY)


def _google():
    return [p.name for p in secrets._legacy_json("google.client")]


def _lake():
    return lake.read_cursor("granola")


def _meetgeek():
    return [d for d in recovery.legacy_journal_dirs() if ".dor" in d.parts]


def _sessions():
    return [r for r in sessions_legacy.roots() if ".dor" in r.parts]


def _evals():
    return secrets.evals_env().get("H2T_EVALS_X")


# reader -> (answer while .dor is read, answer when it is ignored)
READERS = {
    "secrets": (_secret, "from-dor", None),
    "google": (_google, "google-credentials.json", None),
    "lake": (_lake, {"c": 1}, {}),
    "meetgeek": (_meetgeek, True, False),
    "sessions": (_sessions, True, False),
    "evals": (_evals, "old", None),
}


def _norm(name, got):
    if name == "google":
        return "google-credentials.json" if "google-credentials.json" in got else None
    if name in ("meetgeek", "sessions"):
        return bool(got)
    return got


@pytest.mark.parametrize("name", READERS)
def test_dor_is_read_without_the_layout_file(name):
    fn, reads, _ = READERS[name]
    assert _norm(name, fn()) == reads


@pytest.mark.parametrize("name", READERS)
def test_no_dor_read_after_migration(name):
    _migrate('{"layout": 1}')
    fn, _, ignored = READERS[name]
    assert _norm(name, fn()) == ignored


@pytest.mark.parametrize("name", READERS)
def test_future_layout_counts_as_migrated(name):
    _migrate('{"layout": 2}')
    fn, _, ignored = READERS[name]
    assert _norm(name, fn()) == ignored


@pytest.mark.parametrize("name", READERS)
@pytest.mark.parametrize("text", ['{"layout": 0}', "{not json"])
def test_layout_0_and_malformed_keep_reads(name, text):
    _migrate(text)
    fn, reads, _ = READERS[name]
    assert _norm(name, fn()) == reads


def test_legacy_read_gates_only_dor_keys():
    _migrate('{"layout": 1}')
    assert all(paths.legacy_read(k) is None for k in paths.DOR_KEYS)
    assert paths.legacy_read("sessions.h2t") == paths.legacy("sessions.h2t")
    assert paths.legacy_read("telegram") == paths.legacy("telegram")


def test_migration_still_sees_the_dor_secrets_after_layout_1():
    _migrate('{"layout": 1}')
    assert any(name == "dor-secrets" for name, _, _ in secrets.migration_sources())
