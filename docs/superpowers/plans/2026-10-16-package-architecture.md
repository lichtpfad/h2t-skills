---
title: "Package architecture"
status: "draft"
owner: "lichtpfad"
date: "2026-10-16"
milestone: ""
issue: "541"
---

# Package architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** весь исполняемый код пака — в пакете `h2t_ops`, плагины — тексты и `hooks/run`; на машине всегда одна версия пака, `h2t-setup sync` сводит машину к текущему выпуску из любого состояния.

**Architecture:** выпуск — тег + GitHub Release (wheel, constraints, `release.json`) + указатель на main (`marketplace.json` с `git-subdir`). Обёртка `hooks/run` сравнивает две строки версий на bash и запускает `h2t-hook`. `sync` работает из `uvx --isolated` и проверяет установку запуском; состояние фиксирует `install.env`, записываемый последним.

**Tech Stack:** Python 3.12.11 (uv-managed), uv ≥ 0.9, hatchling, bash (macOS, Git Bash на Windows), GitHub Actions, Claude Code plugin CLI.

**Spec:** `docs/superpowers/specs/2026-10-16-package-architecture.md` (v5, прошла раунд 6 Codex). Исполнитель читает спеку и план вместе; номера разделов ниже — разделы спеки.

## Global Constraints

- Python выпуска: `3.12.11`, всегда с `--managed-python`; `requires-python = ">=3.11"` в `pyproject.toml` не меняется (dev-окружения).
- Имя дистрибутива — `h2t-ops`; модуль — `h2t_ops`; девять существующих команд сохраняют имена.
- Код выхода: 0 ok, 1 provider, 2 usage **для коннекторов**, 3 config, 4 auth, 5 not found, 6 network. Для `h2t-hook` код 2 — только намеренная блокировка; ошибка разбора аргументов `h2t-hook` — 64.
- Каналы хуков: `hookSpecificOutput.additionalContext` — модели; `systemMessage` — человеку.
- Уведомление о версиях — только на `SessionStart`, один раз на `session_id`, каналом `systemMessage`.
- Сравнение версий в bash — только на равенство.
- `uvx` в бутстрапе — всегда с `--isolated`.
- Порядок записи состояния: `install.env` `STATE=updating` → замена CLI → проверка запуском → `install.json` → `install.env` `STATE=ready` последним.
- Кэш плагинов: `sync` оставляет две последние версии на плагин.
- `url` в `git-subdir` — полный HTTPS-адрес `https://github.com/lichtpfad/h2t-skills.git` (сокращение уходит в SSH).
- Ни один шаг не меняет данных в `~/.h2t` (кроме `~/.h2t/run`, `~/.h2t/logs`), `~/.dor`, `~/.config`. Порядок поиска секретов не меняется.
- Codex: скиллы и CLI поддерживаются, плагины `sync` не ставит.
- Репо-правила: тест засчитывается только после красного прогона; все 15 путей pytest из `.github/workflows/evals.yml` отдельно; `uvx ruff@0.16.4 check plugins/ lib/ h2t_ops/ tests/ scripts/`; явные пути в `git add`; без heredoc в Bash; commit/push/tag — только с согласия владельца на шагах, помеченных **[владелец]**.

## Review Focus

1. **Windows-путь с пробелом или кириллицей в `H2T_HOOK`** (`C:/Users/Лидия Иванова/.local/bin/h2t-hook.exe`): обёртка должна запустить его, а не разрезать по пробелу. Тест — в Task 9.
2. **`session_id` отсутствует в payload `SessionStart`** (старый харнесс, Codex): уведомление должно появиться, а не упасть на `mkdir ""`. Тест — в Task 9.
3. **`install.env` с CRLF** (запись на Windows, чтение Git Bash): `VERSION=4.0.0\r` не равно `4.0.0`. Чтение обязано срезать `\r`. Тест — в Task 5 (писатель пишет LF) и Task 9 (читатель терпит CRLF).
4. **Сеть недоступна на шаге «цель» `sync`**: ничего не тронуто, код 6, текст причины. Тест — в Task 14.
5. **Пользователь отключил плагин h2t-ops, но оставил h2t-core**: `sync` не включает выключенное обратно и не считает его отсутствующим. Тест — в Task 15.

---

## Фаза P — пробы (первыми; от результатов зависят пороги и ветки)

