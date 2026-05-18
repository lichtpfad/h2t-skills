from h2t.core.envelope import success_envelope, error_envelope
from h2t.core.errors import AuthError


def test_success_shape():
    assert success_envelope("notion", {"id": "abc"}) == {
        "ok": True, "provider": "notion", "result": {"id": "abc"}}


def test_error_shape_with_hint():
    env = error_envelope("notion", AuthError("denied", hint="Set NOTION_API_TOKEN"))
    assert env == {"ok": False, "provider": "notion",
                   "error": {"type": "auth", "message": "denied",
                             "hint": "Set NOTION_API_TOKEN"}}


def test_error_shape_unknown_exception_is_provider():
    env = error_envelope("notion", ValueError("boom"))
    assert env["error"]["type"] == "provider" and env["error"]["hint"] is None
