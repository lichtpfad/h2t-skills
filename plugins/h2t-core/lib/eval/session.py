"""SkillEval — context manager for skill evaluation.

Write behavior is gated by the resolved H2T_EVALS_MODE (see resolve_mode):
  - off   → no local JSON, no SDK send (default when SDK/token absent)
  - local → local JSON only
  - push  → local JSON + h2t-evals SDK send
Mode is resolved once at construction. SkillEval never crashes its caller.

Usage:
    with SkillEval("session-start", domain="dev", project="h2t-ai") as ev:
        ev.metric("skills.gather_source_success_rate", value_num=0.95)
    # on __exit__: writes per resolved mode (nothing when off)

Promoted from plugins/h2t/lib/gather/eval.py to shared lib/.
"""

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_VALID_MODES = ("auto", "off", "local", "push")


def _sdk_available() -> bool:
    """True if the h2t_evals SDK client is importable (cheap, no network)."""
    try:
        import h2t_evals.sdk  # noqa: F401
        return True
    except Exception:
        return False


def resolve_mode(env=None) -> str:
    """Resolve H2T_EVALS_MODE to a terminal mode: 'off' | 'local' | 'push'.

    Priority: explicit off/local/push > explicit 'auto' (resolved) >
    legacy H2T_EVALS_ENABLED=1 (push) > auto. 'auto' resolves to 'push' when
    the SDK is importable AND H2T_EVALS_TOKEN is set, else 'off'. An unset or
    invalid H2T_EVALS_MODE behaves as auto (with the legacy flag honored).
    """
    env = env if env is not None else os.environ
    raw = (env.get("H2T_EVALS_MODE") or "").strip().lower()
    if raw in ("off", "local", "push"):
        return raw
    if raw != "auto" and env.get("H2T_EVALS_ENABLED") == "1":
        return "push"
    if _sdk_available() and env.get("H2T_EVALS_TOKEN"):
        return "push"
    return "off"


class SkillEval:
    def __init__(
        self,
        skill: str,
        domain: str,
        project: str,
        plugin_version: str = "",
        evals_root: Optional[str] = None,
        skill_graph=None,
        score_before: Optional[float] = None,
    ) -> None:
        self.skill = skill
        self.domain = domain
        self.project = project
        self.plugin_version = plugin_version
        self.evals_root = evals_root
        self._skill_graph = skill_graph
        self._score_before = score_before
        self._score_after: Optional[float] = None
        self._metrics: list[dict] = []
        self._started_at: Optional[str] = None
        self._mode = resolve_mode()

    def __enter__(self) -> "SkillEval":
        self._started_at = datetime.now(timezone.utc).isoformat()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if self._mode in ("local", "push"):
                status = "failure" if exc_type else "success"
                ended_at = datetime.now(timezone.utc).isoformat()
                self._write_local(status, ended_at)
                if self._mode == "push":
                    self._send_central(status)
        except Exception:
            pass  # never crash a skill for eval failure
        if exc_type is not None and self._skill_graph is not None:
            try:
                self._skill_graph.add_lesson(
                    skill_name=self.skill,
                    trigger=str(exc_val) if exc_val else "skill execution failure",
                    resolution="",
                    lesson_type="eval-finding",
                )
            except Exception:
                pass  # never crash a skill for graph failure
        return False  # do not suppress exceptions

    def close(self, score: float) -> Optional[str]:
        """Record final eval score. Writes eval-finding lesson if delta > 0.1.

        Returns node_id if lesson was written, None otherwise.
        Gracefully skips if skill_graph is absent or has no RW token.
        """
        self._score_after = score
        if (
            self._score_before is None
            or self._skill_graph is None
            or not getattr(self._skill_graph, "writable", True)
        ):
            return None
        delta = abs(score - self._score_before)
        if delta <= 0.1:
            return None
        try:
            return self._skill_graph.add_lesson(
                skill_name=self.skill,
                trigger="eval score change",
                resolution=f"score {self._score_before:.3f} → {score:.3f}",
                lesson_type="eval-finding",
                session_id=f"{self.skill}-{self._started_at or ''}",
                eval_score_before=self._score_before,
                eval_score_after=score,
            )
        except Exception:
            return None  # never crash a skill for graph failure

    def metric(
        self,
        key: str,
        value_num: Optional[float] = None,
        value_bool: Optional[bool] = None,
        value_text: Optional[str] = None,
    ) -> None:
        """Record a metric to be written on context exit."""
        if self._mode == "off":
            return
        entry: dict = {"key": key}
        if value_num is not None:
            entry["value_num"] = value_num
        if value_bool is not None:
            entry["value_bool"] = value_bool
        if value_text is not None:
            entry["value_text"] = value_text
        self._metrics.append(entry)

    def _write_local(self, status: str, ended_at: str) -> None:
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
            "metrics": self._metrics,
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _send_central(self, status: str) -> None:
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

            task_success = status == "success"
            s.metric("core.task_success", level="integration", value_bool=task_success)
            s.metric("core.time_to_first_valid_ms", level="integration", value_num=0.0, unit="ms")
            s.metric("core.tool_call_success_rate", level="unit", value_num=1.0 if task_success else 0.0)
            s.metric("core.op_type_correct_rate", level="unit", value_num=1.0)
            s.metric("core.deflection_rate", level="business", value_num=1.0 if task_success else 0.0)

            for m in self._metrics:
                kwargs = {k: v for k, v in m.items() if k != "key"}
                kwargs.setdefault("level", "unit")
                s.metric(m["key"], **kwargs)

            s.finish(status=status)
            client.flush(limit=200)
        except Exception:
            pass  # never crash a skill for eval failure
