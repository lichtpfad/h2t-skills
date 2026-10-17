"""A stateful stand-in for `claude plugin … --json`, injected as the `run` of
`harness_claude.Claude`, so the real wrapper builds every command line it parses.

State lives in a JSON file: marketplaces (with `ref` when pinned and the version their
catalog offers) and installed plugins (version, scope, enabled). Behaviour follows the
probes of 2026-10-17 (docs/reports/2026-10-17-package-arch-probes.md, row 3):
`marketplace remove` uninstalls the marketplace's plugins and forgets that one was
disabled; `install` enables; `update` keeps enabled as it was.
"""
from __future__ import annotations

import json
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


class FakeClaude:
    def __init__(self, path: Path, config: Path, *, head: str, pins: dict[str, str] | None = None,
                 tick=None, fail_on: str | None = None) -> None:
        self.path = Path(path)
        self.config = Path(config)
        self.head = head  # what main's catalog offers
        self.pins = pins or {}  # ref -> what that ref's catalog offers
        self.tick = tick or (lambda label: None)
        self.fail_on = fail_on  # a command prefix that exits 1, once
        self.calls: list[list[str]] = []
        if not self.path.exists():
            self.save({"marketplaces": {}, "plugins": []})

    # -- state ------------------------------------------------------------------------
    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")

    def seed(self, *, ref: str | None = None, offers: str | None = None,
             plugins: list[tuple[str, str, str, bool]] = ()) -> None:
        """A marketplace (pinned to `ref` when given) and installed (name, version, scope,
        enabled) plugins."""
        data = {"marketplaces": {"lichtpfad": {
            "repo": "lichtpfad/h2t-skills", "ref": ref,
            "offers": offers or (self.pins[ref] if ref else self.head)}}, "plugins": []}
        for name, version, scope, enabled in plugins:
            data["plugins"].append({"id": f"{name}@lichtpfad", "version": version,
                                    "scope": scope, "enabled": enabled})
            self._cache(name, version)
        self.save(data)

    def installed(self) -> dict[str, dict]:
        return {p["id"].split("@")[0]: p for p in self.load()["plugins"]}

    def mutations(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] not in (["marketplace", "list"], ["list"])]

    def _cache(self, name: str, version: str) -> Path:
        d = self.config / "plugins" / "cache" / "lichtpfad" / name / version
        d.mkdir(parents=True, exist_ok=True)
        (d / "plugin.json").write_text(json.dumps({"name": name, "version": version}))
        return d

    # -- the process ------------------------------------------------------------------
    def __call__(self, argv, **kwargs):
        assert argv[1] == "plugin" and argv[-1] == "--json", argv
        args = list(argv[2:-1])
        self.calls.append(args)
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
        elif head == ["list"] or args == ["list"]:
            out = [dict(p, installPath=str(self.config / "plugins" / "cache" / "lichtpfad"
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
            plugins[:] = [p for p in plugins if not p["id"].endswith("@" + args[2])]
        elif args[0] in ("install", "update", "disable"):
            pid, scope = args[1], args[args.index("--scope") + 1]
            name, _, market = pid.partition("@")
            m = markets.get(market)
            if m is None or name not in CATALOG:
                return self._fail(argv, f"plugin {pid} not found")
            entry = next((p for p in plugins if p["id"] == pid and p["scope"] == scope), None)
            if args[0] == "install":
                if entry is None:
                    plugins.append({"id": pid, "version": m["offers"], "scope": scope,
                                    "enabled": True})
                    self._cache(name, m["offers"])
            elif entry is None:
                return self._fail(argv, f"plugin {pid} is not installed in scope {scope}")
            elif args[0] == "update":
                entry["version"] = m["offers"]
                self._cache(name, m["offers"])
            else:
                entry["enabled"] = False
        else:
            raise AssertionError(f"the fake does not know {args}")
        if out == {"ok": True}:
            self.save(data)
            self.tick("claude " + " ".join(args))
        return subprocess.CompletedProcess(argv, 0, json.dumps(out) + "\n", "")

    @staticmethod
    def _fail(argv, message):
        return subprocess.CompletedProcess(argv, 1, "", message + "\n")
