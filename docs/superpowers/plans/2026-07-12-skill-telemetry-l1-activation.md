---
title: "Skill telemetry l1 activation"
status: "draft"
date: "2026-07-12"
milestone: ""
---

# Skill telemetry L1 activation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every instrumented L1 skill session self-complete and coherent — real/proxy `core.*` written to BOTH the local and central paths, a `level`/`unit`-aware `metric()`, per-class `eval_set`, research-cost unified on `SkillEval`, minimal parse-valid repo-assets, and dead `record_eval` removed — all in `local` mode under the existing `agent-skills` identity.

**Architecture:** The crossbeam is `lib/eval/session.py` (byte-identical vendored copy at `plugins/h2t-core/lib/eval/session.py`, guarded by `tests/core/test_eval_vendored_parity.py`). `core.*` are computed once in a single `__exit__` helper (`_finalize_metrics`) and written to both `_write_local` and `_send_central`; inline `core.*` are removed from `_send_central` to prevent duplicates. A new sibling module `skill_class.py` (also vendored) is the single source of the skill→class→`eval_set` map. Research telemetry moves off the bespoke dead endpoint onto `SkillEval`. Everything is `local`-mode; NO metric-def registration, NO `validate-repo` green, NO push, NO identity rebrand (all `#305`).

**Tech Stack:** Python 3.11 stdlib only in `session.py`/`skill_class.py` (enforced by `test_session_imports_only_stdlib`); pytest; ruff. Test command: `C:/dev/h2t-skills/.venv/Scripts/pytest`.

---

## Scope & boundaries (read before starting)

**In scope (this run):** D3, D1, D5, D9, D7, D4, D6 — as tasks below.

**D8 (integration sweep) is SCOPED to research only (via D4).** The spec lists ~8 integration skills
(connectors, drive, meetgeek, research, telegram, drawio, docs-*, edu-transcripts). Instrumenting all
of them in one run is unbounded and each has a different entry surface. This run proves the shared
pattern on `research` (its telemetry seam already exists and is the reconciliation target). The
remaining skills are a **documented follow-up** (Task 8) — NOT silently dropped. Extend later per the
recorded pattern.

**Hard boundaries (do not cross — all `#305`/push track):**
- Do NOT register metric-defs (`metric-def upsert`), do NOT push, do NOT run `validate-repo` for green.
- Do NOT rename `agent-skills`→`h2t-skills`; runtime `repo` stays `agent-skills`; metric prefix stays `skills.*`.
- D6 = author files + parse-test ONLY (the `validate-repo` gate reads central DB → unreachable local).

**Session.py discipline (MANDATORY on every task that edits `session.py` or a vendored sibling):**
1. Edit BOTH copies: `lib/eval/session.py` AND `plugins/h2t-core/lib/eval/session.py` (and `skill_class.py` when added).
2. Run `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_eval_vendored_parity.py -v` → PASS.
3. Run the FULL suite `C:/dev/h2t-skills/.venv/Scripts/pytest` → green, before commit.
Never let parity drift between steps — the two copies change in the same commit.

**Concurrent-repo hazard:** many branches/worktrees are live (`codex/research-parity` touches
`exa_search.py` = D4 target). Work on a fresh branch off `main`; verify branch before every commit;
expect a possible D4 merge conflict — record it in handoff, do not force-resolve another branch's work.

**Bash constraint (CLAUDE.md):** one command per Bash call; no `&&`/`||`/`;`/`|`. Sequential calls for
dependent steps.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `lib/eval/session.py` | `SkillEval` — canonical. `metric()` signature, `_finalize_metrics` core.* helper, filename scheme, eval_set lookup | 1,2,3,4 |
| `plugins/h2t-core/lib/eval/session.py` | Byte-identical vendored runtime copy | 1,2,3,4 |
| `lib/eval/skill_class.py` | NEW. skill→class→eval_set single-source map | 3 |
| `plugins/h2t-core/lib/eval/skill_class.py` | NEW. Vendored copy | 3 |
| `lib/eval/test_session.py` | Unit tests for `SkillEval` (local + pure helpers) | 1,2,4 |
| `lib/eval/test_skill_class.py` | NEW. Unit tests for the map | 3 |
| `tests/core/test_eval_vendored_parity.py` | Extend to guard `skill_class.py` too | 3 |
| `lib/gather/eval.py` + `plugins/h2t/lib/gather/eval.py` + `plugins/h2t-core/lib/gather/eval.py` | DELETE (dead `record_eval`/`estimate_tokens`) | 5 |
| `lib/gather/test_eval.py` (+2 copies) | DELETE (tests for deleted module) | 5 |
| `lib/gather/__init__.py` (+2 copies) | Remove `record_eval`/`estimate_tokens` exports | 5 |
| `plugins/h2t-ops/skills/research/scripts/exa_search.py` | Replace `post_telemetry` with `SkillEval` emit | 6 |
| `plugins/h2t-ops/skills/research/tests/test_exa_search.py` | Update telemetry test | 6 |
| `evals/unit_cases.jsonl`, `evals/integration_cases.jsonl`, `evals/business_kpi.toml` | NEW. Minimal parse-valid repo-assets | 7 |
| `evals/repo.toml` | Update `default_eval_set_id` to class scheme | 3 |
| `tests/core/test_evals_repo_assets.py` | NEW. Parse-validity test for assets | 7 |

---

## Task 1 (D3): Extend `metric()` with `level` and `unit`

**Files:**
- Modify: `lib/eval/session.py:133-150` (the `metric` method)
- Modify: `plugins/h2t-core/lib/eval/session.py` (same region — vendored)
- Test: `lib/eval/test_session.py`

**Why:** `metric()` cannot carry `level`/`unit` → `_send_central` defaults every custom metric to
`level="unit"` (`:217`), so business metrics degrade to unit. Extend the signature and thread
`level`/`unit` into the stored entry so BOTH paths preserve them.

