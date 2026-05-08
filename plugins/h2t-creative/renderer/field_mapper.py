"""Field mapping engine (T3 of v0 plan).

Translates a semantic Block + skin BlockMapping into a dict of
component-template field values that the existing assembler's
`_build_section_html` can consume.

Design boundaries (per user guardrail):

- Helpers are NARROW adapters for known component templates only.
  `render_cards`, `render_flow_steps`, `render_table_head`,
  `render_table_body` produce the exact HTML shape that the
  card-grid / flow / comparison-table component templates expect.
  Helpers are NOT a general-purpose HTML generator.

- No arbitrary `eval`. Helper invocations use the syntax
  `${helper_name(arg1, arg2)}` where:
    - `helper_name` MUST be in `ALLOWED_HELPERS`
    - each argument MUST be a path into block content (no string
      literals, no numeric literals, no nested calls)
  Anything that doesn't match this exact shape is rejected at
  parse time.

- No file I/O, no component lookup, no Jinja, no interpolation.
  This module is a pure dict-in/dict-out transform.
"""
from __future__ import annotations

import html
import re
from typing import Any, Callable

from renderer.semantic_parser import Block
from renderer.skin_loader import BlockMapping


# ---------------------------------------------------------------------------
# Public errors + helper allowlist
# ---------------------------------------------------------------------------

class FieldMappingError(ValueError):
    """Raised when a field-map source cannot be resolved against block
    content, when a helper invocation is invalid, or when an argument
    fails the path-only contract."""


# Closed set known at module-load time. A new helper requires an
# explicit code change + tests.
ALLOWED_HELPERS: frozenset[str] = frozenset({
    "render_cards",
    "render_flow_steps",
    "render_table_head",
    "render_table_body",
    "render_comparison_cards",
})


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def map_block_fields(block: Block, mapping: BlockMapping) -> dict[str, Any]:
    """Apply the skin's field_map to the block's content.

    Returns a plain dict suitable for passing to
    `_build_section_html({..., "content": <this dict>})`. Defaults
    declared in `mapping.extra["defaults"]` fill in for missing
    paths; unmissing-and-undefaulted paths raise
    `FieldMappingError`.
    """
    defaults = (mapping.extra or {}).get("defaults") or {}
    if not isinstance(defaults, dict):
        raise FieldMappingError(
            f"blocks[{block.index}] ({block.type}): mapping.extra "
            f"['defaults'] must be a mapping when present, got "
            f"{type(defaults).__name__}"
        )

    out: dict[str, Any] = {}
    for component_field, source_expr in mapping.field_map.items():
        try:
            out[component_field] = _resolve_expression(
                source_expr, block.content
            )
        except _MissingPath as e:
            if component_field in defaults:
                out[component_field] = defaults[component_field]
                continue
            raise FieldMappingError(
                f"blocks[{block.index}] ({block.type}): required "
                f"field {component_field!r} not found at path "
                f"{e.path!r}. Either provide the path in recipe "
                f"content or declare a default in skin "
                f"`mapping.extra.defaults.{component_field}`."
            ) from None
    return out


# ---------------------------------------------------------------------------
# Expression resolution
# ---------------------------------------------------------------------------

class _MissingPath(Exception):
    """Internal — raised when a path cannot be resolved. Wrapped into
    `FieldMappingError` at the public boundary so that the optional
    default mechanism can intercept first."""

    def __init__(self, path: str):
        super().__init__(path)
        self.path = path


_HELPER_CALL_RE = re.compile(
    r"^\$\{(?P<name>\w+)\((?P<args>.*)\)\}$"
)
_HELPER_INTRO_RE = re.compile(r"^\$\{")  # any string starting with `${`
_PATH_TOKEN_RE = re.compile(r"^[A-Za-z_][\w\-]*(\[\d+\])?(\.[A-Za-z_][\w\-]*(\[\d+\])?)*$")


def _resolve_expression(expr: Any, content: dict) -> Any:
    """Dispatch between helper invocation and path resolution."""
    if not isinstance(expr, str):
        raise FieldMappingError(
            f"field_map values must be strings, got "
            f"{type(expr).__name__} ({expr!r})"
        )

    if _HELPER_INTRO_RE.match(expr):
        return _resolve_helper(expr, content)
    return _resolve_path(expr, content)


def _resolve_helper(expr: str, content: dict) -> Any:
    """Parse and execute a `${helper_name(arg1, arg2)}` invocation."""
    match = _HELPER_CALL_RE.match(expr)
    if not match:
        raise FieldMappingError(
            f"helper invocation {expr!r} is malformed. Expected "
            f"shape `${{helper_name(arg1, arg2)}}` with bare "
            f"identifier helper name and path-only arguments."
        )

    helper_name = match.group("name")
    args_blob = match.group("args").strip()

    if helper_name not in ALLOWED_HELPERS:
        raise FieldMappingError(
            f"helper {helper_name!r} is not in the allowlist. "
            f"Known helpers: {sorted(ALLOWED_HELPERS)}. New helpers "
            f"require an explicit code change in field_mapper.py + "
            f"tests."
        )

    # Parse + resolve args
    if args_blob == "":
        resolved_args: list[Any] = []
    else:
        # Top-level comma split. Helper args are simple paths so we
        # don't need to handle nested parens / brackets beyond [N].
        raw_args = [a.strip() for a in args_blob.split(",")]
        resolved_args = [_resolve_helper_arg(a, content) for a in raw_args]

    helper_fn = _HELPERS[helper_name]
    return helper_fn(*resolved_args)


