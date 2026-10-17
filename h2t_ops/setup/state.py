# h2t_ops/setup/state.py
"""Install state: install.json for Python, install.env for bash; env is the commit point."""
from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


def run_dir() -> Path:
    return Path.home() / ".h2t" / "run"


@dataclass
class Install:
    version: str
    generation: str
    tool_root: str
    entrypoints: dict[str, str]
    editable: str | None = None
    user_options: dict = field(default_factory=lambda: {"extras": [], "with": []})
    plugins: list[str] = field(default_factory=lambda: ["h2t-core", "h2t-ops"])


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _fwd(p: str | None) -> str:
    return (p or "").replace("\\", "/")


def _write_env(state: str, version: str, generation: str, hook: str, editable: str | None) -> None:
    lines = [f"STATE={state}", f"VERSION={version}", f"GENERATION={generation}",
             f"H2T_HOOK={_fwd(hook)}", f"EDITABLE_ROOT={_fwd(editable)}"]
    _atomic_write(run_dir() / "install.env", ("\n".join(lines) + "\n").encode("utf-8"))


def begin_update(version: str) -> None:
    _write_env("updating", version, "", "", None)


def commit(install: Install) -> None:
    _atomic_write(run_dir() / "install.json",
                  json.dumps(asdict(install), ensure_ascii=False, indent=2).encode("utf-8"))
    _write_env("ready", install.version, install.generation,
               install.entrypoints.get("h2t-hook", ""), install.editable)


def _read_env() -> dict[str, str]:
    try:
        text = (run_dir() / "install.env").read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return {}
    out = {}
    for line in text.splitlines():
        key, sep, value = line.rstrip("\r").partition("=")
        if not sep:
            return {}
        out[key] = value
    return out


def read() -> Install | None:
    env = _read_env()
    if env.get("STATE") != "ready":
        return None
    fields = {f.name for f in dataclasses.fields(Install)}
    try:
        data = json.loads((run_dir() / "install.json").read_text(encoding="utf-8"))
        install = Install(**{k: v for k, v in data.items() if k in fields})
    except (FileNotFoundError, ValueError, TypeError, AttributeError):
        return None
    return install if install.generation == env.get("GENERATION") else None
