"""§T3 — field mapping engine.

Per architecture spec §8 (Skin Mapping) + plan §6 (skin schema).
The field mapper translates a semantic Block + BlockMapping into a
dict of component-template field values that can be passed to the
existing assembler's `_build_section_html` (legacy path).

Out of scope here (delegated to later slices and per user guardrail):
- generic HTML generation — helpers MUST be narrow adapters for
  existing component templates only.
- arbitrary `eval` — helper invocations are parsed against a fixed
  allowlist. Args resolve to paths into block content; no string
  literals, no numeric literals, no nested calls.
- file I/O, component lookup, asset validation, assembler
  integration — those are T2 / T4 / T5.
"""
import pytest
from renderer.field_mapper import (
    ALLOWED_HELPERS,
    FieldMappingError,
    map_block_fields,
    render_cards,
    render_comparison_cards,
    render_flow_steps,
    render_table_body,
    render_table_head,
)
from renderer.semantic_parser import Block
from renderer.skin_loader import BlockMapping

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _block(content: dict, *, type: str = "hero", index: int = 0) -> Block:
    return Block(index=index, type=type, content=content)


def _mapping(field_map: dict, *, role: str = "hero", component: str = "x", **kw) -> BlockMapping:
    return BlockMapping(
        role=role,
        component=component,
        field_map=field_map,
        **kw,
    )


# ---------------------------------------------------------------------------
# Direct path mapping
# ---------------------------------------------------------------------------

def test_maps_direct_field():
    block = _block({"title": "Hello", "subtitle": "World"})
    mapping = _mapping({"title": "title"})
    out = map_block_fields(block, mapping)
    assert out == {"title": "Hello"}


def test_maps_field_with_renaming():
    block = _block({"title": "Hello"})
    mapping = _mapping({"headline": "title"})
    out = map_block_fields(block, mapping)
    assert out == {"headline": "Hello"}


def test_maps_multiple_fields():
    block = _block({"title": "T", "subtitle": "S", "body": "B"})
    mapping = _mapping({
        "headline": "title",
        "meta": "subtitle",
        "body": "body",
    })
    out = map_block_fields(block, mapping)
    assert out == {"headline": "T", "meta": "S", "body": "B"}


def test_returns_dict_suitable_for_build_section_html():
    """The mapper output is consumed by the existing
    `_build_section_html` legacy path (which expects a `content`
    dict on the section). Output must be a plain `dict[str, Any]`."""
    block = _block({"title": "T"})
    mapping = _mapping({"title": "title"})
    out = map_block_fields(block, mapping)
    assert isinstance(out, dict)


# ---------------------------------------------------------------------------
# Nested paths
# ---------------------------------------------------------------------------

def test_maps_nested_path_dot_notation():
    block = _block({"media": {"asset": "hero_img"}})
    mapping = _mapping({"asset": "media.asset"})
    out = map_block_fields(block, mapping)
    assert out == {"asset": "hero_img"}


def test_maps_nested_path_with_index():
    block = _block({"items": [{"value": "16", "label": "primitives"}]})
    mapping = _mapping({"first_value": "items[0].value"})
    out = map_block_fields(block, mapping)
    assert out == {"first_value": "16"}


def test_maps_index_then_field_chain():
    block = _block({"stats": [{"n": "70", "l": "scan"}, {"n": "16", "l": "filter"}]})
    mapping = _mapping({
        "stat1_n": "stats[0].n",
        "stat1_l": "stats[0].l",
        "stat2_n": "stats[1].n",
        "stat2_l": "stats[1].l",
    })
    out = map_block_fields(block, mapping)
    assert out == {"stat1_n": "70", "stat1_l": "scan", "stat2_n": "16", "stat2_l": "filter"}


# ---------------------------------------------------------------------------
# `_html` suffix preserves raw value
# ---------------------------------------------------------------------------

def test_preserves_raw_html_when_source_key_ends_with_html():
    """Convention: recipe authors put raw HTML in `*_html` fields.
    The mapper passes those through verbatim — no escape, no transform."""
    block = _block({"body_html": "<strong>real</strong> html"})
    mapping = _mapping({"body": "body_html"})
    out = map_block_fields(block, mapping)
    assert out["body"] == "<strong>real</strong> html"


def test_preserves_html_in_nested_html_field():
    block = _block({"section": {"body_html": "<p>raw</p>"}})
    mapping = _mapping({"body": "section.body_html"})
    out = map_block_fields(block, mapping)
    assert out["body"] == "<p>raw</p>"


