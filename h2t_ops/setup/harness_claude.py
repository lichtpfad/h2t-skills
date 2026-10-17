"""Claude Code as `h2t-setup sync` sees it: `claude plugin … --json` (spec §7.3.5).

The CLI, not its files. `claude plugin list --json` and `claude plugin marketplace list
--json` (Claude Code 2.1.301, read 2026-10-17 under an isolated CLAUDE_CONFIG_DIR) report
what `known_marketplaces.json`, `installed_plugins.json` and the `enabledPlugins` of
settings hold together: a marketplace's `ref`, and each plugin's `version`, `scope` and
`enabled`. Reading the files would mean following three formats the CLI already merges.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

MARKETPLACE = "lichtpfad"
SOURCE = "lichtpfad/h2t-skills"
TIMEOUT = 600
# Looked up when a Claude is made, so the tests can refuse the real `claude` here.
_run_process = subprocess.run


class HarnessError(Exception):
    """A `claude` command failed; `command` is the one to show a person."""

    def __init__(self, command: list[str], message: str) -> None:
        super().__init__(f"{' '.join(command)}: {message}")
        self.command = command


def plugin_id(name: str) -> str:
    return f"{name}@{MARKETPLACE}"


def config_dir() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(configured) if configured else Path.home() / ".claude"


class Claude:
    def __init__(self, exe: str | None = None, run=None, which=shutil.which) -> None:
        self._exe = exe
        self._run = run or _run_process
        self._which = which

    def found(self) -> bool:
        return self._resolve() is not None

    def _resolve(self) -> str | None:
        if self._exe is None:
            self._exe = self._which("claude") or ""
        return self._exe or None

    @staticmethod
    def command(*args: str) -> list[str]:
        """The words a person types; the report shows these."""
        return ["claude", "plugin", *args]

    def _call(self, *args: str) -> str:
        shown = self.command(*args)
        exe = self._resolve()
        if exe is None:
            raise HarnessError(shown, "claude is not on PATH")
        try:
            done = self._run([exe, "plugin", *args, "--json"], capture_output=True, text=True,
                             encoding="utf-8", timeout=TIMEOUT)
        except (OSError, subprocess.SubprocessError) as exc:
            raise HarnessError(shown, str(exc)) from exc
        if done.returncode != 0:
            text = (done.stderr or done.stdout or "").strip().splitlines()
            raise HarnessError(shown, text[-1] if text else f"exit {done.returncode}")
        return done.stdout or ""

    def _list(self, *args: str) -> list[dict]:
        out = self._call(*args)
        try:
            data = json.loads(out)
        except ValueError as exc:
            raise HarnessError(self.command(*args), f"not JSON: {exc}") from exc
        if not isinstance(data, list):
            raise HarnessError(self.command(*args), "not a JSON list")
        return [d for d in data if isinstance(d, dict)]

    def marketplace(self) -> dict | None:
        """The `lichtpfad` marketplace entry (`ref` when pinned), or None."""
        return next((m for m in self._list("marketplace", "list")
                     if m.get("name") == MARKETPLACE), None)

    def plugins(self) -> list[dict]:
        """Installed plugins of `lichtpfad`: id, version, scope, enabled, installPath."""
        return [p for p in self._list("list")
                if str(p.get("id", "")).endswith("@" + MARKETPLACE)]

    # Mutations. Each is one command; the report quotes the same words.
    @staticmethod
    def add_args(ref: str | None = None, source: str = SOURCE) -> tuple[str, ...]:
        return ("marketplace", "add", f"{source}#{ref}" if ref else source)

    @staticmethod
    def remove_args() -> tuple[str, ...]:
        return ("marketplace", "remove", MARKETPLACE)

    @staticmethod
    def install_args(name: str, scope: str) -> tuple[str, ...]:
        return ("install", plugin_id(name), "--scope", scope)

    @staticmethod
    def disable_args(name: str, scope: str) -> tuple[str, ...]:
        return ("disable", plugin_id(name), "--scope", scope)

    def marketplace_add(self, ref: str | None = None, source: str = SOURCE) -> None:
        self._call(*self.add_args(ref, source))

    def marketplace_update(self) -> None:
        self._call("marketplace", "update", MARKETPLACE)

    def marketplace_remove(self) -> None:
        self._call(*self.remove_args())

    def install(self, name: str, scope: str) -> None:
        self._call(*self.install_args(name, scope))

    def update(self, name: str, scope: str) -> None:
        self._call("update", plugin_id(name), "--scope", scope)

    def disable(self, name: str, scope: str) -> None:
        self._call(*self.disable_args(name, scope))