- [ ] **Step 1: Write the failing test** — append to `lib/eval/test_session.py`:

```python
def test_metric_records_level_and_unit_in_local(tmp_path, monkeypatch):
    """metric(level=..., unit=...) is preserved in the local JSON entry."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("research", domain="dev", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.research_cost_usd", value_num=0.42, level="business", unit="usd")
    files = list((evals_root / "research" / "sessions").glob("*.json"))
    entry = next(m for m in json.loads(files[0].read_text())["metrics"]
                 if m["key"] == "skills.research_cost_usd")
    assert entry["level"] == "business"
    assert entry["unit"] == "usd"
    assert entry["value_num"] == 0.42


def test_metric_level_defaults_to_none_when_omitted(tmp_path, monkeypatch):
    """Omitting level leaves it absent (no forced 'unit') in the stored entry."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="dev", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.token_consumption", value_num=1.0)
    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    entry = next(m for m in json.loads(files[0].read_text())["metrics"]
                 if m["key"] == "skills.token_consumption")
    assert "level" not in entry


def test_metric_level_unit_propagate_to_central(tmp_path, monkeypatch):
    """level/unit reach the central SDK path (not just local). business != unit."""
    import sys
    import types
    captured = []

    class FakeSession:
        def __init__(self, **kw):
            pass

        def start(self):
            pass

        def metric(self, key, **kw):
            captured.append((key, kw))

        def finish(self, **kw):
            pass

    class FakeClient:
        def __init__(self, **kw):
            pass

        def flush(self, **kw):
            pass

    fake = types.ModuleType("h2t_evals.sdk")
    fake.EvalClient = FakeClient
    fake.EvalSession = FakeSession
    monkeypatch.setitem(sys.modules, "h2t_evals", types.ModuleType("h2t_evals"))
    monkeypatch.setitem(sys.modules, "h2t_evals.sdk", fake)
    monkeypatch.setenv("H2T_EVALS_MODE", "push")
    with SkillEval("research", domain="d", project="p",
                   evals_root=str(tmp_path / "evals")) as ev:
        ev.metric("skills.research_cost_usd", value_num=0.4, level="business", unit="usd")
    biz = [kw for key, kw in captured if key == "skills.research_cost_usd"]
    assert biz and biz[0]["level"] == "business" and biz[0]["unit"] == "usd"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py::test_metric_records_level_and_unit_in_local -v`
Expected: FAIL — `metric() got an unexpected keyword argument 'level'`.

- [ ] **Step 3: Implement in BOTH copies** — replace the `metric` method body in `lib/eval/session.py`
      and `plugins/h2t-core/lib/eval/session.py`:

```python
    def metric(
        self,
        key: str,
        value_num: Optional[float] = None,
        value_bool: Optional[bool] = None,
        value_text: Optional[str] = None,
        *,
        level: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> None:
        """Record a metric to be written on context exit.

        level/unit are optional and threaded to both the local JSON and the
        central SDK path (via _finalize_metrics). Omitted level stays absent
        locally; _send_central applies the SDK default only when level is None.
        """
        if self._mode == "off":
            return
        entry: dict = {"key": key}
        if value_num is not None:
            entry["value_num"] = value_num
        if value_bool is not None:
            entry["value_bool"] = value_bool
        if value_text is not None:
            entry["value_text"] = value_text
        if level is not None:
            entry["level"] = level
        if unit is not None:
            entry["unit"] = unit
        self._metrics.append(entry)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py -v`
Expected: PASS (all, including the two new tests).

- [ ] **Step 5: Parity + full suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_eval_vendored_parity.py -v`
Expected: PASS.
Run: `C:/dev/h2t-skills/.venv/Scripts/pytest`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add lib/eval/session.py plugins/h2t-core/lib/eval/session.py lib/eval/test_session.py
git commit -m "feat(eval): metric() accepts level/unit, threaded to stored entry (#306)"
```

---

## Task 2 (D1): `core.*` computed once in `_finalize_metrics`, written to BOTH paths

**Files:**
- Modify: `lib/eval/session.py` — `__init__`, `__enter__`, `__exit__`, `_write_local`, `_send_central`; add `_finalize_metrics`, `record_op_type`, `record_fallback`
- Modify: `plugins/h2t-core/lib/eval/session.py` (same — vendored)
- Test: `lib/eval/test_session.py`

**Why (Codex-P1):** the 5 `core.*` are emitted ONLY in `_send_central` (`:209-213`) — in `local` mode
`core.*` are never written. And 4/5 are hardcoded stubs. Fix: compute all 5 once in a helper, write to
both paths, remove the inline block from `_send_central` (else duplicates on push). Caller-supplied
`core.*` override the proxy (dedup by key).

**Contract (nail these — they ripple to D4/D8):**
- `record_op_type(valid: bool)` — call-sites with a defined output schema call this after validating
  output; sets `self._op_type_valid`. `core.op_type_correct_rate` = `1.0/0.0` from it; if never called →
  honest proxy `1.0` on success / `0.0` on failure (documented as proxy in the metric, see `unit=None`).
- `record_fallback(used: bool = True)` — call-sites call this when a degraded path was taken; sets
  `self._fallback_used` AND emits the custom `skills.fallback_used` (bool, business).
  `core.deflection_rate` = `0.0 if fallback else 1.0`.
- `core.time_to_first_valid_ms` = honest proxy: wall-clock script runtime in ms.
- `core.tool_call_success_rate` = honest proxy: `1.0` on success / `0.0` on failure.
- `core.task_success` = `status == "success"`.

- [ ] **Step 1: Write the failing tests** — append to `lib/eval/test_session.py`:

