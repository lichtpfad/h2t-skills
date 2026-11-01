"""Daily-brief task sections from the user's tasks database (#507).

Ranks by what a date means, not by how close it is. Rule 3 of the owner's task-priority
rule, in this order: the day's plan, the plan not done, external deadlines, checks that
are due, dates without a reason, the rest. A date nobody gave a reason for never reaches
HIGH, whatever it says.

The property names and select values are the user's: `notion.tasks_schema` in user.yaml.
No defaults — a schema in the code would be the author's database, and a missing key is
named instead of guessed.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from h2t_ops.core.errors import ConfigError

SCHEMA_KEY = "notion.tasks_schema"
_FIELDS = ("title", "due", "due_kind", "day", "done")
_KINDS = ("external", "check", "intent")
HIGH_WINDOW = timedelta(days=3)

SECTIONS = (
    ("planned_today", "Решил сделать сегодня"),
    ("plan_missed", "Не сделано из плана"),
    ("high", "HIGH"),
    ("check", "Проверить"),
    ("unfounded", "Сроки без основания"),
    ("med_low", "MED / LOW"),
    ("rest", "Остальное"),
)

_EXAMPLE = ("notion:\n  tasks_schema:\n    title: <title property>\n    due: <deadline date>\n"
            "    due_kind: <deadline type select>\n    day: <day-plan date>\n    done: <done checkbox>\n"
            "    kinds: {external: <option>, check: <option>, intent: <option>}")


def schema(raw: Any, source: str) -> dict:
    """The validated schema, or a ConfigError naming every missing key."""
    if not isinstance(raw, dict):
        raise ConfigError(f"{SCHEMA_KEY} is not set in {source}", hint=f"add to {source}:\n{_EXAMPLE}")
    kinds = raw.get("kinds") if isinstance(raw.get("kinds"), dict) else {}
    missing = [f for f in _FIELDS if not raw.get(f)] + [f"kinds.{k}" for k in _KINDS if not kinds.get(k)]
    if missing:
        raise ConfigError(f"{SCHEMA_KEY} in {source} lacks {', '.join(missing)}",
                          hint=f"expected shape:\n{_EXAMPLE}")
    return {**{f: str(raw[f]) for f in _FIELDS}, "kinds": {str(kinds[k]): k for k in _KINDS}}


def done_filter(s: dict) -> dict:
    return {"property": s["done"], "checkbox": {"equals": False}}


def _date(prop: Any) -> date | None:
    start = ((prop or {}).get("date") or {}).get("start")
    return date.fromisoformat(start[:10]) if start else None


def task(row: dict, s: dict) -> dict:
    """One row as the fields the sections read; an unknown select value is kept, not mapped."""
    props = row.get("properties", {})
    title = "".join(t.get("plain_text", "") for t in (props.get(s["title"]) or {}).get("title", []))
    kind_name = ((props.get(s["due_kind"]) or {}).get("select") or {}).get("name")
    return {"id": row.get("id"), "title": title, "url": row.get("url"),
            "due": _date(props.get(s["due"])), "day": _date(props.get(s["day"])),
            "kind": s["kinds"].get(kind_name) if kind_name else None, "kind_name": kind_name,
            "done": bool((props.get(s["done"]) or {}).get("checkbox"))}


def _section(t: dict, today: date) -> str:
    if t["day"] == today:
        return "planned_today"
    if t["day"] and t["day"] < today:
        return "plan_missed"
    if t["due"] and not t["kind_name"]:
        return "unfounded"
    if t["kind"] == "external" and t["due"]:
        return "high" if t["due"] <= today + HIGH_WINDOW else "med_low"
    if t["kind"] == "check" and t["due"] and t["due"] <= today:
        return "check"
    return "rest"


def sections(tasks: list[dict], today: date) -> dict:
    """Each open task in exactly one section, the first that claims it; dated sections by date."""
    out: dict[str, list[dict]] = {key: [] for key, _ in SECTIONS}
    for t in tasks:
        if not t["done"]:
            out[_section(t, today)].append(t)
    for items in out.values():
        items.sort(key=lambda t: (t["due"] or t["day"] or date.max, t["title"]))
    return out


def render(out: dict, today: date) -> str:
    lines = [f"Tasks for {today.isoformat()}"]
    for key, label in SECTIONS:
        items = out[key]
        lines.append(f"\n### {label} ({len(items)})")
        for t in items:
            when = f" — срок {t['due'].isoformat()}" if t["due"] else ""
            day = f" · на день {t['day'].isoformat()}" if t["day"] and key == "plan_missed" else ""
            kind = f" · {t['kind_name']}" if t["kind_name"] else ""
            lines.append(f"- [{t['title']}]({t['url']}){when}{kind}{day}")
    return "\n".join(lines)


def to_json(out: dict, today: date) -> dict:
    def j(t):
        return {**t, "due": t["due"] and t["due"].isoformat(), "day": t["day"] and t["day"].isoformat()}
    return {"today": today.isoformat(), "order": [k for k, _ in SECTIONS],
            "sections": {k: [j(t) for t in v] for k, v in out.items()}}