def _resolve_helper_arg(arg: str, content: dict) -> Any:
    """Resolve one helper argument as a path. String / numeric
    literals are rejected here per user guardrail (no arbitrary eval)."""
    if not arg:
        raise FieldMappingError("helper argument is empty")

    # Reject string literals (single or double quoted).
    if (arg.startswith('"') and arg.endswith('"')) or (
        arg.startswith("'") and arg.endswith("'")
    ):
        raise FieldMappingError(
            f"helper argument {arg!r} is a string literal — only "
            f"paths into block content are allowed (no literals, no "
            f"eval). Move the literal value into recipe content and "
            f"reference its path."
        )

    # Reject numeric literals.
    try:
        float(arg)
        raise FieldMappingError(
            f"helper argument {arg!r} is a numeric literal — only "
            f"paths into block content are allowed."
        )
    except ValueError:
        pass

    # Validate it looks like a path token
    if not _PATH_TOKEN_RE.match(arg):
        raise FieldMappingError(
            f"helper argument {arg!r} is not a valid path. Expected "
            f"shape `name`, `name.sub`, `name[0]`, `name[0].sub`, "
            f"etc."
        )

    try:
        return _resolve_path(arg, content)
    except _MissingPath as e:
        raise FieldMappingError(
            f"helper argument path {e.path!r} not found in block "
            f"content"
        ) from None


_PATH_SEGMENT_RE = re.compile(r"^([A-Za-z_][\w\-]*)(\[(\d+)\])?$")


def _resolve_path(path: str, content: Any) -> Any:
    """Walk a dotted+indexed path against content. Raises _MissingPath
    on any missing segment so the caller can decide between default
    and error."""
    if not isinstance(path, str) or not path:
        raise _MissingPath(repr(path))

    cursor: Any = content
    for segment in path.split("."):
        m = _PATH_SEGMENT_RE.match(segment)
        if not m:
            raise FieldMappingError(
                f"path segment {segment!r} (in {path!r}) is malformed. "
                f"Allowed: name, name[N], name.sub, name[N].sub."
            )
        key = m.group(1)
        idx_str = m.group(3)

        if not isinstance(cursor, dict) or key not in cursor:
            raise _MissingPath(path)
        cursor = cursor[key]

        if idx_str is not None:
            idx = int(idx_str)
            if not isinstance(cursor, list) or idx >= len(cursor):
                raise _MissingPath(path)
            cursor = cursor[idx]

    return cursor


# ---------------------------------------------------------------------------
# Helpers — narrow adapters for existing component templates
# ---------------------------------------------------------------------------
#
# Each helper produces the EXACT HTML fragment that the matching
# component template inlines via `{{ field_html | safe }}`.
#
# Helpers escape user-controlled text via html.escape to prevent
# injection through recipe content. When a recipe author wants
# raw HTML in a slot, the convention is `<slot>_html: "<raw>"` and
# the helper falls back to that.


def render_cards(items: list[dict]) -> str:
    """Render a list of `{title, body}` items as `.card` HTML
    fragments. Matches the card-grid component template's
    `{{ cards_html | safe }}` slot."""
    if not items:
        return ""
    pieces: list[str] = []
    for item in items:
        title = html.escape(str(item.get("title", "")))
        if "body_html" in item:
            body = str(item["body_html"])
        else:
            body = html.escape(str(item.get("body", "")))
        pieces.append(
            f'<div class="card"><h3>{title}</h3><p>{body}</p></div>'
        )
    return "\n".join(pieces)


def render_flow_steps(steps: list[dict]) -> str:
    """Render a list of `{title, body}` steps as `.flow-step` +
    `.flow-sep` fragments. Matches the flow component template's
    `{{ steps_html | safe }}` slot. Steps are auto-numbered from 1."""
    if not steps:
        return ""
    pieces: list[str] = []
    for i, step in enumerate(steps, start=1):
        if i > 1:
            pieces.append('<div class="flow-sep"></div>')
        title = html.escape(str(step.get("title", "")))
        if "body_html" in step:
            body = str(step["body_html"])
        else:
            body = html.escape(str(step.get("body", "")))
        pieces.append(
            f'<div class="flow-step">'
            f'<div class="flow-num">{i}</div>'
            f'<div class="flow-body">'
            f'<div class="flow-title">{title}</div>'
            f'<div class="flow-desc">{body}</div>'
            f'</div>'
            f'</div>'
        )
    return "\n".join(pieces)


