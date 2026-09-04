"""select_targets decides which Codex brokers a SessionEnd reap may kill.

The kill itself (taskkill) lives in main() and is never exercised here — a test
that shelled out could nuke a real broker. Only the pure selection is asserted,
and it is exactly where the safety rules live: kill this session's own broker and
brokers whose working directory is gone; never touch a live sibling in another
worktree.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE = (
    Path(__file__).parents[2]
    / "plugins" / "h2t-core" / "hooks-handlers" / "reap_codex.py"
)
_spec = importlib.util.spec_from_file_location("reap_codex", _MODULE)
reap_codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reap_codex)
select_targets = reap_codex.select_targets


def _reasons(targets):
    return {t["pid"]: t["reason"] for t in targets}


def test_kills_this_sessions_own_broker():
    brokers = [{"pid": 1, "cwd": "C:/dev/proj"}]
    out = select_targets(brokers, "C:/dev/proj", path_exists=lambda p: True)
    assert _reasons(out) == {1: "session"}


def test_matches_across_separator_and_case_and_trailing_slash():
    """Codex writes forward slashes; the payload cwd may be backslashed."""
    brokers = [{"pid": 7, "cwd": "C:/dev/Proj"}]
    out = select_targets(brokers, "C:\\dev\\proj\\", path_exists=lambda p: True)
    assert _reasons(out) == {7: "session"}


def test_kills_orphan_with_dead_cwd():
    brokers = [{"pid": 2, "cwd": "C:/dev/kraken-32"}]
    out = select_targets(brokers, "C:/dev/other", path_exists=lambda p: False)
    assert _reasons(out) == {2: "orphan"}


def test_spares_live_sibling_in_another_worktree():
    """cwd exists and is not this session's — a live parallel chat. Leave it."""
    brokers = [{"pid": 3, "cwd": "C:/dev/sibling"}]
    out = select_targets(brokers, "C:/dev/mine", path_exists=lambda p: True)
    assert out == []


def test_session_match_wins_even_if_its_cwd_is_gone():
    brokers = [{"pid": 4, "cwd": "C:/dev/mine"}]
    out = select_targets(brokers, "C:/dev/mine", path_exists=lambda p: False)
    assert _reasons(out) == {4: "session"}


def test_skips_broker_without_a_cwd():
    brokers = [{"pid": 5, "cwd": ""}, {"pid": 6, "cwd": "   "}]
    out = select_targets(brokers, "C:/dev/mine", path_exists=lambda p: False)
    assert out == []


def test_no_session_cwd_still_reaps_orphans_only():
    brokers = [
        {"pid": 8, "cwd": "C:/dev/gone"},
        {"pid": 9, "cwd": "C:/dev/alive"},
    ]
    out = select_targets(brokers, "", path_exists=lambda p: p.endswith("alive"))
    assert _reasons(out) == {8: "orphan"}


def test_mixed_batch_classifies_each_broker():
    brokers = [
        {"pid": 10, "cwd": "C:/dev/mine"},      # session
        {"pid": 11, "cwd": "C:/dev/gone"},      # orphan
        {"pid": 12, "cwd": "C:/dev/sibling"},   # spared
    ]
    out = select_targets(
        brokers, "C:/dev/mine",
        path_exists=lambda p: p.rstrip("/").endswith(("mine", "sibling")),
    )
    assert _reasons(out) == {10: "session", 11: "orphan"}
