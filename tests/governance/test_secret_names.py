"""Every file the package writes into secrets/ matches the naming contract (§4, §7.3)."""
from h2t_ops.core import providers


def test_package_names_match():
    for name in ("notion.env", "exa.env", "google.client.json", "google.token.json",
                 "telegram.session", "telegram.auth-state.json", "h2t-evals.env"):
        m = providers.FILE_NAME.match(name)
        assert m and providers.is_package_provider(m["provider"]), name


def test_exemptions_and_rejections():
    assert providers.EXEMPT.search("other.env")
    assert providers.EXEMPT.search("exa.env.from-dor")
    assert not providers.FILE_NAME.match("google-calendar-mcp.json")
    assert not providers.is_package_provider("calendar")


def test_every_secret_write_uses_a_package_name(tmp_path, monkeypatch):
    """Every writer secrets.py has, for every name it accepts, recorded at store.replace —
    the one call that lands a file in secrets/. A new provider or _JSON entry with a
    non-contract name turns this red without anyone listing it here."""
    import os

    from h2t_ops.core import secrets, store
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_"):
            monkeypatch.delenv(k)
    seen: list[tuple[str, str]] = []
    real = store.replace

    def recording(path, data, *, place, **kw):
        seen.append((place, os.path.basename(path)))
        return real(path, data, place=place, **kw)

    monkeypatch.setattr(store, "replace", recording)
    for provider in sorted(providers.PROVIDERS):
        key = f"{providers.key_prefix(provider)}NAME_CHECK"
        secrets.write_env(provider, {key: f"fake-{provider}-shared"})
        secrets.write_env(provider, {key: f"fake-{provider}-local"}, local=True)
    for name in sorted(secrets._JSON):
        secrets.write_json(name, {"k": f"fake-{name}"})
    secret_writes = [n for place, n in seen if place in ("secrets.shared", "secrets.local")]
    assert len(secret_writes) == 2 * len(providers.PROVIDERS) + len(secrets._JSON)
    for name in secret_writes:
        m = providers.FILE_NAME.match(name)
        assert m and providers.is_package_provider(m["provider"]), name
