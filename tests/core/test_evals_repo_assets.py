import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals"


def test_unit_cases_jsonl_parses():
    lines = (EVALS / "unit_cases.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines, "unit_cases.jsonl is empty"
    for ln in lines:
        rec = json.loads(ln)
        assert "id" in rec and "eval_set_id" in rec


def test_integration_cases_jsonl_parses():
    lines = (EVALS / "integration_cases.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines, "integration_cases.jsonl is empty"
    for ln in lines:
        rec = json.loads(ln)
        assert "id" in rec and "eval_set_id" in rec


def test_business_kpi_toml_parses():
    with (EVALS / "business_kpi.toml").open("rb") as f:
        data = tomllib.load(f)
    assert "kpi" in data
