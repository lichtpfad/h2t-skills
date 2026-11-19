"""social connector: Instagram, Facebook and Threads analytics through one journaled door."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="social",
    help="Instagram, Facebook and Threads analytics, read-only and journaled",
    client="h2t_ops.connectors.social.meta:MetaClient",
    register=register,
)
