"""social connector: Instagram and Threads insights, Facebook Page check, through one journaled door."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="social",
    help="Instagram and Threads insights, Facebook Page check; read-only and journaled",
    client="h2t_ops.connectors.social.meta:MetaClient",
    register=register,
)
