import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.github import gather_github, _parse_json, _parse_jsonl_or_json

def test_gather_github_returns_expected_keys():
    result = gather_github("lichtpfad/claude-agent-skills")
    for key in ("issues", "milestones", "prs", "bugs"):
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["issues"], list)

def test_gather_github_with_project_filter():
    result = gather_github("lichtpfad/claude-agent-skills", project_label="nonexistent")
    assert "issues" in result

def test_parse_json_empty():
    assert _parse_json("") == []
    assert _parse_json("   ") == []

def test_parse_json_valid():
    assert _parse_json('[{"a":1}]') == [{"a": 1}]

def test_parse_jsonl_or_json_array():
    assert _parse_jsonl_or_json('[{"a":1},{"b":2}]') == [{"a": 1}, {"b": 2}]

def test_parse_jsonl_or_json_newline_delimited():
    result = _parse_jsonl_or_json('{"a":1}\n{"b":2}')
    assert len(result) == 2

if __name__ == "__main__":
    test_parse_json_empty()
    test_parse_json_valid()
    test_parse_jsonl_or_json_array()
    test_parse_jsonl_or_json_newline_delimited()
    test_gather_github_returns_expected_keys()
    test_gather_github_with_project_filter()
    print("All github tests passed")


def test_gather_github_reports_failed_sources():
    """Every gh call failing must be reported, not rendered as an empty repo."""
    import gather.github as gh_mod
    original = gh_mod.run_parallel
    gh_mod.run_parallel = lambda commands, **kw: {name: None for name in commands}
    try:
        result = gather_github("lichtpfad/h2t-skills")
    finally:
        gh_mod.run_parallel = original
    assert result["issues"] == []
    assert result["failed"] == ["bugs", "issues", "milestones", "prs"]


def test_gather_github_no_failures_when_calls_succeed():
    """A repo that genuinely has no issues reports no failed sources."""
    import gather.github as gh_mod
    original = gh_mod.run_parallel
    gh_mod.run_parallel = lambda commands, **kw: {name: "[]" for name in commands}
    try:
        result = gather_github("lichtpfad/h2t-skills")
    finally:
        gh_mod.run_parallel = original
    assert result["issues"] == []
    assert result["failed"] == []
