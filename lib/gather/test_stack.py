import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.stack import detect_stack


def test_detect_stack_returns_dict():
    result = detect_stack(".")
    assert isinstance(result, dict)
    assert "name" in result and "commands" in result

def test_detect_stack_no_marker(tmp_path):
    """A directory with no stack markers should return 'none'."""
    result = detect_stack(str(tmp_path))
    assert result["name"] == "none"

if __name__ == "__main__":
    test_detect_stack_returns_dict()
    test_detect_stack_no_marker()
    print("All stack tests passed")
