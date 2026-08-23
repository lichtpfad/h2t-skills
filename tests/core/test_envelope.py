from h2t_ops.core.envelope import error_envelope, success_envelope
from h2t_ops.core.errors import AuthError, ProviderError


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


def test_error_shape_with_details():
    env = error_envelope(
        "research",
        ProviderError(
            "Exa failed",
            details={"provider_envelope": {"status": "FAILED", "primary_engine": "exa"}},
        ),
    )
    assert env == {
        "ok": False,
        "provider": "research",
        "error": {
            "type": "provider",
            "message": "Exa failed",
            "hint": None,
            "details": {"provider_envelope": {"status": "FAILED", "primary_engine": "exa"}},
        },
    }


def test_error_shape_without_details_keeps_old_shape():
    env = error_envelope("research", ProviderError("Exa failed"))
    assert env == {
        "ok": False,
        "provider": "research",
        "error": {"type": "provider", "message": "Exa failed", "hint": None},
    }
