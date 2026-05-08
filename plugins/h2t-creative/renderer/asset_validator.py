"""Semantic asset validator (T5 of v0 plan, #118).

Pure schema validation of `recipe.assets[]` declarations per
architecture spec §6 (Asset Model) + §7 (Complex Visuals). Returns
a normalised id-keyed mapping of typed Asset dataclasses.

Out of scope:
- file existence checks for local `src` / `poster` paths (deferred;
  v0 is schema-only per user T5 scope + plan)
- block ↔ asset cross-resolution (handled at adapter time when a
  later slice introduces media-bearing blocks)
- visual-gate exclusion of placeholders (downstream concern)
- assembler integration                                — pure module
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Public errors + closed sets
# ---------------------------------------------------------------------------

class AssetValidationError(ValueError):
    """Raised when an asset declaration fails schema validation.

    Error messages always carry the asset id (when present) and
    list index so the recipe author can locate the offending entry.
    """


# Closed type set — architecture spec §6 + §7.
ALLOWED_ASSET_TYPES: frozenset[str] = frozenset({"image", "video", "scripted"})


# Closed embed-host allowlist — architecture spec §6 last rule:
# "external embeds require an allowlist (youtube, vimeo, or explicit
# local mp4)". Adding a host requires an explicit code change + tests.
ALLOWED_EMBED_HOSTS: frozenset[str] = frozenset({
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "vimeo.com",
    "www.vimeo.com",
    "player.vimeo.com",
})


# ---------------------------------------------------------------------------
# Asset dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Asset:
    """One validated asset declaration.

    All known fields are normalised to typed slots. `extra` carries
    any other keys verbatim for forward-compat.
    """

    id: str
    type: str
    src: str | None = None
    embed_url: str | None = None
    alt: str | None = None
    poster: str | None = None
    role: str | None = None
    required: bool = True
    fallback: str | None = None
    placeholder: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def validate_assets(raw: Any) -> dict[str, Asset]:
    """Validate `recipe.assets` and return id-keyed mapping.

    Accepts `None` or `[]` (returns empty dict). Raises
    `AssetValidationError` with index/id context on any schema
    failure.
    """
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise AssetValidationError(
            f"`assets` must be a list when present, got "
            f"{type(raw).__name__}"
        )

    out: dict[str, Asset] = {}
    for index, entry in enumerate(raw):
        asset = _validate_one_asset(entry, index)
        if asset.id in out:
            raise AssetValidationError(
                f"assets[{index}] declares duplicate id "
                f"{asset.id!r} — ids must be unique within a "
                f"recipe."
            )
        out[asset.id] = asset
    return out


# Reserved keys go to typed slots; everything else lands in `extra`.
_RESERVED_KEYS: frozenset[str] = frozenset({
    "id", "type", "src", "embed_url", "alt", "poster",
    "role", "required", "fallback", "placeholder",
})


def _validate_one_asset(entry: Any, index: int) -> Asset:
    if not isinstance(entry, dict):
        raise AssetValidationError(
            f"assets[{index}] must be a mapping, got "
            f"{type(entry).__name__}"
        )

    # Required at the entry level
    asset_id = entry.get("id")
    if not isinstance(asset_id, str) or not asset_id:
        raise AssetValidationError(
            f"assets[{index}] missing required `id` field (or empty)."
        )

    asset_type = entry.get("type")
    if asset_type is None:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) missing required `type` "
            f"field. Allowed types: {sorted(ALLOWED_ASSET_TYPES)}."
        )
    if asset_type not in ALLOWED_ASSET_TYPES:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) has unsupported type "
            f"{asset_type!r}. Allowed: {sorted(ALLOWED_ASSET_TYPES)}."
        )

    # Per-type validation
    if asset_type == "image":
        _validate_image(entry, index, asset_id)
    elif asset_type == "video":
        _validate_video(entry, index, asset_id)
    elif asset_type == "scripted":
        _validate_scripted(entry, index, asset_id)

    # Build the typed Asset
    extra = {k: v for k, v in entry.items() if k not in _RESERVED_KEYS}
    return Asset(
        id=asset_id,
        type=asset_type,
        src=entry.get("src"),
        embed_url=entry.get("embed_url"),
        alt=entry.get("alt"),
        poster=entry.get("poster"),
        role=entry.get("role"),
        required=bool(entry.get("required", True)),
        fallback=entry.get("fallback"),
        placeholder=bool(entry.get("placeholder", False)),
        extra=extra,
    )


# ---------------------------------------------------------------------------
# Per-type validators
# ---------------------------------------------------------------------------

def _validate_image(entry: dict, index: int, asset_id: str) -> None:
    src = entry.get("src")
    if not isinstance(src, str) or not src:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) is type=image and "
            f"requires `src` (local path under assets/)."
        )
    placeholder = bool(entry.get("placeholder", False))
    _check_local_or_data_uri(src, "src", index, asset_id, placeholder, "image")

    if "alt" not in entry:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) is type=image and "
            f"requires `alt` (architecture spec §6: alt is required "
            f"for images). Use `alt: \"\"` for decorative images."
        )
    alt = entry["alt"]
    if not isinstance(alt, str):
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) `alt` must be a string."
        )


def _validate_video(entry: dict, index: int, asset_id: str) -> None:
    has_src = "src" in entry and entry["src"]
    has_embed = "embed_url" in entry and entry["embed_url"]

    if has_src and has_embed:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) is type=video and "
            f"declares BOTH `src` and `embed_url`. Pick one — videos "
            f"have a single source."
        )
    if not has_src and not has_embed:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) is type=video and "
            f"requires either `src` (local mp4) or `embed_url` "
            f"(youtube/vimeo allowlisted host)."
        )

    placeholder = bool(entry.get("placeholder", False))

    if has_src:
        _check_local_or_data_uri(
            entry["src"], "src", index, asset_id, placeholder, "video"
        )
    else:
        _check_embed_url(entry["embed_url"], index, asset_id)

    poster = entry.get("poster")
    if not isinstance(poster, str) or not poster:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) is type=video and "
            f"requires `poster` (architecture spec §6: video requires "
            f"a poster/fallback)."
        )
    _check_local_or_data_uri(
        poster, "poster", index, asset_id, placeholder, "video"
    )


def _validate_scripted(entry: dict, index: int, asset_id: str) -> None:
    role = entry.get("role")
    if not isinstance(role, str) or not role:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) is type=scripted and "
            f"requires `role` (architecture spec §7 — visual role "
            f"the script implements, e.g. ambient_system, "
            f"product_demo)."
        )

    fallback = entry.get("fallback")
    if not isinstance(fallback, str) or not fallback:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) is type=scripted and "
            f"requires `fallback` (architecture spec §7 — every "
            f"scripted visual must declare a static fallback "
            f"asset id)."
        )

    # Optional `src` (path to JS file). When present, must be local.
    src = entry.get("src")
    if src is not None:
        if not isinstance(src, str) or not src:
            raise AssetValidationError(
                f"assets[{index}] ({asset_id!r}) `src` must be a "
                f"non-empty string when present."
            )
        placeholder = bool(entry.get("placeholder", False))
        _check_local_or_data_uri(src, "src", index, asset_id, placeholder, "scripted")


# ---------------------------------------------------------------------------
# URL / data URI checks
# ---------------------------------------------------------------------------

def _check_local_or_data_uri(
    value: str,
    field_name: str,
    index: int,
    asset_id: str,
    placeholder: bool,
    asset_type: str,
) -> None:
    """Reject external URLs always; reject data URIs unless the
    asset is flagged `placeholder: true`."""
    parsed = urlparse(value)
    scheme = (parsed.scheme or "").lower()

    if scheme in ("http", "https"):
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) {asset_type} `{field_name}` "
            f"is an external URL ({value!r}). External URLs are "
            f"forbidden for {asset_type} assets — host them locally "
            f"under assets/. (Video `embed_url` allows allowlisted "
            f"hosts; for other slots and types, only local paths.)"
        )

    if scheme == "data":
        if not placeholder:
            raise AssetValidationError(
                f"assets[{index}] ({asset_id!r}) {asset_type} "
                f"`{field_name}` is a data URI. Data URIs are allowed "
                f"only when the asset declares `placeholder: true` "
                f"(arch §6: neutral placeholders may be used only for "
                f"structural smoke tests, excluded from visual gates)."
            )

    # Anything else (bare path, relative, file://, etc.) is accepted
    # at the schema level. File-existence checks are deferred.


def _check_embed_url(embed_url: str, index: int, asset_id: str) -> None:
    """Validate that a video's `embed_url` host is in the
    allowlist."""
    parsed = urlparse(embed_url)
    if parsed.scheme not in ("http", "https"):
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) `embed_url` must be an "
            f"http(s) URL, got scheme {parsed.scheme!r}."
        )
    host = (parsed.netloc or "").lower()
    if host not in ALLOWED_EMBED_HOSTS:
        raise AssetValidationError(
            f"assets[{index}] ({asset_id!r}) video `embed_url` host "
            f"{host!r} is not in the embed allowlist. Allowlisted "
            f"hosts: {sorted(ALLOWED_EMBED_HOSTS)}. Adding a host "
            f"requires an explicit code change in "
            f"renderer/asset_validator.py + tests."
        )
