"""§T5 — semantic asset validator (#118).

Per architecture spec §6 (Asset Model) + §7 (Complex Visuals).
The validator takes a list of asset declarations from
`recipe.assets` and returns a normalised id-keyed mapping. Pure
schema validation — no file I/O, no rendering, no integration
with the assembler in v0.

Scope rules:
- image / video / scripted asset types only
- per-type required fields enforced
- duplicate ids rejected
- external URLs rejected for image/script (arch §6 last rule)
- video `embed_url` allowed only with allowlisted host (youtube,
  vimeo) — arch §6 last rule
- data URIs rejected unless asset declares `placeholder: true`
  (arch §6 "neutral placeholders may be used only for structural
  smoke tests")
- `required: false` flag preserved but does NOT relax schema
  (downstream block-resolution decides what to do with missing
  optionals)

Out of scope (per user T5 scope + plan §4 T5 schema-only):
- file existence checks for local `src` / `poster` paths
- block ↔ asset cross-resolution (handled at adapter time)
- visual gate exclusion of placeholders (downstream concern)
- assembler integration
"""
import pytest
from renderer.asset_validator import (
    ALLOWED_ASSET_TYPES,
    ALLOWED_EMBED_HOSTS,
    Asset,
    AssetValidationError,
    validate_assets,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _img(**kw) -> dict:
    base = {"id": "img1", "type": "image", "src": "assets/img1.jpg", "alt": "img"}
    base.update(kw)
    return base


def _video(**kw) -> dict:
    base = {
        "id": "vid1",
        "type": "video",
        "src": "assets/vid1.mp4",
        "poster": "assets/vid1-poster.jpg",
    }
    base.update(kw)
    return base


def _scripted(**kw) -> dict:
    base = {
        "id": "scr1",
        "type": "scripted",
        "role": "ambient_system",
        "fallback": "static_fallback_id",
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# §1 — empty / missing
# ---------------------------------------------------------------------------

def test_assets_field_missing_returns_empty_map():
    assert validate_assets(None) == {}


def test_empty_assets_list_returns_empty_map():
    assert validate_assets([]) == {}


def test_assets_field_must_be_list_when_present():
    with pytest.raises(AssetValidationError):
        validate_assets({"id": "not-a-list"})  # type: ignore[arg-type]


def test_each_asset_entry_must_be_a_mapping():
    with pytest.raises(AssetValidationError) as exc:
        validate_assets(["not-a-dict"])  # type: ignore[list-item]
    assert "0" in str(exc.value)


# ---------------------------------------------------------------------------
# §2 — image required fields
# ---------------------------------------------------------------------------

def test_image_with_all_required_fields_validates():
    out = validate_assets([_img()])
    assert "img1" in out
    assert isinstance(out["img1"], Asset)
    assert out["img1"].type == "image"


def test_image_requires_id():
    asset = _img()
    del asset["id"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "id" in str(exc.value).lower()


def test_image_requires_src():
    asset = _img()
    del asset["src"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    msg = str(exc.value)
    assert "src" in msg.lower()
    assert "img1" in msg
    assert "image" in msg.lower()


def test_image_requires_alt():
    asset = _img()
    del asset["alt"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "alt" in str(exc.value).lower()


def test_image_alt_can_be_empty_string():
    """Decorative images use `alt=""`. Schema requires the key but
    accepts empty value (arch §6 calls out `alt is required` — the
    presence is the contract, not a non-empty value)."""
    out = validate_assets([_img(alt="")])
    assert out["img1"].alt == ""


# ---------------------------------------------------------------------------
# §3 — video required fields
# ---------------------------------------------------------------------------

def test_video_with_local_src_and_poster_validates():
    out = validate_assets([_video()])
    assert out["vid1"].type == "video"


def test_video_requires_id():
    asset = _video()
    del asset["id"]
    with pytest.raises(AssetValidationError):
        validate_assets([asset])


def test_video_requires_poster():
    asset = _video()
    del asset["poster"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    msg = str(exc.value)
    assert "poster" in msg.lower()
    assert "vid1" in msg


def test_video_requires_src_or_embed_url():
    asset = _video()
    del asset["src"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    msg = str(exc.value).lower()
    assert "src" in msg or "embed_url" in msg


def test_video_with_both_src_and_embed_url_rejected():
    """XOR — one source per video."""
    asset = _video(embed_url="https://www.youtube.com/embed/abc")
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "src" in str(exc.value).lower() and "embed_url" in str(exc.value).lower()


def test_video_with_only_embed_url_validates():
    asset = {
        "id": "vid_embed",
        "type": "video",
        "embed_url": "https://www.youtube.com/embed/abc",
        "poster": "assets/p.jpg",
    }
    out = validate_assets([asset])
    assert out["vid_embed"].embed_url == "https://www.youtube.com/embed/abc"


# ---------------------------------------------------------------------------
# §4 — scripted required fields
# ---------------------------------------------------------------------------

def test_scripted_with_all_required_fields_validates():
    out = validate_assets([_scripted()])
    assert out["scr1"].type == "scripted"
    assert out["scr1"].role == "ambient_system"


def test_scripted_requires_id():
    asset = _scripted()
    del asset["id"]
    with pytest.raises(AssetValidationError):
        validate_assets([asset])


def test_scripted_requires_role():
    asset = _scripted()
    del asset["role"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "role" in str(exc.value).lower()


def test_scripted_requires_fallback():
    asset = _scripted()
    del asset["fallback"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "fallback" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# §5 — unsupported type
# ---------------------------------------------------------------------------

def test_unsupported_type_rejected():
    asset = {"id": "x", "type": "audio", "src": "assets/x.mp3"}
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    msg = str(exc.value)
    assert "audio" in msg
    # error must list the canonical types so the recipe author can
    # pick a correct one
    assert any(t in msg for t in ALLOWED_ASSET_TYPES)


def test_missing_type_rejected():
    asset = {"id": "x", "src": "assets/x"}
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "type" in str(exc.value).lower()


def test_allowed_asset_types_explicit():
    """Closed set known at module-load time."""
    assert ALLOWED_ASSET_TYPES == frozenset({"image", "video", "scripted"})


# ---------------------------------------------------------------------------
# §6 — duplicate ids
# ---------------------------------------------------------------------------

def test_duplicate_asset_ids_rejected():
    a1 = _img(id="dup")
    a2 = _img(id="dup", src="assets/other.jpg")
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([a1, a2])
    msg = str(exc.value)
    assert "dup" in msg
    assert "duplicate" in msg.lower() or "already" in msg.lower()


def test_distinct_ids_validate_together():
    out = validate_assets([_img(id="a"), _img(id="b", src="assets/b.jpg")])
    assert set(out.keys()) == {"a", "b"}


# ---------------------------------------------------------------------------
# §7 — required: false flag preserved (does NOT change schema)
# ---------------------------------------------------------------------------

def test_required_false_flag_preserved():
    out = validate_assets([_img(required=False)])
    assert out["img1"].required is False


def test_required_true_is_default_when_flag_absent():
    out = validate_assets([_img()])
    assert out["img1"].required is True


def test_required_false_does_not_relax_per_type_schema():
    """`required: false` is a downstream signal (block-resolution
    can omit the slot) — but the asset SCHEMA still enforces
    per-type fields. An `image` declaration without `alt` is invalid
    even when `required: false`."""
    asset = _img(required=False)
    del asset["alt"]
    with pytest.raises(AssetValidationError):
        validate_assets([asset])


# ---------------------------------------------------------------------------
# §9 — External URL policy
# ---------------------------------------------------------------------------

def test_image_with_external_http_url_rejected():
    asset = _img(src="https://example.com/img.jpg")
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "external" in str(exc.value).lower() or "http" in str(exc.value).lower()


def test_image_with_external_https_url_rejected():
    asset = _img(src="https://cdn.example.com/img.jpg")
    with pytest.raises(AssetValidationError):
        validate_assets([asset])


def test_scripted_with_external_url_in_extra_src_rejected():
    """If a scripted asset declares `src` (the JS file path), it
    must be local."""
    asset = _scripted(src="https://example.com/script.js")
    with pytest.raises(AssetValidationError):
        validate_assets([asset])


@pytest.mark.parametrize("host", [
    "https://www.youtube.com/embed/abc",
    "https://youtube.com/embed/abc",
    "https://youtu.be/abc",
    "https://vimeo.com/12345",
    "https://www.vimeo.com/12345",
    "https://player.vimeo.com/video/12345",
])
def test_video_with_allowed_embed_host_validates(host):
    asset = {
        "id": "vid",
        "type": "video",
        "embed_url": host,
        "poster": "assets/p.jpg",
    }
    out = validate_assets([asset])
    assert out["vid"].embed_url == host


@pytest.mark.parametrize("host", [
    "https://malicious.example.com/embed/abc",
    "https://other-video-host.com/play/123",
    "http://youtube.com.attacker.com/abc",  # subdomain attack pattern
])
def test_video_with_disallowed_embed_host_rejected(host):
    asset = {
        "id": "vid",
        "type": "video",
        "embed_url": host,
        "poster": "assets/p.jpg",
    }
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    msg = str(exc.value).lower()
    assert "embed" in msg or "allowlist" in msg or "host" in msg


def test_allowed_embed_hosts_explicit():
    assert "youtube.com" in ALLOWED_EMBED_HOSTS
    assert "vimeo.com" in ALLOWED_EMBED_HOSTS


# ---------------------------------------------------------------------------
# §10 — Data URI policy
# ---------------------------------------------------------------------------

def test_image_with_data_uri_src_rejected_without_placeholder():
    asset = _img(src="data:image/svg+xml;base64,PHN2Zy8+")
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    msg = str(exc.value).lower()
    assert "data" in msg and ("placeholder" in msg or "uri" in msg)


def test_image_with_data_uri_and_placeholder_flag_validates():
    """Per arch §6: 'neutral placeholders may be used only for
    structural smoke tests'. The `placeholder: true` flag opts in."""
    asset = _img(
        src="data:image/svg+xml;base64,PHN2Zy8+",
        placeholder=True,
    )
    out = validate_assets([asset])
    assert out["img1"].placeholder is True


def test_video_poster_data_uri_rejected_without_placeholder():
    asset = _video(poster="data:image/png;base64,iVBORw0KGgo=")
    with pytest.raises(AssetValidationError):
        validate_assets([asset])


def test_video_poster_data_uri_with_placeholder_validates():
    asset = _video(
        poster="data:image/png;base64,iVBORw0KGgo=",
        placeholder=True,
    )
    out = validate_assets([asset])
    assert out["vid1"].placeholder is True


def test_placeholder_does_not_bypass_external_url_rule():
    """Placeholder flag is for DATA URIs only. External http(s) URLs
    are still rejected even with the flag set, because they can't
    be neutralised the way data URIs can."""
    asset = _img(src="https://example.com/img.jpg", placeholder=True)
    with pytest.raises(AssetValidationError):
        validate_assets([asset])


# ---------------------------------------------------------------------------
# §11 — error messages include id / index
# ---------------------------------------------------------------------------

def test_error_message_includes_asset_index_when_id_missing():
    """When the asset has no `id` field, the error must locate it
    by list index so the recipe author can find it."""
    assets = [_img(), {"type": "image", "src": "assets/x", "alt": "x"}]  # second has no id
    with pytest.raises(AssetValidationError) as exc:
        validate_assets(assets)
    msg = str(exc.value)
    # Either "[1]" or "index 1" or "1" with context — the second
    # asset's position must surface
    assert "1" in msg


def test_error_message_includes_asset_id_when_present():
    asset = _img(id="my_hero_image")
    del asset["alt"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "my_hero_image" in str(exc.value)


def test_error_message_locates_per_type_failure_with_type_name():
    asset = _video()
    del asset["poster"]
    with pytest.raises(AssetValidationError) as exc:
        validate_assets([asset])
    assert "video" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_returns_id_keyed_mapping():
    out = validate_assets([_img(id="a"), _video(id="b")])
    assert set(out.keys()) == {"a", "b"}


def test_output_assets_are_immutable_dataclass():
    out = validate_assets([_img()])
    asset = out["img1"]
    with pytest.raises(Exception):  # FrozenInstanceError
        asset.alt = "mutated"  # type: ignore[misc]


def test_preserves_extra_unknown_fields():
    asset = _img(custom_metadata={"author": "test"}, version=2)
    out = validate_assets([asset])
    extra = out["img1"].extra
    assert extra["custom_metadata"] == {"author": "test"}
    assert extra["version"] == 2


def test_extra_does_not_leak_known_fields():
    """Reserved fields go to typed slots, NOT extra."""
    out = validate_assets([_img(role="hero")])
    assert "role" not in out["img1"].extra
    assert out["img1"].role == "hero"


def test_normalised_video_has_role_optional():
    """Video role is optional in the schema."""
    out = validate_assets([_video()])
    assert out["vid1"].role is None
