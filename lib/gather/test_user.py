import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.user import gather_user_context

def test_gather_user_context_returns_expected_keys():
    result = gather_user_context()
    assert "core_path" in result
    assert "language" in result
    assert "available_contexts" in result
    assert "deep_paths" in result

def test_gather_user_context_core_exists():
    result = gather_user_context()
    if result["core_path"]:
        assert os.path.exists(result["core_path"])

def test_gather_user_context_never_returns_core_content():
    """core.md is referenced by path only; its body is not carried in the payload."""
    assert "core_content" not in gather_user_context()

def test_gather_user_context_core_path_missing(tmp_path):
    result = gather_user_context(config_root=str(tmp_path))
    assert result["core_path"] == ""

def test_gather_user_context_language():
    result = gather_user_context()
    assert result["language"] == "ru"

def test_gather_user_context_with_personal_domain():
    result = gather_user_context(domain="personal")
    # personal domain should include psychology.md if it exists
    assert isinstance(result["deep_paths"], list)

def test_gather_user_context_with_unknown_domain():
    result = gather_user_context(domain="nonexistent")
    assert result["deep_paths"] == []

if __name__ == "__main__":
    test_gather_user_context_returns_expected_keys()
    test_gather_user_context_core_exists()
    test_gather_user_context_language()
    test_gather_user_context_with_personal_domain()
    test_gather_user_context_with_unknown_domain()
    print("All user tests passed")
