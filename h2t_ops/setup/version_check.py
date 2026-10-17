"""`h2t-ops version --expect`: is the installed package the one the skill expects, and does PATH reach it."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import h2t_ops
from h2t_ops.setup import state

# Task 13 replaces this with the bootstrap literal stamped by the release script.
BOOTSTRAP_HINT = "h2t-ops не установлен как инструмент uv. Выполни: h2t-setup sync"


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _inside(path: str, root: str) -> bool:
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def _result(ok: bool, reason: str | None, hint: str | None) -> dict:
    return {"ok": ok, "version": h2t_ops.__version__, "reason": reason, "hint": hint}


def check(expect: str, which=shutil.which) -> dict:
    install = state.read()
    if install is None:
        return _result(False, "not_installed", BOOTSTRAP_HINT)
    if h2t_ops.__version__ != expect or h2t_ops.__version__ != install.version:
        return _result(False, "version", (
            f"Ожидалась версия {expect}, запущена {h2t_ops.__version__}, "
            f"установлена {install.version}. Выполни: h2t-setup sync"))
    bad = []
    for name in install.entrypoints:
        found = which(name)
        if not found or not _inside(found, install.tool_root):
            bad.append(name)
    if bad:
        bin_dir = str(Path(next(iter(install.entrypoints.values()))).parent)
        return _result(False, "path", (
            f"Установка исправна, но PATH не ведёт к ней для: {', '.join(bad)}. "
            f"Каталог команд: {bin_dir}. перезапусти харнесс; если не помогло, "
            "выполни сам: uv tool update-shell"))
    return _result(True, None, None)
