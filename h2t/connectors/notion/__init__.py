"""Notion connector — registry entry."""
from h2t.core.registry import ConnectorSpec
from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="notion",
    help="Work with Notion pages and databases",
    client="h2t.connectors.notion.client:NotionClient",  # lazy ref (spec §4.1)
    register=register,
)
