# H2T Ops Shippable Evidence Log

**Date:** 2026-05-23

## Goal
Track clean-install / shareability execution results with exit codes and evidence snapshots.

## Header
- run_id: "20260523-1723-windows-runtime-blocked"
- issue_context: "#161 (closed), PR #165"
- environment:
  - os: Windows + macOS
  - machine: user clean-runtime check on both machines
  - claude_user: stani
  - installer_session: "user clean Claude Code runtime (Windows + macOS)"
- started_at: "2026-05-23T17:23:12+03:00"
- ended_at: "2026-05-23T23:20:00+03:00"
- result: PASS (as reported by clean-runtime runs)
- notes: "Initial pass in this session failed due environment blocker. Final shareability gate was then executed on clean user environments on both Win/Mac and reported as PASS."

## Command runs

- timestamp: "2026-05-23T17:23:12.7115355+03:00"
  - command: "py -3 \"C:/Users/stani/.claude/plugins/cache/lichtpfad/h2t-core/3.1.10/skills/setup/scripts/setup_h2t.py\" doctor --json"
  - expected_exit: 0
  - exit_code: 112
  - output_path: "C:\\dev\\h2t-skills\\.agent_evidence\\doctor_json.log"
  - started_at: "2026-05-23T17:23:12.7115355+03:00"
  - finished_at: "2026-05-23T17:23:13.7521208+03:00"
  - expected_signal: "JSON with kind=h2t_setup_v1 and status=ready"
  - observed_signal: "No output, error `No installed Python found!`"
  - status: FAIL
  - failure_root_cause: "Missing Python runtime expected by py launcher"
  - follow_up_issue: "#148 (runtime/environment hygiene)"

- timestamp: "2026-05-23T17:23:13.7548663+03:00"
  - command: "py -3 \"C:/Users/stani/.claude/plugins/cache/lichtpfad/h2t-core/3.1.10/skills/setup/scripts/setup_h2t.py\" connectors-check --json"
  - expected_exit: 0
  - exit_code: 112
  - output_path: "C:\\dev\\h2t-skills\\.agent_evidence\\connectors_json.log"
  - started_at: "2026-05-23T17:23:13.7548663+03:00"
  - finished_at: "2026-05-23T17:23:14.8382158+03:00"
  - expected_signal: "JSON includes h2t_ops connector payload"
  - observed_signal: "No output, error `No installed Python found!`"
  - status: FAIL
  - failure_root_cause: "Missing Python runtime expected by py launcher"
  - follow_up_issue: "#148 (runtime/environment hygiene)"

- timestamp: "2026-05-23T17:23:14.8383747+03:00"
  - command: "py -3 \"C:/Users/stani/.claude/plugins/cache/lichtpfad/h2t-core/3.1.10/skills/setup/scripts/setup_h2t.py\" doctor"
  - expected_exit: 0
  - exit_code: 112
  - output_path: "C:\\dev\\h2t-skills\\.agent_evidence\\doctor_text.log"
  - started_at: "2026-05-23T17:23:14.8383747+03:00"
  - finished_at: "2026-05-23T17:23:15.8466990+03:00"
  - expected_signal: "Text output (doctor table) without traceback"
  - observed_signal: "No output, error `No installed Python found!`"
  - status: FAIL
  - failure_root_cause: "Missing Python runtime expected by py launcher"
  - follow_up_issue: "#148 (runtime/environment hygiene)"

- timestamp: "2026-05-23T17:23:15.8467827+03:00"
  - command: "uv.exe run h2t-ops --help"
  - expected_exit: 0
  - exit_code: 112
  - output_path: "C:\\dev\\h2t-skills\\.agent_evidence\\h2t_ops_help.log"
  - started_at: "2026-05-23T17:23:15.8467827+03:00"
  - finished_at: "2026-05-23T17:23:16.8641148+03:00"
  - expected_signal: "Usage/help text containing CLI entrypoint"
  - observed_signal: "No output, error `No installed Python found!`"
  - status: FAIL
  - failure_root_cause: "uv could not provision/run Python runtime"
  - follow_up_issue: "#148 (runtime/environment hygiene)"

- timestamp: "2026-05-23T17:23:16.8641980+03:00"
  - command: "uv.exe run h2t-ops connectors --help"
  - expected_exit: 0
  - exit_code: 112
  - output_path: "C:\\dev\\h2t-skills\\.agent_evidence\\h2t_ops_connectors_help.log"
  - started_at: "2026-05-23T17:23:16.8641980+03:00"
  - finished_at: "2026-05-23T17:23:17.8788095+03:00"
  - expected_signal: "connector help text"
  - observed_signal: "No output, error `No installed Python found!`"
  - status: FAIL
  - failure_root_cause: "uv could not provision/run Python runtime"
  - follow_up_issue: "#148 (runtime/environment hygiene)"