```python
CORE_KEYS = {
    "core.task_success", "core.op_type_correct_rate", "core.deflection_rate",
    "core.time_to_first_valid_ms", "core.tool_call_success_rate",
}


def _local_metrics(evals_root, skill):
    files = list((evals_root / skill / "sessions").glob("*.json"))
    return {m["key"]: m for m in json.loads(files[0].read_text())["metrics"]}


def test_local_write_contains_all_five_core(tmp_path, monkeypatch):
    """_write_local carries all 5 core.* (not only caller metrics)."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.token_consumption", value_num=1.0)
    m = _local_metrics(evals_root, "session-start")
    assert CORE_KEYS <= set(m)


def test_core_task_success_reflects_status(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with pytest.raises(ValueError):
        with SkillEval("handoff", domain="d", project="p", evals_root=str(evals_root)):
            raise ValueError("boom")
    m = _local_metrics(evals_root, "handoff")
    assert m["core.task_success"]["value_bool"] is False
    assert m["core.tool_call_success_rate"]["value_num"] == 0.0


def test_op_type_correct_rate_from_record_op_type(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("research", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.record_op_type(False)  # schema-invalid output
    m = _local_metrics(evals_root, "research")
    assert m["core.op_type_correct_rate"]["value_num"] == 0.0


def test_deflection_rate_from_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("research", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.record_fallback()  # degraded path taken
    m = _local_metrics(evals_root, "research")
    assert m["core.deflection_rate"]["value_num"] == 0.0
    assert m["skills.fallback_used"]["value_bool"] is True


def test_caller_core_override_wins_no_duplicate(tmp_path, monkeypatch):
    """A caller-emitted core.* overrides the proxy; exactly one entry survives."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("research", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("core.op_type_correct_rate", value_num=0.5, level="unit")
    files = list((evals_root / "research" / "sessions").glob("*.json"))
    entries = [m for m in json.loads(files[0].read_text())["metrics"]
               if m["key"] == "core.op_type_correct_rate"]
    assert len(entries) == 1
    assert entries[0]["value_num"] == 0.5


def test_time_to_first_valid_is_nonneg_proxy(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)):
        pass
    m = _local_metrics(evals_root, "session-start")
    assert m["core.time_to_first_valid_ms"]["value_num"] >= 0.0


def test_auto_custom_duration_always_emitted(tmp_path, monkeypatch):
    """skills.duration_ms is auto-emitted for every session (emit-ahead)."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)):
        pass
    m = _local_metrics(evals_root, "session-start")
    assert m["skills.duration_ms"]["value_num"] >= 0.0
    assert m["skills.duration_ms"]["unit"] == "ms"


def test_auto_custom_error_class_on_failure(tmp_path, monkeypatch):
    """skills.error_class carries the exception class name on failure; absent on success."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with pytest.raises(ValueError):
        with SkillEval("handoff", domain="d", project="p", evals_root=str(evals_root)):
            raise ValueError("boom")
    m = _local_metrics(evals_root, "handoff")
    assert m["skills.error_class"]["value_text"] == "ValueError"
    with SkillEval("handoff", domain="d", project="p", evals_root=str(evals_root)):
        pass
    ok = list((evals_root / "handoff" / "sessions").glob("*.json"))
    latest = max(ok, key=lambda p: p.stat().st_mtime)
    assert "skills.error_class" not in {mm["key"] for mm in json.loads(latest.read_text())["metrics"]}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py::test_local_write_contains_all_five_core -v`
Expected: FAIL — core.* absent from local write.

- [ ] **Step 3: Implement in BOTH copies.**

3a. In `__init__`, add signal fields (after `self._metrics: list[dict] = []`):

```python
        self._start_dt: Optional[datetime] = None
        self._op_type_valid: Optional[bool] = None
        self._fallback_used: bool = False
        self._error_class: Optional[str] = None
```

3b. In `__enter__`, capture the start datetime (keep the isoformat string too):

```python
    def __enter__(self) -> "SkillEval":
        self._start_dt = datetime.now(timezone.utc)
        self._started_at = self._start_dt.isoformat()
        return self
```

3c. Add the two call-site signal methods and the finalize helper (place after `metric`):

```python
    def record_op_type(self, valid: bool) -> None:
        """Call-site signal: was the output schema-valid? Drives core.op_type_correct_rate."""
        self._op_type_valid = valid

    def record_fallback(self, used: bool = True) -> None:
        """Call-site signal: was a degraded/fallback path taken? Drives core.deflection_rate."""
        self._fallback_used = used
        self.metric("skills.fallback_used", value_bool=used, level="business")

    def _core_metrics(self, status: str, ended_at: str) -> list[dict]:
        """The 5 mandatory core.* for this session (real values + honest proxies)."""
        success = status == "success"
        if self._op_type_valid is not None:
            op_type = 1.0 if self._op_type_valid else 0.0
        else:
            op_type = 1.0 if success else 0.0  # proxy: no schema signal from call-site
        if self._start_dt is not None:
            duration_ms = (
                datetime.fromisoformat(ended_at) - self._start_dt
            ).total_seconds() * 1000.0
        else:
            duration_ms = 0.0
        return [
            {"key": "core.task_success", "value_bool": success, "level": "integration"},
            {"key": "core.op_type_correct_rate", "value_num": op_type, "level": "unit"},
            {"key": "core.deflection_rate",
             "value_num": 0.0 if self._fallback_used else 1.0, "level": "business"},
            {"key": "core.time_to_first_valid_ms",
             "value_num": duration_ms, "level": "integration", "unit": "ms"},  # proxy: script wall-clock
            {"key": "core.tool_call_success_rate",
             "value_num": 1.0 if success else 0.0, "level": "unit"},  # proxy: script success
        ]

    def _auto_custom(self, status: str, ended_at: str) -> list[dict]:
        """Cross-class custom metrics emitted for every session (emit-ahead, D3)."""
        out: list[dict] = []
        if self._start_dt is not None:
            duration_ms = (
                datetime.fromisoformat(ended_at) - self._start_dt
            ).total_seconds() * 1000.0
            out.append({"key": "skills.duration_ms", "value_num": duration_ms,
                        "level": "integration", "unit": "ms"})
        if self._error_class:
            out.append({"key": "skills.error_class",
                        "value_text": self._error_class, "level": "unit"})
        return out

    def _finalize_metrics(self, status: str, ended_at: str) -> list[dict]:
        """Merge caller metrics with core.* + auto-custom; caller keys override the proxy."""
        caller_keys = {m["key"] for m in self._metrics}
        auto = self._core_metrics(status, ended_at) + self._auto_custom(status, ended_at)
        extra = [c for c in auto if c["key"] not in caller_keys]
        return self._metrics + extra
```

