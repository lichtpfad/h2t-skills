"""Drive connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="drive",
    help="Work with Google Drive files",
    client="h2t_ops.connectors.drive.client:DriveClient",
    register=register,
)
