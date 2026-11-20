# SDD ledger — plan: C:/dev/h2t-skills-wt-social-phase1/docs/superpowers/plans/2026-11-19-social-phase1-insights.md

Spec: docs/superpowers/specs/2026-11-19-social-pipeline-design.md (reachable).
Plan gate: Codex terra, round 3 GATE: PASS (2026-11-19).
Baseline: tests/connectors/social + tests/governance → 369 passed, 2 skipped (after `uv sync --all-extras`).
Scope: Tasks 1-8 by subagents. Task 9 = human-gated live checks, controller + owner only.

## Pre-flight scan

| tasks | shared file/interface | produced vs consumed | finding |
|---|---|---|---|
| T2↔T3 | insights.py, test_insights.py | T2 result shape `accounts.<id>.summary/posts` → T3 asserts on it | consistent |
| T2↔T5 | insights.run(store=...) | T2 adds param, T5 uses it | consistent |
| T4↔T5↔T6↔T7 | commands.py | separate subcommands; T5 adds --trigger/--store, T6 command() consumes them | consistent |
| T5↔T7 | journal.new_run(store=False) | T7 uses default | consistent |
| T7↔T8 | core/secrets.py | T7 reads shared_env_values, T8 adds source() | no overlap |
| T1 | spec + plan file | T1 commits the (untracked) plan with the spec | ok |
| T2 self | tests vs code | second-account test is regression, marked | ok |
| T5 self | db.py + sandbox case | conditional on governance test naming db.py | ok |
| T7 self | place "state" | exists in core/paths.py:40 | ok |
| T8 self | connector_matrix test | tests/test_setup_doctor_checks.py | ok |

Scan clean, no rulings needed.

## Progress

