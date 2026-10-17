"""The target release (spec §7.3.1): the h2t-core pointer on main, then that tag's release.json.

Nothing here writes. A failure to reach GitHub stops `h2t-setup` before it has touched the
disk, so the install it was asked to repair is the install it leaves behind.

The frozen contract every executor of every version must read (§7.3.2): the fields
`format`, `version` and `bootstrap` of release.json, the tag taken from the `ref` of the
h2t-core entry, and the word order of a re-launch: the mode is the first word after
`bootstrap`, the original arguments follow it.
"""
from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable

from h2t_ops.core.errors import ConfigError, H2TError, NetworkError

RAW = "https://raw.githubusercontent.com/lichtpfad/h2t-skills"
MARKETPLACE_URL = f"{RAW}/main/.claude-plugin/marketplace.json"
# The shorthand `owner/repo` goes to SSH and fails (probe 2026-10-16, §7.1).
REPO_URL = "https://github.com/lichtpfad/h2t-skills.git"
FORMAT = 1
REQUIRED = ("version", "python", "wheel", "constraints", "bootstrap")
TIMEOUT = 30

Fetch = Callable[[str], bytes]


def release_url(ref: str) -> str:
    return f"{RAW}/{ref}/release.json"


# What a failed read means. A 4xx is an answer, not an outage: the pointer names a file
# GitHub does not serve, and retrying will not change it. Everything else is the network.
_READ_FAILURES = (OSError, ValueError, http.client.HTTPException)


def _failure(url: str, exc: BaseException) -> H2TError:
    if isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500:
        return ConfigError(f"{url} answered HTTP {exc.code}",
                           hint=f"the release pointer names a file GitHub does not serve: {url}")
    return NetworkError(f"cannot read {url}: {exc}",
                        hint="check the network and run the same command again")


def urllib_fetch(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return response.read()
    except _READ_FAILURES as exc:  # HTTPError before URLError: both are OSError
        raise _failure(url, exc) from exc


def _get_json(fetch: Fetch, url: str) -> object:
    try:
        body = fetch(url)
    except H2TError:
        raise
    except _READ_FAILURES as exc:
        raise _failure(url, exc) from exc
    try:
        return json.loads(body)
    except ValueError as exc:
        raise ConfigError(f"{url} is not JSON: {exc}") from exc


def _core_ref(marketplace: object) -> str:
    plugins = marketplace.get("plugins") if isinstance(marketplace, dict) else None
    entry = next((p for p in plugins or [] if isinstance(p, dict) and p.get("name") == "h2t-core"),
                 None)
    src = entry.get("source") if entry else None
    if not (isinstance(src, dict) and src.get("source") == "git-subdir"
            and src.get("url") == REPO_URL and isinstance(src.get("ref"), str) and src["ref"]):
        raise ConfigError(
            f"the h2t-core entry of {MARKETPLACE_URL} is not pinned to a release: {src!r}",
            hint="main has no released pointer yet; from a checkout use `h2t-setup dev-sync`")
    return src["ref"]


def render(argv: object) -> str | None:
    if isinstance(argv, list) and argv and all(isinstance(w, str) for w in argv):
        return " ".join(w if w and " " not in w else f'"{w}"' for w in argv)
    return None


def _validate(release: object, url: str) -> dict:
    if not isinstance(release, dict):
        raise ConfigError(f"{url} is not a release manifest")
    if release.get("format") != FORMAT:
        bootstrap = render(release.get("bootstrap"))
        raise ConfigError(
            f"{url} has format {release.get('format')!r}; this h2t-setup reads format {FORMAT}. "
            "A newer h2t-setup is needed.",
            hint=f"{bootstrap} sync" if bootstrap else None)
    missing = [k for k in REQUIRED if not release.get(k)]
    if missing:
        raise ConfigError(f"{url} lacks {', '.join(missing)}")
    if render(release["bootstrap"]) is None:
        raise ConfigError(f"{url}: bootstrap is not a list of words")
    return release


def current(fetch: Fetch | None = None) -> dict:
    """The release main points at: its release.json, plus the `ref` it was read from."""
    fetch = fetch or urllib_fetch
    ref = _core_ref(_get_json(fetch, MARKETPLACE_URL))
    url = release_url(ref)
    return dict(_validate(_get_json(fetch, url), url), ref=ref)
