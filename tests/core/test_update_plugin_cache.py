"""`update-plugin.sh` must install what the marketplace installs.

The script refreshes the local plugin cache during development. It used to drop the
plugin's own `lib/` and copy the repo-root one over it, but the two copies have
drifted: `plugins/h2t-core/lib/gather/sessions.py` defines `find_latest_session_index`
and the repo-root copy does not, while `skills/session-start/scripts/gather.py` imports
it. Running the script therefore replaced a working cache with one that raises
ImportError on every session start.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "h2t-core" / "scripts" / "update-plugin.sh"


def test_update_plugin_keeps_the_lib_the_plugin_ships():
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'rm -rf "$CACHE_DIR/lib"' not in script
    assert 'cp -r "$REPO_DIR/lib"' not in script


def test_plugin_lib_satisfies_the_import_that_broke():
    """Guards the specific symbol the swap removed."""
    sessions = (ROOT / "plugins" / "h2t-core" / "lib" / "gather" / "sessions.py").read_text(encoding="utf-8")
    gather = (ROOT / "plugins" / "h2t-core" / "skills" / "session-start" / "scripts" / "gather.py").read_text(encoding="utf-8")
    assert "find_latest_session_index" in gather
    assert "def find_latest_session_index" in sessions