Ruling: task reviews run on Codex (terra), not Claude — rule "checker is not the writer" + stage plan "Codex review each" — slower (~5 min/review) — cost if wrong: time only.
Task 1: complete (commits 0ac8640..209edba, review clean). ⚠️ docs-lint checked by controller: spec + new plan are orphans (not linked from docs/README.md), same as every 2026-11-19 sibling doc — pre-existing index gap, not this task.
Task 2: implemented a4539a6a (base 209edba1), implementer agent a9d246665f24b5626; Codex review dispatched.
Ruling: Task 4 dispatched before Task 3, in parallel with Task 2 review — Task 3 shares insights.py/test_insights with Task 2 and must wait for its review; Task 4 touches commands.py only — cost if wrong: a rebase of a small fix.
Task 4: complete (commits a4539a6..9f49b32, review clean). Pyright "not accessed" was a false positive (commands.py:237-241). Controller ran suite at 96222015: 377 passed, 2 skipped.
Task 2: Codex review → Needs fixes, 1 Important: empty run (all disabled, no --account) exits 0. Fix round 1 sent to implementer. Ruling: empty `accounts` after loop → NotFoundError incl. all-skipped (facebook-only) case naming skip reasons; nothing enabled → raise before new_run — spec "empty result is an error" — cost if wrong: one more edit.
Task 2: fix round 1/5 (1 addressed, 0 open; commits 9f49b32..9622201).
Task 2: complete (commits 209edba..9622201 incl. a4539a6, review clean after round 1).
Task 3: complete (commits 9622201..ee5bbf6, review clean). Note for final review: pyright "token possibly unbound" insights.py:97 (pre-existing shape, IG branch).
Task 5: implemented f12ac111 (base ee5bbf67), agent a0bdac8734cffc5b0; Codex review dispatched (risks: read_* creates db; stored-run set; secret check before sqlite).
Task 5: Codex → Needs fixes. Important: put_result (insights.py:216-217, db.py:129-134) bypasses the secret-value gate → token could reach social.db. QUEUED fix round 1 until Task 7 implementer finishes (one writer per tree).
Task 5: minor (deferred): journal round-trip not exact for non-JSON-native extras (tuple → list).
Task 6: complete (commits f12ac11..ecc8beb, review clean).
Task 7: complete (commits ecc8beb..6379987, review clean).
Task 5: fix round 1/5 (1 addressed, 0 open; commits 6379987..82c7a1a).
Task 5: complete (commits ee5bbf6..f12ac11 + 82c7a1a, 1 minor deferred).
Task 8: implemented cff350ec (base 82c7a1a7), agent a5dcd2870908994de; Codex review dispatched. test_wheel_contents 6 errors were env (no pip in uv venv): controller installed pip into worktree venv → 6 passed.
Task 8: Codex → Needs fixes. Important: _social_check lets ConfigError from a broken accounts.yaml crash connector_matrix. Fix round 1 sent. Ruling: catch ConfigError only → social status "error" with the value-free message.
Task 8: minor (deferred): test "missing without tokens" clears only Meta env keys, not THREADS_TOKEN_*.
Task 8: fix round 1/5 (0 addressed, 1 open — str(exc) can echo a value from accounts.yaml secrets.* (config.py:147); commits cff350e..3491b0c).
Ruling (correction): controller's round-1 claim "config.py ConfigError messages are value-free" was wrong; social entry carries a fixed message (path + remedy), no exception text — cost if wrong: less detail in the error line.
Task 8: fix round 2/5 (1 addressed, 0 open; commits 3491b0c..1dfdcae).
Task 8: complete (commits 82c7a1a..1dfdcae, 1 minor deferred).
Final review: Codex terra high over 0ac86401..1dfdcaea → With fixes. 2 Important (env-sourced Threads token silently not rotated; corrupt secrets file crashes connectors-check), 2 minors to fix (test THREADS_TOKEN_* isolation; pyright unbound token).
Ruling: env-sourced key → ConfigError before any network call, nothing rotated — cost if wrong: user must move the token out of env first.
Ruling: _social_check catches (ConfigError, OSError, UnicodeDecodeError), fixed value-free message — cost if wrong: less detail.
Ruling: Task 5 tuple→list round-trip left as is (JSON contract) — cost if wrong: none observed.
Final fix wave: commits 206c2225, bb130fc5, 7a5d79fe, 244d21cb (fix base 1dfdcaea); 440 passed, 4 skipped; ruff clean. Codex scoped re-review dispatched. Full suite at 244d21cb running in background → scratchpad/full-suite-final.txt.
Final fix re-review: 1, 3, 4 ADDRESSED; 2 NOT ADDRESSED (test corrupts legacy secrets.env, not shared threads.env).
Final: parked — finding 2 residual — Ruling: the social row handles unreadable files (legacy.py:476); a corrupt shared threads.env still aborting OTHER rows is a pre-existing package defect in secrets.get, same on main, outside this branch → propose an issue — cost if wrong: connectors-check still crashes on a corrupt shared .env, as today.
Controller: full `pytest tests` at 244d21cb → 4738 passed, 55 skipped, 2 deselected (scratchpad/full-suite-final.txt).
Owner asked (2026-11-20) for a compliance audit by both Claude (Opus) and Codex (terra high). Claude: With fixes — Important: shipped reference plugins/h2t-ops/skills/connectors/references/social.md stale (report path, Threads refresh "not built", no --store/schedule/tokens docs); 8 minors in final-audit-claude.md.
Codex audit: With fixes — Important: mirror failure leaves dangling step-1 run (journal.py:95-100); tokens shared_env_values outside guard (tokens.py:52-55). Minor: "read-only" help; plan filename "phase1".
Owner (2026-11-20): "да делае все правки" → audit fix wave with all 11 items (audit-fix-brief.md), fixer a436d38e5905681bf, fix base 244d21cb.
Ruling: "все" read as all 11 incl. the 4 I proposed to leave — cost if wrong: small extra diff (spec sentence, schtasks encoding, CHANGELOG entry, plan rename).
Audit fix wave: commits dbbcf5ac, 7ef0aa83, 3cc08d8e, 59dfe963, b4232402 (head b4232402); 1005 passed, 27 skipped (targeted); ruff clean. Plan renamed to docs/superpowers/plans/2026-11-19-social-insights-complete.md (this workspace keeps its old dir name). Codex scoped re-review dispatched; full suite at b4232402 in background → scratchpad/full-suite-audit.txt.
Audit re-review: 10/11 addressed; item 2 gap (put_result failure kept mirroring) → fix 6ef8092c → Codex: ADDRESSED, no new breakage. All 11 closed. Full suite at 6ef8092c: 4751 passed, 55 skipped, 2 deselected; tree clean.
Pre-existing encoding crash reproduced on main (exit 2, h2t_setup_error; control exit 0) → issue #713.
Owner chose option 2: branch pushed, PR #714 (closes #679 #689 #676; #674 #677 #678 #694 stay open until Task 9 live checks). Worktree kept for PR feedback.
Task 9 live 1/8 (owner yes 2026-11-20): run insights instagram:hou2touch → exit 0, schema v1, 120 posts, median_reach 1126; no new file under data/social/insights (only the 2026-11-19 file from the old code); journal run cef75ed0: steps 1,2×124,3,4,6, step3 source_ids == step2 ids; no token pattern in output (positive control on fixture: 1 hit).
Task 9 live 2/8: run insights threads:hou2touch → exit 0, schema v1, 55 posts (all the account has), 53 with metrics, median views 6; 2 skipped = REPOST_FACADE (reposts, Meta returns no metric data, no error); journal c9f5e9fb: steps 1,2×56,3,4,6, step3 == step2 ids; no token pattern in output.
Task 9 live 3/8: accounts discover (human) → exit 0, table of 24 accounts, "not written: pass --write"; accounts.yaml untouched.
#675 probe (owner asked, read-only, scratchpad/probe_fb_page_metrics.py, page Hou2Touch 124310164296279, period day): OK — page_post_engagements, page_views_total, page_follows, page_daily_follows_unique, page_media_view, page_total_media_view_unique, page_video_views, page_actions_post_reactions_total (2 points each = default window, need since/until); code 100 "not a valid insights metric" — page_impressions_unique, page_impressions, page_fan_adds, page_fans.
Probe posted to #675 (comment 7025758323). Owner: "может 675 прямо сейчас сделать" → #675 started (task-675-brief.md), implementer a408cf30f86643ac0, base 6ef8092c.
Ruling: #675 goes into the same branch/PR #714, not a stacked PR — stacked-PR retarget hazard (memory) — cost if wrong: a larger PR.
Ruling: Page metric list lives in resources/social/defaults.yaml (Meta renames metrics often) — cost if wrong: one more config key.
Ruling: fixed 28-day window, no new flag (YAGNI) — cost if wrong: add a flag later.
#675: implemented 625fcd8c + 8bc08f03. Codex review: 1 Important — all-unavailable path ends with generic failure step 6, not schema_version + metrics 0. Implementer's "no page_id" claim false (commands.py:103); `page_id or remote_id` fallback judged correct.
#675: parked — Ruling: brief said "journal as the other networks do"; the Instagram no-data path (insights.py:171-176) ends the same way (step 3 "no data", step 4, NotFoundError → record_failure step 6); schema_version+count step 6 is a success record — code stands, consistent — cost if wrong: a consumer reading step 6 of a failed run sees no metrics count.
#675: minor (deferred): FB and IG per-account blocks in insights.run repeat the step-3/4/no-data pattern.
Full suite at 8bc08f03: 4763 passed, 55 skipped. Pushed; PR #714 body updated (#675 listed, live results added).
Task 9 live 4/8 (#675, owner yes): accounts.yaml facebook:hou2touch enabled false→true (backup scratchpad/accounts.yaml.bak). run insights facebook:hou2touch → exit 0, schema v1, unavailable [], 6 metrics × 28 days (2026-10-24..2026-11-20): reach 19, media views 30, page views 18, new follows 2, engagements 0, reactions = dict values, all {} ; journal 5c21efdf: 1,2×7,3,4,6, step3==step2 ids, step6 metrics 6; no token pattern.
#675: minor (deferred): metric values are not always numbers (reactions = dict breakdown) — §9b/reference should say so.
Task 9 live 5/8 (#694 mechanics, owner yes): social.db absent before (chat runs wrote none). run insights --trigger schedule --store (all 11 enabled) → exit 0 after >600s, schema v1, 11 accounts, skipped {}, unavailable []; social.db 2184 KB: journal 972, raw 938, results 11 rows, all this run; step1 trigger schedule.
Owner (2026-11-20): "social.db architecture and ETL principles were not planned?" — correct: only D3 (where/when) decided; no analytics data model, dedupe, snapshot history, DB schema versioning/migrations, consumer read path. Proposed: decision issue (decision.yml) before #677 goes live daily. Owner: yes → decision #715 (options A mirror / B snapshot tables / C provenance only, model at consumer; notes D1-vs-D3 tension). #677 commented: live blocked by #715. PR #714: Closes #674 #675 #676 #679 #689 #694. facebook:hou2touch stays enabled (owner yes).
Owner: consumers are not only rejuve (author's own channels, client projects, pack users) → #715 updated. Owner: "no DB" is valid; first load big, then incremental → #715 common requirements (no-DB default; daily metrics from watermark; posts re-read in an N-day window). Owner's boundary: connector only extracts on request; storing is a separate loader → #715 option D. Owner: keep --store as interim (a) → PR #714 body notes it.
Owner: "D конечно, 2 да, 3 да". #715 decision D recorded (comment 7027079572). #678 live: 4 social keys copied legacy → secrets/shared/{meta,threads}.env (names+lengths only, 3.x files kept); connectors-check → all "shared"; social check 11 accounts OK. PR #714 squash-merged as dcdf2e43; #674 #675 #676 #678 #679 #689 #694 CLOSED. Local main fast-forwarded.
Open: #677 (blocked by #715 → loader plan + ADR), #713 (encoding crash), #670 items 1-5, deferred minors (FB/IG block repetition; reactions value is a dict — §9b note).
Out of scope (pre-existing, for the owner): a corrupt shared secrets file crashes other connectors' rows (telegram, notion) in connectors-check via secrets.get.
Controller: full `pytest tests -x` (started at cff350ec, tree moved to 1dfdcaea mid-run): 4734 passed, 55 skipped, 2 deselected. Must re-run at final HEAD before merge.
Task 5: fix round 1 sent to a0bdac8734cffc5b0 (fix base 63799871). Ruling: one shared secret check in journal.py, called by _append and before put_result — no duplicated logic.
Task 8: waits for Task 5 fix (one writer per tree).
