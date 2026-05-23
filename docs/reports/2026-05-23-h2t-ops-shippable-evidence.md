# h2t-ops Shippable Evidence — 2026-05-23

**Type:** mac clean-runtime smoke  
**Result:** PASS  
**Date:** 2026-05-23  
**Environment:** macOS arm64, Python 3.11.9

## Run

| Check | Result |
|-------|--------|
| Plugin reinstall (marketplace) | PASS — h2t-core@3.1.10, h2t-ops installed fresh |
| `h2t-core:setup doctor --json` | h2t-ops missing → installed via uv; post-install all green |
| `connectors-check --json` | 7/7 ready (calendar, drive, gmail, meetgeek, notion, research, telegram) |
| `h2t-ops --version` | 0.2.1 |
| `h2t-ops --help` | Correct surface: 9 subcommands |
| `h2t-ops connectors list` | 7 connectors listed |
| `h2t-ops research preflight --json` | `{"ok": true, "provider": "research", "result": {"status": "OK", "provider": "exa"}}` |
| `uv run h2t-ops --help` | Identical to direct call ✓ |
| `uv run h2t-ops research preflight --json` | exa OK ✓ |

## Notes

- `connectors list --json` flag has no effect (plain-text in both cases) — non-blocking known nuance
- `h2t-ops:daily-brief` is a skill, not a CLI subcommand — present in `/context` as expected
- Cleanup was plugin manager uninstall/reinstall (not full `rm -rf` cache purge); h2t-ops CLI was genuinely absent before setup

## Gate Cleared

Installed-plugin smoke for #161 closure: confirmed `h2t-ops:connectors`, `h2t-ops:research`, `h2t-ops:daily-brief` present in `/context`.

GH comment: https://github.com/lichtpfad/h2t-skills/issues/166#issuecomment-4526444273
