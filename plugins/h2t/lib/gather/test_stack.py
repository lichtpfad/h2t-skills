import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.stack import detect_stack

def test_detect_stack_returns_dict():
    result = detect_stack(".")
    assert isinstance(result, dict)
    assert "name" in result and "commands" in result

def test_detect_stack_no_marker():
    """Current repo has no package.json/pyproject.toml — should return 'none'."""
    result = detect_stack(".")
    assert result["name"] == "none"

if __name__ == "__main__":
    test_detect_stack_returns_dict()
    test_detect_stack_no_marker()
    print("All stack tests passed")
