from importlib import resources

import yaml

from h2t_ops.core import providers


def test_social_providers_and_prefixes():
    assert providers.CONNECTOR_PROVIDERS["social"] == ("meta", "threads")
    assert providers.provider_of_key("META_USER_TOKEN") == "meta"
    assert providers.provider_of_key("THREADS_TOKEN_ACME") == "threads"


def test_defaults_yaml_ships_with_the_package():
    text = (resources.files("h2t_ops.resources") / "social" / "defaults.yaml").read_text(encoding="utf-8")
    api = yaml.safe_load(text)["api"]
    assert api["meta_graph"] == "https://graph.facebook.com/v27.0"
    assert api["threads_graph"] == "https://graph.threads.net/v1.0"
