"""daily-brief task sections by deadline type (#507), against rows shaped like the Notion API."""
import json
from datetime import date, timedelta

import pytest

from h2t_ops.connectors.notion import brief
from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError

TODAY = date(2026, 11, 2)
RAW = {"title": "Задача", "due": "Срок", "due_kind": "Тип срока", "day": "На день", "done": "Готово",
       "kinds": {"external": "Внешний", "check": "Контроль", "intent": "Намерение"}}
S = brief.schema(RAW, "user.yaml")


def _d(days):
    return {"date": {"start": (TODAY + timedelta(days=days)).isoformat()}} if days is not None else {"date": None}


def row(title, *, due=None, kind=None, day=None, done=False):
    return {"id": title, "url": f"https://notion.so/{title}", "properties": {
        "Задача": {"title": [{"plain_text": title}]},
        "Срок": _d(due), "На день": _d(day), "Готово": {"checkbox": done},
        "Тип срока": {"select": {"name": kind} if kind else None}}}


def placed(*rows):
    out = brief.sections([brief.task(r, S) for r in rows], TODAY)
    return {t["title"]: key for key, items in out.items() for t in items}


def test_a_date_without_a_reason_never_reaches_high():
    got = placed(row("agent-set", due=-1), row("agent-set-today", due=0))
    assert got == {"agent-set": "unfounded", "agent-set-today": "unfounded"}


def test_the_day_plan_comes_first_even_without_a_deadline():
    assert placed(row("chosen", day=0))["chosen"] == "planned_today"
    assert placed(row("chosen-and-due", day=0, due=-5, kind="Внешний"))["chosen-and-due"] == "planned_today"


def test_a_past_day_plan_not_done_is_plan_missed_not_overdue():
    assert placed(row("yesterday", day=-1, due=10, kind="Внешний"))["yesterday"] == "plan_missed"


def test_external_is_high_when_overdue_or_within_three_days_else_med_low():
    got = placed(row("late", due=-40, kind="Внешний"), row("soon", due=3, kind="Внешний"),
                 row("later", due=4, kind="Внешний"))
    assert got == {"late": "high", "soon": "high", "later": "med_low"}


def test_a_check_shows_once_its_date_has_come():
    got = placed(row("due-check", due=0, kind="Контроль"), row("future-check", due=1, kind="Контроль"))
    assert got == {"due-check": "check", "future-check": "rest"}


def test_intent_and_undated_tasks_are_kept_not_dropped():
    got = placed(row("intent", due=2, kind="Намерение"), row("no-date"))
    assert got == {"intent": "rest", "no-date": "rest"}


def test_done_tasks_appear_nowhere():
    assert placed(row("finished", day=0, done=True)) == {}


def test_sections_keep_the_rule_order():
    assert [k for k, _ in brief.SECTIONS] == ["planned_today", "plan_missed", "high", "check",
                                             "unfounded", "med_low", "rest"]


@pytest.mark.parametrize("drop", ["day", "done", "kinds.check"])
def test_a_missing_schema_key_is_named(drop):
    raw = json.loads(json.dumps(RAW))
    if "." in drop:
        del raw["kinds"][drop.split(".")[1]]
    else:
        del raw[drop]
    with pytest.raises(ConfigError) as ei:
        brief.schema(raw, "user.yaml")
    assert drop in str(ei.value)


# --- the command ----------------------------------------------------------------------------

def _user_yaml(text):
    f = paths.config_dir() / "user.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def _cli(capsys, monkeypatch, rows, *extra):
    from h2t_ops.cli import dispatch
    from h2t_ops.connectors.notion import client

    seen = {}

    class Fake:
        def query_database_page(self, database_id, filter_dict=None, **_):
            seen.update(db=database_id, filter=filter_dict)
            return {"items": rows, "truncated": False}

    monkeypatch.setattr(client, "NotionClient", Fake)
    rc = dispatch(["notion", "brief-tasks", "--today", TODAY.isoformat(), *extra])
    out, err = capsys.readouterr()
    return rc, out, err, seen


SCHEMA_YAML = """notion:
  tasks_database_id: db-1
  tasks_schema:
    title: Задача
    due: Срок
    due_kind: Тип срока
    day: На день
    done: Готово
    kinds: {external: Внешний, check: Контроль, intent: Намерение}
"""


def test_cli_reads_open_tasks_of_the_configured_database(capsys, monkeypatch):
    _user_yaml(SCHEMA_YAML)
    rc, out, err, seen = _cli(capsys, monkeypatch, [row("chosen", day=0), row("agent-set", due=-1)], "--json")
    assert rc == 0, err
    assert seen == {"db": "db-1", "filter": {"property": "Готово", "checkbox": {"equals": False}}}
    result = json.loads(out)["result"]
    assert result["order"][0] == "planned_today"
    assert [t["title"] for t in result["sections"]["planned_today"]] == ["chosen"]
    assert [t["title"] for t in result["sections"]["unfounded"]] == ["agent-set"]
    assert result["sections"]["high"] == []


def test_cli_without_a_schema_is_exit_3_before_any_request(capsys, monkeypatch):
    _user_yaml("notion:\n  tasks_database_id: db-1\n")
    rc, _, err, seen = _cli(capsys, monkeypatch, [])
    assert rc == 3 and seen == {}
    assert "tasks_schema" in err


def test_cli_human_output_lists_sections_in_order(capsys, monkeypatch):
    _user_yaml(SCHEMA_YAML)
    rc, out, err, _ = _cli(capsys, monkeypatch, [row("late", due=-1, kind="Внешний")])
    assert rc == 0, err
    assert out.index("Решил сделать сегодня") < out.index("HIGH (1)") < out.index("Сроки без основания")
    assert "[late](https://notion.so/late)" in out
