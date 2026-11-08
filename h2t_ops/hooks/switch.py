"""The opt-in switch of the answer guards: `guards: [grade, plain, structure]` in user.yaml.

A guard logs every answer or imposes rules on the user's repository, so it is off until the
user turns it on (§15 rule 5). The hooks stay registered and each handler asks here first
(.claude/rules/hooks.md). A user.yaml that cannot be read leaves every guard off: a hook must
never break the session.
"""
from __future__ import annotations


def guard_enabled(name: str) -> bool:
    from h2t_ops.core import settings  # imported when a guard fires, not by every hook
    from h2t_ops.core.errors import ConfigError
    try:
        value = settings.resolve("guards").value
    except ConfigError:
        return False
    return isinstance(value, list) and name in value
