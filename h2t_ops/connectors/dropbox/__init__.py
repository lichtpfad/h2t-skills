"""Dropbox connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="dropbox",
    help="Read Dropbox folders and files over HTTP API v2",
    client="h2t_ops.connectors.dropbox.client:DropboxClient",
    register=register,
)