Каждая проба пишет результат в `docs/reports/2026-10-XX-package-arch-probes.md` (одна таблица: проба, команда, что получено, вывод) и, если результат меняет спеку, правку в §10 спеки. Пробы — во временных каталогах (`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `CLAUDE_CONFIG_DIR`), глобальная установка не трогается.

### Task 1: Пробы на macOS

**Files:**
- Create: `docs/reports/2026-10-XX-package-arch-probes.md` (дата — день выполнения, генератор не нужен: отчёт без frontmatter-контракта; проверить `lint.py doctor` на отчёт)
- Create: `scripts/probes/` — не создавать; команды живут в отчёте

**Interfaces:** Produces — таблица результатов, на которую ссылаются Task 9 (порог таймаута), Task 14–16 (ветки `sync`).

- [x] **Step 1: Wheel по URL GitHub Release.** На форке нет Release; используем черновой Release в репозитории только с согласия **[владелец]**, иначе — локальный HTTP-сервер, отдающий wheel и `constraints.txt` по URL:

```bash
uv build --wheel -o "$SP/whl"
uv export --frozen --no-dev --all-extras --no-emit-project --no-hashes -o "$SP/whl/constraints.txt"
(cd "$SP/whl" && python3 -m http.server 8765) &
uvx --isolated --python 3.12.11 --managed-python -c http://127.0.0.1:8765/constraints.txt \
  --from "h2t-ops @ http://127.0.0.1:8765/h2t_ops-0.2.1-py3-none-any.whl" h2t-ops --version
```
Expected: печатает версию; записать время холодного и тёплого запуска.

- [x] **Step 2: Прерывание `uv tool install --reinstall`.** Установить во временный каталог, запустить переустановку и через 2 с `kill -9`; затем `h2t-ops --version` и повторная установка.
Expected (записать факт): рабочая/нерабочая старая установка; повтор восстанавливает.

- [x] **Step 3: Закреплённый marketplace.** В изолированном `CLAUDE_CONFIG_DIR`: `add lichtpfad/h2t-skills#v2.15.0`, `install h2t-core --scope user`, `disable`, затем `remove` → `add` без ref → `install` → `disable`. Записать, сохранились ли scope и disabled без восстановления из снимка.

- [x] **Step 4: Полные обработчики 3.x на окружении нового CLI.** Взять `~/.claude/plugins/cache/lichtpfad/h2t-core/3.2.61/hooks-handlers/` и выполнить каждый с `H2T_PYTHON=<python окружения CLI из Step 1>` и `echo '{}' |`. Expected: код 0, без traceback.

- [x] **Step 5: Записать отчёт и правки спеки §10; commit** (`git add docs/reports/... docs/superpowers/specs/2026-10-16-package-architecture.md`).

### Task 2: Пробы на Windows **[владелец — ноутбук]**

**Files:** тот же отчёт.

- [x] **Step 1:** подготовить для владельца текст (как 2026-10-16) с командами: в какой оболочке Claude Code запускает команды хуков (хук, печатающий `$0`, `$SHELL`, `$BASH_VERSION`, `ps -p $$`) — с Git Bash и с переименованным `bash.exe` на PATH; `time` для `bash hooks/run` с подделкой `h2t-hook` (порог Stop); запуск `h2t-hook` из окружения uv холодно/тепло; поведение PATH в уже открытом Claude Code после `uv tool install`.
- [ ] **Step 2:** *(ожидает владельца: данные проб с ноутбука (R5))* внести полученную таблицу в отчёт, пороги — в §2.7 спеки; commit.

---

## Фаза R0 — заморозка

### Task 3: Указатель выпуска и заморозка

**Files:**
- Create: `scripts/release_pointer.py`
- Modify: `.claude-plugin/marketplace.json`
- Create: `tests/release/test_release_pointer.py`
- Modify: `scripts/hooks/pre-commit` (проверка синхронности версий должна понимать `git-subdir`)

**Interfaces:**
- Produces: `release_pointer.read_pointer(marketplace: dict) -> dict[str, tuple[str, str]]` (плагин → (ref, sha)); `release_pointer.set_pointer(marketplace: dict, ref: str, sha: str) -> dict`; CLI `python scripts/release_pointer.py set <ref> <sha>` / `check`.

- [x] **Step 1: Write the failing test**

```python
# tests/release/test_release_pointer.py
import json
from pathlib import Path

import pytest

from scripts import release_pointer as rp

ROOT = Path(__file__).resolve().parents[2]
URL = "https://github.com/lichtpfad/h2t-skills.git"


def _mk(source):
    return {"name": "lichtpfad", "plugins": [{"name": "h2t-core", "source": source}]}


def test_set_pointer_turns_relative_path_into_pinned_git_subdir():
    m = rp.set_pointer(_mk("./plugins/h2t-core"), "v3.3.0", "a" * 40)
    assert m["plugins"][0]["source"] == {
        "source": "git-subdir", "url": URL, "path": "plugins/h2t-core",
        "ref": "v3.3.0", "sha": "a" * 40,
    }


def test_set_pointer_rejects_short_sha():
    with pytest.raises(ValueError, match="40"):
        rp.set_pointer(_mk("./plugins/h2t-core"), "v3.3.0", "abc1234")


def test_read_pointer_requires_one_ref_for_all_plugins():
    m = {"plugins": [
        {"name": "a", "source": {"source": "git-subdir", "url": URL, "path": "plugins/a", "ref": "v1", "sha": "a" * 40}},
        {"name": "b", "source": {"source": "git-subdir", "url": URL, "path": "plugins/b", "ref": "v2", "sha": "a" * 40}},
    ]}
    with pytest.raises(ValueError, match="one release"):
        rp.read_pointer(m)


def test_repository_marketplace_is_pinned():
    m = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    pins = rp.read_pointer(m)
    assert pins, "marketplace.json has no pinned plugins"
```

- [x] **Step 2: Run** `.venv/bin/pytest tests/release/test_release_pointer.py -v` — Expected: FAIL `ModuleNotFoundError: scripts.release_pointer` (создать `tests/release/__init__.py`; `scripts/__init__.py` есть? проверить `ls scripts/__init__.py`, при отсутствии — импорт через `importlib.util.spec_from_file_location`, как в `tests/test_bump_plugin_encoding.py`).

- [x] **Step 3: Implement**

```python
# scripts/release_pointer.py
"""Read and move the release pointer: marketplace.json plugin sources pinned to one tag."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

URL = "https://github.com/lichtpfad/h2t-skills.git"
_SHA = re.compile(r"^[0-9a-f]{40}$")


def set_pointer(marketplace: dict, ref: str, sha: str) -> dict:
    if not _SHA.match(sha):
        raise ValueError("sha must be 40 lowercase hex characters")
    for entry in marketplace["plugins"]:
        entry["source"] = {"source": "git-subdir", "url": URL,
                           "path": f"plugins/{entry['name']}", "ref": ref, "sha": sha}
    return marketplace


def read_pointer(marketplace: dict) -> dict[str, tuple[str, str]]:
    pins = {}
    for entry in marketplace["plugins"]:
        src = entry["source"]
        if not isinstance(src, dict) or src.get("source") != "git-subdir":
            raise ValueError(f"{entry['name']}: source is not a pinned git-subdir")
        pins[entry["name"]] = (src["ref"], src["sha"])
    if len({p for p in pins.values()}) > 1:
        raise ValueError("plugins point at more than one release")
    return pins


def main(argv: list[str]) -> int:
    path = Path(__file__).resolve().parents[1] / ".claude-plugin" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if argv[:1] == ["set"] and len(argv) == 3:
        path.write_text(json.dumps(set_pointer(data, argv[1], argv[2]), indent=2,
                                   ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    if argv[:1] == ["check"]:
        print(json.dumps(read_pointer(data)))
        return 0
    print("usage: release_pointer.py set <ref> <sha40> | check", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [x] **Step 4:** pre-commit сверяет `version` в marketplace и `plugin.json`; убедиться, что он не требует строковый `source` (`grep -n source scripts/hooks/pre-commit`); при необходимости — читать `version` как прежде, источник не трогать. Run: тесты Task 3 — 3 PASS, `test_repository_marketplace_is_pinned` всё ещё FAIL (указатель ещё не сдвинут).

- [ ] **Step 5 [владелец]: заморозка.** *(ожидает владельца)* Владелец подтверждает имя тега `v3.3.0`. Затем:

```bash
git tag -a v3.3.0 -m "freeze before package architecture" origin/main
git push origin v3.3.0
.venv/bin/python scripts/release_pointer.py set v3.3.0 "$(git rev-parse v3.3.0^{commit})"
```

- [ ] **Step 6: Проверка вживую** *(ожидает владельца: после заморозки, Step 5)* в изолированном `CLAUDE_CONFIG_DIR`: `marketplace add <путь к чекауту>` → `install h2t-core@lichtpfad` → в кэше версия из `plugin.json` тега. Run все тесты Task 3 — PASS. Все 15 путей CI + ruff.

- [ ] **Step 7: Commit, PR** *(коммит сделан; PR и мерж — владелец)* «chore(release): freeze — marketplace points at v3.3.0» с `Refs #541`. После мержа владелец делает `/plugin marketplace update lichtpfad` и проверяет `ls ~/.claude/plugins/cache/lichtpfad/h2t-core/`.

---

## Фаза D1 — карта и сторожа

### Task 4: Карта исполняемых файлов, ratchet, формы вызова 3.x

**Files:**
- Create: `scripts/exec_map.py` — строит карту
- Create: `docs/reports/2026-10-XX-exec-map.md` — сгенерированная таблица (коммитится)
- Create: `tests/release/test_ratchets.py`
- Create: `tests/release/legacy_call_forms.json` — формы вызова CLI плагинами 3.x
- Create: `tests/release/test_legacy_call_forms.py`

**Interfaces:**
- Produces: `exec_map.shipped_runtime_python(root: Path) -> list[str]` — `.py` в `plugins/` вне тестов; `ALLOWLIST = {"hooks/run"}`; `legacy_call_forms.json` — список `{"argv": [...], "source": "<file:line>"}`.

- [x] **Step 1: Failing tests**

```python
# tests/release/test_ratchets.py
from pathlib import Path

from scripts import exec_map

ROOT = Path(__file__).resolve().parents[2]
# Measured on the commit that adds this test; may only decrease (spec §2.2).
RUNTIME_PY_CEILING = 69
AUTHOR_LITERALS = ["beabac7bf4314952a9327759c638d89f", "Asia/Jerusalem",
                   "Projects/DOR|Projects/newsengine"]
AUTHOR_LITERAL_CEILING = 0  # set to the measured count in Step 3


def test_runtime_python_in_plugins_does_not_grow():
    found = exec_map.shipped_runtime_python(ROOT)
    assert len(found) <= RUNTIME_PY_CEILING, found[RUNTIME_PY_CEILING:]


def test_author_literals_do_not_grow():
    hits = exec_map.literal_hits(ROOT, AUTHOR_LITERALS)
    assert len(hits) <= AUTHOR_LITERAL_CEILING, hits
```

```python
# tests/release/test_legacy_call_forms.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORMS = json.loads((ROOT / "tests/release/legacy_call_forms.json").read_text(encoding="utf-8"))


def test_inventory_covers_scaffolded_project_hooks():
    names = {tuple(f["argv"][:2]) for f in FORMS}
    for hook in ("layout-precommit", "bulk-precommit", "secrets-precommit"):
        assert ("h2t-hook", hook) in names
```

- [x] **Step 2:** Run — FAIL (`exec_map` нет, json нет).
- [x] **Step 3: Implement** `exec_map.py`:

```python
"""Map every executable file the pack ships and count what must reach zero."""
from __future__ import annotations

import subprocess
from pathlib import Path

ALLOWLIST = {"hooks/run"}
_TEST_PARTS = ("/tests/", "/test_", "conftest.py")


def _tracked(root: Path, prefix: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", prefix], cwd=root, check=True,
                         capture_output=True, text=True).stdout.split()
    return out


def shipped_runtime_python(root: Path) -> list[str]:
    return sorted(p for p in _tracked(root, "plugins/") if p.endswith(".py")
                  and not any(t in "/" + p for t in _TEST_PARTS))


def literal_hits(root: Path, literals: list[str]) -> list[str]:
    hits = []
    for path in _tracked(root, "plugins/") + _tracked(root, "h2t_ops/"):
        if any(t in "/" + path for t in _TEST_PARTS):
            continue
        try:
            text = (root / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        hits += [f"{path}: {lit}" for lit in literals if lit in text]
    return hits
```

Run `python -c` из корня, чтобы получить фактические числа; вписать их в `RUNTIME_PY_CEILING` и `AUTHOR_LITERAL_CEILING` (сейчас 69 — из подсчёта `.py` вне тестов: 39+22+5+2+1; перепроверить).

- [x] **Step 4: Инвентарь форм вызова.** Собрать grep'ом и вписать в `legacy_call_forms.json` с `source`:

```bash
git grep -nE 'h2t-(ops|gather|handoff|activity-log|hook|project-[a-z-]+|scaffold-project)\b' v3.3.0 -- plugins/ \
  | grep -vE '/tests?/|test_' > "$SP/forms.txt"
```
Каждая уникальная форма (команда + подкоманда + флаги) — запись. Обязательно: `h2t-gather --cwd <dir> --briefing-only`, `h2t-handoff write …`, `h2t-activity-log …`, `h2t-hook layout-precommit|bulk-precommit|secrets-precommit`, `h2t-ops <connector> …` из references.

- [x] **Step 5:** `scripts/exec_map.py` получает `main()`, печатающий таблицу «файл → потребители (grep по имени) → назначение по спеке §5»; вывод — в `docs/reports/2026-10-XX-exec-map.md`. Run тесты — PASS. Красный контроль: временно поднять число `.py` (создать `plugins/h2t-core/x.py`) — ratchet FAIL; убрать.
- [x] **Step 6:** 15 путей CI + ruff; commit `test(release): ratchets and the 3.x call-form inventory (#541)`.

### Task 5: Фиксация порядка поиска секретов

**Files:**
- Create: `tests/core/test_secrets_precedence.py`
- Read: `h2t_ops/core/secrets.py:14-35`

- [x] **Step 1:** тест: в пустом HOME создать одинаковый ключ `EXA_API_KEY` с разными значениями во всех местах, которые читает `h2t_ops/core/secrets.py`, и в переменной окружения; утверждать, какое значение выигрывает, по одному кейсу на каждую пару соседних мест. Значения сравнивать по `hashlib.sha256(v.encode()).hexdigest()[:8]`, не печатать.
- [x] **Step 2:** Run — тест должен пройти на текущем коде (это фиксация, не изменение). Красный контроль: поменять в тесте ожидаемый порядок двух мест — FAIL; вернуть.
- [x] **Step 3:** commit `test(secrets): pin today's lookup order before the move (#541)`.

---

## Фаза D2 — пакет

### Task 6: Состояние установки — `h2t_ops/setup/state.py`

**Files:**
- Create: `h2t_ops/setup/__init__.py`, `h2t_ops/setup/state.py`
- Test: `tests/setup/test_state.py`

**Interfaces:**
- Produces:
  - `RUN_DIR: Path = Path.home() / ".h2t" / "run"` (функция `run_dir() -> Path`, читает `Path.home()` при вызове)
  - `@dataclass Install(version: str, generation: str, tool_root: str, entrypoints: dict[str, str], editable: str | None, user_options: dict, plugins: list[str])`
  - `begin_update(version: str) -> None` — пишет `install.env` со `STATE=updating`
  - `commit(install: Install) -> None` — пишет `install.json`, затем `install.env` `STATE=ready` (LF, прямые слеши)
  - `read() -> Install | None` — `None`, если `install.env` не `ready` или `GENERATION` ≠ `generation`

- [x] **Step 1: Failing tests**

```python
# tests/setup/test_state.py
import json

import pytest

from h2t_ops.setup import state


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def _install(**kw):
    base = dict(version="4.0.0", generation="g1", tool_root="C:\\uv\\tools\\h2t-ops",
                entrypoints={"h2t-hook": "C:\\Users\\Лидия Иванова\\.local\\bin\\h2t-hook.exe"},
                editable=None, user_options={"extras": [], "with": []},
                plugins=["h2t-core", "h2t-ops"])
    base.update(kw)
    return state.Install(**base)


def test_commit_then_read_round_trips():
    state.commit(_install())
    assert state.read().version == "4.0.0"


def test_env_written_last_with_forward_slashes_and_lf(home):
    state.commit(_install())
    raw = (home / ".h2t/run/install.env").read_bytes()
    assert b"\r" not in raw
    assert b"H2T_HOOK=C:/Users/\xd0\x9b" in raw  # Лидия, forward slashes
    assert raw.splitlines()[0] == b"STATE=ready"


def test_updating_state_reads_as_absent():
    state.commit(_install())
    state.begin_update("4.1.0")
    assert state.read() is None


def test_generation_mismatch_reads_as_absent(home):
    state.commit(_install())
    data = json.loads((home / ".h2t/run/install.json").read_text(encoding="utf-8"))
    data["generation"] = "other"
    (home / ".h2t/run/install.json").write_text(json.dumps(data), encoding="utf-8")
    assert state.read() is None


def test_interrupt_between_json_and_env_reads_as_absent(home, monkeypatch):
    state.commit(_install())
    state.begin_update("4.1.0")
    real = state._write_env
    monkeypatch.setattr(state, "_write_env", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        state.commit(_install(version="4.1.0", generation="g2"))
    monkeypatch.setattr(state, "_write_env", real)
    assert state.read() is None
```

- [x] **Step 2:** Run `.venv/bin/pytest tests/setup/test_state.py -v` — FAIL (`h2t_ops.setup` нет).
- [x] **Step 3: Implement**

```python
# h2t_ops/setup/state.py
"""Install state: install.json for Python, install.env for bash; env is the commit point."""
from __future__ import annotations

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
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


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
    try:
        data = json.loads((run_dir() / "install.json").read_text(encoding="utf-8"))
        install = Install(**data)
    except (FileNotFoundError, ValueError, TypeError):
        return None
    return install if install.generation == env.get("GENERATION") else None
```

- [x] **Step 4:** Run — PASS (5). Красный контроль: поменять порядок в `commit()` (env раньше json) — `test_interrupt_between_json_and_env_reads_as_absent` FAIL; вернуть.
- [x] **Step 5:** commit `feat(setup): install state with install.env as the commit point (#541)`.

### Task 7: `h2t-ops version --expect`

**Files:**
- Create: `h2t_ops/setup/version_check.py`
- Modify: `h2t_ops/cli.py` (подкоманда `version`)
- Test: `tests/setup/test_version_check.py`

**Interfaces:**
- Consumes: `state.read()`.
- Produces: `check(expect: str, which=shutil.which) -> dict` с полями `ok: bool`, `version: str`, `reason: None | "version" | "path" | "not_installed"`, `hint: str | None`. CLI: `h2t-ops version [--expect V] [--json]`, код 0 при `ok`, иначе 3.

- [x] **Step 1: Failing tests**

```python
# tests/setup/test_version_check.py
import pytest

import h2t_ops
from h2t_ops.setup import state, version_check


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def _commit(tool_root, version=None):
    names = ["h2t-ops", "h2t-gather", "h2t-hook"]
    state.commit(state.Install(version=version or h2t_ops.__version__, generation="g",
                               tool_root=str(tool_root),
                               entrypoints={n: str(tool_root / "bin" / n) for n in names}))
    return names


def test_not_installed():
    r = version_check.check(h2t_ops.__version__, which=lambda n: None)
    assert (r["ok"], r["reason"]) == (False, "not_installed")


def test_version_mismatch_hints_sync(tmp_path):
    _commit(tmp_path / "tools", version="0.0.1")
    r = version_check.check("9.9.9", which=lambda n: str(tmp_path / "tools/bin" / n))
    assert r["reason"] == "version" and "h2t-setup" in r["hint"] and "sync" in r["hint"]


def test_entry_point_outside_tool_root_is_path(tmp_path):
    _commit(tmp_path / "tools")
    def which(n):
        return str(tmp_path / "other/bin" / n) if n == "h2t-gather" else str(tmp_path / "tools/bin" / n)
    r = version_check.check(h2t_ops.__version__, which=which)
    assert r["reason"] == "path"
    assert "uv tool update-shell" in r["hint"] and str(tmp_path / "tools" / "bin") in r["hint"]


def test_all_match_is_ok(tmp_path):
    _commit(tmp_path / "tools")
    r = version_check.check(h2t_ops.__version__, which=lambda n: str(tmp_path / "tools/bin" / n))
    assert r == {"ok": True, "version": h2t_ops.__version__, "reason": None, "hint": None}
```

- [x] **Step 2:** Run `.venv/bin/pytest tests/setup/test_version_check.py -v` — FAIL `ImportError: version_check`.
- [x] **Step 3: Implement** `check()` (версия пакета — `h2t_ops.__version__`; сравнение `os.path.normcase(os.path.realpath(...))` начала пути с `tool_root`); в `cli.py` — подпарсер `version`, вывод через существующий `h2t_ops/core/envelope.py` (`--json`), человеческий текст иначе.
- [x] **Step 4:** Run — PASS; `h2t-ops version --json` в dev-окружении печатает конверт.
- [x] **Step 5:** commit `feat(cli): h2t-ops version --expect checks every entry point (#541)`.

### Task 8: `lib/` → `h2t_ops/lifecycle/`, точки входа зовут пакет

**Files:**
- Move: `lib/activity`, `lib/eval`, `lib/gather` → `h2t_ops/lifecycle/{activity,eval,gather}` (`git mv`)
- Move: скрипты `plugins/h2t-core/skills/session-start/scripts/gather.py`, `handoff/scripts/writer.py`, `init-project/scripts/{detect_project,apply_registration}.py`, `project-audit/scripts/{scan,report}.py`, `scaffold-project/scripts/scaffold_project.py` → `h2t_ops/lifecycle/` (копия, не перенос — оригиналы остаются до Task 12: их загружает CLI 3.x)
- Modify: `h2t_ops/{gather,handoff,activity_log,project_*,scaffold_project}_entry.py` — импортировать `h2t_ops.lifecycle.*` вместо `plugin_script_path`
- Modify: `pyproject.toml` — убрать force-include `plugins/h2t-core/lib` в `_plugin_payload` только в Task 12; здесь не трогать
- Test: `tests/lifecycle/` (существующие тесты `lib/**/test_*.py` переезжают туда же)

- [x] **Step 1: Failing test** `tests/lifecycle/test_entrypoints_use_package.py`: для каждой из шести точек входа — модуль не импортирует `h2t_ops.plugin_entrypoints` (`ast`-проверка) и `main(["--help"])` завершается кодом 0 при `H2T_PLUGIN_ROOT`, указывающем в пустой каталог.
- [x] **Step 2:** Run — FAIL.
- [x] **Step 3:** `git mv` библиотек; копии скриптов; переписать импорты (`from lib.gather import …` → `from h2t_ops.lifecycle.gather import …`); точки входа вызывают `main()` модулей пакета.
- [x] **Step 4: Round trip:** `tests/lifecycle/test_handoff_gather_round_trip.py` — `h2t-handoff write` в пустой HOME, затем `h2t-gather --briefing-only` видит запись. Тест формы вызова 3.x: для каждой записи `legacy_call_forms.json` с командой из этих шести — `subprocess.run` с `--help`-безопасными аргументами завершается не кодом 2 «unknown argument».
- [x] **Step 5:** все 15 путей CI (пути `lib/` в `evals.yml` заменить на `tests/lifecycle`), ruff, parity-тест `test_vendored_lib_parity.py` перевести на сравнение `h2t_ops/lifecycle` ↔ `plugins/h2t-core/lib` (он удаляется в Task 12); commit.

### Task 9: Хуки в пакете и обёртка `hooks/run`

**Files:**
- Create: `h2t_ops/hooks/{__init__,emit,gather,structure_guard,grade_guard,plain_guard,plan_closer,new_repo_hint,reap_codex,inject_context}.py`
- Modify: `h2t_ops/hook_entry.py` — диспетчер: имя из таблицы новых модулей → `handle()`; иначе — прежний путь через `plugin_script_path` (формы 3.x: `layout-precommit`, `bulk-precommit`, `secrets-precommit`, остальные имена из `legacy_call_forms.json`)
- Create: `plugins/h2t-core/hooks/run`
- Create: `plugins/h2t-core/release.env` (`VERSION=` — текущая версия плагина)
- Test: `tests/hooks/test_hook_modules.py`, `tests/hooks/test_hooks_run.py`

**Interfaces:**
- Produces: `h2t_ops.hooks.emit.Reply(text: str = "", block: bool = False)`; `emit.write(event_name: str, reply: Reply) -> int` (печатает конверт по каналу, возвращает код: 0 или 2); каждый модуль: `handle(event: dict) -> Reply`; `HANDLERS: dict[str, Callable]` в `h2t_ops/hooks/__init__.py`.

- [x] **Step 1: Failing tests модулей** — для каждого хука: событие из fixtures (`tests/fixtures/hooks/<name>/<event>.json`, собрать из текущих тестов `tests/hooks/`) → ожидаемый `Reply` (спека §2.8). `gather`: ответ содержит `BRIEFING:` и `GATHER_META: cwd=<cwd> at=`.
- [x] **Step 2: Failing tests обёртки** (`tests/hooks/test_hooks_run.py`, skip без bash): подделка `h2t-hook` — bash-скрипт, печатающий заданное и выходящий заданным кодом; фикстура пишет `install.env` и `release.env`. Кейсы — строки таблицы §6.1 сверху вниз:

```python
CASES = [
    # (install.env lines or None, plugin_inside_editable, fake_hook_exit, event, expect)
    (None, False, 0, "SessionStart", "notice:not_installed"),
    (None, False, 0, "Stop", "silent"),
    (["STATE=updating", "VERSION=4.0.0"], False, 0, "SessionStart", "notice:not_installed"),
    (["STATE=ready", "VERSION=4.0.0", "EDITABLE_ROOT=<tmp>/checkout"], True, 0, "Stop", "ran"),
    (["STATE=ready", "VERSION=4.0.0", "EDITABLE_ROOT=<tmp>/checkout"], False, 0, "SessionStart", "notice:editable"),
    (["STATE=ready", "VERSION=4.0.0"], False, 0, "Stop", "ran"),
    (["STATE=ready", "VERSION=3.9.0"], False, 0, "SessionStart", "notice:mismatch"),
    (["STATE=ready", "VERSION=4.0.0"], False, 2, "PreToolUse", "blocked"),
    (["STATE=ready", "VERSION=4.0.0"], False, 1, "Stop", "silent+logged"),
    (["STATE=ready", "VERSION=4.0.0"], False, 1, "SessionStart", "notice:broken"),
]
```
Плюс: каждое уведомление — валидный JSON (`json.loads` вывода) при бутстрапе с двойными кавычками и обратным слешем; CRLF в `install.env` → совпадение версий; `H2T_HOOK` с пробелом и кириллицей; `SessionStart` без `session_id`; второй `SessionStart` того же `session_id` → без уведомления; `~/.h2t/run` только для чтения → уведомление на каждом; подделка, спящая дольше `timeout − 1` → обработано как «иное» до таймаута; `UserPromptSubmit` «привет» → тишина без чтения файлов (проверка: `install.env` отсутствует, вывода нет, < 50 мс).
- [x] **Step 3:** Run — FAIL.
- [x] **Step 4: Implement `hooks/run`**

```bash
#!/usr/bin/env bash
# h2t hook wrapper — spec §6.1. Bash only; no interpreter until a handler has work.
set -u
name="${1:?hook name}"
input=$(cat)
event=$(printf '%s' "$input" | grep -o '"hook_event_name" *: *"[A-Za-z]*"' | head -1 | sed 's/.*"\([A-Za-z]*\)"$/\1/')

if [ "$event" = "UserPromptSubmit" ]; then
  printf '%s' "$input" | grep -qE '"prompt" *: *"[[:space:]]*/([A-Za-z0-9_.-]+:)?(session-start|handoff|init-project)([[:space:]"]|$)' || exit 0
fi

kv() { grep -m1 "^$1=" "$2" 2>/dev/null | cut -d= -f2- | tr -d '\r'; }
run_dir="$HOME/.h2t/run"
plugin_version=$(kv VERSION "${CLAUDE_PLUGIN_ROOT}/release.env")
state=$(kv STATE "$run_dir/install.env"); cli_version=$(kv VERSION "$run_dir/install.env")
hook=$(kv H2T_HOOK "$run_dir/install.env"); editable=$(kv EDITABLE_ROOT "$run_dir/install.env")

notice() {
  [ "$event" = "SessionStart" ] || exit 0
  sid=$(printf '%s' "$input" | grep -o '"session_id" *: *"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
  if [ -n "$sid" ] && mkdir -p "$run_dir/notified" 2>/dev/null; then
    mkdir "$run_dir/notified/$sid" 2>/dev/null || exit 0
  fi
  msg=${1//\\/\\\\}; msg=${msg//\"/\\\"}   # the bootstrap literal carries double quotes
  printf '{"systemMessage": "%s"}\n' "$msg"
  exit 0
}

BOOTSTRAP='@BOOTSTRAP@'   # literal written by the release script (spec §7.1)
[ "$state" = "ready" ] && [ -n "$hook" ] || notice "h2t: CLI не установлен. Установить: $BOOTSTRAP sync"
if [ -n "$editable" ]; then
  case "${CLAUDE_PLUGIN_ROOT}/" in
    "$editable"/*) ;;
    *) notice "h2t: CLI в режиме разработки ($editable), плагины из marketplace. Плагины грузить из чекаута или выполнить: $BOOTSTRAP sync" ;;
  esac
elif [ "$plugin_version" != "$cli_version" ]; then
  notice "h2t: плагины $plugin_version, CLI $cli_version. Свести к текущему выпуску: $BOOTSTRAP sync"
fi

out=$(mktemp); err=$(mktemp)
limit="${H2T_HOOK_TIMEOUT:-9}"
printf '%s' "$input" | "$hook" "$name" >"$out" 2>"$err" & pid=$!
( sleep "$limit"; kill "$pid" 2>/dev/null ) & watchdog=$!
wait "$pid"; rc=$?
kill "$watchdog" 2>/dev/null
case "$rc" in
  0) cat "$out" ;;
  2) cat "$err" >&2; rm -f "$out" "$err"; exit 2 ;;
  *) mkdir -p "$HOME/.h2t/logs" 2>/dev/null
     printf '{"hook":"%s","rc":%s}\n' "$name" "$rc" >> "$HOME/.h2t/logs/hooks.jsonl" 2>/dev/null
     rm -f "$out" "$err"
     notice "h2t: CLI неисправен (хук $name, код $rc). Починить: $BOOTSTRAP sync" ;;
esac
rm -f "$out" "$err"
exit 0
```
`H2T_HOOK_TIMEOUT` — `timeout` записи `hooks.json` минус 1; скрипт выпуска подставляет его в `hooks.json` как переменную окружения команды (`"command": "H2T_HOOK_TIMEOUT=9 bash …/hooks/run gather"`).
- [x] **Step 5: Implement модули** из текущих `hooks-handlers/*.py` и bash-обработчиков (`gather-on-skill`, `gather-on-prompt`, `inject-h2t-context`, `structure-guard`, `grade-guard`, `plain-guard`, `plan-closer`, `new-repo-hint`, `session-end-reap-codex`): логика переносится, поиск интерпретатора, `jq` и ручная сборка JSON удаляются; вывод — только `emit.write`.
- [x] **Step 6:** Run — PASS; бюджеты §2.7 измерить `tests/hooks/test_budgets.py` (20 прогонов, p95; на CI — только macOS/Linux, порог Windows — из Task 2).
- [x] **Step 7:** commit `feat(hooks): handlers in the package, hooks/run compares two version strings (#541)`.

### Task 10: Инструменты и ресурсы

**Files:**
- Move: `plugins/h2t-dev/skills/docs-lint/scripts/*`, `plugins/h2t-dev/skills/docs-sync-labels/scripts/*`, `plugins/h2t-dev/skills/milestone-closure/scripts/*`, `plugins/h2t-dev/lib/docs` → `h2t_ops/tools/docs/`; `plugins/h2t-arch/skills/drawio/scripts/*` + `config/defaults.yaml` → `h2t_ops/tools/drawio/` и `h2t_ops/resources/drawio/`; `plugins/h2t-creative/assembler.py` + `base/`, `profiles/`, `shared/` → `h2t_ops/tools/creative/` и `h2t_ops/resources/creative/`; `plugins/h2t-core/skills/setup/scripts/known_secrets.yaml` → `h2t_ops/resources/`; `plugins/h2t-core/skills/agent-profile/scripts/*` → `h2t_ops/tools/agent_profile/`
- Modify: `pyproject.toml` — новые точки входа: `h2t-docs-lint`, `h2t-drawio`, `h2t-creative`, `h2t-agent-profile`; `[tool.hatch.build]` включает `h2t_ops/resources/**`
- Test: `tests/tools/test_resources_from_wheel.py`

- [x] **Step 1: Failing test** — собрать wheel (`uv build --wheel -o tmp`), установить в изолированный каталог, из чужого cwd вызвать `h2t-creative --help`, `h2t-drawio --help`, `h2t-docs-lint doctor` на пустом репо; каждый находит свои ресурсы (`importlib.resources.files("h2t_ops.resources.creative") / "base"` существует).
- [x] **Step 2:** FAIL. **Step 3:** перенос, `Path(__file__).parent / "base"` → `importlib.resources`. Исходные скрипты в плагинах **остаются** до Task 12 (их зовут скиллы 3.x и CI-пути `evals.yml`).
- [x] **Step 4:** перенести тесты в `tests/tools/`, обновить пути в `evals.yml`; все пути CI, ruff; commit.

### Task 11: Коннекторы — одна реализация

**Files:**
- Test: `tests/connectors/test_script_verbs_in_cli.py`
- Delete (в Task 12): `plugins/h2t-ops/skills/{drive,meetgeek,research}/scripts/*`

- [x] **Step 1: Failing test** — для каждого глагола из `drive_cli.py`, `meetgeek_cli.py`, `exa_search.py`, `fetch_url.py` (список — парсер `argparse` каждого скрипта, загруженного через `importlib`) есть команда `h2t-ops <connector> <verb>` с теми же флагами; контрактный сценарий на подделке API (существующие фикстуры `tests/connectors/`) даёт тот же результат, что скрипт.
- [x] **Step 2:** FAIL на недостающих. **Step 3:** дописать недостающие глаголы в `h2t_ops/connectors/*` (только недостающие, по списку из FAIL). **Step 4:** PASS; commit.

---

## Фаза D3 — плагины

### Task 12: Плагины становятся текстом

**Files:**
- Modify: все `plugins/*/hooks/hooks.json` → `bash "${CLAUDE_PLUGIN_ROOT}/hooks/run" <имя>` с `H2T_HOOK_TIMEOUT`
- Create: `plugins/*/hooks/run` (копия из h2t-core; тест — байтовая идентичность), `plugins/*/release.env`
- Modify: каждый `SKILL.md` — первая команда `h2t-ops version --expect @VERSION@ --json` и правило исходов §6.3 (текст — `plugins/h2t-core/references/version-check.md`, на него ссылаются скиллы); вызовы `scripts/*.py` → команды CLI из Task 10/11; session-start, handoff, init-project — правило брифинга §6.3: использовать брифинг из контекста, только если его `GATHER_META` `cwd` равен текущему и `at` не старше 120 с, иначе `h2t-gather`
- Delete: `plugins/h2t-core/hooks-handlers/`, `plugins/*/skills/*/scripts/`, `plugins/h2t-core/lib/`, `plugins/h2t-dev/lib/`, `plugins/h2t-core/scripts/resolve-h2t-python.sh`, `plugins/h2t-core/scripts/h2t_secrets.py`, корневые `hooks/hooks.json`, `hooks-handlers/register-session`, `setup.sh`, `requirements.txt`, `h2t_ops/plugin_entrypoints.py`, `h2t_ops/dev.py`, force-include `_plugin_payload` в `pyproject.toml`
- Modify: `h2t_ops/hook_entry.py` — имена `layout-precommit`, `bulk-precommit`, `secrets-precommit` → модули пакета (перенести их обработчики в `h2t_ops/hooks/`), без `plugin_script_path`
- Test: `tests/release/test_ratchets.py` — `RUNTIME_PY_CEILING = 0`; `tests/skills/test_skill_commands_exist.py`

- [x] **Step 1: Failing tests** — ratchet = 0; каждый вызов CLI в `SKILL.md` (regex по `h2t-[a-z-]+`) существует в парсере (`h2t_ops.cli` + точки входа `pyproject.toml`); каждый `SKILL.md` h2t начинается проверкой версии; `hooks/run` во всех плагинах идентичен; формы `legacy_call_forms.json` с `h2t-hook` работают против нового `hook_entry`.
- [ ] **Step 2:** *(Steps 2–4 и коммиты сделаны (12a–12c); PR — владелец)* FAIL. **Step 3:** правки и удаления. **Step 4:** PASS; все пути CI (пути удалённых тестов убрать из `evals.yml`), ruff; `lint.py doctor`. **Step 5:** commit, PR `refactor: plugins carry text only; all code in the package (#541)`.

---

## Фаза D4 — `sync` и выпуск

### Task 13: Манифест выпуска и скрипт выпуска

**Files:**
- Create: `scripts/release.py`, `release.json` (генерируется), `tests/release/test_release_script.py`
- Modify: `scripts/bump_plugin.py` — остаётся для совместимости, но `release.py` ставит одну версию во все места

**Interfaces:**
- Produces: `release.py prepare <ver>` — пишет версию в `pyproject.toml`, `h2t_ops/__init__.py`, все `plugin.json`, `marketplace.json` (`version`), все `release.env`; подставляет `@VERSION@` и `@BOOTSTRAP@`; экспортирует `constraints.txt`; пишет `release.json` (формат §7.1, `format: 1`, `previous` — текущий `ref` указателя). Функция `bootstrap_argv(ver: str, wheel_url: str, constraints_url: str, python: str) -> list[str]` — единственный источник литерала.

- [x] **Step 1: Failing tests** — после `prepare 4.0.0` в копии репо (`tmp_path` + `git worktree add`): все версии равны; `bootstrap_argv` начинается с `["uvx", "--isolated", "--python", "3.12.11", "--managed-python", "-c"]` и заканчивается `"h2t-setup"`; `@BOOTSTRAP@` не осталось нигде; `constraints.txt` не содержит строки `h2t-ops`; `previous` = текущий ref указателя.
- [x] **Step 2–4:** FAIL → implement → PASS. **Step 5:** commit.

### Task 14: `h2t-setup sync` — цель и исполнитель

**Files:**
- Create: `h2t_ops/setup/manifest.py`, `h2t_ops/setup/sync.py`, `h2t_ops/setup/cli.py`; точка входа `h2t-setup = "h2t_ops.setup.cli:main"`
- Test: `tests/setup/test_sync_target.py`

**Interfaces:**
- Produces: `manifest.current(fetch=urllib_fetch) -> dict` (читает `marketplace.json` с `https://raw.githubusercontent.com/lichtpfad/h2t-skills/main/.claude-plugin/marketplace.json`, ref h2t-core, затем `release.json` тега); `sync.ensure_executor(target: dict, mode: str, argv: list[str], *, prefix=sys.prefix, version=h2t_ops.__version__, tool_root: str | None) -> None` — возвращает, если исполнитель годен, иначе `os.execvp` по `target["bootstrap"] + [mode] + argv`.
- Ошибка сети → `H2TError(code=6)` с текстом причины; ничего не тронуто.

- [x] **Step 1: Failing tests** — `fetch` подменяется словарём URL → bytes: цель читается; сеть падает → код 6, `state.read()` не изменился, `install.env` не создан; версия исполнителя ≠ цели → `execvp` вызван с bootstrap цели + `update` + исходные аргументы (подмена `os.execvp`); версия совпадает, но `prefix` внутри `tool_root` → тоже перезапуск; совпадает и вне — возврат.
- [x] **Step 2–4:** FAIL → implement → PASS. **Step 5:** commit.

### Task 15: `sync` — CLI, плагины, кэш, отчёт

**Files:**
- Modify: `h2t_ops/setup/sync.py`
- Create: `h2t_ops/setup/harness_claude.py` (обёртка над `claude plugin … --json`), `tests/setup/test_sync_converges.py`, `tests/setup/fake_claude.py` (подделка `claude` с состоянием в JSON-файле: marketplaces с `ref`, установленные плагины с версией, scope, enabled)

**Interfaces:**
- Consumes: `state.begin_update/commit/read`, `manifest.current`, `ensure_executor`.
- Produces: `sync.run(mode: str, *, uv=run_uv, claude=harness_claude.Claude(), confirm=input) -> Report`; `Report(done: list[str], failed: list[tuple[str, str]], reload_needed: bool)`.

- [x] **Step 1: Failing tests — сходимость** (§2.5, тест 5 спеки), каждый кейс — начальное состояние подделок → `run("sync")` → конечное состояние:
  - чистая машина: marketplace отсутствует → добавлен; `h2t-core`, `h2t-ops` установлены версии цели; `install.env` `ready`;
  - CLI 0.2.1 (receipt без `install.json`) → `user_options` из receipt, CLI цели;
  - повреждённое окружение при `ready` (подделка `--version` падает) → переустановка;
  - прерывание после каждого шага (исключение из подделки на шаге *k*) → повторный `run` доводит до цели;
  - прерывание между `install.json` и `install.env` → повтор переписывает обе проекции;
  - закреплённый marketplace → в `sync` остановка, `failed` содержит команды `remove`/`add`/`install` со scope из снимка, ничего не изменено; в `update` с `confirm → "да"` — выполнено, scope и disabled восстановлены;
  - выключенный пользователем `h2t-ops` (Review Focus 5) → остаётся выключенным, версия обновлена;
  - пустой набор плагинов → `failed`, не успех;
  - кэш: 4 версии плагина → остаются 2 последние;
  - `EDITABLE_ROOT` задан → остановка с сообщением о чекауте, ничего не тронуто.
- [x] **Step 2–4:** FAIL → implement шаги §7.3.3–8 → PASS. Каждый шаг: сравнить факт с целью, пропустить совпавшее.
- [x] **Step 5:** commit `feat(setup): sync converges a machine to the current release (#541)`.

### Task 16: `update`, `dev-sync`

**Files:** `h2t_ops/setup/cli.py`, `tests/setup/test_update_devsync.py`

- [x] **Step 1: Failing tests** — `update` показывает «было → станет» и CHANGELOG цели, без «да» ничего не меняет; `update` старого исполнителя → перезапуск в цель с `update` (Task 14) → вопрос задаёт исполнитель цели о своей версии; `dev-sync` пишет `EDITABLE_ROOT`, не вызывает `git`, берёт `user_options` из `install.json`.
- [x] **Step 2–4:** FAIL → implement → PASS. **Step 5:** commit.

### Task 17: Workflow выпуска

**Files:**
- Create: `.github/workflows/release.yml`
- Create: `tests/release/test_release_workflow.py` — статическая проверка YAML

- [x] **Step 1: Failing test** — workflow существует; `on: push: tags: ['v*']`; `concurrency: {group: release, cancel-in-progress: false}`; шаги в порядке: сборка wheel → прогон тестов на установленном wheel (`tests/tools/test_resources_from_wheel.py`, `tests/setup`) → `gh release create` с wheel и `constraints.txt` → сдвиг указателя: `release_pointer.py check` равен `previous` из `release.json`, иначе `exit 1` → `release_pointer.py set <tag> <sha>` → коммит на main.
- [x] **Step 1b: Детерминированность (§2.6)** — `tests/release/test_determinism.py`, маркер `slow`, запускается в workflow выпуска и вручную: собрать wheel, экспортировать constraints, установить дважды в разные `UV_TOOL_DIR` с `--python 3.12.11 --managed-python -c constraints.txt`; утверждать равенство `uv pip freeze --python <python окружения>` и `sys.version` обоих окружений. Красный контроль: во второй установке убрать `-c` — набор должен разойтись (если не расходится — тест не ловит дрейф, искать пакет с незакреплённой зависимостью).
- [x] **Step 2–4:** FAIL → workflow → PASS. `test_release_pointer.py` дополнить: с 4.0.0 у тега указателя есть Release с wheel (проверка через `gh release view` — только в CI с `GH_TOKEN`, локально skip).
- [ ] **Step 5:** *(коммит сделан; PR — владелец)* commit, PR `feat(release): one workflow publishes the wheel, then moves the pointer (#541)`.

---

## Фаза R1 — выпуск 4.0.0

### Task 18: Выпуск **[владелец]**

- [ ] **Step 1:** *(README и CLAUDE.md сделаны; трекер #541 — владелец, после выпуска)* README: раздел установки — одна команда бутстрапа (§7.2), раздел Codex — что не работает без хуков (§4) и ручная команда плагинов; `CLAUDE.md` — граница `h2t-ops` = весь пак; трекер #541 — D5, D6, D9 закрываются ссылкой на этот выпуск.
- [x] **Step 1b: подсистема 2 не теряется.** 4.0.0 переносит код, но не данные: корни хранения, файл путей, порядок секретов, литералы автора остаются как были (Global Constraints). В README — раздел «Известные ограничения» со ссылкой на #548; в CHANGELOG 4.0.0 — та же строка; трекер #541 не закрывается, пока #548 не решён и его спека не написана. Выпуск без этих трёх строк не делается.
- [ ] **Step 2:** *(ожидает владельца)* `release.py prepare 4.0.0`; все 15 путей CI + ruff; PR, мерж владельцем.
- [ ] **Step 3 [владелец]:** *(ожидает владельца)* `git tag -a v4.0.0` на коммите мержа, `git push origin v4.0.0`. Workflow публикует Release и сдвигает указатель.
- [ ] **Step 4: Проверка состояния, не отчёта:** *(ожидает владельца)* `release_pointer.py check` на main = `v4.0.0`; Release содержит wheel и `constraints.txt`; в пустом HOME бутстрап `… h2t-setup sync` ставит CLI 4.0.0 и плагины 4.0.0 в изолированный `CLAUDE_CONFIG_DIR`; `h2t-ops version --expect 4.0.0 --json` → `ok: true`.
- [ ] **Step 5:** *(ожидает владельца)* машины автора: `/plugin marketplace update lichtpfad` → уведомление → бутстрап `sync`; на Mac с чекаутом — `dev-sync` вместо `sync`.

### Task 19: Живая приёмка **[владелец]**

- [ ] *(ожидает владельца)* Матрица §4: macOS × Claude Code (Mac автора, чистый пользователь), Windows × Claude Code (ноутбук, чистый пользователь), Codex — скиллы и CLI. Для каждой ячейки: бутстрап, `/h2t-core:session-start` даёт брифинг, `handoff` пишет запись, обычное сообщение без вывода хуков, бюджеты §2.7. Результаты — в отчёт фазы P и в трекер #541.
