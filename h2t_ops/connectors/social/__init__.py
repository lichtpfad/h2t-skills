"""social connector: Instagram and Threads insights, Facebook Page check, through one journaled door.

Read-only Graph reads, plus local maintenance commands (schedule, tokens)."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="social",
    help="Instagram and Threads insights, Facebook Page check; read-only Graph reads, local schedule and token upkeep, journaled",
    client="h2t_ops.connectors.social.meta:MetaClient",
    register=register,
)
