import pytest
import yaml


@pytest.fixture
def social_config(tmp_path, monkeypatch):
    """Points H2T_PATH_ROOT at tmp_path; returns write(accounts=None, rules=None, domains=None)."""
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path))
    cfg = tmp_path / "config"

    def write(accounts=None, rules=None, domains=None):
        for name, doc in (("social/accounts.yaml", accounts), ("social/rules.yaml", rules),
                          ("domains.yaml", domains)):
            if doc is None:
                continue
            f = cfg / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(yaml.safe_dump(doc), encoding="utf-8")
        return cfg

    return write