- timestamp: "2026-05-23T17:23:17.8788823+03:00"
  - command: "uv.exe run h2t-ops connectors list --json"
  - expected_exit: 0
  - exit_code: 112
  - output_path: "C:\\dev\\h2t-skills\\.agent_evidence\\h2t_ops_connectors_list.log"
  - started_at: "2026-05-23T17:23:17.8788823+03:00"
  - finished_at: "2026-05-23T17:23:18.9190517+03:00"
  - expected_signal: "machine-parseable connectors payload"
  - observed_signal: "No output, error `No installed Python found!`"
  - status: FAIL
  - failure_root_cause: "uv could not provision/run Python runtime"
  - follow_up_issue: "#148 (runtime/environment hygiene)"

- timestamp: "2026-05-23T17:23:18.9191270+03:00"
  - command: "uv.exe run h2t-ops research preflight --json"
  - expected_exit: 0
  - exit_code: 112
  - output_path: "C:\\dev\\h2t-skills\\.agent_evidence\\h2t_ops_research_preflight.log"
  - started_at: "2026-05-23T17:23:18.9191270+03:00"
  - finished_at: "2026-05-23T17:23:19.9366898+03:00"
  - expected_signal: "preflight JSON fields present"
  - observed_signal: "No output, error `No installed Python found!`"
  - status: FAIL
  - failure_root_cause: "uv could not provision/run Python runtime"
  - follow_up_issue: "#148 (runtime/environment hygiene)"

- timestamp: "2026-05-23T17:23:19.9367454+03:00"
  - command: "uv.exe run h2t-ops daily-brief --help"
  - expected_exit: 0
  - exit_code: 112
  - output_path: "C:\\dev\\h2t-skills\\.agent_evidence\\h2t_ops_daily_brief_help.log"
  - started_at: "2026-05-23T17:23:19.9367454+03:00"
  - finished_at: "2026-05-23T17:23:20.9539002+03:00"
  - expected_signal: "help text for daily-brief"
  - observed_signal: "No output, error `No installed Python found!`"
  - status: FAIL
  - failure_root_cause: "uv could not provision/run Python runtime"
  - follow_up_issue: "#148 (runtime/environment hygiene)"

## Inventory check

- timestamp: "2026-05-23T17:23:21+03:00"
- context_output_path: "not_run"
- observed_h2t_ops_skills:
  - "not_run"
- has_only_target_ops_skills: false
- result: FAIL
- notes: "Блокер runtime: /context inventory не собирался в этой сессии в изолированном clean-user режиме."

## Summary

- windows_result: "FAIL (first runtime) -> PASS (clean user session)"
- mac_result: PASS
- blocking_fail: "No active blocker in final clean-pass."
- next_step: "Move to #148/#85 as follow-up."

---

## Final clean-runtime PASS (as of 2026-05-23)

- run_id: "20260523-2200-shippable-pass-clean-runtime"
- environment:
  - windows: "clean user Claude Code runtime"
  - macos: "clean user Claude Code runtime"
- evidence_source: "issue #166 comment chain; user-confirmed execution outputs"
- started_at: "2026-05-23"
- ended_at: "2026-05-23"
- result: PASS

### Command matrix (clean install + shareability)

- `/plugin uninstall h2t-core@lichtpfad` → PASS
- `/plugin uninstall h2t-ops@lichtpfad` → PASS
- `/plugin install h2t-core@lichtpfad` → PASS
- `/plugin install h2t-ops@lichtpfad` → PASS
- `/reload-plugins` → PASS
- `/h2t-core:setup doctor --json` → PASS
- `/h2t-core:setup connectors-check --json` → PASS
- `h2t-core:setup doctor` → PASS
- `h2t-ops --help` → PASS
- `h2t-ops connectors list --json` → PASS
- `h2t-ops research preflight --json` → PASS
- `h2t-ops daily-brief --help` → PASS (Windows and macOS clean sessions)

### /context inventory

- Windows clean runtime: target `h2t-ops` entries shown:
  - `h2t-ops:connectors`
  - `h2t-ops:research`
  - `h2t-ops:daily-brief`
- Legacy per-connector `h2t-ops:calendar`, `...gmail`, `...notion`, `...drive`, `...telegram`, `...meetgeek` not present as top-level `/context` entries from final gate.

### Version / plugin state check

- h2t-core plugin installed and healthy.
- h2t-ops CLI install command used on mac:
  - `~/.local/bin/uv tool install --reinstall git+https://github.com/lichtpfad/h2t-skills.git`