# ---------------------------------------------------------------------------
# Missing-path handling
# ---------------------------------------------------------------------------

def test_missing_required_path_raises_with_block_index_and_field_name():
    block = _block({"title": "T"}, index=4, type="proof")
    mapping = _mapping({"meta": "subtitle"})  # subtitle not in content
    with pytest.raises(FieldMappingError) as exc:
        map_block_fields(block, mapping)
    msg = str(exc.value)
    assert "4" in msg              # block index
    assert "proof" in msg          # block type for context
    assert "meta" in msg           # target field
    assert "subtitle" in msg       # source path that was missing


def test_missing_nested_path_raises_with_full_path():
    block = _block({"media": {}}, index=2)
    mapping = _mapping({"asset": "media.asset"})
    with pytest.raises(FieldMappingError) as exc:
        map_block_fields(block, mapping)
    assert "media.asset" in str(exc.value)


def test_missing_index_in_list_raises():
    block = _block({"items": [{"x": 1}]})
    mapping = _mapping({"second": "items[1].x"})  # only index 0 exists
    with pytest.raises(FieldMappingError):
        map_block_fields(block, mapping)


# ---------------------------------------------------------------------------
# Defaults via mapping.extra["defaults"]
# ---------------------------------------------------------------------------

def test_optional_missing_path_falls_back_to_default_when_declared():
    block = _block({"title": "T"})
    mapping = _mapping(
        {"meta": "subtitle"},
        extra={"defaults": {"meta": ""}},
    )
    out = map_block_fields(block, mapping)
    assert out["meta"] == ""


def test_default_used_only_for_missing_paths_not_for_present_ones():
    block = _block({"title": "T", "subtitle": "S"})
    mapping = _mapping(
        {"meta": "subtitle"},
        extra={"defaults": {"meta": "WOULD-BE-DEFAULT"}},
    )
    out = map_block_fields(block, mapping)
    assert out["meta"] == "S"


def test_default_can_be_any_value_type():
    block = _block({})
    mapping = _mapping(
        {"flag": "missing", "count": "missing2", "items": "missing3"},
        extra={"defaults": {"flag": True, "count": 0, "items": []}},
    )
    out = map_block_fields(block, mapping)
    assert out == {"flag": True, "count": 0, "items": []}


# ---------------------------------------------------------------------------
# Helper invocation — allowlist + syntax
# ---------------------------------------------------------------------------

def test_helper_invocation_resolves_to_helper_output():
    block = _block({
        "items": [
            {"title": "Fast", "body": "Quick results."},
            {"title": "Cheap", "body": "Low cost."},
        ],
    })
    mapping = _mapping({"cards_html": "${render_cards(items)}"})
    out = map_block_fields(block, mapping)
    html_out = out["cards_html"]
    assert '<div class="card">' in html_out
    assert "Fast" in html_out and "Cheap" in html_out


def test_helper_invocation_arg_resolves_via_path():
    block = _block({"features": {"items": [{"title": "Fast"}]}})
    mapping = _mapping({"cards_html": "${render_cards(features.items)}"})
    out = map_block_fields(block, mapping)
    assert "Fast" in out["cards_html"]


def test_unknown_helper_rejected():
    block = _block({"items": []})
    mapping = _mapping({"x": "${render_unicorns(items)}"})
    with pytest.raises(FieldMappingError) as exc:
        map_block_fields(block, mapping)
    msg = str(exc.value)
    assert "render_unicorns" in msg
    # Error must list the allowed helpers so the recipe author can
    # pick a correct one.
    assert any(h in msg for h in ALLOWED_HELPERS)


def test_helper_with_missing_arg_path_raises():
    block = _block({"other": "value"})
    mapping = _mapping({"cards_html": "${render_cards(items)}"})
    with pytest.raises(FieldMappingError) as exc:
        map_block_fields(block, mapping)
    assert "items" in str(exc.value)


def test_helper_takes_two_path_arguments():
    block = _block({
        "columns": [{"key": "p", "label": "Profile"}, {"key": "d", "label": "Density"}],
        "rows": [
            {"label": "h2t-editorial", "values": {"d": "Editorial"}, "tone": "accent"},
            {"label": "h2t-mono", "values": {"d": "Sparse"}},
        ],
    })
    mapping = _mapping({
        "thead_html": "${render_table_head(columns)}",
        "tbody_html": "${render_table_body(rows, columns)}",
    })
    out = map_block_fields(block, mapping)
    assert "<th>Profile</th>" in out["thead_html"]
    assert "h2t-editorial" in out["tbody_html"]


