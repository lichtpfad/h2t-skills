import json
from h2t_ops.core.output import emit
from h2t_ops.core.errors import AuthError


def test_emit_json_success(capsys):
    code = emit("notion", result={"id": "p1"}, fmt="json")
    out = capsys.readouterr()
    assert code == 0
    assert json.loads(out.out) == {"ok": True, "provider": "notion", "result": {"id": "p1"}}
    assert out.err == ""


def test_emit_json_error_to_stderr_nonzero(capsys):
    code = emit("notion", exc=AuthError("denied", hint="Set NOTION_API_TOKEN"), fmt="json")
    out = capsys.readouterr()
    assert code == 4
    payload = json.loads(out.err)
    assert payload["ok"] is False and payload["error"]["type"] == "auth"
    assert out.out == ""


def test_emit_md_passthrough_string(capsys):
    code = emit("notion", result="# Title\n", fmt="md")
    out = capsys.readouterr()
    assert code == 0 and "# Title" in out.out


def test_emit_human_error_writes_stderr(capsys):
    code = emit("notion", exc=AuthError("denied", hint="Set NOTION_API_TOKEN"), fmt="human")
    out = capsys.readouterr()
    assert code == 4 and "denied" in out.err and "Set NOTION_API_TOKEN" in out.err
    assert out.out == ""


def test_emit_human_dict_result(capsys):
    code = emit("notion", result={"key": "val"}, fmt="human")
    out = capsys.readouterr()
    assert code == 0
    assert json.loads(out.out) == {"key": "val"}


def test_emit_human_error_no_hint(capsys):
    code = emit("notion", exc=AuthError("denied"), fmt="human")
    out = capsys.readouterr()
    assert code == 4
    assert "denied" in out.err and "hint:" not in out.err
    assert out.out == ""
