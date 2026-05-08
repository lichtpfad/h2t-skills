"""Skin mapping loader (T2 of v0 plan).

Per architecture spec §8 (Skin Mapping). The loader reads
`profiles/<profile>/skins/<format>.yaml` and returns a typed Skin
with per-role BlockMapping. Role names are validated against
`KNOWN_BLOCK_TYPES` from the semantic parser (architecture spec §4).

Out of scope here (delegated to later slices):
- component existence checks (verifying `profile_dir/components/<name>`
  exists) — deferred; loader does not touch profile components.
- field-mapping syntax interpretation — T3 field_mapper.
- default-skin (`h2t-default`) fallback — deferred.
- assembler integration                                 — T4 adapter.

Schema (architecture spec §8):

```yaml
profile: <profile-name>           # optional; defaults to profile_dir.name
blocks:                            # required mapping
  <role>:                          # role MUST be in KNOWN_BLOCK_TYPES
    component: <component-name>    # required
    variant: <variant-name>?       # optional
    field_map:                     # optional, dict[str, Any]
      <component-field>: <recipe-path-or-helper>
    mobile_representation: <name>? # optional
    # any other keys preserved opaquely in BlockMapping.extra
```
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from renderer.semantic_parser import KNOWN_BLOCK_TYPES


# v0 supports landing format only. Future slices may add deck/dashboard.
SUPPORTED_FORMATS: frozenset[str] = frozenset({"landing"})


class SkinLoaderError(ValueError):
    """Raised when a skin file fails validation.

    Error messages always carry enough context (role name, file path)
    for the recipe author to locate the offending entry.
    """


@dataclass(frozen=True)
class BlockMapping:
    """One role → component mapping inside a Skin.

    `role` is one of `KNOWN_BLOCK_TYPES`.

    `component` names a profile component directory (existence is NOT
    verified here; that's a later slice).

    `variant`, `field_map`, `mobile_representation` are optional; absent
    values default to None / empty dict. `extra` carries any other keys
    from the source mapping verbatim for forward-compat with future
    skin-schema additions.
    """

    role: str
    component: str
    variant: str | None = None
    field_map: dict[str, Any] = field(default_factory=dict)
    mobile_representation: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Skin:
    """Parsed skin — typed view over `profiles/<p>/skins/<format>.yaml`.

    `blocks` is a plain dict (Python lacks a frozen-dict primitive), but
    every value is a frozen `BlockMapping`, so individual mappings
    cannot be mutated by accident.
    """

    profile: str
    format: str
    blocks: dict[str, BlockMapping]
    raw: dict[str, Any]


def load_skin(profile_dir: Path, format: str = "landing") -> Skin:
    """Load and validate a skin file from disk.

    Resolves `<profile_dir>/skins/<format>.yaml`, parses YAML, then
    delegates to `parse_skin`. Raises `SkinLoaderError` with a clear
    path on a missing or malformed file.
    """
    if format not in SUPPORTED_FORMATS:
        raise SkinLoaderError(
            f"v0 skin loader supports format='landing' only, "
            f"got format={format!r}. Other formats (deck, dashboard, "
            f"…) are deferred to later slices."
        )

    skin_path = profile_dir / "skins" / f"{format}.yaml"
    if not skin_path.exists():
        raise SkinLoaderError(
            f"skin file not found: {skin_path}. "
            f"Expected at <profile_dir>/skins/{format}.yaml. "
            f"Profile dir: {profile_dir}"
        )

    text = skin_path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SkinLoaderError(
            f"skin file at {skin_path} is not valid YAML: {e}"
        ) from e

    if raw is None:
        raise SkinLoaderError(
            f"skin file at {skin_path} is empty. Expected a YAML "
            f"mapping with 'blocks:' (architecture spec §8)."
        )

    skin = parse_skin(raw, format=format, default_profile=profile_dir.name)
    return skin


def parse_skin(
    raw: Any,
    format: str = "landing",
    default_profile: str | None = None,
) -> Skin:
    """Validate a YAML-loaded skin dict and return a typed Skin.

    `default_profile` is used when the skin YAML omits the optional
    `profile:` field (typically the profile-dir name). When called
    in-memory without a profile_dir, callers may omit this — but
    then the YAML must declare `profile:` explicitly.
    """
    if format not in SUPPORTED_FORMATS:
        raise SkinLoaderError(
            f"v0 skin loader supports format='landing' only, "
            f"got format={format!r}."
        )

    if not isinstance(raw, dict):
        raise SkinLoaderError(
            f"skin top-level must be a YAML mapping, got "
            f"{type(raw).__name__}"
        )

    if "blocks" not in raw:
        raise SkinLoaderError(
            "skin missing required 'blocks:' key (architecture spec §8). "
            "Even an empty mapping (`blocks: {}`) is acceptable."
        )

    raw_blocks = raw["blocks"]
    if not isinstance(raw_blocks, dict):
        raise SkinLoaderError(
            f"skin 'blocks:' must be a mapping (role → component-mapping), "
            f"got {type(raw_blocks).__name__}"
        )

    parsed_blocks: dict[str, BlockMapping] = {}
    for role, mapping in raw_blocks.items():
        parsed_blocks[role] = _parse_block_mapping(role, mapping)

    profile = raw.get("profile") or default_profile
    if not profile:
        raise SkinLoaderError(
            "skin missing 'profile:' field and no default_profile was "
            "provided. Either declare `profile: <name>` in the YAML or "
            "call load_skin(profile_dir, ...) which derives it from "
            "profile_dir.name."
        )
    if not isinstance(profile, str):
        raise SkinLoaderError(
            f"skin 'profile:' must be a string, got {type(profile).__name__}"
        )

    return Skin(
        profile=profile,
        format=format,
        blocks=parsed_blocks,
        raw=raw,
    )


# Reserved keys handled explicitly by the loader. Anything outside this
# set lands in BlockMapping.extra for forward-compat.
_RESERVED_MAPPING_KEYS: frozenset[str] = frozenset({
    "component",
    "variant",
    "field_map",
    "mobile_representation",
})


def _parse_block_mapping(role: str, mapping: Any) -> BlockMapping:
    """Validate one role → mapping entry."""
    if role not in KNOWN_BLOCK_TYPES:
        raise SkinLoaderError(
            f"skin role {role!r} is not a known block type. "
            f"Known types (architecture spec §4 Universal Landing Block "
            f"Roles): {sorted(KNOWN_BLOCK_TYPES)}"
        )

    if not isinstance(mapping, dict):
        raise SkinLoaderError(
            f"skin blocks[{role!r}] must be a mapping, got "
            f"{type(mapping).__name__}"
        )

    if "component" not in mapping:
        raise SkinLoaderError(
            f"skin blocks[{role!r}] missing required 'component:' field. "
            f"Every role mapping must name the profile component that "
            f"renders it."
        )

    component = mapping["component"]
    if not isinstance(component, str) or not component:
        raise SkinLoaderError(
            f"skin blocks[{role!r}].component must be a non-empty string, "
            f"got {component!r}"
        )

    variant = mapping.get("variant")
    if variant is not None and not isinstance(variant, str):
        raise SkinLoaderError(
            f"skin blocks[{role!r}].variant must be a string when "
            f"present, got {type(variant).__name__}"
        )

    field_map_raw = mapping.get("field_map", {})
    if not isinstance(field_map_raw, dict):
        raise SkinLoaderError(
            f"skin blocks[{role!r}].field_map must be a mapping when "
            f"present, got {type(field_map_raw).__name__}"
        )

    mobile_rep = mapping.get("mobile_representation")
    if mobile_rep is not None and not isinstance(mobile_rep, str):
        raise SkinLoaderError(
            f"skin blocks[{role!r}].mobile_representation must be a "
            f"string when present, got {type(mobile_rep).__name__}"
        )

    extra = {k: v for k, v in mapping.items() if k not in _RESERVED_MAPPING_KEYS}

    return BlockMapping(
        role=role,
        component=component,
        variant=variant,
        field_map=dict(field_map_raw),
        mobile_representation=mobile_rep,
        extra=extra,
    )
