"""Telegram connector - registry entry."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="telegram",
    help="Work with Telegram dialogs and messages",
    client="h2t_ops.connectors.telegram.client:TelegramClientAdapter",
    register=register,
)
