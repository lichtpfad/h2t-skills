"""`h2t-setup sync`: the executor of the target release (spec §7.3.2) and the steps after it.

Only the target's own code, run from an isolated `uvx`, may bring an install to the target:
an older executor does not know the newer steps, and one running from the installed tool's
environment would be replacing the environment it runs from.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import h2t_ops
from h2t_ops.core.errors import ConfigError, H2TError
from h2t_ops.setup import harness_claude, manifest, state
from h2t_ops.setup.manifest import render
from h2t_ops.setup.version_check import inside

# Set to the target version before the re-launch. If the process it starts is still not the
# target, the release's bootstrap does not produce its own version, and launching it again
# would loop forever.
RELAUNCH_ENV = "H2T_SETUP_RELAUNCHED_FOR"
# Read at call time, so a test can choose the branch without changing os.name for everyone.
OS_NAME = os.name


def uv_tool_root(which=shutil.which, run=subprocess.run) -> str | None:
    """The `h2t-ops` directory under `uv tool dir`, if there is one: a 3.x install has no
    install.json, and its executor must still count as the installed tool."""
    uv = which("uv")
    if not uv:
        return None
    try:
        done = run([uv, "tool", "dir"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0 or not done.stdout.strip():
        return None
    root = Path(done.stdout.strip()) / "h2t-ops"
    return str(root) if root.is_dir() else None


def installed_tool_root(detect=None) -> str | None:
    install = state.read()
    if install is not None and install.tool_root:
        return install.tool_root
    return (detect or uv_tool_root)()


def receipt_editable(tool_root: str | None = None) -> str | None:
    """The checkout an install without install.json (3.x) is editable from, per uv's receipt.

    uv records `[tool] requirements = [{ name = "h2t-ops", editable = "<path>" }]`; a wheel or
    git install has no `editable` key there."""
    root = tool_root or uv_tool_root()
    if not root:
        return None
    main, _ = _receipt_requirements(_receipt(root))
    editable = main.get("editable")
    return editable if isinstance(editable, str) and editable else None


def _receipt(root: str | Path) -> dict:
    """The `[tool]` table of uv's receipt, or {} when there is none to read."""
    try:
        data = tomllib.loads((Path(root) / "uv-receipt.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):  # TOMLDecodeError and UnicodeDecodeError are ValueError
        return {}
    tool = data.get("tool")
    return tool if isinstance(tool, dict) else {}


def _receipt_requirements(tool: dict) -> tuple[dict, list[dict]]:
    """The `h2t-ops` requirement and the others (the `--with` of that install)."""
    reqs = [r for r in tool.get("requirements") or [] if isinstance(r, dict)]
    main = next((r for r in reqs if r.get("name") == "h2t-ops"), {})
    return main, [r for r in reqs if r is not main and isinstance(r.get("name"), str)]


def receipt_entrypoints(tool: dict) -> dict[str, str]:
    return {e["name"]: e["install-path"] for e in tool.get("entrypoints") or []
            if isinstance(e, dict) and isinstance(e.get("name"), str)
            and isinstance(e.get("install-path"), str)}


def receipt_user_options(tool: dict) -> dict | None:
    """What an install without install.json (3.x) was asked for: its extras and `--with`."""
    main, others = _receipt_requirements(tool)
    if not main:
        return None
    extras = [e for e in main.get("extras") or [] if isinstance(e, str)]
    with_ = []
    for r in others:
        if isinstance(r.get("url"), str):
            with_.append(f"{r['name']} @ {r['url']}")
        else:
            extra = ",".join(e for e in r.get("extras") or [] if isinstance(e, str))
            with_.append(r["name"] + (f"[{extra}]" if extra else "") + (r.get("specifier") or ""))
    return {"extras": extras, "with": with_}


def relaunch_command(target: dict, mode: str, argv: list[str]) -> list[str]:
    """The frozen word order (§7.3.2): the mode is the first word after the bootstrap, the
    original arguments follow it.

    No word of argv carries consent: the parser takes `--json` only, and `update` asks its
    question inside `run`, after this hand-over. So nothing confirmed before the re-launch
    reaches the target; the target executor asks about its own version."""
    return list(target["bootstrap"]) + [mode] + list(argv)


def ensure_executor(target: dict, mode: str, argv: list[str], *, prefix: str | None = None,
                    version: str | None = None, tool_root: str | None = None,
                    execvp=None, os_name: str | None = None, spawn=None,
                    detect_tool_root=None) -> None:
    """Return if this process may act for `target`; otherwise hand over to its bootstrap.

    Continues only when this is the target version AND `prefix` lies outside the installed
    tool. Otherwise runs `relaunch_command`: the same mode and arguments, so `update` stays
    `update` (§7.3.2). POSIX replaces the process with `execvp`.

    Windows has no real exec. From outside the installed tool (an older isolated executor)
    the bootstrap runs as a child and its exit code becomes ours. From inside it (the
    installed h2t-setup started to repair itself) nothing is spawned: the waiting parent
    would hold the very environment the reinstall must delete, and Windows locks it. That
    case stops with ConfigError (exit 3, reason `relaunch_required`) whose hint is the exact
    command to run from a terminal.
    """
    prefix = sys.prefix if prefix is None else prefix
    version = h2t_ops.__version__ if version is None else version
    if tool_root is None:
        tool_root = installed_tool_root(detect=detect_tool_root)
    from_tool = bool(tool_root) and inside(prefix, tool_root)
    if version == target["version"] and not from_tool:
        # The marker scopes one re-launch; a child this run starts must not inherit it.
        os.environ.pop(RELAUNCH_ENV, None)
        return
    if os.environ.get(RELAUNCH_ENV) == target["version"]:
        raise ConfigError(
            f"the bootstrap of {target['version']} started h2t-setup {version} "
            f"from {prefix}; it does not reach its own release",
            hint="the release manifest is inconsistent; report it with h2t-core:report-issue")
    command = relaunch_command(target, mode, argv)
    windows = (os_name or OS_NAME) == "nt"
    if windows and from_tool:
        raise ConfigError(
            f"h2t-setup {version} runs from the installed tool {tool_root}, which the update "
            "replaces and Windows keeps locked while this process lives; run the command in "
            "the hint from a terminal",
            hint=render(command),
            details={"reason": "relaunch_required", "command": command})
    os.environ[RELAUNCH_ENV] = target["version"]
    if windows:
        done = (spawn or subprocess.run)(command)
        raise SystemExit(done.returncode)
    (execvp or os.execvp)(command[0], command)




# --- steps 3–8 of §7.3 ---------------------------------------------------------------------

DEFAULT_PLUGINS = ["h2t-core", "h2t-ops"]
KEEP_VERSIONS = 2
YES = {"да", "д", "yes", "y"}

# Sent to the tool environment's own python (`-I`, so nothing in the current directory
# shadows the package). It loads every console script of h2t-ops and imports what each
# chosen extra installs; `sync` compares the answer with the target.
PROBE = r"""
import importlib, importlib.metadata as md, json, re, sys
extras = json.loads(sys.argv[1])
import h2t_ops
out = {"version": h2t_ops.__version__, "unloadable": [], "missing": []}
dist = md.distribution("h2t-ops")
for ep in dist.entry_points:
    if ep.group == "console_scripts":
        try:
            ep.load()
        except Exception as exc:
            out["unloadable"].append(f"{ep.name}: {exc}")
norm = lambda s: re.sub(r"[-_.]+", "-", s).lower()
top = md.packages_distributions()
for extra in extras:
    pattern = r"extra\s*==\s*['\"]" + re.escape(extra) + r"['\"]"
    names = [re.match(r"[A-Za-z0-9._-]+", r).group(0) for r in dist.requires or []
             if re.search(pattern, r)]
    if not names:
        out["missing"].append(f"{extra}: no such extra")
    for name in names:
        try:
            md.version(name)
            for mod, dists in top.items():
                if not mod.startswith("_") and any(norm(d) == norm(name) for d in dists):
                    importlib.import_module(mod)
        except Exception as exc:
            out["missing"].append(f"{extra}: {name}: {exc}")
print(json.dumps(out))
"""


@dataclass
class Report:
    done: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    reload_needed: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"done": list(self.done), "failed": [list(f) for f in self.failed],
                "reload_needed": self.reload_needed, "notes": list(self.notes)}

    def text(self) -> str:
        lines = [f"done: {d}" for d in self.done]
        for subject, remedy in self.failed:
            lines.append(f"failed: {subject}")
            lines += [f"  {r}" for r in remedy.splitlines()]
        return "\n".join(lines + self.notes)


def run_uv(args: list[str]) -> subprocess.CompletedProcess:
    uv = shutil.which("uv")
    if not uv:
        raise ConfigError("uv is not on PATH", hint="the bootstrap runs from uvx; run it again")
    return subprocess.run([uv, *args], capture_output=True, text=True, encoding="utf-8")


def _tool_dir(uv) -> Path:
    done = uv(["tool", "dir"])
    if done.returncode != 0 or not (done.stdout or "").strip():
        raise ConfigError(f"`uv tool dir` failed: {(done.stderr or '').strip()}")
    return Path(done.stdout.strip())


def _last_install_json() -> dict | None:
    """install.json as written last, whatever install.env says: an interrupted run still
    knows what the user had chosen."""
    try:
        data = json.loads((state.run_dir() / "install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _utc_stamp() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _pending_path() -> Path:
    # The Claude Code part of a snapshot whose re-pin has not finished: a re-run after an
    # interruption must still restore the scopes and the disabled plugins it had.
    return state.run_dir() / "rollback" / "claude-pending.json"


def _snapshot(root: Path, claude) -> dict:
    """Step 3: what is there now, under ~/.h2t/run/rollback/<UTC>/."""
    where = state.run_dir() / "rollback" / _utc_stamp()
    where.mkdir(parents=True, exist_ok=True)
    for src in (state.run_dir() / "install.json", root / "uv-receipt.toml"):
        if src.is_file():
            shutil.copyfile(src, where / src.name)
    harness: dict = {"found": claude.found()}
    if harness["found"]:
        try:
            harness["marketplace"] = claude.marketplace()
            harness["plugins"] = claude.plugins()
        except harness_claude.HarnessError as exc:
            harness["error"] = str(exc)
    (where / "claude.json").write_text(json.dumps(harness, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    harness["path"] = str(where)
    return harness


def _python(root: Path) -> Path:
    return root / "Scripts" / "python.exe" if OS_NAME == "nt" else root / "bin" / "python"


def _verify(entrypoints: dict[str, str], root: Path, version: str, extras: list[str],
            execute) -> str | None:
    """None if the install, run, answers as `version` with `extras`; otherwise what did not."""
    if "h2t-ops" not in entrypoints:
        return "no h2t-ops entry point is recorded"
    absent = sorted(n for n, p in entrypoints.items() if not Path(p).is_file())
    if absent:
        return f"entry points missing: {', '.join(absent)}"
    try:
        done = execute([entrypoints["h2t-ops"], "--version"], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
        if done.returncode != 0:
            return f"`h2t-ops --version` exited {done.returncode}"
        words = (done.stdout or "").split()
        if words[:2] != ["h2t-ops", version]:
            return f"`h2t-ops --version` says {' '.join(words[:2]) or 'nothing'}"
        done = execute([str(_python(root)), "-I", "-c", PROBE, json.dumps(extras)],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"cannot run the install: {exc}"
    if done.returncode != 0:
        return f"the environment's python failed: {(done.stderr or '').strip()[-300:]}"
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        return "the environment's python gave no answer"
    if answer.get("version") != version:
        return f"the package is {answer.get('version')}"
    problems = list(answer.get("unloadable") or []) + list(answer.get("missing") or [])
    return "; ".join(problems) or None


def _install_args(target: dict, options: dict) -> list[str]:
    extras = ",".join(options.get("extras") or [])
    spec = f"h2t-ops[{extras}] @ {target['wheel']}" if extras else f"h2t-ops @ {target['wheel']}"
    args = ["tool", "install", "--reinstall", "--python", target["python"], "--managed-python",
            "-c", target["constraints"], spec]
    for w in options.get("with") or []:
        args += ["--with", w]
    return args


def _commit(version: str, root: Path, entrypoints: dict[str, str], options: dict,
            plugins: list[str], editable: str | None = None) -> None:
    # install.json, then install.env STATE=ready last (§6.4); a new generation every time.
    state.commit(state.Install(version=version, generation=str(uuid.uuid4()),
                               tool_root=str(root), entrypoints=entrypoints, editable=editable,
                               user_options=options, plugins=plugins))


def _cli_step(target: dict, root: Path, last: dict | None, plugins: list[str], uv, execute,
              report: Report, retry: str) -> bool:
    """Step 4: check the CLI by running it; reinstall only what does not answer."""
    version = target["version"]
    current = state.read()
    tool = _receipt(root)
    options = (last or {}).get("user_options") or receipt_user_options(tool) or {}
    options = {"extras": list(options.get("extras") or []), "with": list(options.get("with") or [])}
    entrypoints = current.entrypoints if current is not None else receipt_entrypoints(tool)
    problem = _verify(entrypoints, root, version, options["extras"], execute)
    if problem is None:
        _commit(version, root, entrypoints, options, plugins)
        report.done.append(f"CLI h2t-ops {version}: answers as the target when run")
        return True
    state.begin_update(version)
    done = uv(_install_args(target, options))
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-1:] or ["no output"]
        report.failed.append((f"CLI h2t-ops {version}: uv tool install failed: {tail[0]}", retry))
        _keep_previous(last, root, execute)
        return False
    entrypoints = receipt_entrypoints(_receipt(root))
    after = _verify(entrypoints, root, version, options["extras"], execute)
    if after is not None:
        # install.env stays `updating`: the wrapper and the next sync read it as no install.
        report.failed.append((f"CLI h2t-ops {version}: installed but does not answer: {after}",
                              retry))
        return False
    _commit(version, root, entrypoints, options, plugins)
    report.done.append(f"CLI h2t-ops {version}: reinstalled ({problem}); answers when run")
    return True


def _keep_previous(last: dict | None, root: Path, execute) -> None:
    """A failed resolution leaves the previous CLI working (probe 2026-10-16). If it still
    answers as the version install.json recorded, write it back as ready."""
    if not last or not isinstance(last.get("entrypoints"), dict) or not last.get("version"):
        return
    options = last.get("user_options") or {"extras": [], "with": []}
    if _verify(last["entrypoints"], root, last["version"], list(options.get("extras") or []),
               execute) is None:
        _commit(last["version"], root, last["entrypoints"], options,
                list(last.get("plugins") or []), editable=last.get("editable") or None)


def _plugin_set(last: dict | None, harness: dict) -> list[str]:
    """§6.4: install.json; else the installed plugins of lichtpfad; else the default two."""
    if last is not None and isinstance(last.get("plugins"), list):
        return [p for p in last["plugins"] if isinstance(p, str)]
    names = sorted({p["id"].split("@")[0] for p in harness.get("plugins") or []})
    return names or list(DEFAULT_PLUGINS)


def _name(entry: dict) -> str:
    return str(entry.get("id", "")).split("@")[0]


def _scope(entry: dict) -> str:
    return entry.get("scope") or "user"


def _where(entry: dict) -> str | None:
    """The directory a command for this entry runs in: its project, or None (neutral)."""
    if _scope(entry) in harness_claude.PROJECT_SCOPES:
        return entry.get("projectPath") or ""
    return None


def _gone(cwd: str | None) -> bool:
    return cwd is not None and not (cwd and Path(cwd).is_dir())


def _key(entry: dict) -> tuple:
    return (entry.get("id"), _scope(entry), _where(entry))


def _show(args: tuple[str, ...], cwd: str | None) -> str:
    line = harness_claude.Claude.shown(args, cwd or None)
    return f"manual (the project directory is gone): {line}" if _gone(cwd) else line


def _restore_plan(names: list[str], before: list[dict]) -> list[tuple[str, tuple, str | None]]:
    """(kind, args, cwd) that rebuild the snapshot after `remove`: an install for EVERY entry
    (remove uninstalls every scope, probe 3b), a user-scope one for a set member the snapshot
    lacks, then a disable for each entry disabled in its own scope."""
    C = harness_claude.Claude
    plan = [("install", C.install_args(_name(e), _scope(e)), _where(e)) for e in before]
    present = {_name(e) for e in before}
    plan += [("install", C.install_args(n, "user"), None) for n in names if n not in present]
    plan += [("disable", C.disable_args(_name(e), _scope(e)), _where(e)) for e in before
             if e.get("enabled") is False]
    return plan


def _apply(claude, kind: str, args: tuple, cwd: str | None) -> None:
    getattr(claude, kind)(args[1].split("@")[0], args[3], cwd or None)


def _redisable(claude, before: list[dict], hold=lambda: None) -> None:
    """Disable again what the snapshot had disabled in its own scope (remove forgets it,
    probe 3b; whether update keeps it is not probed)."""
    now = {_key(p): p for p in claude.plugins()}
    for p in before:
        if p.get("enabled") is not False or _gone(_where(p)):
            continue
        cur = now.get(_key(p))
        if cur is not None and cur.get("enabled") is not False:
            hold()
            claude.disable(_name(p), _scope(p), _where(p) or None)


def _restore(claude, before: dict) -> None:
    """Put Claude Code back as the snapshot had it: the marketplace on its ref, each entry in
    its scope (and project), the disabled ones disabled."""
    market = before.get("marketplace") or {}
    ref = market.get("ref")
    now = claude.marketplace()
    if now is not None and now.get("ref") != ref:
        claude.marketplace_remove()
        now = None
    if now is None:
        claude.marketplace_add(ref, market.get("repo") or harness_claude.SOURCE)
    have = {_key(p) for p in claude.plugins()}
    for p in before.get("plugins") or []:
        if _key(p) not in have and not _gone(_where(p)):
            claude.install(_name(p), _scope(p), _where(p) or None)
    _redisable(claude, before.get("plugins") or [])


def _plugins_step(mode: str, target: dict, names: list[str], harness: dict, claude, confirm,
                  report: Report, retry: str) -> bool:
    """Step 5. Returns whether anything in Claude Code changed."""
    version = target["version"]
    if not names:
        report.failed.append(("Claude Code: the managed plugin set is empty "
                              "(install.json `plugins`); nothing to bring to the target", retry))
        return False
    pending = _pending_path()
    try:
        before = json.loads(pending.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        before = {"marketplace": harness.get("marketplace"),
                  "plugins": harness.get("plugins") or []}

    def hold() -> None:
        # Before the first mutation: a crash anywhere after it (between an update and the
        # re-disable, mid re-pin) leaves the rerun the state to restore.
        if not pending.exists():
            pending.parent.mkdir(parents=True, exist_ok=True)
            pending.write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")

    changed = False
    manual: list[str] = []
    manual_names: set[str] = set()

    def by_hand(name: str, line: str) -> None:
        manual_names.add(name)
        if line not in manual:
            manual.append(line)

    try:
        market = claude.marketplace()
        fresh = False
        if market is None:
            hold()
            claude.marketplace_add()
            report.done.append(f"Claude Code: marketplace added: {harness_claude.SOURCE}")
            changed = fresh = True
        elif market.get("ref") not in (None, "", "main"):
            ref = market["ref"]
            plan = _restore_plan(names, before["plugins"])
            C = harness_claude.Claude
            shown = "\n".join([C.shown(C.remove_args()), C.shown(C.add_args())]
                              + [_show(args, cwd) for _, args, cwd in plan])
            subject = (f"Claude Code: marketplace lichtpfad is pinned to {ref}; re-pinning means "
                       "`remove`, which uninstalls its plugins in every scope")
            if mode != "update":
                report.failed.append((subject + "; sync changes nothing here", shown))
                return False
            answer = confirm(
                f"Marketplace lichtpfad закреплён на {ref}. Перезакрепление запускает "
                "`marketplace remove`, а он удаляет плагины lichtpfad во всех scope; затем "
                "они ставятся заново с тем же scope и тем же состоянием disabled. "
                f"Команды:\n{shown}\nда? ")
            if (answer or "").strip().lower() not in YES:
                report.failed.append((subject + "; not confirmed, plugins unchanged", shown))
                return False
            hold()
            try:
                claude.marketplace_remove()
                changed = True
                claude.marketplace_add()
                for kind, args, cwd in plan:
                    if _gone(cwd):
                        by_hand(args[1].split("@")[0], _show(args, cwd))
                    else:
                        _apply(claude, kind, args, cwd)
            except harness_claude.HarnessError as exc:
                try:
                    _restore(claude, before)
                except harness_claude.HarnessError as again:
                    report.failed.append((f"Claude Code: re-pin failed ({exc}) and the restore "
                                          f"failed too ({again})", shown))
                    return True
                pending.unlink(missing_ok=True)
                report.failed.append((f"Claude Code: re-pin failed ({exc}); restored as it was "
                                      f"(pinned to {ref})", retry))
                return True
            report.done.append(f"Claude Code: marketplace lichtpfad re-pinned from {ref} to main")
            fresh = True

        current = claude.plugins()
        present = {_name(e) for e in current}
        missing = [n for n in names if n not in present]
        behind = [e for e in current if _name(e) in names and e.get("version") != version]
        if (missing or behind) and not fresh:
            hold()
            claude.marketplace_update()
        C = harness_claude.Claude
        for n in missing:
            own = [e for e in before["plugins"] if _name(e) == n] or [
                {"id": harness_claude.plugin_id(n), "scope": "user"}]
            for e in own:
                args, cwd = C.install_args(n, _scope(e)), _where(e)
                if _gone(cwd):
                    by_hand(n, _show(args, cwd))
                    continue
                hold()
                _apply(claude, "install", args, cwd)
                changed = True
                report.done.append(f"Claude Code: {n} installed ({_scope(e)})")
        for e in behind:
            args, cwd = C.update_args(_name(e), _scope(e)), _where(e)
            if _gone(cwd):
                by_hand(_name(e), _show(args, cwd))
                continue
            hold()
            _apply(claude, "update", args, cwd)
            changed = True
            report.done.append(f"Claude Code: {_name(e)} {e.get('version')} → {version} "
                               f"({_scope(e)})")
        # A plugin the user disabled stays disabled (Review Focus 5), whatever an update did.
        _redisable(claude, before["plugins"], hold)
        # Everything the snapshot asked for has been applied: a later run must not replay an
        # old disabled state over a choice the user makes after this one.
        pending.unlink(missing_ok=True)
        final = [e for e in claude.plugins() if not _gone(_where(e))]
        wrong = []
        for n in names:
            mine = [e for e in final if _name(e) == n]
            if not mine and n in manual_names:
                continue
            if not mine or any(e.get("version") != version for e in mine):
                wrong.append(f"{n} {', '.join(str(e.get('version')) for e in mine) or 'absent'}")
    except harness_claude.HarnessError as exc:
        report.failed.append((f"Claude Code: {exc}", retry))
        return changed
    for line in manual:
        report.notes.append(f"Claude Code: {line}")
    if wrong:
        report.failed.append((f"Claude Code: not at {version}: {'; '.join(wrong)}", retry))
        return changed
    if not changed:
        report.done.append(f"Claude Code: {', '.join(names)} already at {version}")
    return changed


def _semver(name: str) -> tuple[int, int, int] | None:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", name)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


# A seam for the interruption tests; deletion is the step there.
_remove_tree = shutil.rmtree


def clean_cache(config: Path, installed: list[dict], keep: int = KEEP_VERSIONS) -> list[Path]:
    """Step 7: under <config>/plugins/cache/lichtpfad/<plugin>/, keep the `keep` highest
    versions and every installed one; delete the other version directories. Names that are
    not X.Y.Z are not versions and stay."""
    root = Path(config) / "plugins" / "cache" / harness_claude.MARKETPLACE
    if not root.is_dir() or root.is_symlink():
        return []
    held = {(p["id"].split("@")[0], str(p.get("version"))) for p in installed
            if isinstance(p.get("id"), str)}
    removed = []
    for plugin in sorted(root.iterdir()):
        if plugin.is_symlink() or not plugin.is_dir():
            continue
        versions = sorted(((_semver(d.name), d) for d in plugin.iterdir()
                           if d.is_dir() and not d.is_symlink() and _semver(d.name)),
                          reverse=True)
        for _, d in versions[keep:]:
            if (plugin.name, d.name) not in held:
                _remove_tree(d)
                removed.append(d)
    return removed


def _codex_note(names: list[str]) -> str:
    lines = ["Codex: sync does not manage its plugins. Install them for this release by hand:",
             "  codex plugin marketplace add lichtpfad/h2t-skills"]
    lines += [f"  codex plugin add {harness_claude.plugin_id(n)}" for n in names]
    return "\n".join(lines)


# --- update: the question before step 3 (§7.3, last paragraph) -----------------------------

def ask(prompt: str) -> str:
    """The default question: the prompt on stderr, so `--json` keeps stdout to the envelope;
    one line from stdin, and "" at its end, which is not a yes."""
    sys.stderr.write(prompt)
    sys.stderr.flush()
    return sys.stdin.readline()


def changelog_url(version: str) -> str:
    return f"{manifest.RAW}/v{version}/CHANGELOG.md"


def changelog_sections(text: str, installed: str | None, target: str) -> str | None:
    """The `## <ver>` sections (Task 13's contract) newer than `installed` up to `target`,
    in file order; only the target's own when `installed` is not X.Y.Z. None when the file
    has no section for the target."""
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        m = re.match(r"## (\S+)", line)
        if m:
            sections.append((m[1], [line]))
        elif sections:
            sections[-1][1].append(line)
    if target not in {v for v, _ in sections}:
        return None
    low, high = _semver(installed or ""), _semver(target)

    def wanted(v: str) -> bool:
        s = _semver(v)
        return v == target or bool(low and high and s and low < s < high)
    return "\n\n".join("\n".join(lines).strip() for v, lines in sections if wanted(v))


def _changelog(version: str, installed: str | None, fetch) -> str:
    url = changelog_url(version)
    try:
        shown = changelog_sections(fetch(url).decode("utf-8"), installed, version)
    except (H2TError, OSError, ValueError):  # UnicodeDecodeError is a ValueError
        shown = None
    return shown if shown is not None else f"CHANGELOG недоступен: {url}"


def _installed_version(root: Path, execute) -> str | None:
    """What the installed CLI says it is, when run; None when it does not answer."""
    current = state.read()
    entrypoints = current.entrypoints if current is not None else receipt_entrypoints(
        _receipt(root))
    exe = entrypoints.get("h2t-ops")
    if not exe or not Path(exe).is_file():
        return None
    try:
        done = execute([exe, "--version"], capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    words = (done.stdout or "").split()
    return words[1] if done.returncode == 0 and words[:1] == ["h2t-ops"] and len(words) > 1 \
        else None


def _preview(target: dict, root: Path, claude, execute, fetch) -> str:
    """«было → станет» for the CLI and each plugin of the set, then the target's CHANGELOG.
    Reads only: nothing is written before the answer."""
    version = target["version"]
    was = _installed_version(root, execute)
    lines = ["h2t-setup update: было → станет",
             f"  CLI h2t-ops: {was or 'не установлен'} → {version}"]
    try:
        plugins = claude.plugins() if claude.found() else None
    except harness_claude.HarnessError:
        plugins = None
    if plugins is None:
        lines.append("  Claude Code: не найден или не читается; плагины не сравнить")
    else:
        for name in _plugin_set(_last_install_json(), {"plugins": plugins}):
            have = [str(e.get("version")) for e in plugins if _name(e) == name]
            lines.append(f"  {name}: {', '.join(have) or 'не установлен'} → {version}")
    try:
        market = claude.marketplace() if plugins is not None else None
    except harness_claude.HarnessError:
        market = None
    ref = (market or {}).get("ref")
    if ref not in (None, "", "main"):
        lines.append(f"  Marketplace lichtpfad закреплён на {ref}: после этого будет второй "
                     "вопрос — о перезакреплении, которое переустанавливает плагины")
    lines += ["", f"CHANGELOG {version}:", _changelog(version, was, fetch), ""]
    return "\n".join(lines)


# --- dev-sync (§7.4) ----------------------------------------------------------------------

DEV_RETRY = "h2t-setup dev-sync"


def find_checkout(start: Path) -> Path | None:
    """The nearest directory at or above `start` whose pyproject.toml names h2t-ops."""
    for d in [start, *start.parents]:
        try:
            data = tomllib.loads((d / "pyproject.toml").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        project = data.get("project")
        if isinstance(project, dict) and project.get("name") == "h2t-ops":
            return d
    return None


def _installed_plugins(claude) -> list[dict]:
    """What Claude Code has installed, read only; [] when it is absent or does not answer."""
    try:
        return claude.plugins() if claude.found() else []
    except harness_claude.HarnessError:
        return []


def _plugins_note(checkout: Path) -> str:
    return ("Plugins: dev-sync does not touch the marketplace plugins. Load them from the "
            f"checkout: claude --plugin-dir {checkout / 'plugins'}/<name> "
            "(or pwsh scripts/claude-dev.ps1). The checkout itself is not updated: git is "
            "yours to run.")


def dev_sync(uv, execute, claude, cwd: str | None = None) -> Report:
    """The CLI from the checkout, editable, with the checkout's own constraints and the
    user's options; verified by running it, then install.json and install.env with
    EDITABLE_ROOT. Offline (the lock is exported `--frozen --offline`); no git."""
    start = Path(cwd or os.getcwd()).resolve()
    checkout = find_checkout(start)
    if checkout is None:
        raise ConfigError(f"no h2t-ops checkout at or above {start}",
                          hint="run `h2t-setup dev-sync` from inside an h2t-skills checkout",
                          details={"reason": "not_a_checkout"})
    project = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project.get("version")
    if not isinstance(version, str) or not version:
        raise ConfigError(f"{checkout / 'pyproject.toml'} has no static [project] version")
    root = _tool_dir(uv) / "h2t-ops"
    constraints = state.run_dir() / "dev-constraints.txt"
    constraints.parent.mkdir(parents=True, exist_ok=True)
    done = uv(["export", "--project", str(checkout), "--frozen", "--offline", "--no-dev",
               "--all-extras", "--no-emit-project", "--no-hashes", "-o", str(constraints)])
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-1:] or ["no output"]
        raise ConfigError(f"cannot export constraints from {checkout / 'uv.lock'}: {tail[0]}",
                          hint=f"bring the lock up to date in the checkout (`uv lock`), then "
                               f"run `{DEV_RETRY}` again")
    last = _last_install_json()
    options = (last or {}).get("user_options") or receipt_user_options(_receipt(root)) or {}
    options = {"extras": list(options.get("extras") or []), "with": list(options.get("with") or [])}
    extras = ",".join(options["extras"])
    args = ["tool", "install", "--editable", f"{checkout}[{extras}]" if extras else str(checkout),
            "--reinstall", "-c", str(constraints)]
    for w in options["with"]:
        args += ["--with", w]
    if OS_NAME == "nt" and inside(sys.prefix, str(root)):
        # The same lock as the repair from inside the tool (ensure_executor): the reinstall
        # deletes the environment this process runs from, and Windows holds it.
        command = ["uv", *args]
        raise ConfigError(
            f"h2t-setup runs from the installed tool {root}, which dev-sync replaces and "
            "Windows keeps locked while this process lives; run the command in the hint "
            "from a terminal",
            hint=render(command), details={"reason": "relaunch_required", "command": command})
    report = Report()
    state.begin_update(version)
    done = uv(args)
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-1:] or ["no output"]
        report.failed.append((f"CLI h2t-ops {version} (editable {checkout}): uv tool install "
                              f"failed: {tail[0]}", DEV_RETRY))
        _keep_previous(last, root, execute)
        return report
    entrypoints = receipt_entrypoints(_receipt(root))
    problem = _verify(entrypoints, root, version, options["extras"], execute)
    if problem is not None:
        report.failed.append((f"CLI h2t-ops {version} (editable {checkout}): installed but "
                              f"does not answer: {problem}", DEV_RETRY))
        return report
    # §6.4: install.json; else the installed lichtpfad plugins; else the default two.
    plugins = _plugin_set(last, {"plugins": _installed_plugins(claude)})
    _commit(version, root, entrypoints, options, plugins, editable=str(checkout))
    report.done.append(f"CLI h2t-ops {version}: installed editable from {checkout}; "
                       "answers when run")
    report.notes.append(_plugins_note(checkout))
    return report


def run(mode: str, target: dict | None, argv: list[str], *, uv=None, claude=None,
        confirm=None, execute=None, which=shutil.which, fetch=None) -> Report:
    """Steps 3–8 of §7.3. Every step compares the fact with the target and skips what
    matches, so a run after any interruption continues from the first mismatch.

    `uv` runs one uv command (default `run_uv`); `execute` runs the installed processes the
    check starts (default subprocess.run); `claude` is a harness_claude.Claude (created here
    when None); `confirm` asks `update`'s questions (default `ask`); `fetch` reads the
    target's CHANGELOG (default manifest.urllib_fetch)."""
    # Resolved here, not at definition: the tests refuse the real ones by patching these.
    uv = uv or run_uv
    execute = execute or subprocess.run
    claude = claude if claude is not None else harness_claude.Claude()
    if mode == "dev-sync":
        return dev_sync(uv, execute, claude)
    confirm = confirm or ask
    root = _tool_dir(uv) / "h2t-ops"
    # cli.main stops here first; this is the same stop for a caller that skips it.
    install = state.read()
    checkout = install.editable if install is not None else receipt_editable(str(root))
    if checkout:
        raise ConfigError(f"the CLI is installed editable from the checkout {checkout}; "
                          f"`h2t-setup {mode}` does not touch it",
                          hint="update the checkout yourself, then run `h2t-setup dev-sync`",
                          details={"reason": "editable", "checkout": checkout})
    report = Report()
    if mode == "update":
        # Asked by this executor, the target's own: a yes given to an older one before the
        # re-launch never reaches here (§7.3.2). Before the snapshot, so a no writes nothing.
        preview = _preview(target, root, claude, execute, fetch or manifest.urllib_fetch)
        answer = confirm(preview + "да? ")
        if (answer or "").strip().lower() not in YES:
            report.notes.append(f"h2t-setup update to {target['version']} not confirmed; "
                                "nothing was changed")
            return report
    retry = render(relaunch_command(target, "sync", [])) or "h2t-setup sync"
    harness = _snapshot(root, claude)                                         # 3
    last = _last_install_json()
    names = _plugin_set(last, harness)
    cli_ok = _cli_step(target, root, last, names, uv, execute, report, retry)  # 4
    changed = False
    if not harness["found"]:                                                  # 5
        report.notes.append("Claude Code: `claude` not found; no plugins were managed")
    elif not cli_ok:
        report.notes.append(f"Claude Code: plugins left as they are; they follow the CLI, "
                            f"which is not at {target['version']}")
    else:
        changed = _plugins_step(mode, target, names, harness, claude, confirm, report, retry)
    if which("codex"):                                                        # 6
        report.notes.append(_codex_note(names))
    if harness["found"]:                                                      # 7
        try:
            removed = clean_cache(harness_claude.config_dir(), claude.plugins())
        except harness_claude.HarnessError as exc:
            report.notes.append(f"plugin cache not cleaned: cannot list what is installed ({exc})")
        else:
            if removed:
                changed = True
                report.done.append("plugin cache: removed " + ", ".join(
                    f"{d.parent.name} {d.name}" for d in removed))
    report.reload_needed = changed                                            # 8
    if changed:
        report.notes.append("Open Claude Code sessions: run /reload-plugins or start a new "
                            "session. Sessions more than two releases old must: their plugin "
                            "files may have been removed from the cache.")
    if report.failed:
        report.notes.append(f"Repeat after fixing: {retry}")
    return report
