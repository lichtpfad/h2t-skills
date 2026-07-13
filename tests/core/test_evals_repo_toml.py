"""Contract: every custom skills.* metric the runtime emits must be declared in
evals/repo.toml [custom_metrics], with matching level/type/aggregation.

This guards the declared-vs-emitted drift that #317 fixed: the runtime emitted 9
custom keys while repo.toml declared only 3, so 6 keys would land in the SDK
quarantine (E_METRIC_NOT_REGISTERED) instead of central. A new emit-site added
without a declaration here re-opens that silent gap and fails this test.
"""
import tomllib
from pathlib import Path

REPO_TOML = Path(__file__).resolve().parents[2] / "evals" / "repo.toml"

# The contract: skills.* keys emitted by the runtime, with the metric-def form.
# level/type/aggregation are decorative on the current h2t-evals server (no
# allowlist; scorecard AVGs COALESCE(value_num, value_bool)), but declaring them
# accurately keeps repo.toml an honest source of truth and the prod registration
# aligned. Sources: lib/cli/main.py, lib/eval/session.py, exa_search.py.
EMITTED_METRICS = {
    "skills.gather_source_success_rate": ("unit", "num", "avg"),
    "skills.token_consumption": ("unit", "num", "avg"),
    "skills.sources_failed_count": ("unit", "num", "avg"),
    "skills.fallback_used": ("business", "bool", "avg"),
    "skills.duration_ms": ("integration", "num", "avg"),
    "skills.error_class": ("unit", "text", "count"),
    "skills.research_cost_usd": ("business", "num", "sum"),
    "skills.api_latency_ms": ("integration", "num", "avg"),
    "skills.records_returned": ("unit", "num", "avg"),
}


def _declared_metrics() -> dict[str, tuple[str, str, str]]:
    data = tomllib.load(REPO_TOML.open("rb"))
    out: dict[str, tuple[str, str, str]] = {}
    for entry in data.get("custom_metrics", {}).values():
        out[entry["key"]] = (entry["level"], entry["type"], entry["aggregation"])
    return out


def test_every_emitted_metric_is_declared():
    declared = _declared_metrics()
    missing = sorted(k for k in EMITTED_METRICS if k not in declared)
    assert not missing, f"emitted but undeclared in evals/repo.toml: {missing}"


def test_declared_metric_forms_match_emission():
    declared = _declared_metrics()
    mismatched = {
        k: (declared[k], want)
        for k, want in EMITTED_METRICS.items()
        if k in declared and declared[k] != want
    }
    assert not mismatched, f"level/type/aggregation mismatch: {mismatched}"


def test_framework_identity_singular():
    """repo.toml framework aligns with the value the runtime sends ('h2t-skill')."""
    data = tomllib.load(REPO_TOML.open("rb"))
    assert data["framework"] == "h2t-skill"
    assert data["repo"] == "h2t-skills"
