"""Data the tools read, shipped inside the package (spec section 5).

The plugin originals found these files beside their own `__file__`: `assembler.py` next to
`base/`, drawio two levels above `config/defaults.yaml`. That holds in a checkout and in the
plugin cache and nowhere else. Here they are package data, located through
`importlib.resources`, so a wheel installed anywhere carries and finds them.
"""
from importlib.resources import files
from pathlib import Path


def resource_dir(name: str) -> Path:
    """The directory of `h2t_ops.resources.<name>`, as a filesystem path."""
    return Path(str(files(f"{__name__}.{name}")))


def known_secrets_path() -> Path:
    """The registry of API-key credentials the setup wizard asks for."""
    return Path(str(files(__name__) / "known_secrets.yaml"))
