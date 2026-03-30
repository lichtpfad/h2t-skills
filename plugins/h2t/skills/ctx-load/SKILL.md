---
name: ctx-load
description: Load project context and display formatted briefing. Use with /h2t:ctx-load.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 0.1.0
---

# Instructions

The PreToolUse hook has already injected complete instructions and a pre-formatted briefing into the system messages. Follow those instructions exactly.

Look for `=== DEV-SESSION-START ===` in the system messages from this conversation.

**If found:** Follow the steps described there. Do NOT deviate, supplement, or re-gather data.

**If not found:** The hook did not fire. Show this error:
> "Hook gather-on-skill не сработал. Проверь версию плагина: bash plugins/h2t/scripts/update-plugin.sh"