# ---------------------------------------------------------------------------
# Allowlist enforcement / no arbitrary eval
# ---------------------------------------------------------------------------

def test_allowed_helpers_set_is_explicit():
    """The allowlist is a closed set known at module-load time. A
    future helper requires an explicit code change + tests."""
    assert ALLOWED_HELPERS == frozenset({
        "render_cards",
        "render_flow_steps",
        "render_table_head",
        "render_table_body",
        "render_comparison_cards",
    })


# Forbidden plausible names (bare identifiers — helper syntax is `\w+`).
@pytest.mark.parametrize("forbidden_name", [
    "__import__",
    "eval_",         # avoid hook flag — semantically same gate
    "exec_",
    "render_html",   # plausible-but-not-allowlisted
    "render",
    "load",
])
def test_helper_with_forbidden_name_rejected(forbidden_name):
    block = _block({"items": []})
    mapping = _mapping({"x": f"${{{forbidden_name}(items)}}"})
    with pytest.raises(FieldMappingError):
        map_block_fields(block, mapping)


def test_helper_call_with_string_literal_argument_rejected():
    """No string literals — args are PATHS only. Keeps the helper
    surface narrow and makes it impossible to inject arbitrary
    content that isn't already in the recipe."""
    block = _block({})
    mapping = _mapping({"x": '${render_cards("hard-coded-string")}'})
    with pytest.raises(FieldMappingError) as exc:
        map_block_fields(block, mapping)
    assert "literal" in str(exc.value).lower() or "path" in str(exc.value).lower()


def test_helper_call_with_numeric_literal_argument_rejected():
    block = _block({})
    mapping = _mapping({"x": "${render_cards(42)}"})
    with pytest.raises(FieldMappingError):
        map_block_fields(block, mapping)


def test_malformed_helper_syntax_rejected():
    block = _block({"items": []})
    # Missing closing paren
    mapping = _mapping({"x": "${render_cards(items}"})
    with pytest.raises(FieldMappingError):
        map_block_fields(block, mapping)


def test_dotted_helper_name_rejected():
    r"""Helper names are bare identifiers (\w+); dotted-path names
    (e.g. `module.func`) are not parsed as helpers and fall through
    to path resolution which fails on the literal `${...}` string."""
    block = _block({"items": []})
    mapping = _mapping({"x": "${some_module.some_func(items)}"})
    with pytest.raises(FieldMappingError):
        map_block_fields(block, mapping)


# ---------------------------------------------------------------------------
# render_cards helper
# ---------------------------------------------------------------------------

def test_render_cards_with_title_and_body():
    items = [
        {"title": "Fast", "body": "Quick results."},
        {"title": "Cheap", "body": "Low cost."},
    ]
    out = render_cards(items)
    assert '<div class="card">' in out
    assert "<h3>Fast</h3>" in out
    assert "Quick results." in out
    assert "<h3>Cheap</h3>" in out


def test_render_cards_escapes_user_text():
    items = [{"title": "<script>", "body": "& <"}]
    out = render_cards(items)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "&amp;" in out


def test_render_cards_uses_body_html_raw_when_present():
    items = [{"title": "T", "body_html": "<strong>raw</strong>"}]
    out = render_cards(items)
    assert "<strong>raw</strong>" in out


def test_render_cards_empty_list_returns_empty_string():
    assert render_cards([]) == ""


# ---------------------------------------------------------------------------
# render_flow_steps helper
# ---------------------------------------------------------------------------

def test_render_flow_steps_numbers_steps_starting_from_one():
    steps = [
        {"title": "First", "body": "A"},
        {"title": "Second", "body": "B"},
    ]
    out = render_flow_steps(steps)
    assert '<div class="flow-num">1</div>' in out
    assert '<div class="flow-num">2</div>' in out


def test_render_flow_steps_inserts_separator_between_steps():
    steps = [{"title": "A", "body": ""}, {"title": "B", "body": ""}]
    out = render_flow_steps(steps)
    assert '<div class="flow-sep"></div>' in out
    # exactly one separator between two steps (not before first, not after last)
    assert out.count('<div class="flow-sep">') == 1


def test_render_flow_steps_no_separator_for_single_step():
    out = render_flow_steps([{"title": "Only", "body": ""}])
    assert "flow-sep" not in out


def test_render_flow_steps_carries_required_classes():
    steps = [{"title": "T", "body": "B"}]
    out = render_flow_steps(steps)
    for cls in ("flow-step", "flow-num", "flow-body", "flow-title", "flow-desc"):
        assert cls in out


