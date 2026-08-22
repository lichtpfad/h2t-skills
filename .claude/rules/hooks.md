# Hook Rules

Hooks in `hooks-handlers/` are enforcement, not convenience. 672249e moved gathering out
of the model's hands ("Closes #12 — gather.py can no longer be ignored by Claude"). Do not
replace a hook with an instruction in SKILL.md, and do not "simplify" it into something the
model performs itself.

A silent hook is a failure, not a steady state.

Subscribe to every entry path, not the obvious one. `PreToolUse: Skill` never fires for a
slash alias: the harness expands `/plugin:skill` straight into the prompt, so no Skill tool
call happens. Plain-text requests do call the Skill tool. Cover the slash form with
`UserPromptSubmit`, matched anchored to a leading slash — that event also fires for harness
messages such as `<task-notification>`, whose paths contain the same words.

Delivery channel differs by event: the model reads `hookSpecificOutput.additionalContext`;
`systemMessage` is the user-visible TUI line. Every exit path of a handler must honour the
channel, including early exits that return before the normal emitter exists.

Hook edits take effect without restarting the session, contrary to
`plugin-dev/hook-development/SKILL.md:576`. Verify by observing behaviour, not by reasoning
about the docs.
