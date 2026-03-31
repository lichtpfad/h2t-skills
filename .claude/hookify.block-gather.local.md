---
name: block-gather-during-ctx-load
enabled: true
event: bash
action: block
conditions:
  - field: command
    operator: regex_match
    pattern: ^(git log|git status|git branch|git diff|git stash|gh issue|gh pr |gh milestone|gh api)
---

Данные проекта уже собраны через PreToolUse hook и доступны в system messages (BRIEFING).
Не нужно запускать git/gh команды для сбора контекста вручную.
Используй данные из hook output.