def render_table_head(columns: list[dict]) -> str:
    """Render `<tr><th>...</th></tr>` from a list of `{key, label}`
    column dicts. Matches the comparison-table component's
    `{{ thead_html | safe }}` slot."""
    cells: list[str] = []
    for col in columns:
        if isinstance(col, dict):
            label = str(col.get("label", col.get("key", "")))
        else:
            label = str(col)
        cells.append(f"<th>{html.escape(label)}</th>")
    return f"<tr>{''.join(cells)}</tr>"


# Tone → tr class. Limited to the System B-Landing comparison-table
# vocabulary. Unknown tones produce no class attribute (renders as
# default tr).
_TONE_TR_CLASS: dict[str, str] = {
    "accent": "rejuve",
}


def render_table_body(rows: list[dict], columns: list[dict]) -> str:
    """Render `<tr>...<td>...</td>...</tr>` rows. Matches the
    comparison-table component's `{{ tbody_html | safe }}` slot.

    Row schema (architecture spec §5):
        {label?: str, values: {col_key: value}, tone?: str}

    Columns provide the key-ordering for the row.values lookup. The
    first column receives `row.label` if present (otherwise the
    matching `row.values[columns[0].key]`).
    """
    if not rows:
        return ""
    pieces: list[str] = []
    for row in rows:
        tone = row.get("tone", "default") if isinstance(row, dict) else "default"
        cls_attr = ""
        if tone in _TONE_TR_CLASS:
            cls_attr = f' class="{_TONE_TR_CLASS[tone]}"'

        cells: list[str] = []
        values = row.get("values", {}) if isinstance(row, dict) else {}
        label = row.get("label") if isinstance(row, dict) else None

        for i, col in enumerate(columns):
            if isinstance(col, dict):
                key = col.get("key")
            else:
                key = None
            if i == 0 and label is not None:
                cell_value = str(label)
            elif key and isinstance(values, dict) and key in values:
                cell_value = str(values[key])
            else:
                cell_value = ""
            cells.append(f"<td>{html.escape(cell_value)}</td>")
        pieces.append(f"<tr{cls_attr}>{''.join(cells)}</tr>")
    return "\n".join(pieces)


def render_comparison_cards(rows: list[dict], columns: list[dict]) -> str:
    """Mobile representation of `comparison-table`.

    Mirrors `render_table_body` for input shape, but emits the
    `.bt-card` HTML — the dual-representation contract from rhythm
    spec §A.4 declares that a `comparison-table` block with
    `mobile_representation: cards` should render stacked cards below
    the table's mobile breakpoint instead of going invisible:

        <div class="bt-card[ rejuve]">
          <h3>{label}</h3>
          <dl>
            <dt>{col[1].label}</dt><dd>{values[col[1].key]}</dd>
            <dt>{col[2].label}</dt><dd>{values[col[2].key]}</dd>
            ...
          </dl>
        </div>

    First column is treated as the label cell — it lands in the `<h3>`
    and is NOT echoed as a `<dt>/<dd>` pair. Remaining columns become
    one `<dt>/<dd>` pair each. Missing values render as empty `<dd>`,
    matching `render_table_body`'s behaviour for the desktop tr.

    `tone: accent` adds the `rejuve` class (same vocabulary as
    `_TONE_TR_CLASS`), so a `.bt-card.rejuve` style applies in any
    profile that defines one.
    """
    if not rows:
        return ""
    pieces: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tone = row.get("tone", "default")
        cls = "bt-card"
        if tone in _TONE_TR_CLASS:
            cls = f"bt-card {_TONE_TR_CLASS[tone]}"

        label = row.get("label", "")
        values = row.get("values", {}) if isinstance(row.get("values"), dict) else {}

        dl_pairs: list[str] = []
        for i, col in enumerate(columns):
            if i == 0:
                continue  # label cell goes into <h3> instead
            if isinstance(col, dict):
                col_label = str(col.get("label", col.get("key", "")))
                col_key = col.get("key")
            else:
                col_label = str(col)
                col_key = None
            cell_value = ""
            if col_key and col_key in values:
                cell_value = str(values[col_key])
            dl_pairs.append(
                f"<dt>{html.escape(col_label)}</dt>"
                f"<dd>{html.escape(cell_value)}</dd>"
            )
        dl = f"<dl>{''.join(dl_pairs)}</dl>" if dl_pairs else ""
        pieces.append(
            f'<div class="{cls}">'
            f'<h3>{html.escape(str(label))}</h3>'
            f'{dl}'
            f'</div>'
        )
    return "\n".join(pieces)


# Helper registry — keyed by name. Module-private; consumers go
# through `map_block_fields` which validates against ALLOWED_HELPERS.
_HELPERS: dict[str, Callable[..., Any]] = {
    "render_cards": render_cards,
    "render_flow_steps": render_flow_steps,
    "render_table_head": render_table_head,
    "render_table_body": render_table_body,
    "render_comparison_cards": render_comparison_cards,
}

# Sanity check at module load: keys of _HELPERS must equal ALLOWED_HELPERS.
assert set(_HELPERS) == set(ALLOWED_HELPERS), (
    "_HELPERS registry must match ALLOWED_HELPERS exactly"
)
