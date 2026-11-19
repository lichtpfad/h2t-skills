from h2t_ops.connectors.social import db


def test_journal_round_trip(social_data):
    rec = {"id": "j1", "ts": "2026-11-19T10:00:00+00:00", "run_id": "r1", "process": "insights",
           "step": 5, "channel": "instagram", "account": "instagram:acme", "action": "reply",
           "source_ids": ["a", "b"], "context_refs": ["c"], "rule_id": "rule-1", "decision": "auto",
           "approved_by": "stas", "task_id": "t-9",
           "result": {"remote_id": "9", "url": "u", "error": None},
           "trigger": "schedule", "endpoint": "media", "schema_version": "h2t_social_insights/v1"}
    db.put_journal(rec)
    assert db.read_journal("r1") == [rec]


def test_raw_and_result_round_trip(social_data):
    raw = {"id": "w1", "ts": "2026-11-19T10:00:00+00:00", "run_id": "r1", "process": "insights",
           "account": "instagram:acme", "endpoint": "media", "payload": {"data": [{"id": "m1"}]}}
    db.put_raw(raw)
    assert db.read_raw("r1") == [raw]
    body = {"network": "instagram", "summary": {"posts": 2}, "posts": []}
    db.put_result("r1", "instagram:acme", body)
    assert db.read_results("r1") == [{"run_id": "r1", "account": "instagram:acme",
                                       "schema_version": "h2t_social_insights/v1", "body": body}]
    assert db.read_journal("other") == [] and db.read_raw("other") == []
