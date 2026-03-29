---
name: dev-session-start
description: Use when starting a coding or product development session. Triggers on "/session-start", "начинаем работу", "start session", "new session", or at the beginning of any development conversation. NOT for non-coding sessions (personal, management, psychology)., 'h2t:dev-session-start'
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.12.0
---

# Instructions

The PreToolUse hook has already injected complete instructions and a pre-formatted briefing into the system messages. Follow those instructions exactly.

Look for `=== DEV-SESSION-START: ОБЯЗАТЕЛЬНЫЕ ИНСТРУКЦИИ ===` in the system messages from this conversation.

**If found:** Follow the steps described there. Do NOT deviate, supplement, or re-gather data.

**If not found:** The hook did not fire. Show this error:
> "Hook gather-on-skill не сработал. Проверь версию плагина: bash plugins/h2t/scripts/update-plugin.sh"

**Paired with:** `h2t:handoff` (SAVE at end) — this skill is LOAD at start.
