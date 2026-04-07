"""SkillGraphClient — thin HTTP wrapper over h2t-graphs API.

Token policy (project-scoped, see h2t-graphs#98):
  query()       → H2T_SKILL_GRAPH_TOKEN_RO
  add_lesson()  → H2T_SKILL_GRAPH_TOKEN_RW
  add_pattern() → H2T_SKILL_GRAPH_TOKEN_RW

Source IDs: {H2T_SKILL_GRAPH_PROJECT_ID}-{alias}
All credentials loaded from ~/.dor/secrets.env (falls back to env vars).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)

_NODES_PATH = "/api/nodes"    # POST — add node (auto-embeds on write)
_QUERY_PATH = "/api/query"    # GET  — keyword + semantic search
_EDGES_PATH = "/api/edges"    # POST — add crosslink edges

VALID_PATTERN_TYPES = frozenset({
    "hook", "etl", "pipeline", "generation",
    "eval", "marketplace", "trigger", "eval-derived",
})


def _load_secrets(secrets_path: Optional[str] = None) -> dict[str, str]:
    """Load token/URL from secrets.env file, fall back to env vars."""
    path = Path(secrets_path) if secrets_path else Path.home() / ".dor" / "secrets.env"
    result: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    # env vars override file values
    for key in ("H2T_GRAPHS_URL", "H2T_SKILL_GRAPH_PROJECT_ID",
                "H2T_SKILL_GRAPH_TOKEN_RO", "H2T_SKILL_GRAPH_TOKEN_RW"):
        if os.environ.get(key):
            result[key] = os.environ[key]
    return result


class SkillGraphClient:
    def __init__(self, url: Optional[str] = None, secrets_path: Optional[str] = None):
        self._secrets = _load_secrets(secrets_path)
        self.url = (
            url
            or self._secrets.get("H2T_GRAPHS_URL")
            or "https://graphs.lichtpfadstudio.com"
        ).rstrip("/")
        self._project_id = self._secrets.get("H2T_SKILL_GRAPH_PROJECT_ID", "")

    def _source_id(self, alias: str) -> str:
        """Returns project-scoped source ID: {project_id}-{alias}. See h2t-graphs#98."""
        return f"{self._project_id}-{alias}" if self._project_id else alias

    @property
    def _ro_token(self) -> str:
        return self._secrets.get("H2T_SKILL_GRAPH_TOKEN_RO", "")

    @property
    def _rw_token(self) -> str:
        return self._secrets.get("H2T_SKILL_GRAPH_TOKEN_RW", "")

    def _get(self, path: str, params: dict, token: str) -> dict:
        query = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"{self.url}{path}?{query}",
            headers={"X-H2T-Token": token},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def _post(self, path: str, data: dict, token: str) -> dict:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=body,
            headers={"X-H2T-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def query(self, context: str, skill_name: Optional[str] = None,
              sources: tuple = ("skill-patterns", "skill-lessons"),
              top_k: int = 5) -> list[dict]:
        results: list[dict] = []
        for source in sources:
            params: dict = {"source": self._source_id(source), "semantic": context, "limit": top_k}
            try:
                data = self._get(_QUERY_PATH, params, self._ro_token)
                results.extend(data.get("results", []))
            except (urllib.error.URLError, OSError, json.JSONDecodeError):
                pass  # never crash a skill for graph failure
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:top_k]

    def add_lesson(self, skill_name: str, trigger: str, resolution: str,
                   lesson_type: str = "bug", session_id: Optional[str] = None,
                   eval_score_before: Optional[float] = None,
                   eval_score_after: Optional[float] = None,
                   crosslinks: Optional[list[dict]] = None) -> str:
        content: dict = {
            "lesson_type": lesson_type,
            "skill_name": skill_name,
            "trigger": trigger,
            "resolution": resolution,
            "session_id": session_id or "",
            "date": datetime.now(timezone.utc).isoformat(),
        }
        if eval_score_before is not None:
            content["eval_score_before"] = eval_score_before
        if eval_score_after is not None:
            content["eval_score_after"] = eval_score_after
        if crosslinks:
            content["crosslinks"] = crosslinks

        result = self._post(_NODES_PATH, {"source_id": self._source_id("skill-lessons"), "content": content},
                            self._rw_token)
        node_id: str = result.get("id", "")

        # patch reverse edges — eventual consistency, never raises
        if crosslinks and node_id:
            for link in crosslinks:
                try:
                    self._post(
                        _NODES_PATH,
                        {"source_id": self._source_id("skill-patterns"), "node_id": link["to"],
                         "patch": {"crosslinks": [{"to": node_id, "relation": link["relation"]}]}},
                        self._rw_token,
                    )
                except Exception as exc:
                    _log.warning("crosslink patch failed for node %s: %s", link.get("to"), exc)

        return node_id

    def add_pattern(self, pattern_type: str, title: str, body: str, source: str,
                    applies_to: Optional[list[str]] = None, confidence: float = 0.7,
                    source_url: Optional[str] = None,
                    tags: Optional[list[str]] = None) -> str:
        raise NotImplementedError
