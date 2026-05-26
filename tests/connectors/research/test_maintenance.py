from __future__ import annotations

from h2t_ops.connectors.research import maintenance, store


def test_doctor_reports_malformed_canonical_object_as_error(tmp_path):
    root = tmp_path / "research"
    path = store.object_path(root, "documents", "research-doc:bad")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad json", encoding="utf-8")

    result = maintenance.doctor(root)

    assert result["kind"] == "research_doctor"
    assert result["status"] == "error"
    assert result["counts"]["errors"] == 1
    assert result["findings"][0]["severity"] == "error"
    assert result["findings"][0]["code"] == "object_json_invalid"
    assert result["findings"][0]["path"] == str(path)


def test_doctor_reports_non_utf8_canonical_object_as_error(tmp_path):
    root = tmp_path / "research"
    path = store.object_path(root, "documents", "research-doc:bad-encoding")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00")

    result = maintenance.doctor(root)

    matching_findings = [
        finding
        for finding in result["findings"]
        if finding["code"] == "object_json_invalid" and finding["path"] == str(path)
    ]
    assert result["status"] == "error"
    assert matching_findings


def test_doctor_reports_schema_and_id_mismatch_as_errors(tmp_path):
    root = tmp_path / "research"
    store.write_json(
        store.object_path(root, "documents", "research-doc:bad"),
        {"schema": "research_thread/v0.1", "document_id": "research-doc:other"},
    )

    result = maintenance.doctor(root)

    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] == "error"
    assert "object_schema_mismatch" in codes
    assert "object_id_mismatch" in codes