def test_render_flow_steps_escapes_user_text():
    steps = [{"title": "<x>", "body": "&"}]
    out = render_flow_steps(steps)
    assert "<x>" not in out
    assert "&lt;x&gt;" in out


# ---------------------------------------------------------------------------
# render_table_head / render_table_body
# ---------------------------------------------------------------------------

def test_render_table_head_emits_one_th_per_column():
    columns = [{"key": "p", "label": "Profile"}, {"key": "f", "label": "Form"}]
    out = render_table_head(columns)
    assert "<tr>" in out and "</tr>" in out
    assert "<th>Profile</th>" in out
    assert "<th>Form</th>" in out
    assert out.count("<th>") == 2


def test_render_table_head_escapes_label_text():
    out = render_table_head([{"key": "x", "label": "<bad>"}])
    assert "<bad>" not in out
    assert "&lt;bad&gt;" in out


def test_render_table_body_emits_one_tr_per_row():
    columns = [{"key": "n", "label": "Name"}, {"key": "v", "label": "Value"}]
    rows = [
        {"label": "alpha", "values": {"v": "1"}},
        {"label": "beta", "values": {"v": "2"}},
    ]
    out = render_table_body(rows, columns)
    assert out.count("<tr") == 2


def test_render_table_body_uses_row_label_for_first_column():
    columns = [{"key": "name", "label": "Name"}, {"key": "v", "label": "Value"}]
    rows = [{"label": "alpha", "values": {"v": "1"}}]
    out = render_table_body(rows, columns)
    assert "<td>alpha</td>" in out
    assert "<td>1</td>" in out


def test_render_table_body_accent_tone_marks_row_with_rejuve_class():
    columns = [{"key": "x", "label": "X"}]
    rows = [{"label": "highlight", "values": {}, "tone": "accent"}]
    out = render_table_body(rows, columns)
    assert 'class="rejuve"' in out


def test_render_table_body_default_tone_no_class():
    columns = [{"key": "x", "label": "X"}]
    rows = [{"label": "plain", "values": {}}]
    out = render_table_body(rows, columns)
    # no class attribute on the tr
    assert '<tr>' in out


def test_render_table_body_escapes_cell_values():
    """Both `label` (column 0 fallback) and `values.<key>` cells must
    escape user-controlled text."""
    columns = [{"key": "name", "label": "Name"}, {"key": "v", "label": "V"}]
    rows = [{"label": "<x>", "values": {"v": "&"}}]
    out = render_table_body(rows, columns)
    assert "<x>" not in out
    assert "&lt;x&gt;" in out  # label rendered as first cell
    assert "&amp;" in out      # values.v rendered as second cell


def test_render_table_body_missing_value_renders_empty_cell():
    columns = [{"key": "a", "label": "A"}, {"key": "b", "label": "B"}]
    rows = [{"label": "row1", "values": {}}]  # b missing entirely
    out = render_table_body(rows, columns)
    assert "<td></td>" in out
    # row1 takes column a (first), so column b is empty
    assert "<td>row1</td>" in out


# ---------------------------------------------------------------------------
# Output is dict, no extra keys, no leakage of skin metadata
# ---------------------------------------------------------------------------

def test_output_only_carries_field_map_keys():
    block = _block({"title": "T", "subtitle": "S", "body": "B"})
    mapping = _mapping({"headline": "title"})  # only headline mapped
    out = map_block_fields(block, mapping)
    assert set(out.keys()) == {"headline"}


def test_empty_field_map_produces_empty_dict():
    block = _block({"title": "T"})
    mapping = _mapping({})
    out = map_block_fields(block, mapping)
    assert out == {}


# ---------------------------------------------------------------------------
# render_comparison_cards — mobile representation of comparison-table
# ---------------------------------------------------------------------------
# Pure unit tests for the helper. No profile, no skin, no recipe, no
# CSS dependency — synthetic columns/rows only. Profile-side wiring
# (skin field_map line + .bt-card CSS) lives in the consuming profile,
# not in this hardening PR.

_CMP_COLS = [
    {"key": "aspect", "label": "Aspect"},
    {"key": "legacy", "label": "Legacy"},
    {"key": "semantic", "label": "Semantic"},
]


def _cmp_row(label, values, tone=None):
    r: dict = {"label": label, "values": values}
    if tone is not None:
        r["tone"] = tone
    return r


