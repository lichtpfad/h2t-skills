"""Google connector - registry entry (shared OAuth bootstrap for gmail/calendar/drive)."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="google",
    help="Authorize Gmail, Calendar and Drive in one browser consent",
    client="h2t_ops.core.google_auth:bootstrap_google_token",
    register=register,
)
