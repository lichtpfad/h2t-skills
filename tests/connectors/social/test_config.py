import pytest

from h2t_ops.connectors.social import config
from h2t_ops.core.errors import ConfigError, exit_code_for

ACCOUNT = {"network": "instagram", "handle": "acme", "remote_id": "ig_111", "page_id": "page_222",
           "token_key": "META_USER_TOKEN", "project": None, "enabled": True}
RULE = {"id": "r1", "process": "insights", "action": "read", "account": "*", "kind": "*",
        "verdict": "auto", "added": "2026-11-19", "origin": "author said do it yourself"}


def test_accounts_load(social_config):
    social_config(accounts={"accounts": [ACCOUNT]})
    [a] = config.load_accounts()
    assert (a.id, a.network, a.page_id, a.enabled) == ("instagram:acme", "instagram", "page_222", True)


def test_missing_accounts_file_is_config_error(social_config):
    social_config()
    with pytest.raises(ConfigError) as e:
        config.load_accounts()
    assert exit_code_for(e.value) == 3
    assert "h2t-ops social accounts discover" in e.value.hint


@pytest.mark.parametrize("extra", [
    {"token": "x"}, {"access_token": "x"}, {"handle": "EAA" + "a" * 30},
])
def test_inline_token_is_refused(social_config, extra):
    social_config(accounts={"accounts": [{**ACCOUNT, **extra}]})
    with pytest.raises(ConfigError):
        config.load_accounts()


def test_token_key_must_have_provider_prefix(social_config):
    social_config(accounts={"accounts": [{**ACCOUNT, "token_key": "FOO"}]})
    with pytest.raises(ConfigError, match="instagram:acme"):
        config.load_accounts()


def test_unknown_project_refused_when_domains_exist(social_config):
    domains = {"domains": {"art": {"projects": [{"id": "proj_a"}]}}}
    social_config(accounts={"accounts": [{**ACCOUNT, "project": "nope"}]}, domains=domains)
    with pytest.raises(ConfigError, match="nope"):
        config.load_accounts()
    social_config(accounts={"accounts": [{**ACCOUNT, "project": "proj_a"}]})
    assert config.load_accounts()[0].project == "proj_a"
    social_config(accounts={"accounts": [{**ACCOUNT, "project": "art"}]})
    assert config.load_accounts()[0].project == "art"


def test_project_unchecked_without_domains(social_config):
    social_config(accounts={"accounts": [{**ACCOUNT, "project": "anything"}]})
    assert config.load_accounts()[0].project == "anything"


def test_rules_missing_file_is_empty(social_config):
    social_config()
    assert config.load_rules() == []


def test_rules_load_with_defaults(social_config):
    social_config(rules={"rules": [{k: v for k, v in RULE.items() if k not in ("account", "kind")}]})
    [r] = config.load_rules()
    assert (r.account, r.kind, r.verdict) == ("*", "*", "auto")


def test_rule_without_origin_is_refused(social_config):
    social_config(rules={"rules": [{**RULE, "origin": ""}]})
    with pytest.raises(ConfigError, match="r1"):
        config.load_rules()


def test_rule_verdict_must_be_known(social_config):
    social_config(rules={"rules": [{**RULE, "verdict": "maybe"}]})
    with pytest.raises(ConfigError, match="r1"):
        config.load_rules()


def test_api_base_default_and_override(social_config):
    social_config()
    assert config.api_base("meta") == "https://graph.facebook.com/v27.0"
    assert config.api_base("threads") == "https://graph.threads.net/v1.0"
    social_config(accounts={"api": {"meta_graph": "https://example.test/v1"}, "accounts": [ACCOUNT]})
    assert config.api_base("meta") == "https://example.test/v1"
    assert config.api_base("instagram") == "https://example.test/v1"
    assert config.api_base("threads") == "https://graph.threads.net/v1.0"


@pytest.mark.parametrize("network,url", [
    ("meta", "https://graph.facebook.com/v27.0"), ("instagram", "https://graph.facebook.com/v27.0"),
    ("facebook", "https://graph.facebook.com/v27.0"), ("threads", "https://graph.threads.net/v1.0"),
])
def test_api_base_per_network(social_config, network, url):
    social_config()
    assert config.api_base(network) == url


def test_api_base_unknown_network(social_config):
    social_config()
    with pytest.raises(ConfigError):
        config.api_base("tiktok")


@pytest.mark.parametrize("api", ["bad", ["x"], {"meta_graph": 5}, {"meta_graph": ""}])
def test_api_must_be_mapping_of_strings(social_config, api):
    social_config(accounts={"api": api, "accounts": [ACCOUNT]})
    with pytest.raises(ConfigError):
        config.api_base("meta")


@pytest.mark.parametrize("enabled", ["false", "no", 0, None])
def test_enabled_must_be_boolean(social_config, enabled):
    social_config(accounts={"accounts": [{**ACCOUNT, "enabled": enabled}]})
    with pytest.raises(ConfigError, match="instagram:acme"):
        config.load_accounts()


def test_enabled_false_is_kept(social_config):
    social_config(accounts={"accounts": [{**ACCOUNT, "enabled": False}]})
    assert config.load_accounts()[0].enabled is False


TOKEN = "EAA" + "b" * 30


@pytest.mark.parametrize("where", ["nested_value", "nested_key", "list", "api"])
def test_token_anywhere_in_accounts_file_is_refused(social_config, where):
    acc = dict(ACCOUNT)
    doc = {"accounts": [acc]}
    if where == "nested_value":
        acc["extra"] = {"deep": TOKEN}
    elif where == "nested_key":
        acc["extra"] = [{"access_token": "x"}]
    elif where == "list":
        acc["tags"] = ["ok", TOKEN]
    else:
        doc["api"] = {"meta_graph": "https://x.test", "note": TOKEN}
    social_config(accounts=doc)
    with pytest.raises(ConfigError) as e:
        config.load_accounts()
    assert TOKEN not in str(e.value)
    if where != "api":
        assert "instagram:acme" in str(e.value)


@pytest.mark.parametrize("field", ["origin", "note", "account"])
def test_token_in_rules_is_refused(social_config, field):
    social_config(rules={"rules": [{**RULE, field: TOKEN}]})
    with pytest.raises(ConfigError, match="r1"):
        config.load_rules()