3d. Rewrite `_write_local` to write finalized metrics (change its signature to take the list):

```python
    def _write_local(self, status: str, ended_at: str, metrics: list[dict]) -> None:
        root = Path(self.evals_root) if self.evals_root else Path.home() / ".h2t" / "evals"
        sessions_dir = root / self.skill / "sessions"
        try:
            sessions_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing = list(sessions_dir.glob(f"{self.skill[:2]}-{now_str}-*.json"))
        seq = len(existing) + 1
        prefix = self.skill[:2]
        filepath = sessions_dir / f"{prefix}-{now_str}-{seq:03d}.json"

        record = {
            "skill": self.skill,
            "domain": self.domain,
            "project": self.project,
            "status": status,
            "started_at": self._started_at,
            "ended_at": ended_at,
            "metrics": metrics,
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
```

3e. Update `__exit__` to finalize once and pass to both paths:

```python
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._error_class = exc_type.__name__ if exc_type is not None else None
        try:
            if self._mode in ("local", "push"):
                status = "failure" if exc_type else "success"
                ended_at = datetime.now(timezone.utc).isoformat()
                final = self._finalize_metrics(status, ended_at)
                self._write_local(status, ended_at, final)
                if self._mode == "push":
                    self._send_central(status, final)
        except Exception:
            pass  # never crash a skill for eval failure
        # ... (skill_graph block unchanged) ...
```

(Keep the existing `skill_graph.add_lesson` block and `return False` exactly as-is.)

- [ ] **Step 3g: Fix the stale monkeypatch signature.** The existing test
      `test_push_with_absent_sdk_degrades_to_local` monkeypatches `_send_central` with the OLD 2-arg
      signature — after this task the real call is `_send_central(status, final)`, so a mismatched stub
      would raise `TypeError` (silently swallowed → test passes for the wrong reason). Update it in
      `lib/eval/test_session.py`:

```python
    def _boom(self, status, metrics):
        raise ImportError("no sdk")
```

3f. Rewrite `_send_central` to consume the finalized list (REMOVE the inline core.* block at
`:208-213`; core.* now come from `final`):

```python
    def _send_central(self, status: str, metrics: list[dict]) -> None:
        """Send to h2t-evals SDK. Silent on any failure."""
        try:
            from h2t_evals.sdk import EvalClient, EvalSession
        except ImportError:
            return

        service_url = os.environ.get("H2T_EVALS_SERVICE_URL", "http://127.0.0.1:8088")
        token = os.environ.get("H2T_EVALS_TOKEN", "")
        spool = os.environ.get(
            "H2T_EVALS_SPOOL",
            str(Path.home() / ".h2t" / "evals" / ".h2t_evals_spool.db"),
        )
        try:
            client = EvalClient(service_url=service_url, token=token, spool_path=spool)
            source = f"{self.skill}:v{self.plugin_version}" if self.plugin_version else self.skill
            s = EvalSession(
                client=client,
                repo=self.project,
                framework="h2t-skill",
                source=source,
                eval_set_id="skills-session-baseline-v1",
                host=platform.node().lower().split(".")[0],
                run_env=os.environ.get("H2T_EVALS_RUN_ENV", "agent"),
            )
            s.start()
            for m in metrics:
                kwargs = {k: v for k, v in m.items() if k != "key"}
                kwargs.setdefault("level", "unit")
                s.metric(m["key"], **kwargs)
            s.finish(status=status)
            client.flush(limit=200)
        except Exception:
            pass  # never crash a skill for eval failure
```

