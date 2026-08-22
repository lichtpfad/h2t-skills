"""Keep the meetgeek test suite out of the user's real data lake.

Four upload tests derived their paths from Path.home() and wrote mp4 stubs and
submission artifacts into ~/.dor/lake, which Syncthing then carried to the other
machine (#386, defect 6). lake_root() makes the location overridable; this
fixture makes the override unconditional, so a future test that forgets still
cannot reach production data.
"""

import pytest


@pytest.fixture(autouse=True)
def _isolated_lake(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("H2T_LAKE_ROOT", str(home / ".dor" / "lake"))
    yield
