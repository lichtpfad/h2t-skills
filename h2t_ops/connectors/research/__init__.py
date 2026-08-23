"""Research connector - registry entry."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="research",
    help="Run provider-backed web research and URL fetching",
    client="h2t_ops.connectors.research.client:ResearchClient",
    register=register,
)
