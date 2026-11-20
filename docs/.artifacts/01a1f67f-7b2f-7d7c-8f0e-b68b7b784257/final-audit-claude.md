# Final audit (Claude, independent) — feat/social-phase1-insights 0ac86401..244d21cb

Read-only. Evidence = code at 244d21cb. One focused run:
`.venv/Scripts/pytest tests/governance tests/connectors/social/test_tokens.py tests/connectors/social/test_db.py -q -p no:cacheprovider` → `221 passed, 2 skipped`.
`git grep meta-h2t-social-pages h2t_ops/` → no output (no match).

## Spec compliance

| section | verdict | evidence |
|---|---|---|
| §1 delivery-only connector | ✅ | insights decides nothing: step 4 is always `noop` (insights.py:131, journal.py:135-138); schedule only registers a trigger (schedule.py:36-45) |
| §4.2 six steps | ⚠️ | insights writes 1,2,3,4,6 (journal.py:99,113; insights.py:129,131,138). `tokens refresh` writes 1,2,6 only, no step 4 although it rotates a remote credential and writes the secrets file (tokens.py:52-72); spec line 91 "Step 4 is the only place a decision is made". Plan Task 7 defines a 1/2/6 run, same shape as `check`/`discover` → Minor 8 |
| §5 config / paths / no hardcode | ✅ | db path via paths.data_dir (db.py:33-34); expiry via paths.state_dir + store.replace place="state" (tokens.py:21-22,68); Threads URL from api_base config (threads.py:40-41); no Path.home() added |
| §6 inv. 1 (no write w/o approved/auto) | ✅ n/a | no network write added; GraphClient is GET-only (_graph.py:1) |
| §6 inv. 2 (step 5 names source) | ✅ n/a | no step 5 added; guard intact journal.py:80-81 |
| §6 inv. 3 (no token value) | ✅ | one shared check `check_no_secret` (journal.py:65-70) used by JSONL append (journal.py:75) and SQLite results (db.py:68); journal/raw mirrored only after the JSONL check (journal.py:87-91,108-112); new Threads token registered before return (threads.py:47-49); `access_token` stripped by _redact (journal.py:16,43-48) |
| §6 inv. 4 (raw never rewritten) | ✅ | raw JSONL via store.append only (journal.py:76,108); SQLite `INSERT OR REPLACE` on uuid ids is a mirror, not the raw zone (db.py:52,59) |
| §9 storage (no DB unless pipeline/user asks) | ✅ | DB only when `store=True` (insights.py:116,136; journal.py:97-98); default `--trigger cli`, `--store` off (commands.py:40-41) |
| §9 nothing author-specific | ✅ | no handle/id/path literal in shipped code; tests use `acme` |
| §9a doctor reports source | ⚠️ justified | moved to `setup connectors-check` (legacy.py:468-491, 529) by plan Task 8 ruling (plan:194) |
| §9b output contract v1 | ✅ | top keys insights.py:147-148; account entry `{network, summary, posts}` + IG extra insights.py:135, 90-91; post shape insights.py:96-97; step-6 carries schema_version, no report insights.py:138-139 |

## Plan compliance

| task | verdict | evidence |
|---|---|---|
| T1 spec §9b | ✅ | spec §9b present (spec:259-283) |
| T2 versioned JSON, no report | ✅ | report write removed (insights.py diff); unknown/disabled id → NotFoundError before new_run insights.py:111-114; no metrics → NotFoundError insights.py:132-134; empty run → NotFoundError insights.py:109-110,140-143 (progress ruling); tests test_insights.py:172-258 |
| T3 Threads contract, field check | ✅ | insights.py:92-95; tests test_insights.py:356,377 |
| T4 discover human table | ✅ | commands.py:171-182, 257-260; test_commands `test_discover_human_is_a_table` |
| T5 --store SQLite | ✅ (1 minor) | db.py:14-96 matches interface; flags forwarded commands.py:40-41,266; tests test_db.py:6-26, test_insights.py:194,210. Partial `results` rows survive a failed multi-account run (insights.py:136-137 inside loop) |
| T6 schtasks | ✅ | schedule.py:17-50 matches interface; argv order test_schedule.py:36; no real schtasks in tests (fake runner) |
| T7 Threads refresh | ✅ (1 minor) | threads.py:34-49; tokens.py:32-74; other keys survive tokens.py:54,67; env-pinned refusal tokens.py:45-51 (progress ruling); tests test_tokens.py:47-139. Missing `expires_in` path below |
| T8 source per secret | ✅ | secrets.py:99-121; legacy.py:468-491; tests test_secrets_source.py:22-42, test_setup_doctor_checks.py:240-278 |
| Review Focus 1-5 | ✅ | 1: insights.py:111-114; 2: except→record_failure insights.py:144-146; 3: insights.py:133; 4: insights.py:92-95; 5: tokens.py:54 + test_tokens.py:74 |

## Stage-plan compliance

| row | verdict | evidence |
|---|---|---|
| S12 | ✅ | no write under `<data>/social/insights/` (no store.replace left in insights.py); test_insights.py:172 |
| S1 | ✅ | chain test test_insights.py:356; no Threads writes added |
| S6 | ✅ | commands.py:257-260; other commands untouched |
| S4b | ✅ | db.py round trip test_db.py:15-26; no Postgres |
| S4a | ✅ | schedule.py:17-18 `--trigger schedule --store` order; non-win32 → UsageError, no cron (schedule.py:24-25) |
| S3 | ✅ | via secrets.write_env tokens.py:67; Meta user token untouched |
| S5 (code part) | ✅ | source() + connectors-check; legacy fallback kept (secrets.py:99-110); no deletion/move; move itself is Task 9 (human) |
| Rules every row: output contract / empty=exit 5 | ✅ | see T2 |

