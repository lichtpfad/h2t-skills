"""Tests for exa_search.py CLI wrapper."""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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


# --- validate_args helper & tests ---

def _args(**kwargs):
    defaults = dict(
        mode="generic",
        start_date=None, end_date=None,
        include_domains=None, exclude_domains=None,
        include_text=None, exclude_text=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_validate_competitor_with_start_date_exits_1(capsys):
    args = _args(mode="competitor", start_date="2025-01-01")
    with pytest.raises(SystemExit) as excinfo:
        exa_search.validate_args(args)
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "EXA_ERROR:ARGS" in err
    assert "mode=competitor" in err
    assert "category=company" in err
    assert "--start-date" in err


def test_validate_people_with_exclude_text_exits_1(capsys):
    args = _args(mode="people", exclude_text=["foo"])
    with pytest.raises(SystemExit) as excinfo:
        exa_search.validate_args(args)
    assert excinfo.value.code == 1
    assert "EXA_ERROR:ARGS" in capsys.readouterr().err


def test_validate_include_text_multi_item_exits_1(capsys):
    args = _args(mode="generic", include_text=["foo", "bar"])
    with pytest.raises(SystemExit) as excinfo:
        exa_search.validate_args(args)
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "single-item" in err


def test_validate_valid_combinations_pass():
    # news + dates + domains — all allowed
    exa_search.validate_args(_args(
        mode="news",
        start_date="2025-01-01",
        end_date="2026-04-18",
        include_domains=["techcrunch.com"],
    ))
    # competitor without restricted params — allowed
    exa_search.validate_args(_args(mode="competitor"))
    # single-item include_text — allowed
    exa_search.validate_args(_args(mode="generic", include_text=["solo"]))


# --- load_system_prompt tests ---

def test_load_system_prompt_parses_frontmatter_and_body(tmp_path, monkeypatch):
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "generic.md").write_text(
        "---\n"
        "mode: generic\n"
        "exa_type: auto\n"
        "---\n"
        "You are a neutral research assistant. Cite sources.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)
    body, schema = exa_search.load_system_prompt("generic")
    assert "neutral research assistant" in body
    assert schema == {}


def test_load_system_prompt_parses_output_schema_json(tmp_path, monkeypatch):
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "competitor.md").write_text(
        "---\n"
        "mode: competitor\n"
        'output_schema: {"type": "object", "properties": {"name": {"type": "string"}}}\n'
        "---\n"
        "Competitive intel researcher.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)
    body, schema = exa_search.load_system_prompt("competitor")
    assert "Competitive intel" in body
    assert schema == {"type": "object", "properties": {"name": {"type": "string"}}}


def test_load_system_prompt_missing_file_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        exa_search.load_system_prompt("nonexistent")
    assert excinfo.value.code == 1
    assert "EXA_ERROR:ARGS" in capsys.readouterr().err
