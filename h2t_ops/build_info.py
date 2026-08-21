"""Which build of h2t-ops is installed (#363).

`uv tool install --reinstall git+...` refetches the branch head regardless of
`__version__`, so the semver says nothing about how current an install is. uv records
the resolved commit in the PEP 610 `direct_url.json` next to the dist metadata; this
module reads it back so `--version` — and through it `setup doctor` — names the build.
"""
from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, distribution
from urllib.parse import urlparse
from urllib.request import url2pathname

import h2t_ops

_DIST_NAME = "h2t-ops"


def _direct_url(dist=None) -> dict:
    """PEP 610 metadata for the installed dist, or {} when it is unavailable."""
    if dist is None:
        try:
            dist = distribution(_DIST_NAME)
        except PackageNotFoundError:
            return {}
    try:
        raw = dist.read_text("direct_url.json")
    except OSError:
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def build_id(dist=None) -> str:
    """'git 03197a8' for a VCS install, 'editable <path>' for a live checkout, '' otherwise.

    Empty is a legitimate answer: a wheel built from a tarball carries no provenance,
    and a missing build id must never be louder than the version itself.
    """
    data = _direct_url(dist)
    commit = (data.get("vcs_info") or {}).get("commit_id") or ""
    if commit:
        return f"git {commit[:7]}"
    if (data.get("dir_info") or {}).get("editable"):
        return f"editable {_local_path(data.get('url') or '')}"
    return ""


def _local_path(url: str) -> str:
    """file:// URL back to a native path — Windows checkouts are in scope."""
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return url
    return url2pathname(parsed.path)


def version_line(dist=None) -> str:
    """The single line `--version` prints; doctor parses its first line."""
    build = build_id(dist)
    return f"h2t-ops {h2t_ops.__version__}" + (f" ({build})" if build else "")