## Architecture standards

| standard | verdict | evidence |
|---|---|---|
| Connector delivery-only, door core in journal.py | ✅ | secret check moved into journal.py:65-70, db.py calls it (db.py:68) |
| One secret reader (core/secrets.py) | ✅ | new reads via secrets.get/_lookup/keys_with_prefix/shared_env_values; governance suite green (run above) |
| One sqlite door (core/store.connect_sqlite) | ✅ | db.py:37-41; ratchet green |
| Writes only via core.store | ✅ | store.replace tokens.py:68; write_env→store.replace secrets.py:220-224 |
| CLI: lazy imports in commands.py | ✅ | schedule/tokens/insights imported in handlers commands.py:264,268,274 |
| CLI: envelope / exit codes | ✅ | handlers return dicts or str; errors are core.errors classes (UsageError 2, ConfigError 3, ProviderError 1, NotFoundError 5); non-H2T exceptions still mapped centrally (cli.py:133-134) |
| fail-loud | ⚠️ | no silent empty success found; but `_read_expiry` raises raw JSONDecodeError/TypeError on a corrupt or naive-date state file (tokens.py:26-29,44,58) instead of ConfigError naming the file |
| naming | ✅ | db.py, schedule.py, tokens.py; schema `h2t_social_insights/v1` |
| Docs kept true (verification.md "judge the state") | ❌ | shipped skill reference now false — see Important 1 |

## Issues

### Critical
None.

### Important
1. plugins/h2t-ops/skills/connectors/references/social.md:141,151-152,159 — states step 6 holds "the `report` path", "The report is saved as `social/insights/<account>/<date>.json`", and "Threads token refresh: … generate a new one" under "Not built yet". All three are false after this branch (insights.py:138-139 writes schema_version/posts, no file; tokens.py exists). `--store`, `schedule add|remove`, `tokens refresh` are not documented anywhere an agent reads. Breaks spec §9b "writes no report files" as documented contract and the S12/S3 acceptance as seen by a user of the pack. Fix: update the reference (commands table, step-6 line, "Not built yet", exit 5 for no data) in this branch.

### Minor
1. h2t_ops/connectors/social/tokens.py:64-67 — `int(result["expires_in"])` (64) runs before `secrets.write_env`; if Meta returns no/invalid `expires_in`, TypeError is raised after the API already issued the new token and the new value is never persisted, contradicting the comment at tokens.py:66. threads.py:45-47 validates `access_token` but not `expires_in`. Fix: raise ProviderError in ThreadsClient.refresh when `expires_in` is not an int, or write_env before computing expiry. Whether Meta invalidates the old token on refresh: [C: не проверено].
2. h2t_ops/connectors/social/insights.py:136-137 — with `--store`, `results` rows for accounts that succeeded stay in social.db when a later account fails the run (Review Focus 2 (plan) says the whole run fails). A consumer reading `results` without joining the step-6 failure takes partial data. Fix: put_result after the loop, or document that results are valid only for runs without a step-6 error.
3. h2t_ops/connectors/social/tokens.py:26-29,44,58 — corrupt `token-expiry.json` or a hand-edited naive date gives raw JSONDecodeError/TypeError (exit via central mapping), not ConfigError naming the file and remedy (fail-closed-fail-loud: actionable message).
4. h2t_ops/connectors/social/commands.py:1-5,15 — docstring "This and insights.py are the only modules that construct a client" is now false (tokens.py:35-37), and the `social` help says "(read-only)" while `tokens refresh` writes secrets and `schedule` writes Task Scheduler.
5. h2t_ops/connectors/social/journal.py:87-91 + insights.py:144-145 — if `db.put_journal` raises (SQLite error), `record_failure` writes the JSONL failure record, then calls `put_journal` again, which likely raises again and replaces the original exception in the error output (original survives only as `__context__`).
6. h2t_ops/connectors/social/schedule.py:30 — `text=True` decodes schtasks stderr with the locale code page; on a non-English Windows the OEM-encoded message can be garbled or raise UnicodeDecodeError. [C: не проверено]
7. CHANGELOG.md:18-22 not updated for the new commands and the output contract change; no version bump (plan Task 9 ships 4.1.x, so may be intentional).
8. h2t_ops/connectors/social/tokens.py:52-72 — `tokens refresh` journals steps 1,2,6 with no step-4 record although it rotates a credential and rewrites threads.env; spec:91 (step 4 is the only decision point), §6 inv. 1 if a credential rotation counts as a connector write. Plan Task 7 did not ask for it; it is human-gated (Task 9). Fix: record `journal.decide(..., "refresh", key)` → `ask`/consent, or state in the spec that upkeep runs are 1/2/6.

## Declined to judge
- Live behaviour (Task 9: real insights/Threads runs, schtasks registration, real refresh, secrets move) — not run by rule.
- Full `pytest tests` at 244d21cb — progress.md:70 says it must be re-run at final HEAD; I ran only governance + two social files.
- Whether Threads refresh invalidates the previous token — needs Meta docs/live check.
- Corrupt shared threads.env crashing other connectors' rows — pre-existing (progress.md:68-69), outside branch.

## Assessment
With fixes — code matches spec, plan and stage plan with no critical defect; the shipped social skill reference still documents report files and "refresh not built", which must be corrected before merge; minors can follow.
