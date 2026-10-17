"""A stateful stand-in for `claude plugin … --json`, injected as the `run` of
`harness_claude.Claude`, so the real wrapper builds every command line it parses.

State lives in a JSON file: marketplaces (with `ref` when pinned and the version their
catalog offers), installed plugin entries (id, version, scope, `projectPath` for project
scope) and the `enabledPlugins` of each settings scope: the user's, and each project's.

What is measured, and what is assumed:
- probe 3b (docs/reports/2026-10-17-package-arch-probes.md): `marketplace remove`
  uninstalls the marketplace's plugins and forgets that one was disabled;
- probe 3c: `install` enables;
- measured 2026-10-17 (Task 15 review): `list` reports `enabled` as seen from its working
  directory, where a project's settings override the user's;
- NOT probed: whether `update` keeps `enabled`. The fake keeps it unless
  `update_enables=True`, which models the other answer.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

CATALOG = ("h2t-core", "h2t-ops", "h2t-dev", "h2t-arch", "h2t-creative")


class Interrupted(BaseException):
    """The process died here: nothing after this point ran."""


class Ticker:
    """Counts completed mutations across the fakes; raises after the `at`-th one."""

    def __init__(self, at: int | None = None) -> None:
        self.at = at
        self.log: list[str] = []

    def __call__(self, label: str) -> None:
        self.log.append(label)
        if self.at is not None and len(self.log) == self.at:
            raise Interrupted(label)


def _real(path) -> str:
    return os.path.realpath(str(path))


class FakeClaude:
    def __init__(self, path: Path, config: Path, *, head: str, pins: dict[str, str] | None = None,
                 tick=None, fail_on: str | None = None, update_enables: bool = False) -> None:
        self.path = Path(path)
        self.config = Path(config)
        self.head = head  # what main's catalog offers
        self.pins = pins or {}  # ref -> what that ref's catalog offers
        self.tick = tick or (lambda label: None)
        self.fail_on = fail_on  # a command prefix that exits 1, once
        self.update_enables = update_enables
        self.calls: list[list[str]] = []
        self.cwds: list[str] = []
        if not self.path.exists():
            self.save({"marketplaces": {}, "plugins": [], "user": {}, "projects": {}})

    # -- state ------------------------------------------------------------------------
    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")

    def seed(self, *, ref: str | None = None, offers: str | None = None, plugins=(),
             project_settings: dict | None = None) -> None:
        """A marketplace (pinned to `ref` when given) and installed plugins as (name, version,
        scope, enabled) or (name, version, scope, enabled, projectPath); `project_settings`
        maps a project directory to {name: enabled} of its own `.claude/settings.json`."""
        data = {"marketplaces": {"lichtpfad": {
            "repo": "lichtpfad/h2t-skills", "ref": ref,
            "offers": offers or (self.pins[ref] if ref else self.head)}},
            "plugins": [], "user": {}, "projects": {}}
        for name, version, scope, enabled, *where in plugins:
            pid = f"{name}@lichtpfad"
            entry = {"id": pid, "version": version, "scope": scope}
            if scope == "user":
                data["user"][pid] = enabled
            else:
                entry["projectPath"] = _real(where[0])
                data["projects"].setdefault(entry["projectPath"], {})[pid] = enabled
            data["plugins"].append(entry)
            self._cache(name, version)
        for where, flags in (project_settings or {}).items():
            data["projects"].setdefault(_real(where), {}).update(
                {f"{n}@lichtpfad": v for n, v in flags.items()})
        self.save(data)

    def entries(self) -> list[tuple]:
        """(name, scope, projectPath, version, enabled in its own scope), sorted."""
        data = self.load()
        out = []
        for p in data["plugins"]:
            own = (data["user"] if p["scope"] == "user"
                   else data["projects"].get(p.get("projectPath"), {}))
            out.append((p["id"].split("@")[0], p["scope"], p.get("projectPath"), p["version"],
                        own.get(p["id"], True)))
        return sorted(out, key=lambda e: (e[0], e[1], e[2] or ""))

    def installed(self) -> dict[str, dict]:
        """name -> its user-scope (else first) entry: version, scope, enabled (own scope)."""
        out: dict[str, dict] = {}
        for name, scope, where, version, enabled in self.entries():
            if name not in out or scope == "user":
                out[name] = {"version": version, "scope": scope, "enabled": enabled,
                             "projectPath": where}
        return out

    def setting(self, name: str, project=None):
        """What one settings file says about a plugin: the user's, or a project's."""
        data = self.load()
        flags = data["user"] if project is None else data["projects"].get(_real(project), {})
        return flags.get(f"{name}@lichtpfad")

    def mutations(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] not in (["marketplace", "list"], ["list"])]

    def _cache(self, name: str, version: str) -> Path:
        d = self.config / "plugins" / "cache" / "lichtpfad" / name / version
        d.mkdir(parents=True, exist_ok=True)
        (d / "plugin.json").write_text(json.dumps({"name": name, "version": version}))
        return d

    @staticmethod
    def _effective(data: dict, pid: str, cwd: str) -> bool:
        project = data["projects"].get(cwd, {})
        return project.get(pid, data["user"].get(pid, True))

    # -- the process ------------------------------------------------------------------
    def __call__(self, argv, **kwargs):
        assert argv[1] == "plugin" and argv[-1] == "--json", argv
        args = list(argv[2:-1])
        cwd = _real(kwargs.get("cwd") or os.getcwd())
        self.calls.append(args)
        self.cwds.append(cwd)
        if self.fail_on and " ".join(args).startswith(self.fail_on):
            self.fail_on = None
            return subprocess.CompletedProcess(argv, 1, "", "network is unreachable\n")
        data = self.load()
        markets, plugins = data["marketplaces"], data["plugins"]
        out: object = {"ok": True}
        head = args[:2]
        if head == ["marketplace", "list"]:
            out = [{"name": n, "source": "github", "repo": m["repo"],
                    **({"ref": m["ref"]} if m["ref"] else {})} for n, m in markets.items()]
        elif args == ["list"]:
            out = [dict(p, enabled=self._effective(data, p["id"], cwd),
                        installPath=str(self.config / "plugins" / "cache" / "lichtpfad"
                                        / p["id"].split("@")[0] / p["version"]))
                   for p in plugins]
        elif head == ["marketplace", "add"]:
            repo, _, ref = args[2].partition("#")
            if "lichtpfad" in markets:
                return self._fail(argv, "marketplace 'lichtpfad' is already installed")
            markets["lichtpfad"] = {"repo": repo, "ref": ref or None,
                                    "offers": self.pins[ref] if ref else self.head}
        elif head == ["marketplace", "update"]:
            m = markets.get(args[2])
            if m is None:
                return self._fail(argv, f"marketplace {args[2]} not found")
            m["offers"] = self.pins[m["ref"]] if m["ref"] else self.head
        elif head == ["marketplace", "remove"]:
            if markets.pop(args[2], None) is None:
                return self._fail(argv, f"marketplace {args[2]} not found")
            gone = {p["id"] for p in plugins if p["id"].endswith("@" + args[2])}
            plugins[:] = [p for p in plugins if p["id"] not in gone]
            for flags in [data["user"], *data["projects"].values()]:
                for pid in gone:
                    flags.pop(pid, None)
        elif args[0] in ("install", "update", "disable"):
            pid, scope = args[1], args[args.index("--scope") + 1]
            name, _, market = pid.partition("@")
            m = markets.get(market)
            if m is None or name not in CATALOG:
                return self._fail(argv, f"plugin {pid} not found")
            where = None if scope == "user" else cwd
            flags = data["user"] if where is None else data["projects"].setdefault(where, {})
            entry = next((p for p in plugins if p["id"] == pid and p["scope"] == scope
                          and p.get("projectPath") == where), None)
            if args[0] == "install":
                if entry is None:
                    plugins.append({"id": pid, "version": m["offers"], "scope": scope,
                                    **({"projectPath": where} if where else {})})
                    self._cache(name, m["offers"])
                flags[pid] = True
            elif entry is None:
                return self._fail(argv, f"plugin {pid} is not installed in scope {scope} here")
            elif args[0] == "update":
                entry["version"] = m["offers"]
                self._cache(name, m["offers"])
                if self.update_enables:
                    flags[pid] = True
            else:
                flags[pid] = False
        else:
            raise AssertionError(f"the fake does not know {args}")
        if out == {"ok": True}:
            self.save(data)
            self.tick("claude " + " ".join(args))
        return subprocess.CompletedProcess(argv, 0, json.dumps(out) + "\n", "")

    @staticmethod
    def _fail(argv, message):
        return subprocess.CompletedProcess(argv, 1, "", message + "\n")