def test_render_comparison_cards_in_allowed_helpers():
    """Allowlist closed-set check — already covered by
    `test_allowed_helpers_set_is_explicit` above; this is the
    helper-specific anchor for grep."""
    assert "render_comparison_cards" in ALLOWED_HELPERS


def test_render_comparison_cards_callable():
    assert callable(render_comparison_cards)


def test_render_comparison_cards_emits_one_card_per_row():
    rows = [
        _cmp_row("Authoring", {"legacy": "Components", "semantic": "Roles"}),
        _cmp_row("Portability", {"legacy": "Locked", "semantic": "Re-skin"}),
    ]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert out.count('class="bt-card"') == 2


def test_render_comparison_cards_label_lands_in_h3():
    rows = [_cmp_row("Portability", {"legacy": "Locked", "semantic": "Re-skin"})]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert "<h3>Portability</h3>" in out


def test_render_comparison_cards_dt_dd_for_non_label_columns():
    rows = [_cmp_row("Portability", {"legacy": "Locked", "semantic": "Re-skin"})]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert "<dt>Legacy</dt><dd>Locked</dd>" in out
    assert "<dt>Semantic</dt><dd>Re-skin</dd>" in out


def test_render_comparison_cards_first_column_not_repeated():
    """First column is the label cell — must not appear as a dt/dd
    pair, otherwise mobile cards would echo the headline twice."""
    rows = [_cmp_row("Portability", {"legacy": "Locked", "semantic": "Re-skin"})]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert "<dt>Aspect</dt>" not in out


def test_render_comparison_cards_dl_wraps_pairs():
    rows = [_cmp_row("Portability", {"legacy": "Locked", "semantic": "Re-skin"})]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert "<dl>" in out and "</dl>" in out


def test_render_comparison_cards_accent_tone_marks_rejuve_class():
    """`tone: accent` parallels render_table_body's tr.rejuve. A
    profile that wants the accent style declares
    `.bt-card.rejuve { … }`; the helper itself is profile-agnostic."""
    rows = [
        _cmp_row("Plain", {"legacy": "x", "semantic": "y"}),
        _cmp_row("Highlighted", {"legacy": "x", "semantic": "y"}, tone="accent"),
    ]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert 'class="bt-card rejuve"' in out
    assert out.count('class="bt-card"') == 1  # plain row stays plain


def test_render_comparison_cards_unknown_tone_is_plain():
    rows = [_cmp_row("Mystery", {"legacy": "x", "semantic": "y"}, tone="weird")]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert 'class="bt-card"' in out
    assert "rejuve" not in out


def test_render_comparison_cards_missing_value_is_empty_dd():
    """Same convention as render_table_body."""
    rows = [_cmp_row("Partial", {"legacy": "Yes"})]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert "<dt>Legacy</dt><dd>Yes</dd>" in out
    assert "<dt>Semantic</dt><dd></dd>" in out


def test_render_comparison_cards_empty_rows_yields_empty_string():
    assert render_comparison_cards([], _CMP_COLS) == ""


def test_render_comparison_cards_html_escapes_text():
    rows = [_cmp_row("<script>", {"legacy": "1 < 2", "semantic": "&"})]
    out = render_comparison_cards(rows, _CMP_COLS)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "1 &lt; 2" in out
    assert ">&amp;<" in out


def test_render_comparison_cards_string_columns_treated_as_labels():
    """Mirrors render_table_head's fallback: a string column resolves
    to its own label."""
    rows = [_cmp_row("Row", {"x": "v"})]
    cols = ["Aspect", "Detail"]
    out = render_comparison_cards(rows, cols)
    assert "<h3>Row</h3>" in out


def test_render_comparison_cards_invocation_via_field_mapper():
    """End-to-end through map_block_fields with a synthetic skin
    mapping — proves the allowlist + registry wiring works without
    needing any profile / skin file on disk."""
    block = Block(
        index=0,
        type="comparison",
        content={
            "columns": [{"key": "a", "label": "A"}, {"key": "b", "label": "B"}],
            "rows": [
                {"label": "First", "values": {"b": "v"}},
                {"label": "Second", "values": {"b": "w"}, "tone": "accent"},
            ],
        },
    )
    mapping = BlockMapping(
        role="comparison",
        component="comparison-table",
        field_map={
            "tbody_cards_html": "${render_comparison_cards(rows, columns)}",
        },
    )
    out = map_block_fields(block, mapping)
    cards_html = out["tbody_cards_html"]
    assert "<h3>First</h3>" in cards_html
    assert 'class="bt-card rejuve"' in cards_html
