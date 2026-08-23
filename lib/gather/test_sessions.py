import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.sessions import extract_session_id, find_session_files, get_machine_name


def test_find_session_files_returns_list():
    assert isinstance(find_session_files("claude-agent-skills"), list)

def test_find_session_files_nonexistent_repo():
    assert find_session_files("nonexistent-repo-xyz") == []

def test_extract_session_id_no_dir():
    assert extract_session_id() == ""
    assert extract_session_id("") == ""

def test_get_machine_name():
    name = get_machine_name()
    assert isinstance(name, str)
    assert len(name) > 0

if __name__ == "__main__":
    test_find_session_files_returns_list()
    test_find_session_files_nonexistent_repo()
    test_extract_session_id_no_dir()
    test_get_machine_name()
    print("All sessions tests passed")
