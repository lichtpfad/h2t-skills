"""Tests for exa_search.py CLI wrapper."""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "exa_search.py"


def test_script_exists():
    assert SCRIPT.is_file(), f"expected script at {SCRIPT}"


def test_version_flag():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "0.1.0" in result.stdout


# --- MODE_CONFIG tests ---
sys.path.insert(0, str(SCRIPT.parent))
import exa_search  # noqa: E402


def test_mode_config_has_all_seven_modes():
    expected = {"fast", "generic", "news", "academic", "competitor", "people", "deep"}
    assert set(exa_search.MODE_CONFIG.keys()) == expected


def test_mode_config_competitor_uses_company_category():
    cfg = exa_search.MODE_CONFIG["competitor"]
    assert cfg["type"] == "auto"
    assert cfg["category"] == "company"
    assert cfg["num_results"] == 10


def test_mode_config_deep_uses_deep_type_default_10():
    cfg = exa_search.MODE_CONFIG["deep"]
    assert cfg["type"] == "deep"
    assert cfg["category"] is None
    assert cfg["num_results"] == 10


def test_mode_config_fast_uses_fast_type():
    cfg = exa_search.MODE_CONFIG["fast"]
    assert cfg["type"] == "fast"
    assert cfg["num_results"] == 10


def test_category_blocks_company_blocks_dates_and_domains():
    blocks = exa_search.CATEGORY_BLOCKS["company"]
    assert "start_date" in blocks
    assert "end_date" in blocks
    assert "include_domains" in blocks
    assert "exclude_domains" in blocks


def test_category_blocks_people_blocks_text_and_dates():
    blocks = exa_search.CATEGORY_BLOCKS["people"]
    assert "include_text" in blocks
    assert "exclude_text" in blocks
    assert "exclude_domains" in blocks
    assert "start_date" in blocks


def test_category_blocks_financial_report_blocks_exclude_text():
    assert "exclude_text" in exa_search.CATEGORY_BLOCKS["financial report"]


def test_die_writes_stderr_and_exits_with_code(capsys):
    with pytest.raises(SystemExit) as excinfo:
        exa_search.die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    assert excinfo.value.code == 4
    captured = capsys.readouterr()
    assert "EXA_ERROR:ENV" in captured.err
    assert "EXA_API_KEY missing" in captured.err
    assert captured.out == ""
