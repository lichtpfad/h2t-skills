"""Secret key NAMES come from config (defaults.yaml, overridable in accounts.yaml), not code."""
import pytest

from h2t_ops.connectors.social import config, journal
from h2t_ops.core.errors import ConfigError

ACCOUNT = {"network": "instagram", "handle": "acme", "remote_id": "ig_111", "page_id": "page_222",
           "token_key": "META_H2T_SOCIAL_USER_TOKEN", "project": None, "enabled": True}
TOKEN = "EAA" + "b" * 30
SECRET = "EAA" + "x" * 10 + "-fake-value"


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def test_secret_key_defaults(social_config):
    social_config()   # no accounts.yaml: discover runs before the file exists
    assert config.secret_key("meta_user_token") == "META_H2T_SOCIAL_USER_TOKEN"
    assert config.secret_key("meta_app_secret") == "META_H2T_SOCIAL_APP_SECRET"
    assert config.secret_key("threads_token_prefix") == "THREADS_TOKEN_"


def test_secret_key_override_wins(social_config):
    social_config(accounts={"secrets": {"meta_user_token": "META_OTHER_USER"}, "accounts": [ACCOUNT]})
    assert config.secret_key("meta_user_token") == "META_OTHER_USER"
    assert config.secret_key("meta_app_secret") == "META_H2T_SOCIAL_APP_SECRET"
    assert config.secret_key("meta_user_token", overrides=False) == "META_H2T_SOCIAL_USER_TOKEN"
    config.load_accounts()


@pytest.mark.parametrize("secrets_doc", [
    {"meta_user_token": ""}, {"meta_user_token": 5}, {"meta_user_token": "THREADS_TOKEN_X"},
    {"threads_token_prefix": "META_X_"}, {"nope": "META_X"}, "bad",
])
def test_bad_secret_override_is_config_error(social_config, secrets_doc):
    social_config(accounts={"secrets": secrets_doc, "accounts": [ACCOUNT]})
    with pytest.raises(ConfigError):
        config.secret_key("meta_user_token")
    with pytest.raises(ConfigError):
        config.load_accounts()


def test_token_value_in_secrets_block_is_refused(social_config):
    social_config(accounts={"secrets": {"meta_user_token": TOKEN}, "accounts": [ACCOUNT]})
    with pytest.raises(ConfigError) as e:
        config.secret_key("meta_user_token")
    assert TOKEN not in str(e.value)


@pytest.mark.parametrize("name", ["META_OTHER_USER", "META_OTHER_APP"])
def test_configured_meta_keys_are_redacted_in_the_journal(social_data, social_config, monkeypatch, name):
    social_config(accounts={"secrets": {"meta_user_token": "META_OTHER_USER",
                                        "meta_app_secret": "META_OTHER_APP"}, "accounts": []})
    monkeypatch.setattr("h2t_ops.core.secrets.get", lambda key: SECRET if key == name else None)
    run = journal.new_run("insights", "manual")
    with pytest.raises(journal.SecretInRecord):
        journal.record(run, 6, note=f"leak {SECRET}")


def test_default_meta_keys_still_redacted_when_accounts_file_is_invalid(social_data, social_config, monkeypatch):
    social_config(accounts={"secrets": {"meta_user_token": ""}, "accounts": []})
    monkeypatch.setattr("h2t_ops.core.secrets.get",
                        lambda key: SECRET if key == "META_H2T_SOCIAL_APP_SECRET" else None)
    run = journal.new_run("insights", "manual")
    with pytest.raises(journal.SecretInRecord):
        journal.record(run, 6, note=f"leak {SECRET}")


def test_meta_client_default_key_comes_from_config(social_config):
    social_config(accounts={"secrets": {"meta_user_token": "META_OTHER_USER"}, "accounts": []})
    from h2t_ops.connectors.social.meta import MetaClient
    assert MetaClient()._key == "META_OTHER_USER"