(Note: `eval_set_id` stays the hardcoded literal here until Task 3 replaces it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py -v`
Expected: PASS (all, incl. the 6 new tests).

- [ ] **Step 5: Parity + full suite** (per session.py discipline)

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_eval_vendored_parity.py -v`
Expected: PASS.
Run: `C:/dev/h2t-skills/.venv/Scripts/pytest`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add lib/eval/session.py plugins/h2t-core/lib/eval/session.py lib/eval/test_session.py
git commit -m "feat(eval): core.* computed once, written to local+central, stubs removed (#306)"
```

---

## Task 3 (D5): skill→class map module + per-class `eval_set`

**Files:**
- Create: `lib/eval/skill_class.py`
- Create: `plugins/h2t-core/lib/eval/skill_class.py` (vendored copy — byte-identical)
- Create: `lib/eval/test_skill_class.py`
- Modify: `lib/eval/session.py` + vendored copy (use the map for `eval_set_id`)
- Modify: `tests/core/test_eval_vendored_parity.py` (guard the new sibling)
- Modify: `evals/repo.toml` (`default_eval_set_id`)
- Test: `lib/eval/test_skill_class.py`, `lib/eval/test_session.py`

**Why (A3 eng-review):** the eval_set must be one source of truth (module constant), not duplicated at
call-sites. `eval_set_id` is a free string (no FK/registration) → per-class needs NO VPS precondition.

- [ ] **Step 1: Write the failing test** — create `lib/eval/test_skill_class.py`:

```python
from lib.eval.skill_class import eval_set_for, skill_class


def test_gather_skills_map_to_gather_eval_set():
    for s in ("session-start", "handoff", "init-project"):
        assert skill_class(s) == "gather"
        assert eval_set_for(s) == "skills-gather-baseline-v1"


def test_integration_skills_map_to_integration_eval_set():
    for s in ("connectors", "research", "drive", "meetgeek", "telegram", "drawio"):
        assert skill_class(s) == "integration"
        assert eval_set_for(s) == "skills-integration-baseline-v1"


def test_unknown_skill_defaults_to_prompt():
    assert skill_class("mystery-skill") == "prompt"
    assert eval_set_for("mystery-skill") == "skills-prompt-baseline-v1"
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_skill_class.py -v`
Expected: FAIL — `ModuleNotFoundError: lib.eval.skill_class`.

- [ ] **Step 3: Create the module in BOTH trees** — `lib/eval/skill_class.py` AND
      `plugins/h2t-core/lib/eval/skill_class.py` (identical content; source = audit §2.2):

```python
"""Single source of truth: skill name → class → eval_set_id.

Classes: gather | integration | prompt. Used by SkillEval to pick the per-class
eval_set. Free-string eval_set (no registration) → no VPS precondition (#309).
"""

_GATHER = {
    "session-start", "handoff", "init-project",
    "scaffold-project", "project-audit", "setup", "agent-profile", "autonomous-run",
}
_INTEGRATION = {
    "connectors", "drive", "meetgeek", "research", "telegram",
    "docs-lint", "docs-init", "docs-index", "docs-cleanup", "docs-sync-labels",
    "milestone-closure", "drawio",
    "convert-meeting-transcript", "process-transcripts", "youtube-transcript",
    "gmail", "notion", "calendar", "daily-brief",
}


def skill_class(skill: str) -> str:
    if skill in _GATHER:
        return "gather"
    if skill in _INTEGRATION:
        return "integration"
    return "prompt"


def eval_set_for(skill: str) -> str:
    return f"skills-{skill_class(skill)}-baseline-v1"
```

- [ ] **Step 4: Run to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_skill_class.py -v`
Expected: PASS.

- [ ] **Step 5: Wire the map into `SkillEval` (BOTH copies).** In `session.py`, add a relative import
      near the top of the module body (relative import keeps `test_session_imports_only_stdlib` green —
      it only checks `node.level == 0`):

```python
from .skill_class import eval_set_for
```

In `__init__`, after `self._mode = resolve_mode()`, add:

```python
        self._eval_set = eval_set_for(skill)
```

In `_send_central`, replace `eval_set_id="skills-session-baseline-v1",` with:

```python
                eval_set_id=self._eval_set,
```

- [ ] **Step 6: Add a session test** — append to `lib/eval/test_session.py`:

```python
def test_eval_set_resolved_per_class():
    from lib.eval.skill_class import eval_set_for
    ev = SkillEval("research", domain="d", project="p")
    assert ev._eval_set == eval_set_for("research") == "skills-integration-baseline-v1"
    ev2 = SkillEval("handoff", domain="d", project="p")
    assert ev2._eval_set == "skills-gather-baseline-v1"
```

- [ ] **Step 7: Extend the parity guard** — replace `tests/core/test_eval_vendored_parity.py` body so it
      guards every vendored sibling:

```python
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VENDORED = ["session.py", "skill_class.py"]


@pytest.mark.parametrize("name", VENDORED)
def test_eval_vendored_parity(name):
    """The vendored plugin copy (the runtime path) must match canonical root."""
    root = (ROOT / "lib" / "eval" / name).read_text(encoding="utf-8")
    vendored = (ROOT / "plugins" / "h2t-core" / "lib" / "eval" / name).read_text(encoding="utf-8")
    assert root == vendored, f"lib/eval/{name} drifted from vendored copy; re-sync"
```

- [ ] **Step 8: Update `evals/repo.toml`** — change the default line to the class scheme:

```toml
default_eval_set_id = "skills-gather-baseline-v1"
```

- [ ] **Step 9: Parity + full suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_eval_vendored_parity.py -v`
Expected: PASS (both params).
Run: `C:/dev/h2t-skills/.venv/Scripts/pytest`
Expected: all green.

- [ ] **Step 10: Commit**

```bash
git add lib/eval/skill_class.py plugins/h2t-core/lib/eval/skill_class.py lib/eval/test_skill_class.py lib/eval/session.py plugins/h2t-core/lib/eval/session.py lib/eval/test_session.py tests/core/test_eval_vendored_parity.py evals/repo.toml
git commit -m "feat(eval): per-class eval_set from single skill->class map (#309)"
```

---

## Task 4 (D9): replace seq-glob filename with collision-free timestamp+uuid

**Files:**
- Modify: `lib/eval/session.py` — `_write_local` filename (add `import uuid`)
- Modify: `plugins/h2t-core/lib/eval/session.py` (same — vendored)
- Test: `lib/eval/test_session.py`

**Why (P1 eng-review):** `_write_local` globs the sessions dir for a seq number on every write → O(n) in
file count; at ~15 hot entrypoints this becomes a hotspot. Replace with a per-write timestamp+uuid name
(no glob). Existing files are NOT migrated (name is only for local inspection; nothing parses it).

- [ ] **Step 1: Write the failing test** — append to `lib/eval/test_session.py`:

```python
def test_write_local_no_collision_without_glob(tmp_path, monkeypatch):
    """Many same-skill/same-day sessions produce distinct files (no seq-glob)."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    for _ in range(5):
        with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)):
            pass
    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    assert len(files) == 5  # all distinct, none overwritten


def test_write_local_filename_has_no_seq_suffix(tmp_path, monkeypatch):
    """Filename no longer uses the 3-digit seq scheme (…-NNN.json)."""
    import re
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("handoff", domain="d", project="p", evals_root=str(evals_root)):
        pass
    name = list((evals_root / "handoff" / "sessions").glob("*.json"))[0].name
    assert not re.search(r"-\d{3}\.json$", name)
```

- [ ] **Step 2: Run to verify failure**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py::test_write_local_filename_has_no_seq_suffix -v`
Expected: FAIL — current name ends in `-001.json`.

- [ ] **Step 3: Implement in BOTH copies.** Add `import uuid` to the import block. Replace the filename
      construction in `_write_local` (the `now_str`/`existing`/`seq`/`filepath` lines) with:

```python
        prefix = self.skill[:2]
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S-%f")
        filepath = sessions_dir / f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}.json"
```

(Removes the `sessions_dir.glob(...)` call entirely.)

- [ ] **Step 4: Run to verify pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py -v`
Expected: PASS.

- [ ] **Step 5: Parity + full suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_eval_vendored_parity.py -v`
Expected: PASS.
Run: `C:/dev/h2t-skills/.venv/Scripts/pytest`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add lib/eval/session.py plugins/h2t-core/lib/eval/session.py lib/eval/test_session.py
git commit -m "perf(eval): drop per-write seq-glob for timestamp+uuid filename (#313)"
```

---

## Task 5 (D7): delete vestigial `record_eval` (×3) + dead `estimate_tokens`

**Files:**
- Delete: `lib/gather/eval.py`, `plugins/h2t/lib/gather/eval.py`, `plugins/h2t-core/lib/gather/eval.py`
- Delete: `lib/gather/test_eval.py`, `plugins/h2t/lib/gather/test_eval.py`, `plugins/h2t-core/lib/gather/test_eval.py`
- Modify: `lib/gather/__init__.py`, `plugins/h2t/lib/gather/__init__.py`, `plugins/h2t-core/lib/gather/__init__.py`

**Why:** `record_eval` is superseded by `SkillEval` (no live caller). `estimate_tokens` in the same file
has no live caller either (only its own `test_eval.py`); `main.py` computes tokens inline. Both go.

- [ ] **Step 1: Confirm no live callers (repo-wide, excluding worktrees/build)**

Run: `grep -rn "record_eval\|estimate_tokens" --include=*.py lib plugins tests scripts h2t_ops`
Expected: matches ONLY in the six files slated for delete/edit above (defs, `__init__` exports,
`test_eval.py`). If any OTHER file calls them → STOP, escalate (relocate instead of delete).

- [ ] **Step 2: Write the guard test** — append to `lib/eval/test_session.py`:

```python
def test_record_eval_module_removed():
    """The vestigial gather.eval module and its exports are gone."""
    import importlib
    import lib.gather as g
    assert not hasattr(g, "record_eval")
    assert not hasattr(g, "estimate_tokens")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("lib.gather.eval")
```

- [ ] **Step 3: Run to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py::test_record_eval_module_removed -v`
Expected: FAIL — `lib.gather.eval` still imports; `record_eval` still exported.

- [ ] **Step 4: Delete the files (git rm)** — six deletes, one Bash call each:

```bash
git rm lib/gather/eval.py lib/gather/test_eval.py
```
```bash
git rm plugins/h2t/lib/gather/eval.py plugins/h2t/lib/gather/test_eval.py
```
```bash
git rm plugins/h2t-core/lib/gather/eval.py plugins/h2t-core/lib/gather/test_eval.py
```

- [ ] **Step 5: Remove exports from all three `__init__.py`.** In each of `lib/gather/__init__.py`,
      `plugins/h2t/lib/gather/__init__.py`, `plugins/h2t-core/lib/gather/__init__.py`:
  - delete the line `from .eval import record_eval, estimate_tokens`
  - delete `"record_eval", "estimate_tokens",` from the `__all__` list.

- [ ] **Step 5b: Remove doc/README references (D7 requires this).**

Run: `grep -rln "record_eval\|estimate_tokens" --include=*.md . `
For each match outside build artifacts/worktrees (e.g. a `lib/gather/README.md` or docs listing the
gather API), delete the specific line/section referencing the removed functions. If there are no `.md`
matches, this step is a no-op — record that.

- [ ] **Step 6: Run to verify pass + full suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py::test_record_eval_module_removed -v`
Expected: PASS.
Run: `C:/dev/h2t-skills/.venv/Scripts/pytest`
Expected: all green (no import errors from removed module).

- [ ] **Step 7: Commit**

```bash
git add -A lib/gather plugins/h2t/lib/gather plugins/h2t-core/lib/gather lib/eval/test_session.py
git commit -m "chore(eval): remove vestigial record_eval/estimate_tokens x3 (#310)"
```

---

## Task 6 (D4): unify research cost on `SkillEval`, deprecate `post_telemetry`

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py` — replace the `post_telemetry(...)`
  call at `:857-876` with a `SkillEval` emit; keep `post_telemetry` def but mark deprecated/unused OR
  remove per Step 4.
- Test: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

**Why (Codex-P2, interim per-sub-call):** research writes cost to a bespoke POST `/api/telemetry/research`
that does not exist on the service → cost never persists centrally. Wrap the existing seam in `SkillEval`
and emit `skills.research_cost_usd` from the envelope. Per-invocation aggregation is a documented
follow-up (Task 8); this is per-sub-call.

**Import mechanism (CRITICAL — do NOT use `spec_from_file_location`):** `session.py` uses a relative
import `from .skill_class import eval_set_for` (Task 3). A module loaded via
`spec_from_file_location(name, path)` has no package context, so that relative import raises
`ImportError: attempted relative import with no known parent package` — silently swallowed in `_emit_eval`,
telemetry lost. Instead, put the vendored `lib` dir on `sys.path` and import `eval.session` as a proper
package (mirrors how the gather runtime already imports it — `lib/cli/main.py:30` `from eval.session import SkillEval`).
This is the shared thin-wrapper seam Task 8 reuses. Add a module-level loader:

- [ ] **Step 1: Write the failing test** — add to `plugins/h2t-ops/skills/research/tests/test_exa_search.py`
      (adapt to the file's existing import/style):

```python
def test_emit_eval_records_research_cost(tmp_path, monkeypatch):
    """_emit_eval writes a local SkillEval session carrying research cost + core.*."""
    import json
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path / "evals"))
    import exa_search
    envelope = {
        "status": "OK",
        "results": [1, 2, 3],
        "telemetry": {"total_cost_usd": 0.037, "total_latency_ms": 1200,
                      "attempts": [{"http": 200, "latency_ms": 1200, "error": None}]},
        "meta": {"timestamp": "2026-07-12T00:00:00Z"},
    }
    exa_search._emit_eval(envelope, exit_code=0, project="h2t-skills", mode="generic")
    files = list((tmp_path / "evals" / "research" / "sessions").glob("*.json"))
    assert len(files) == 1
    keys = {m["key"] for m in json.loads(files[0].read_text())["metrics"]}
    assert "skills.research_cost_usd" in keys
    assert "core.task_success" in keys
```

- [ ] **Step 2: Run to verify failure**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py::test_emit_eval_records_research_cost -v`
Expected: FAIL — `_emit_eval` does not exist.

- [ ] **Step 3: Implement.** Add the loader + `_emit_eval` near the other module-level helpers in
      `exa_search.py` (mirror the `_load_h2t_secrets` candidate-path pattern; `SESSION_PY` points at the
      vendored copy):

```python
_SkillEval = None


def _load_skilleval():
    """Load SkillEval from the vendored h2t-core copy by putting its lib/ on sys.path
    and importing the package (relative imports inside session.py then resolve)."""
    global _SkillEval
    if _SkillEval is not None:
        return _SkillEval
    here = Path(__file__).resolve()
    for base in here.parents:
        lib_dir = base / "plugins" / "h2t-core" / "lib"
        if (lib_dir / "eval" / "session.py").exists():
            if str(lib_dir) not in sys.path:
                sys.path.insert(0, str(lib_dir))
            try:
                mod = importlib.import_module("eval.session")
            except Exception:
                return None
            _SkillEval = mod.SkillEval
            return _SkillEval
    return None


def _emit_eval(envelope: dict[str, Any], exit_code: int, project: str, mode: str) -> None:
    """Emit an L1 SkillEval session for one research sub-call. Never raises."""
    SkillEval = _load_skilleval()
    if SkillEval is None:
        return
    root = os.environ.get("H2T_EVALS_ROOT")
    tel = envelope.get("telemetry", {})
    status_ok = envelope.get("status") in ("OK", "DEGRADED")
    try:
        with SkillEval("research", domain="ops", project=project, evals_root=root) as ev:
            ev.record_op_type(status_ok)
            if envelope.get("status") == "DEGRADED":
                ev.record_fallback()
            ev.metric("skills.research_cost_usd",
                      value_num=float(tel.get("total_cost_usd", 0.0)),
                      level="business", unit="usd")
            ev.metric("skills.api_latency_ms",
                      value_num=float(tel.get("total_latency_ms", 0.0)),
                      level="integration", unit="ms")
            ev.metric("skills.records_returned",
                      value_num=float(len(envelope.get("results", []))), level="unit")
            if exit_code != 0:
                raise RuntimeError("research failed")  # marks status=failure
    except Exception:
        pass
```

Note: the `raise` inside the `with` is caught by the outer `try` — it exists only to flip
`SkillEval` status to `failure` on non-zero exit; it never escapes `_emit_eval`.

- [ ] **Step 4: Replace the `post_telemetry` call.** In `_run_search`, replace the entire
      `post_telemetry(event={...}, buffer_path=...)` block (`:857-876`) with:

```python
    # Telemetry unified on SkillEval (bespoke post_telemetry / H2T_EVALS_URL deprecated).
    _emit_eval(envelope, exit_code=exit_code, project=args.project, mode=args.mode)
```

Delete the now-dead `post_telemetry` function (`:632-670`) and the `sha256` import if it becomes unused
(check: `grep -n "sha256" exa_search.py` → if only the removed block used it, drop the import).

- [ ] **Step 5: Run the research test suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v`
Expected: PASS (new test green; update/remove any old `post_telemetry` test that now references the
deleted function — if an old test asserts `awaiting_endpoint`/`disabled`, delete it, that contract is gone).

- [ ] **Step 6: Connector suite + full suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research`
Expected: green.
Run: `C:/dev/h2t-skills/.venv/Scripts/pytest`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "feat(research): unify cost telemetry on SkillEval, drop dead post_telemetry (#312)"
```

---

## Task 7 (D6): author minimal parse-valid repo-assets

**Files:**
- Create: `evals/unit_cases.jsonl`, `evals/integration_cases.jsonl`, `evals/business_kpi.toml`
- Create: `tests/core/test_evals_repo_assets.py`

**Why:** the repo is missing the standard case-files. This run authors minimal, real, parse-valid files
+ a parse-test. The `validate-repo` central gate is `#305`/push (reads central DB) — NOT in scope here.

- [ ] **Step 1: Write the failing test** — create `tests/core/test_evals_repo_assets.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_evals_repo_assets.py -v`
Expected: FAIL — files do not exist.

- [ ] **Step 3: Create `evals/unit_cases.jsonl`** (one case per gather/integration unit metric):

```json
{"id": "gather-source-success-baseline", "eval_set_id": "skills-gather-baseline-v1", "metric": "core.op_type_correct_rate", "input": {"skill": "session-start"}, "expected": {"min": 0.9}}
{"id": "integration-op-type-baseline", "eval_set_id": "skills-integration-baseline-v1", "metric": "core.op_type_correct_rate", "input": {"skill": "research"}, "expected": {"min": 0.9}}
```

- [ ] **Step 4: Create `evals/integration_cases.jsonl`:**

```json
{"id": "session-start-task-success", "eval_set_id": "skills-gather-baseline-v1", "metric": "core.task_success", "input": {"skill": "session-start"}, "expected": {"equals": true}}
{"id": "research-task-success", "eval_set_id": "skills-integration-baseline-v1", "metric": "core.task_success", "input": {"skill": "research", "mode": "generic"}, "expected": {"equals": true}}
```

- [ ] **Step 5: Create `evals/business_kpi.toml`:**

```toml
# Business KPIs (non-blocking, §10). Cadence: weekly review.
[kpi.research_cost_usd]
metric = "skills.research_cost_usd"
aggregation = "sum"
window = "7d"
description = "Weekly Exa research spend across sessions"

[kpi.deflection_rate]
metric = "core.deflection_rate"
aggregation = "avg"
window = "7d"
description = "Fraction of sessions completing without a manual fallback"
```

- [ ] **Step 6: Run to verify pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_evals_repo_assets.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add evals/unit_cases.jsonl evals/integration_cases.jsonl evals/business_kpi.toml tests/core/test_evals_repo_assets.py
git commit -m "feat(evals): author minimal parse-valid repo-assets (#307)"
```

---

## Task 8 (D3 gather metric): emit `skills.sources_failed_count` at the gather call-site

**Files:**
- Modify: `lib/cli/main.py:101-109` (the `SkillEval` block in `_run_gather`)
- Test: `tests/core/` — new `tests/core/test_gather_eval_metrics.py`

**Why:** the gather-class custom metric `skills.sources_failed_count` (taxonomy §4.2) is declared but not
emitted. The call-site already computes `sources_failed`. Emit it (emit-ahead).

- [ ] **Step 1: Write the failing test** — create `tests/core/test_gather_eval_metrics.py`:

```python
import json
from pathlib import Path

from lib.eval.session import SkillEval


def test_gather_emits_sources_failed_count(tmp_path, monkeypatch):
    """The gather call-site pattern emits skills.sources_failed_count."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    sources_failed = ["github"]
    with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.sources_failed_count", value_num=float(len(sources_failed)), level="unit")
    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    m = {x["key"]: x for x in json.loads(Path(files[0]).read_text())["metrics"]}
    assert m["skills.sources_failed_count"]["value_num"] == 1.0
```

- [ ] **Step 2: Run to verify it passes as a pattern test** (it exercises SkillEval directly)

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_gather_eval_metrics.py -v`
Expected: PASS (this validates the emit shape; Step 3 wires it into the real call-site).

- [ ] **Step 3: Wire into `lib/cli/main.py`.** In the `SkillEval` block (`:102-107`), add one metric line
      after the `skills.token_consumption` line:

```python
        with SkillEval(skill, domain=domain, project=proj_id) as ev:
            ev.metric(
                "skills.gather_source_success_rate",
                value_num=1.0 - len(sources_failed) / max(len(sources_used), 1),
            )
            ev.metric("skills.token_consumption", value_num=float(len(str(data)) // 4))
            ev.metric("skills.sources_failed_count",
                      value_num=float(len(sources_failed)), level="unit")
```

- [ ] **Step 4: Full suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add lib/cli/main.py tests/core/test_gather_eval_metrics.py
git commit -m "feat(eval): gather emits skills.sources_failed_count (#312)"
```

---

## Task 9 (D8 remainder): documented follow-up — instrument remaining integration skills

**This task is NOT executed in this run — it is the recorded, bounded follow-up (see Scope note).**

The shared loader pattern from Task 6 (`_load_skilleval` + a thin `_emit_eval`) is the reusable seam.
Remaining integration skills to instrument, each following the Task 6 shape (load SkillEval → `with`
→ `record_op_type`/`record_fallback` → domain custom metrics → non-zero exit ⇒ failure):

- [ ] connectors (`h2t_ops` connector CLIs) — emit `skills.error_class` (exit codes 1–6), `skills.duration_ms`
- [ ] drive / meetgeek / telegram / gmail / notion / calendar — `skills.duration_ms`, `skills.api_latency_ms`, `skills.records_returned`
- [ ] drawio (generate/export) — `skills.duration_ms`
- [ ] docs-lint / docs-init / docs-index / docs-cleanup / docs-sync-labels / milestone-closure — `skills.duration_ms`
- [ ] edu-transcripts (convert-meeting-transcript / process-transcripts / youtube-transcript) — `skills.duration_ms`, `skills.records_returned`

Open question from spec (operator): all-at-once vs research+connectors first. Recorded, not resolved here.

---

## Self-Review (author checklist — completed)

**Spec coverage:** D1→Task 2; D3→Task 1 (signature) + Task 2 (`skills.fallback_used`, auto `skills.duration_ms`
+ `skills.error_class`) + Task 6 (research custom metrics) + Task 8 (gather `skills.sources_failed_count`);
D4→Task 6; D5→Task 3; D6→Task 7; D7→Task 5; D8→Task 6 (research) + Task 9 (deferred, logged); D9→Task 4.
D2 = `#305`, out of scope (not planned). §4 custom metrics: cross (`duration_ms`/`fallback_used`/`error_class`)
Task 2; gather (`gather_source_success_rate`/`token_consumption` already; `sources_failed_count`) Task 8;
integration (`research_cost_usd`/`api_latency_ms`/`records_returned`) Task 6. Acceptance items: local 5×core.* (Task 2),
`metric()` level/unit both paths (Tasks 1–2), research cost via SkillEval + post_telemetry gone (Task 6),
custom metrics emitted local (Tasks 2,6), per-class eval_set single module (Task 3), repo-assets parse-valid
(Task 7), no per-write glob + parity green (Tasks 3,4), record_eval removed ×3 (Task 5), SkillEval-never-crashes
invariant preserved (every emit wrapped in try/except; `__exit__` unchanged in its swallow behavior).

**Placeholder scan:** none — every code step shows full code; every run step shows command + expected.

**Type consistency:** `_finalize_metrics(status, ended_at)` used by both `_write_local(status, ended_at, metrics)`
and `_send_central(status, metrics)` — signatures match Task 2. `eval_set_for`/`skill_class` names consistent
across Task 3 and its tests. `record_op_type`/`record_fallback` names consistent across Tasks 2 and 6.

**Out-of-scope guardrails restated:** no metric-def registration, no push, no `validate-repo` green, no
identity/namespace rename — all `#305`.
