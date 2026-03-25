import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.eval import record_eval, estimate_tokens

def test_record_eval_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = record_eval(
            skill_name="test-skill",
            metrics={"duration_ms": 150, "sources_used": ["git", "github"]},
            evals_root=tmpdir,
        )
        assert result is not None
        assert os.path.exists(result)
        with open(result) as f:
            data = json.load(f)
        assert data["skill"] == "test-skill"
        assert data["metrics"]["duration_ms"] == 150
        assert "timestamp" in data
        assert "session_id" in data

def test_record_eval_increments_counter():
    with tempfile.TemporaryDirectory() as tmpdir:
        r1 = record_eval("sk", {"a": 1}, evals_root=tmpdir)
        r2 = record_eval("sk", {"a": 2}, evals_root=tmpdir)
        assert r1 != r2
        sessions_dir = os.path.join(tmpdir, "sk", "sessions")
        assert len(os.listdir(sessions_dir)) == 2

def test_estimate_tokens():
    data = {"key": "value", "nested": {"a": 1}}
    tokens = estimate_tokens(data)
    assert isinstance(tokens, int)
    assert tokens > 0

if __name__ == "__main__":
    test_record_eval_creates_file()
    test_record_eval_increments_counter()
    test_estimate_tokens()
    print("All eval tests passed")
