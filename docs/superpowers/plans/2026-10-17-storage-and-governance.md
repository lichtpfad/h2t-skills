---
title: "Storage and governance"
status: "draft"
date: "2026-10-17"
milestone: ""
issue: "548"
---

# Storage and governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** у каждого класса данных один каталог под `~/.h2t`, у каждого провайдера один файл секрета. Путь знает `core/paths.py`, пишет `core/store.py`, секреты читает `core/secrets.py`. Тесты держат ноль обходов. `h2t-setup sync` переносит данные машины копией с журналом и откатом. Всё это выходит одним выпуском 4.0.0 вместе с подсистемой 1.

**Architecture:** порядок работы.

1. Сначала три модуля доступа к диску и сторожа: ratchet-тесты с замеренными потолками и тест песочницы с `sys.addaudithook`.
2. Затем вызывающие переводятся на модули группами: по провайдерам, по сессиям, по записям в репо, по установке. Каждая группа опускает потолки ratchet и добавляет свои случаи в песочницу.
3. Затем индекс сессий: производная SQLite из md с frontmatter.
4. Затем `doctor` и миграция `layout 1` внутри `h2t-setup sync`.
5. Последними идут документация, живой перенос двух машин и выпуск.

**Tech Stack:** Python ≥ 3.11 (CI 3.11, выпуск 3.12.11), PyYAML и ruamel.yaml (уже в зависимостях), `sqlite3` из стандартной библиотеки, `fcntl`/`msvcrt`, pytest, GitHub Actions (ubuntu + windows).

**Spec:** `docs/superpowers/specs/2026-10-17-storage-and-governance.md` (v5). Исполнитель читает спеку и план вместе; «§N» ниже — разделы спеки. Отправные данные плана — инвентарь `main` 70214177 (2026-10-17): 75 строк обращения к домашнему каталогу в 37 файлах, 53 строки `.dor`/`.config` в 15, 33 строки `H2T_*` путей в 19, 210 строк записи в 46.

## Global Constraints

- Не меняется контракт установки из спеки 4.0: `~/.h2t/run/install.json`, `install.env` (LF, `STATE=` первой строкой), чтение `$HOME/.h2t/run` в `plugins/h2t-core/hooks/run`. `paths.run_dir()` не зависит от `H2T_PATH_ROOT`.
- Старые места (`~/.dor/**`, `~/.config/{google-calendar-mcp,gmail,notion,telegram}/**`, `~/.h2t/{sessions,activity,evals,research,creative}`, `~/.h2t/config/secrets/**`) в 4.0.x пакет **не меняет и не удаляет**. Исключения ровно два: зеркало токена Google (`store.replace(..., compat=True)`, §9) и `MOVED-TO.txt` во время миграции.
- Значения секретов никогда не печатаются, не логируются и не попадают в `logs/writes.jsonl`. Отчёты выводят путь, имя ключа, длину и `sha256[:12]`. В тестах только фиктивные значения вида `fake-<имя>`.
- Права на macOS и Linux: 0600 на файлы `secrets/**` и `local/telegram.session`, 0700 на каталоги `secrets/`, `secrets/shared`, `secrets/local`, `run/rollback/<id>`. Тесты на биты прав помечены `skipif(sys.platform == "win32")`. Поведение на Windows задаёт Task 1.
- Имена секретов: `<провайдер>.(env|client.json|token.json|session|auth-state.json)`, ключи `<ПРОВАЙДЕР>_<ЧТО>`. Явные исключения: `other.env`, `*.from-*`, чужие `.env`.
- Переменные окружения пишутся в одной форме `H2T_PATH_<МЕСТО>` (точка → `_`, верхний регистр). Старые имена весь 4.0.x работают как псевдонимы: `H2T_LAKE_ROOT`, `H2T_SESSION_ROOT`, `H2T_ACTIVITY_SPOOL`, `H2T_EVALS_ROOT`, `H2T_EVALS_SPOOL`, `H2T_CONFIG_ROOT`, `H2T_SECRETS_FILE`, `H2T_KB_ROOT`.
- Никаких новых зависимостей.
- Коды выхода коннекторов: 0 ok, 1 provider, 2 usage, 3 config, 4 auth, 5 not found, 6 network. `doctor` всегда выходит с 0.
- Репо-правила.
  - Тест засчитывается только после красного прогона; красный — с прочитанным текстом падения.
  - Красный прогон делается на нарочно испорченном дереве. Порча откатывается до коммита.
  - Ruff: `uvx ruff@0.16.4 check plugins/ lib/ h2t_ops/ tests/ scripts/`.
  - Полный прогон тестов на маке: `.venv/bin/pytest tests/ -q` и `.venv/bin/pytest lib/ -q`.
  - В `git add` только явные пути. Heredoc в Bash не использовать.
  - Commit делается на каждом шаге «Commit». Push, PR, merge, tag, release и любые сообщения наружу (issues в чужие репо, Telegram) — только на шагах **[владелец]**.
- Каждая задача фазы C, которая переносит вызовы:
  - в конце запускает `.venv/bin/python scripts/storage_map.py --check` и вписывает новые потолки в `tests/governance/test_storage_ratchets.py`;
  - добавляет свои строки в `tests/governance/sandbox_cases.py`.

## Review Focus

1. **`paths.yaml`, где место указано через `~`, относительно или через симлинк внутрь `~/.h2t`.** Ожидается отказ с `ConfigError` и именем места, а не тихая запись в `~/.h2t`. Тест — Task 3, `test_place_through_symlink_into_root_is_rejected`.
2. **Миграция, прерванная между фазами (kill), и повторный запуск.** Ожидается продолжение с первой незавершённой фазы, без новых `*.from-*` и без второго экземпляра файла. Тест — Task 21, `test_interrupted_migration_resumes_without_duplicates`.
3. **md сессии с испорченным frontmatter** (пользователь правил руками, конфликт синхронизации). Ожидается, что индекс пропускает файл, записывает его в `problems`, `session-start` показывает остальные. Тест — Task 14, `test_broken_frontmatter_is_skipped_and_reported`.
4. **`USERPROFILE` с пробелом и кириллицей на Windows** (`C:/Users/Лидия Иванова`). Ожидается, что `store.append` под блокировкой и `paths.*` дают корректные пути. Тест — Task 4, `test_append_under_unicode_home` (идёт в CI на windows-latest).
5. **Файл секретов с BOM, CRLF, кавычками, строками `export KEY=…`.** Ожидается тот же разбор, что у `load_secrets` 3.x, при чтении и при миграции. Тест — Task 6, `test_env_parse_matches_3x_on_awkward_files`.

## Решения, принятые при написании плана

Спека v5 — авторитет; ниже — то, о чём она молчит. Цена ошибки указана, чтобы владелец мог развернуть решение до исполнения.

| # | Решение | Почему | Цена, если неверно |
|---|---|---|---|
| R1 | Удаление — пятая операция `store.remove`/`remove_tree`, только в `run`, `state`, `logs`, `tmp`, `harness`; в `records`, `secrets` — только откатом по журналу (`journal=True`, одно место импорта — `setup/layout/rollback.py`) | спека называет четыре операции, но откат миграции и `sync` (кэш плагинов, `claude-pending.json`) удаляют | одна функция и один тест |
| R2 | Миграция создаёт `config/paths.yaml`, если его нет, и вписывает только существующие старые места: `lake: ~/.dor/lake`, `vault: ~/.dor/vault`, `inbox: ~/Downloads` (там 3.x клал вложения Telegram). Существующий файл не трогает | иначе у автора `meetgeek`/`granola` молча начнут писать в `~/.h2t/data/lake` | правка одного шага миграции |
| R3 | Выбор синхронизации в `paths.yaml` — ключ `sync:` с картой `id места → инструмент` (`syncthing`, `git`, `none` или любое имя). `doctor` по нему отвечает «объявлено» | §3 называет «выбор синхронизации», формат не задан | формат одного ключа |
| R4 | Имя машины закрепляется в `state/machine.json` (пишет миграция или `--machine`); `paths.machine_name()`: `H2T_MACHINE_NAME` → `DOR_MACHINE_NAME` → `machine.json` → hostname | §5 говорит «закрепляет в `H2T_MACHINE_NAME`», но постоянную переменную окружения пакет поставить не может; файл в `state` даёт то же | одна строка порядка |
| R5 | Старая переменная, указывающая на файл (`H2T_ACTIVITY_SPOOL`, `H2T_EVALS_SPOOL`), трактуется как явный путь пользователя: каталог файла становится корнем места для классификации | иначе каждый тест с этими переменными (а их ставит корневой `conftest.py`) упирается в отказ записи | правило в одной функции `paths` |
| R6 | Чужой `.env` из старого каталога (`getcourse.env`, `anysite.env` — имя не провайдер пакета) переносится целиком под своим именем; ключи провайдеров пакета из него ещё и участвуют в лестнице; прочие его ключи в `other.env` не идут | сегодня лестница читает все `*.env`, поэтому ключ `EXA_*` из такого файла работает; после переноса пакет чужие файлы не читает | правка таблицы источников |
| R7 | `drawio` и `creative assemble` пишут в путь, названный пользователем, как в `--dest` (`dest=True`), а не через список `repo` | путь задаёт пользователь, и он не обязан быть внутри репо | — |
| R8 | `h2t-setup sync --rollback-layout` требует флаг `--sync-paused` | §7.5 требует паузы; пакет не может проверить Syncthing | один флаг |
| R9 | Миграция переносит ещё `~/.h2t/research` → `data/research` и `~/.h2t/creative/profiles` → `data/creative/profiles` | §3 их называет, §8 забыл | две строки фазы |
| R10 | `latest.json` больше не пишется; ключ `latest` в ответе `h2t-handoff` = путь к md, `latest_session` в `GATHER_META` строится из индекса | §5 | правка скиллов handoff/session-start |

---

## Фаза P — пробы и сторожа

### Task 1: Пробы ноутбука и вывод в спеку **[владелец — ноутбук]**

Пробы отправлены в канал `3dwalker` (сообщение 1581, текст — `scratchpad/h2t-windows-probes-storage.md` сессии плана). Задача закрывается, когда отчёт ноутбука пришёл и разобран.

**Files:**
- Modify: `docs/superpowers/specs/2026-10-17-storage-and-governance.md` (§11 пп. 1, 3, 4, 5; §4 «Права»; §14)

**Interfaces:** Produces — четыре решения, которые читают Task 4 (блокировка на Windows), Task 6 (права на Windows), Task 22 (порядок миграции секретов), Task 26 (Google на двух машинах).

- [ ] **Step 1: Syncthing-проба с маком.** Когда ноутбук пишет «ноутбук: файл создан, Syncthing выключен», на маке:

```bash
mkdir -p ~/.dor/_h2t-probe
printf 'same content 2026-10-17\n' > ~/.dor/_h2t-probe/same.txt
shasum -a 256 ~/.dor/_h2t-probe/same.txt
```
и ответ в канал «мак: файл создан» (`h2t-ops telegram send` — флаги сверить по `--help`, отправка только с `--confirm-send`). После листинга ноутбука: `ls -la ~/.dor/_h2t-probe/` на маке, затем `rm -rf ~/.dor/_h2t-probe`.

- [ ] **Step 2: Разобрать отчёт и вписать в §11.** По каждой пробе — команда, факт, вывод. Ветки:

| Проба | Если | То |
|---|---|---|
| 11.1 Syncthing | одинаковый файл дал `*.sync-conflict-*` | §8 «Порядок у автора»: ноутбук запускает `sync` только после того, как `secrets/shared` с мака приехал (правило «существующий новый файл старше всех» тогда закрывает конфликт) — вписать явно |
| 11.1 | конфликта нет | порядок не важен; оставить как есть |
| 11.3 права Windows | `os.chmod(0o600)` не меняет ACL, а профиль закрыт ACL владельца | §4: «на Windows защита — ACL профиля; пакет права не меняет, `doctor` сообщает `не проверяется`»; Task 6 Step 5 по этой ветке |
| 11.3 | профиль читают другие пользователи | §4: `store` на Windows ставит ACL через `icacls <файл> /inheritance:r /grant:r %USERNAME%:F`; Task 6 Step 5 по этой ветке |
| 11.4 Google | sha12 refresh-токенов совпали | §11.4 закрыт |
| 11.4 | различаются | §8: после миграции ноутбука его токен окажется в `google.token.json.from-<источник>`, а главным — мак; записать, что `doctor` это покажет |
| 11.5 `msvcrt` | B ждал ≥ 2,5 с | Task 4 использует `msvcrt.locking` |
| 11.5 | B не ждал | Task 4: на Windows блокировка через файл-замок `<путь>.lock` с `O_CREAT\|O_EXCL` и повтором |
| 11 п. «сессии ноутбука» | md новее 2026-05-22 есть только в `~/.h2t/sessions` ноутбука | подтверждение §1, вписать число |

- [ ] **Step 3: Commit** — `git add docs/superpowers/specs/2026-10-17-storage-and-governance.md`, сообщение `docs(storage): laptop probe results (#548)`.

### Task 2: Сканер обходов и ratchet-тесты

**Files:**
- Create: `scripts/storage_map.py`
- Create: `tests/governance/__init__.py`
- Create: `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Produces: `storage_map.hits(root: Path, name: str) -> list[str]` (строки `path:line`), `storage_map.PATTERNS: dict[str, str]`, `storage_map.ALLOWED: dict[str, set[str]]`, CLI `python scripts/storage_map.py [--check]` печатает `name count` по строке и при `--check` сверяет с потолками теста.
- Каждая задача фазы C вызывает `--check` и правит потолки.

- [ ] **Step 1: Сканер.**

```python
# scripts/storage_map.py
"""Measure the paths and writes that bypass core/paths, core/store, core/secrets (#548 §7.3).

Partial by design: it matches known spellings, it does not prove there is no bypass —
the sandbox test in tests/governance does that. Counts are lines of tracked
h2t_ops/**/*.py, comment-only lines skipped, so the numbers move with the code and
nothing else.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS: dict[str, str] = {
    "home": r"Path\.home\(\)|expanduser\(|[\"']~/|os\.environ\[.HOME.\]|os\.environ\.get\(.HOME|USERPROFILE",
    "legacy_roots": r"\.dor\b|\.config/|[\"']\.config[\"']",
    "path_env": r"H2T_[A-Z_]*(ROOT|SPOOL|FILE|DIR)\b|H2T_PATH_|H2T_CONFIG_SECRETS",
    "dotenv": r"load_dotenv\(",
    "secret_reads": r"(secret|token|credential|\.env\b|session).*(read_text|read_bytes|open\()",
    "writes": (r"write_text\(|write_bytes\(|os\.replace\(|os\.rename\(|\b(tmp|src)\w*\.(replace|rename)\("
               r"|shutil\.(copy|copy2|copyfile|copytree|move|rmtree)\b|\.unlink\(|os\.remove\(|rmdir\("
               r"|tempfile\.|FileHandler|json\.dump\(|\.mkdir\(|os\.fdopen\(|\.touch\(|tree\.write\("
               r"|file\.write\(\)|\.open\([\"'](w|a|x)|[^_.\w]open\([^)]*,\s*[\"'](w|a|x)[bt+]*[\"']"),
    "sqlite": r"sqlite3\.connect\(",
}
ALLOWED: dict[str, set[str]] = {
    "home": {"h2t_ops/core/paths.py"},
    "legacy_roots": {"h2t_ops/core/paths.py"},
    "path_env": {"h2t_ops/core/paths.py"},
    "dotenv": set(),
    "secret_reads": {"h2t_ops/core/secrets.py"},
    "writes": {"h2t_ops/core/store.py"},
    "sqlite": {"h2t_ops/core/store.py"},
}


def _tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "h2t_ops/"], cwd=root, capture_output=True,
                         text=True, check=True).stdout
    return [p for p in out.splitlines() if p.endswith(".py")]


def hits(root: Path, name: str) -> list[str]:
    rx = re.compile(PATTERNS[name])
    found = []
    for rel in _tracked(root):
        if rel in ALLOWED[name]:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if rx.search(line):
                found.append(f"{rel}:{n}")
    return found


def main(argv: list[str]) -> int:
    counts = {name: len(hits(ROOT, name)) for name in PATTERNS}
    for name, count in counts.items():
        print(f"{name} {count}")
    if "--check" in argv:
        sys.path.insert(0, str(ROOT / "tests" / "governance"))
        from test_storage_ratchets import CEILINGS  # noqa: E402
        drift = {k: (CEILINGS[k], v) for k, v in counts.items() if CEILINGS.get(k) != v}
        for k, (was, now) in drift.items():
            print(f"ceiling {k}: {was} -> {now}")
        return 1 if drift else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 2: Тест с потолками.** Потолок **равен** факту: уменьшил — впиши новое число, иначе тест красный. Так ratchet не ослабевает молча.

```python
# tests/governance/test_storage_ratchets.py
"""Ratchets for #548 §7.3: paths, writes and secret reads outside the three modules.

A ceiling equals the measured count. Going up is a regression; going down means you
removed a bypass — write the new number here so it cannot come back. Target: 0.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("storage_map", ROOT / "scripts" / "storage_map.py")
storage_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage_map)

CEILINGS = {  # measured <дата> on <sha>; Task 2 Step 3 fills these in
    "home": 0, "legacy_roots": 0, "path_env": 0, "dotenv": 0,
    "secret_reads": 0, "writes": 0, "sqlite": 0,
}


@pytest.mark.parametrize("name", sorted(storage_map.PATTERNS))
def test_ratchet_equals_measured(name):
    found = storage_map.hits(ROOT, name)
    assert len(found) == CEILINGS[name], (
        f"{name}: {len(found)} found, ceiling {CEILINGS[name]}. Up = a new bypass "
        f"(route it through core/paths, core/store or core/secrets); down = write the "
        f"new number into CEILINGS.\n" + "\n".join(found[:40]))


def test_scanner_sees_a_planted_bypass(tmp_path):
    """Control: the scanner must report a known-positive line (verification.md)."""
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "x.py").write_text('p = Path.home() / ".dor"\nopen(p, "w")\n')
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "h2t_ops/x.py"], cwd=tmp_path, check=True)
    assert storage_map.hits(tmp_path, "home") == ["h2t_ops/x.py:1"]
    assert storage_map.hits(tmp_path, "legacy_roots") == ["h2t_ops/x.py:1"]
    assert storage_map.hits(tmp_path, "writes") == ["h2t_ops/x.py:2"]
```

- [ ] **Step 3: Замерить и вписать.** Run: `.venv/bin/python scripts/storage_map.py`. Вписать числа в `CEILINGS` и строку `# measured 2026-MM-DD on <git rev-parse --short HEAD>`. Сверка с инвентарём плана: `home` ≈ 75, `legacy_roots` ≈ 53, `writes` ≈ 210 (комментарии исключены, поэтому возможны отличия в единицах; расхождение больше 10 % — разобраться, прежде чем вписывать).

- [ ] **Step 4: Красный прогон.** Добавить в любой файл `h2t_ops/` строку `x = Path.home()`, `git add` её, выполнить `.venv/bin/pytest tests/governance/test_storage_ratchets.py -q`. Expected: FAIL `home: N+1 found, ceiling N`. Откатить строку, повторить: PASS.

- [ ] **Step 5: Commit** — `git add scripts/storage_map.py tests/governance/__init__.py tests/governance/test_storage_ratchets.py`; `test(governance): storage ratchets with measured ceilings (#548)`.

## Фаза F — три модуля

### Task 3: `core/paths.py` — места, переменные, `paths.yaml`, старые места

**Files:**
- Create: `h2t_ops/core/paths.py`
- Create: `tests/governance/test_places_table.py`
- Create: `tests/core/test_paths.py`

**Interfaces:**
- Produces:
  - `Place(id, kind, cls, sync)`, `PLACES: tuple[Place, ...]`, `EXTERNAL = ("lake", "inbox", "vault", "kb")`, `ALIASES: dict[str, str]`, `FILE_ALIASES: dict[str, str]`;
  - `home() -> Path`, `root() -> Path`, `run_dir() -> Path`, `dir_of(place_id: str) -> Path`, `place(name: str) -> Path | None`, `place_or_default(name: str) -> tuple[Path, bool]`;
  - `secrets_shared()`, `secrets_local()`, `state_dir()`, `logs_dir()`, `data_dir()`, `config_dir()`, `records(kind: str, machine: str | None = None) -> Path`, `layout_file() -> Path`, `paths_yaml() -> Path`;
  - `activity_file(machine: str) -> Path`, `evals_spool() -> tuple[Path, bool]` (путь, явный ли);
  - `paths_config() -> PathsConfig` (`places: dict[str, Path]`, `vault_rules: Path | None`, `sync: dict[str, str]`);
  - `legacy(name: str) -> Path`, `LEGACY: dict[str, tuple[str, ...]]`, `LEGACY_FILES`, `legacy_roots() -> list[Path]`, `legacy_dir(name) -> Path`;
  - `expand_user_dest(value: str) -> Path`, `machine_name() -> str`, `alias_in_use() -> list[str]`, `secrets_override() -> Path | None`.

- [ ] **Step 1: Тест таблицы мест (красный: модуля нет).**

```python
# tests/governance/test_places_table.py
"""The `yaml places` block of the spec and paths.PLACES agree both ways (§3, §7.6)."""
import re
from pathlib import Path

import yaml

from h2t_ops.core import paths

SPEC = Path(__file__).resolve().parents[2] / "docs/superpowers/specs/2026-10-17-storage-and-governance.md"


def _spec_places():
    text = SPEC.read_text(encoding="utf-8")
    block = re.search(r"```yaml places\n(.*?)```", text, re.S).group(1)
    return [{"id": r["id"], "kind": r["kind"], "class": r["class"], "sync": r["sync"]}
            for r in yaml.safe_load(block)]


def test_places_table_matches_spec_both_ways():
    code = [{"id": p.id, "kind": p.kind, "class": p.cls, "sync": p.sync} for p in paths.PLACES]
    assert code == _spec_places()
```

Run: `.venv/bin/pytest tests/governance/test_places_table.py -q` → FAIL `ModuleNotFoundError: h2t_ops.core.paths`.

- [ ] **Step 2: Тесты поведения.**

```python
# tests/core/test_paths.py
import os
import sys
from pathlib import Path

import pytest

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.ALIASES or k in paths.FILE_ALIASES \
                or k in ("H2T_MACHINE_NAME", "DOR_MACHINE_NAME", "CLAUDE_CONFIG_DIR"):
            monkeypatch.delenv(k, raising=False)
    return h


def _yaml(home, text):
    p = home / ".h2t" / "config" / "paths.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_classes_live_under_root(home):
    assert paths.dir_of("secrets.shared") == home / ".h2t" / "secrets" / "shared"
    assert paths.records("sessions", "mac") == home / ".h2t" / "records" / "sessions" / "mac"
    assert paths.run_dir() == home / ".h2t" / "run"


def test_root_override_moves_everything_but_run(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "r"))
    assert paths.dir_of("state") == tmp_path / "r" / "state"
    assert paths.run_dir() == home / ".h2t" / "run"


def test_class_and_place_env_override_and_alias(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_RECORDS", str(tmp_path / "rec"))
    assert paths.records("evals") == tmp_path / "rec" / "evals"
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "old-sessions"))
    assert paths.dir_of("records.sessions") == tmp_path / "old-sessions"
    assert "H2T_SESSION_ROOT" in paths.alias_in_use()


def test_external_place_from_yaml_env_beats_yaml(home, monkeypatch, tmp_path):
    _yaml(home, f"version: 1\nplaces:\n  lake: {tmp_path / 'lake'}\n")
    assert paths.place("lake") == tmp_path / "lake"
    monkeypatch.setenv("H2T_PATH_LAKE", str(tmp_path / "lake2"))
    assert paths.place("lake") == tmp_path / "lake2"
    assert paths.place("inbox") is None
    assert paths.place_or_default("inbox") == (home / ".h2t" / "data" / "inbox", True)


def test_tilde_in_yaml_expands(home):
    _yaml(home, "version: 1\nplaces:\n  kb: ~/kb\n")
    assert paths.place("kb") == home / "kb"


def test_overlapping_places_are_rejected(home, tmp_path):
    _yaml(home, f"version: 1\nplaces:\n  vault: {tmp_path / 'v'}\n  inbox: {tmp_path / 'v' / 'in'}\n")
    with pytest.raises(ConfigError, match="vault.*inbox|inbox.*vault"):
        paths.place("lake")


def test_place_inside_root_is_rejected(home):
    _yaml(home, f"version: 1\nplaces:\n  lake: {home / '.h2t' / 'lake'}\n")
    with pytest.raises(ConfigError, match="lake"):
        paths.place("lake")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink needs privilege on Windows")
def test_place_through_symlink_into_root_is_rejected(home, tmp_path):
    (home / ".h2t" / "data").mkdir(parents=True)
    link = tmp_path / "innocent"
    link.symlink_to(home / ".h2t" / "data")
    _yaml(home, f"version: 1\nplaces:\n  inbox: {link}\n")
    with pytest.raises(ConfigError, match="inbox"):
        paths.place("inbox")


def test_relative_place_is_rejected(home):
    _yaml(home, "version: 1\nplaces:\n  lake: relative/lake\n")
    with pytest.raises(ConfigError, match="absolute"):
        paths.place("lake")


def test_machine_name_order(home, monkeypatch):
    (home / ".h2t" / "state").mkdir(parents=True)
    (home / ".h2t" / "state" / "machine.json").write_text('{"name": "pinned"}')
    assert paths.machine_name() == "pinned"
    monkeypatch.setenv("DOR_MACHINE_NAME", "dor")
    assert paths.machine_name() == "dor"
    monkeypatch.setenv("H2T_MACHINE_NAME", "h2t")
    assert paths.machine_name() == "h2t"


def test_legacy_places_are_home_relative_and_ignore_root(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "r"))
    assert paths.legacy("google.store") == home / ".config" / "google-calendar-mcp"
    assert paths.legacy("sessions.dor") == home / ".dor" / "sessions"


def test_activity_alias_is_an_explicit_file(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "a" / "spool.jsonl"))
    assert paths.activity_file("mac") == tmp_path / "a" / "spool.jsonl"
    assert paths.dir_of("records.activity") == tmp_path / "a"
```

Run: `.venv/bin/pytest tests/core/test_paths.py -q` → FAIL, импорт.

- [ ] **Step 3: Реализация.**

```python
# h2t_ops/core/paths.py
"""Where every class of data lives — the only module that knows (#548 §3, §6, §7.2).

Nothing else in h2t_ops calls Path.home() or expanduser, reads H2T_PATH_* or the legacy
aliases, or spells ~/.dor or ~/.config/<program>. tests/governance holds the ratchet.
"""
from __future__ import annotations

import json
import os
import platform
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from h2t_ops.core.errors import ConfigError


@dataclass(frozen=True)
class Place:
    id: str
    kind: str   # fixed | class | place
    cls: str    # run | config | secrets | records | data | state | logs | external
    sync: str   # never | user | owner


PLACES: tuple[Place, ...] = (
    Place("run", "fixed", "run", "never"),
    Place("config", "class", "config", "user"),
    Place("secrets.shared", "class", "secrets", "user"),
    Place("secrets.local", "class", "secrets", "never"),
    Place("records.sessions", "class", "records", "user"),
    Place("records.activity", "class", "records", "user"),
    Place("records.evals", "class", "records", "user"),
    Place("records.imports", "class", "records", "user"),
    Place("data", "class", "data", "user"),
    Place("state", "class", "state", "never"),
    Place("logs", "class", "logs", "never"),
    Place("lake", "place", "external", "owner"),
    Place("inbox", "place", "external", "owner"),
    Place("vault", "place", "external", "owner"),
    Place("kb", "place", "external", "owner"),
    Place("repo", "place", "external", "owner"),
    Place("harness", "place", "external", "owner"),
    Place("tmp", "place", "external", "never"),
)
_BY_ID = {p.id: p for p in PLACES}
EXTERNAL = ("lake", "inbox", "vault", "kb")

# Directory-valued names from 3.x, read through 4.0.x; doctor warns (§6 п. 5).
ALIASES: dict[str, str] = {
    "H2T_CONFIG_ROOT": "config",
    "H2T_SESSION_ROOT": "records.sessions",
    "H2T_EVALS_ROOT": "records.evals",
    "H2T_LAKE_ROOT": "lake",
    "H2T_KB_ROOT": "kb",
}
# File-valued names from 3.x: the file is the user's explicit choice (plan R5).
FILE_ALIASES: dict[str, str] = {
    "H2T_ACTIVITY_SPOOL": "records.activity",
    "H2T_EVALS_SPOOL": "state",
    "H2T_SECRETS_FILE": "secrets.shared",
}

# Where 3.x kept things. Read for migration and fallback in 4.0.x; never written except
# the Google mirror and MOVED-TO.txt (§7.3).
LEGACY: dict[str, tuple[str, ...]] = {
    "secrets.h2t": (".h2t", "config", "secrets"),
    "secrets.dor": (".dor", "secrets", "secrets.env"),
    "secrets.dor_old": (".dor", "secrets.env"),
    "notion.token": (".config", "notion", "token"),
    "google.store": (".config", "google-calendar-mcp"),
    "google.gmail": (".config", "gmail"),
    "google.dor": (".dor", "google-credentials.json"),
    "telegram": (".config", "telegram"),
    "sessions.h2t": (".h2t", "sessions"),
    "sessions.dor": (".dor", "sessions"),
    "activity": (".h2t", "activity"),
    "evals": (".h2t", "evals"),
    "research": (".h2t", "research"),
    "creative": (".h2t", "creative", "profiles"),
    "registry.dor": (".dor", "registry.jsonl"),
    "lake.dor": (".dor", "lake"),
    "vault.dor": (".dor", "vault"),
    "downloads": ("Downloads",),
}


def home() -> Path:
    return Path.home()


def _env(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None


def root() -> Path:
    return _env("H2T_PATH_ROOT") or home() / ".h2t"


def run_dir() -> Path:
    """Fixed by the 4.0 install contract: hooks/run reads $HOME/.h2t/run in bash."""
    return home() / ".h2t" / "run"


def _env_name(place_id: str) -> str:
    return "H2T_PATH_" + place_id.upper().replace(".", "_")


def dir_of(place_id: str) -> Path:
    p = _BY_ID[place_id]
    if p.kind == "fixed":
        return run_dir()
    if p.kind == "class":
        if (own := _env(_env_name(place_id))) is not None:
            return own
        for alias, target in ALIASES.items():
            if target == place_id and (a := _env(alias)) is not None:
                return a
        if place_id == "records.activity" and (a := _env("H2T_ACTIVITY_SPOOL")) is not None:
            return a.parent  # plan R5; H2T_EVALS_SPOOL stays a file, written with dest=True
        cls, _, sub = place_id.partition(".")
        base = _env(_env_name(cls)) or root() / cls
        return base / sub if sub else base
    if place_id == "harness":
        return _env("CLAUDE_CONFIG_DIR") or home() / ".claude"
    if place_id == "tmp":
        return Path(tempfile.gettempdir())
    if place_id == "repo":
        raise ValueError("repo has no fixed directory; pass the repository root to store.repo()")
    found = place(place_id)
    if found is None:
        raise ConfigError(f"place {place_id!r} is not set",
                          hint=f"h2t-ops paths set {place_id} <path>")
    return found


def config_dir() -> Path: return dir_of("config")
def secrets_shared() -> Path: return dir_of("secrets.shared")
def secrets_local() -> Path: return dir_of("secrets.local")
def state_dir() -> Path: return dir_of("state")
def logs_dir() -> Path: return dir_of("logs")
def data_dir() -> Path: return dir_of("data")
def layout_file() -> Path: return root() / "layout.json"
def paths_yaml() -> Path: return config_dir() / "paths.yaml"


def records(kind: str, machine: str | None = None) -> Path:
    base = dir_of(f"records.{kind}")
    return base / machine if machine else base


def activity_file(machine: str) -> Path:
    return _env("H2T_ACTIVITY_SPOOL") or records("activity") / f"{machine}.jsonl"


def evals_spool() -> tuple[Path, bool]:
    explicit = _env("H2T_EVALS_SPOOL")
    return (explicit, True) if explicit else (state_dir() / "evals-spool.sqlite", False)


def secrets_override() -> Path | None:
    return _env("H2T_SECRETS_FILE")


def alias_in_use() -> list[str]:
    return sorted(n for n in (*ALIASES, *FILE_ALIASES) if os.environ.get(n))


@dataclass
class PathsConfig:
    places: dict[str, Path] = field(default_factory=dict)
    vault_rules: Path | None = None
    sync: dict[str, str] = field(default_factory=dict)


def _inside(a: Path, b: Path) -> bool:
    return a == b or b in a.parents


def paths_config() -> PathsConfig:
    f = paths_yaml()
    if not f.is_file():
        return PathsConfig()
    try:
        doc = yaml.safe_load(f.read_bytes().decode("utf-8-sig")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{f} is not valid YAML: {exc}", hint="fix the file or remove it") from exc
    if doc.get("version", 1) != 1:
        raise ConfigError(f"{f}: version {doc.get('version')!r} is not supported", hint="version: 1")
    places: dict[str, Path] = {}
    for name, raw in (doc.get("places") or {}).items():
        if name not in EXTERNAL:
            raise ConfigError(f"{f}: unknown place {name!r}", hint=f"places are {', '.join(EXTERNAL)}")
        value = Path(str(raw)).expanduser()
        if not value.is_absolute():
            raise ConfigError(f"{f}: place {name!r} must be an absolute path, got {raw!r}",
                              hint="use ~/… or a full path")
        places[name] = value
    real = {k: Path(os.path.realpath(v)) for k, v in places.items()}
    h2t = Path(os.path.realpath(root()))
    for name, p in real.items():
        if _inside(p, h2t) or _inside(h2t, p):
            raise ConfigError(f"{f}: place {name!r} ({p}) overlaps the h2t root {h2t}",
                              hint="external places live outside ~/.h2t")
    names = list(real)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _inside(real[a], real[b]) or _inside(real[b], real[a]):
                raise ConfigError(f"{f}: places {a!r} and {b!r} overlap ({real[a]}, {real[b]})",
                                  hint="no place may lie inside another")
    rules = doc.get("vault_rules")
    return PathsConfig(places=places,
                       vault_rules=Path(str(rules)).expanduser() if rules else None,
                       sync={str(k): str(v) for k, v in (doc.get("sync") or {}).items()})


def place(name: str) -> Path | None:
    if (own := _env(_env_name(name))) is not None:
        return own
    for alias, target in ALIASES.items():
        if target == name and (a := _env(alias)) is not None:
            return a
    return paths_config().places.get(name)


def place_or_default(name: str) -> tuple[Path, bool]:
    found = place(name)
    return (found, False) if found is not None else (data_dir() / name, True)


def legacy(name: str) -> Path:
    return home().joinpath(*LEGACY[name])


LEGACY_FILES = frozenset({"secrets.dor", "secrets.dor_old", "notion.token", "google.dor", "registry.dor"})


def legacy_roots() -> list[Path]:
    return [legacy(n) for n in LEGACY if n != "downloads"]


def legacy_dir(name: str) -> Path:
    """The directory a legacy entry lives in: itself, or its parent for a file entry."""
    p = legacy(name)
    return p.parent if name in LEGACY_FILES else p


def expand_user_dest(value: str) -> Path:
    return Path(value).expanduser().absolute()


def machine_name() -> str:
    name = os.environ.get("H2T_MACHINE_NAME") or os.environ.get("DOR_MACHINE_NAME", "")
    if not name:
        try:
            name = json.loads((state_dir() / "machine.json").read_text(encoding="utf-8"))["name"]
        except (OSError, ValueError, KeyError, TypeError):
            name = ""
    return name or platform.node().lower().split(".")[0]
```

`legacy("downloads")` не входит в `legacy_roots()`: `~/Downloads` — это `inbox` по R2, а не старое место пакета.

- [ ] **Step 4: Зелёный прогон.** `.venv/bin/pytest tests/core/test_paths.py tests/governance/test_places_table.py -q` → PASS.

- [ ] **Step 5: Красный контроль таблицы.** Временно удалить `Place("tmp", …)` из `PLACES`. Тест таблицы мест → FAIL, в diff видно `tmp`. Вернуть строку.

- [ ] **Step 6: `get_machine_name` идёт через paths.** В `h2t_ops/lifecycle/gather/sessions.py:148-159` тело заменить на `from h2t_ops.core import paths` + `return paths.machine_name()`, имя функции сохранить (её импортируют handoff и activity). Run: `.venv/bin/pytest tests/core/test_machine_name.py tests/lifecycle -q` → PASS.

- [ ] **Step 7: Ratchet и commit.** `.venv/bin/python scripts/storage_map.py --check` → вписать новые потолки. `git add h2t_ops/core/paths.py h2t_ops/lifecycle/gather/sessions.py tests/core/test_paths.py tests/governance/test_places_table.py tests/governance/test_storage_ratchets.py`; `feat(core): paths.py — the one place that knows where data lives (#548)`.

### Task 4: `core/store.py` — классификация, `replace`, `create`, `append`, `remove`, журнал

**Files:**
- Create: `h2t_ops/core/store.py`
- Create: `tests/core/test_store.py`
- Create: `tests/core/test_store_lock.py`

**Interfaces:**
- Consumes: `paths.dir_of`, `paths.place`, `paths.legacy_roots`, `paths.EXTERNAL`, `paths.activity_file`.
- Produces:
  - `WriteRefused(ConfigError)`, `AlreadyExists(FileExistsError)`;
  - `classify(path) -> str` (id места, `"legacy"` или `"elsewhere"`);
  - `replace(path, data: str | bytes, *, place: str, mode: int | None = None, compat: bool = False, dest: bool = False) -> Path`;
  - `create(path, data, *, place, mode=None, dest=False) -> Path` (бросает `AlreadyExists`);
  - `append(path, line: str, *, place, dest=False) -> None`;
  - `remove(path, *, place, journal=False) -> None`, `remove_tree(path, *, place) -> None`;
  - `scratch(prefix="h2t-") -> ContextManager[Path]`;
  - `mkdir(path, *, place) -> Path`;
  - `sha256(data: bytes) -> str`.

- [ ] **Step 1: Тесты (красные: модуля нет).**

```python
# tests/core/test_store.py
import json
import os
import stat
import sys

import pytest

from h2t_ops.core import paths, store


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.ALIASES or k in paths.FILE_ALIASES:
            monkeypatch.delenv(k, raising=False)
    return h


def test_replace_writes_atomically_and_logs(home):
    target = paths.state_dir() / "x.json"
    store.replace(target, '{"a": 1}', place="state")
    assert target.read_text() == '{"a": 1}'
    row = json.loads((paths.logs_dir() / "writes.jsonl").read_text().splitlines()[-1])
    assert row["op"] == "replace" and row["place"] == "state" and row["path"] == str(target)
    assert row["caller"].startswith("tests.core.test_store") or "test_store" in row["caller"]


def test_write_is_classified_by_real_path_not_by_name(home):
    with pytest.raises(store.WriteRefused, match="secrets.shared"):
        store.replace(paths.secrets_shared() / "x.env", "K=v", place="state")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink needs privilege on Windows")
def test_symlink_does_not_launder_a_write(home, tmp_path):
    paths.secrets_shared().mkdir(parents=True)
    link = paths.state_dir() / "sneaky"
    link.parent.mkdir(parents=True)
    link.symlink_to(paths.secrets_shared())
    with pytest.raises(store.WriteRefused):
        store.replace(link / "exa.env", "EXA_API_KEY=fake", place="state")


def test_vault_write_refused_outside_ingest(home, tmp_path):
    vault = tmp_path / "vault"
    (home / ".h2t" / "config").mkdir(parents=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text(f"version: 1\nplaces:\n  vault: {vault}\n")
    with pytest.raises(store.WriteRefused, match="ingest"):
        store.replace(vault / "n.md", "x", place="vault")
    with pytest.raises(store.WriteRefused):
        store.replace(vault / "n.md", "x", place="elsewhere", dest=True)


def test_legacy_write_refused_without_compat(home):
    with pytest.raises(store.WriteRefused, match="legacy"):
        store.replace(paths.legacy("telegram") / "config.json", "{}", place="legacy")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_secret_files_are_0600_and_dirs_0700(home):
    p = store.replace(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-exa\n",
                      place="secrets.shared")
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert stat.S_IMODE(p.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(p.parent.parent.stat().st_mode) == 0o700
    log = (paths.logs_dir() / "writes.jsonl").read_text()
    assert "fake-exa" not in log and '"sha256": null' in log


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_non_secret_files_follow_umask(home):
    old = os.umask(0o022)
    try:
        p = store.replace(paths.state_dir() / "a.json", "{}", place="state")
    finally:
        os.umask(old)
    assert stat.S_IMODE(p.stat().st_mode) == 0o644


def test_create_never_overwrites(home):
    p = paths.records("sessions", "m") / "proj" / "s.md"
    store.create(p, "one", place="records.sessions")
    with pytest.raises(store.AlreadyExists):
        store.create(p, "two", place="records.sessions")
    assert p.read_text() == "one"
    assert [x.name for x in p.parent.iterdir()] == ["s.md"]  # no temp file left behind


def test_append_one_line_per_call(home):
    p = paths.activity_file("m")
    store.append(p, '{"a":1}', place="records.activity")
    store.append(p, '{"a":2}\n', place="records.activity")
    assert p.read_text().splitlines() == ['{"a":1}', '{"a":2}']


def test_append_under_unicode_home(tmp_path, monkeypatch):
    h = tmp_path / "Лидия Иванова"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.ALIASES or k in paths.FILE_ALIASES:
            monkeypatch.delenv(k, raising=False)
    p = paths.activity_file("m")
    store.append(p, "x", place="records.activity")
    assert p.read_text(encoding="utf-8") == "x\n"


def test_remove_only_in_package_places(home, tmp_path):
    p = store.replace(paths.state_dir() / "t", "x", place="state")
    store.remove(p, place="state")
    assert not p.exists()
    s = store.replace(paths.records("sessions", "m") / "a.md", "x", place="records.sessions")
    with pytest.raises(store.WriteRefused, match="remove"):
        store.remove(s, place="records.sessions")


def test_writes_log_rotates(home, monkeypatch):
    monkeypatch.setattr(store, "_LOG_LIMIT", 200)
    for i in range(40):
        store.replace(paths.state_dir() / f"f{i}", "x", place="state")
    names = sorted(p.name for p in paths.logs_dir().iterdir())
    assert "writes.jsonl" in names and "writes.1.jsonl" in names
    assert len([n for n in names if n.startswith("writes")]) <= 6


def test_dest_allows_explicit_user_path_but_not_package_places(home, tmp_path):
    out = tmp_path / "anywhere" / "f.txt"
    store.replace(out, "x", place="elsewhere", dest=True)
    assert out.read_text() == "x"
    with pytest.raises(store.WriteRefused):
        store.replace(paths.secrets_shared() / "a.env", "x", place="elsewhere", dest=True)
```

```python
# tests/core/test_store_lock.py
"""Mutual exclusion of store.append, deterministic (§7.3 «Тест блокировки»)."""
import subprocess
import sys
import time

from h2t_ops.core import store

HOLDER = r"""
import os, sys, time
from h2t_ops.core import store
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
with store._lock(fd):
    print("locked", flush=True)
    time.sleep(1.0)
    os.write(fd, b"A\n")
os.close(fd)
"""


def test_append_waits_for_the_holder(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    target = tmp_path / "root" / "records" / "activity" / "m.jsonl"
    target.parent.mkdir(parents=True)
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, str(target)],
                              stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "locked"
    t0 = time.monotonic()
    store.append(target, "B", place="records.activity")
    waited = time.monotonic() - t0
    holder.wait(timeout=10)
    assert waited >= 0.7, f"append did not wait for the lock ({waited:.2f}s)"
    assert target.read_text().splitlines() == ["A", "B"]


def test_two_writers_1000_lines_each_stay_whole(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    target = tmp_path / "root" / "records" / "activity" / "m.jsonl"
    code = ("import sys\nfrom h2t_ops.core import store\n"
            "for i in range(1000): store.append(sys.argv[1], sys.argv[2] + str(i) + 'x' * 200, "
            "place='records.activity')\n")
    env = {**__import__("os").environ, "H2T_PATH_ROOT": str(tmp_path / "root")}
    ps = [subprocess.Popen([sys.executable, "-c", code, str(target), tag], env=env) for tag in "PQ"]
    for p in ps:
        assert p.wait(timeout=120) == 0
    lines = target.read_text().splitlines()
    assert len(lines) == 2000
    assert all(len(line) >= 201 and line[0] in "PQ" and line.endswith("x") for line in lines)
```

Run: `.venv/bin/pytest tests/core/test_store.py tests/core/test_store_lock.py -q` → FAIL, импорт.

- [ ] **Step 2: Реализация.** Ветка Windows в `_lock` — по результату Task 1 (11.5); ниже вариант `msvcrt`, если проба подтвердила ожидание.

```python
# h2t_ops/core/store.py
"""The only writer (#548 §7.2): create, append, replace, managed, remove.

Every write is classified by the realpath of its target against every place's root,
whatever place the caller named and wherever the path came from (--dest, a symlink).
A write into vault that does not come through ingest_write is refused. Each write is
logged to logs/writes.jsonl — for doctor and for a person; correctness never rests on it.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError


class WriteRefused(ConfigError):
    """A write the ownership table (§7.1) does not allow."""


class AlreadyExists(FileExistsError):
    """create() found a file at the target; nothing was written."""


_PACKAGE = ("run", "config", "secrets.shared", "secrets.local", "records.sessions",
            "records.activity", "records.evals", "records.imports", "data", "state", "logs")
_REMOVABLE = {"run", "state", "logs", "tmp", "harness"}
_SECRET = {"secrets.shared", "secrets.local"}
_DEST_FORBIDDEN = {*_PACKAGE, "vault", "legacy", "harness"}
_LOG_LIMIT = 10 * 1024 * 1024
_LOG_KEEP = 5

_INGEST: contextvars.ContextVar[bool] = contextvars.ContextVar("h2t_ingest", default=False)
_MIGRATING: contextvars.ContextVar[bool] = contextvars.ContextVar("h2t_migrating", default=False)
_DELEGATED: dict[str, str] = {}


def _real(p) -> Path:
    return Path(os.path.realpath(p))


def _roots() -> list[tuple[str, Path]]:
    out = [(pid, _real(paths.dir_of(pid))) for pid in (*_PACKAGE, "harness", "tmp")]
    for pid in paths.EXTERNAL:
        found = paths.place(pid)
        if found is not None:
            out.append((pid, _real(found)))
    out += [("legacy", _real(p)) for p in paths.legacy_roots()]
    return sorted(out, key=lambda kv: len(kv[1].parts), reverse=True)


def classify(path) -> str:
    real = _real(path)
    for pid, r in _roots():
        if real == r or r in real.parents:
            return pid
    return "elsewhere"


def _compat_allowed(path: Path) -> bool:
    real = _real(path)
    if real == _real(paths.legacy("google.store") / "tokens.json"):
        return True
    return _MIGRATING.get() and path.name == "MOVED-TO.txt"


def _check(path: Path, place: str, *, dest: bool = False, compat: bool = False) -> str:
    got = classify(path)
    if got == "vault" and not _INGEST.get():
        raise WriteRefused(f"{path} is inside vault; only ingest writes there",
                           hint="vault is POS's; the package writes raw material to lake (§6)")
    if got == "legacy":
        if compat and _compat_allowed(path):
            return got
        raise WriteRefused(f"{path} is a legacy 3.x location; 4.0 does not write there",
                           hint="write the new place from core.paths; legacy files stay as copies")
    if dest:
        if got in _DEST_FORBIDDEN:
            raise WriteRefused(f"--dest {path} points into {got}", hint="choose a path outside ~/.h2t")
        return got
    if got != place:
        raise WriteRefused(f"{path} is in {got}, not {place}",
                           hint="name the place the path really belongs to")
    return got


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_mode(place: str) -> int:
    if place in _SECRET:
        return 0o600
    um = os.umask(0)
    os.umask(um)
    return 0o666 & ~um


def _ensure_dir(directory: Path, place: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if place in _SECRET and os.name != "nt":
        top = paths.dir_of(place)
        for d in (paths.root() / "secrets", top, directory):
            if d.exists() and (d == top or top in d.parents or d == paths.root() / "secrets"):
                os.chmod(d, 0o700)


def _caller() -> str:
    f = sys._getframe(1)
    here = __file__
    while f is not None and f.f_code.co_filename == here:
        f = f.f_back
    return f"{f.f_globals.get('__name__', '?')}:{f.f_lineno}" if f else "?"


def _rotate(log: Path) -> None:
    try:
        if log.stat().st_size < _LOG_LIMIT:
            return
    except FileNotFoundError:
        return
    for i in range(_LOG_KEEP - 1, 0, -1):
        older = log.with_name(f"writes.{i}.jsonl")
        if older.exists():
            os.replace(older, log.with_name(f"writes.{i + 1}.jsonl"))
    os.replace(log, log.with_name("writes.1.jsonl"))


def _log(op: str, place: str, path: Path, data: bytes | None, *, key: str | None = None) -> None:
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": op, "place": place, "path": str(path),
           "sha256": None if (data is None or place in _SECRET) else sha256(data),
           "caller": _caller()}
    if key:
        row["key"] = key
    log = paths.logs_dir() / "writes.jsonl"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        _rotate(log)
        fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
        try:
            with _lock(fd):
                os.write(fd, (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass  # the journal is for people; a write must not fail because its log row did


@contextlib.contextmanager
def _lock(fd: int) -> Iterator[None]:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.02)
        try:
            yield
        finally:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def _bytes(data: str | bytes) -> bytes:
    return data.encode("utf-8") if isinstance(data, str) else data


def _tmp_beside(path: Path, payload: bytes, mode: int) -> str:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    return tmp


def replace(path, data: str | bytes, *, place: str, mode: int | None = None,
            compat: bool = False, dest: bool = False) -> Path:
    path = Path(path)
    got = _check(path, place, dest=dest, compat=compat)
    payload = _bytes(data)
    _ensure_dir(path.parent, place)
    tmp = _tmp_beside(path, payload, _default_mode(place) if mode is None else mode)
    try:
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    _log("replace", got, path, payload, key=path.name if place in _SECRET else None)
    return path


def create(path, data: str | bytes, *, place: str, mode: int | None = None,
           dest: bool = False) -> Path:
    path = Path(path)
    got = _check(path, place, dest=dest)
    payload = _bytes(data)
    _ensure_dir(path.parent, place)
    mode = _default_mode(place) if mode is None else mode
    tmp = _tmp_beside(path, payload, mode)
    try:
        try:
            os.link(tmp, path)          # atomic and never overwrites
        except FileExistsError:
            raise AlreadyExists(str(path)) from None
        except OSError:                 # no hard links here (FAT, some network shares)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), mode)
            except FileExistsError:
                raise AlreadyExists(str(path)) from None
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
    _log("create", got, path, payload)
    return path


def append(path, line: str, *, place: str, dest: bool = False) -> None:
    path = Path(path)
    got = _check(path, place, dest=dest)
    payload = (line if line.endswith("\n") else line + "\n").encode("utf-8")
    _ensure_dir(path.parent, place)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0),
                 _default_mode(place))
    try:
        with _lock(fd):
            os.write(fd, payload)       # one write() under the lock: one whole line
    finally:
        os.close(fd)
    _log("append", got, path, payload)


def mkdir(path, *, place: str) -> Path:
    path = Path(path)
    _check(path, place)
    _ensure_dir(path, place)
    return path


def remove(path, *, place: str, journal: bool = False) -> None:
    path = Path(path)
    got = _check(path, place, compat=journal)
    if place not in _REMOVABLE and not journal:
        raise WriteRefused(f"remove is not allowed in {place}", hint="only run, state, logs, tmp, harness")
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
    _log("remove", got, path, None)


def remove_tree(path, *, place: str) -> None:
    path = Path(path)
    got = _check(path, place)
    if place not in _REMOVABLE:
        raise WriteRefused(f"remove_tree is not allowed in {place}", hint="only run, state, logs, tmp, harness")
    shutil.rmtree(path, ignore_errors=True)
    _log("remove_tree", got, path, None)


@contextlib.contextmanager
def scratch(prefix: str = "h2t-") -> Iterator[Path]:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
```

- [ ] **Step 3: Зелёный прогон.** `.venv/bin/pytest tests/core/test_store.py tests/core/test_store_lock.py -q` → PASS.

- [ ] **Step 4: Красный контроль блокировки.** В `_lock` заменить тело ветки POSIX на `yield` (без `flock`). `test_append_waits_for_the_holder` → FAIL `append did not wait for the lock` (или порядок `["B","A"]`). Вернуть.

- [ ] **Step 5: Красный контроль классификации.** В `_check` временно заменить `real = _real(path)` в `classify` на `real = Path(path).absolute()`. `test_symlink_does_not_launder_a_write` → FAIL. Вернуть.

- [ ] **Step 6: Commit** — `git add h2t_ops/core/store.py tests/core/test_store.py tests/core/test_store_lock.py tests/governance/test_storage_ratchets.py`; `feat(core): store.py — the one writer (#548)`.

### Task 5: `store.managed`, `store.repo`, `store.ingest_write`, режим миграции

**Files:**
- Modify: `h2t_ops/core/store.py`
- Create: `h2t_ops/core/repo_writers.py`
- Create: `tests/core/test_store_managed_repo.py`
- Create: `tests/governance/test_single_doors.py`

**Interfaces:**
- Produces:
  - `managed(path, *, place, library: str, dest=False) -> ContextManager[Path]` (регистрирует делегирование на путь и боковые файлы `-journal`, `-wal`, `-shm`; после выхода ставит права места);
  - `delegated(path) -> str | None`;
  - `repo(root: Path, command: str) -> RepoWriter` с методами `create(rel, data)`, `replace(rel, data)`, `append(rel, line)`, `rename(src_rel, dst_rel, *, git: bool)`;
  - `ingest_write(path, data) -> Path`;
  - `migrating() -> ContextManager[None]`;
  - `repo_writers.REPO_WRITERS: dict[str, dict[str, tuple[str, ...]]]`.

- [ ] **Step 1: Тесты (красные).**

```python
# tests/core/test_store_managed_repo.py
import os
import sqlite3
import stat
import sys

import pytest

from h2t_ops.core import paths, store


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.ALIASES or k in paths.FILE_ALIASES:
            monkeypatch.delenv(k, raising=False)
    return h


def test_managed_registers_delegation_only_while_open(home):
    db = paths.state_dir() / "index.sqlite"
    with store.managed(db, place="state", library="sqlite3") as p:
        assert store.delegated(p) == "sqlite3"
        assert store.delegated(str(p) + "-journal") == "sqlite3"
        sqlite3.connect(p).close()
    assert store.delegated(db) is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_managed_secret_gets_0600(home):
    sess = paths.secrets_local() / "telegram.session"
    with store.managed(sess, place="secrets.local", library="telethon") as p:
        p.write_bytes(b"x")  # stands in for the library
    assert stat.S_IMODE(sess.stat().st_mode) == 0o600


def test_repo_writer_honours_allow_list(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    w = store.repo(repo, "init-project")
    w.create(".claude/project-id", "dev/x\n")
    assert (repo / ".claude" / "project-id").read_text() == "dev/x\n"
    with pytest.raises(store.WriteRefused, match="init-project"):
        w.replace("README.md", "x")
    with pytest.raises(store.WriteRefused, match="outside"):
        w.create("../escape", "x")


def test_unknown_command_is_refused(tmp_path):
    with pytest.raises(store.WriteRefused, match="not in the repo allow-list"):
        store.repo(tmp_path, "h2t-something-new")


def test_ingest_is_the_vault_door(home, tmp_path):
    vault = tmp_path / "vault"
    (home / ".h2t" / "config").mkdir(parents=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text(f"version: 1\nplaces:\n  vault: {vault}\n")
    store.ingest_write(vault / "n.md", "note")
    assert (vault / "n.md").read_text() == "note"


def test_moved_marker_only_while_migrating(home):
    legacy = paths.legacy("sessions.h2t")
    legacy.mkdir(parents=True)
    with pytest.raises(store.WriteRefused):
        store.replace(legacy / "MOVED-TO.txt", "x", place="legacy", compat=True)
    with store.migrating():
        store.replace(legacy / "MOVED-TO.txt", "x", place="legacy", compat=True)
    assert (legacy / "MOVED-TO.txt").exists()
```

```python
# tests/governance/test_single_doors.py
"""ingest_write and remove(journal=True) each have one import site (§7.2, plan R1)."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _sites(rx):
    files = subprocess.run(["git", "ls-files", "h2t_ops/"], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.split()
    return [f for f in files if f.endswith(".py") and f != "h2t_ops/core/store.py"
            and re.search(rx, (ROOT / f).read_text(encoding="utf-8"))]


def test_ingest_write_has_at_most_the_ingest_module():
    assert all(s.startswith("h2t_ops/ingest/") for s in _sites(r"\bingest_write\b"))


def test_journal_remove_only_in_rollback():
    assert set(_sites(r"journal\s*=\s*True")) <= {"h2t_ops/setup/layout/rollback.py"}
```

- [ ] **Step 2: Реализация.** Дописать в `store.py`:

```python
def delegated(path) -> str | None:
    real = str(_real(path))
    for key, lib in _DELEGATED.items():
        if real == key or real.startswith(key + "-"):
            return lib
    return None


@contextlib.contextmanager
def managed(path, *, place: str, library: str, dest: bool = False) -> Iterator[Path]:
    """Resolve and check the path, then hand the file to a library that opens it itself."""
    path = Path(path)
    got = _check(path, place, dest=dest)
    _ensure_dir(path.parent, place)
    key = str(_real(path))
    _DELEGATED[key] = library
    try:
        yield path
    finally:
        _DELEGATED.pop(key, None)
        mode = _default_mode(place)
        for side in (path, *(path.with_name(path.name + s) for s in ("-journal", "-wal", "-shm"))):
            if side.exists():
                with contextlib.suppress(OSError):
                    os.chmod(side, mode)
        _log("managed", got, path, None, key=library)


def ingest_write(path, data: str | bytes) -> Path:
    """The vault's single door (§7.2). One import site: the ingest module (subsystem 4)."""
    token = _INGEST.set(True)
    try:
        return replace(path, data, place="vault")
    finally:
        _INGEST.reset(token)


@contextlib.contextmanager
def migrating() -> Iterator[None]:
    token = _MIGRATING.set(True)
    try:
        yield
    finally:
        _MIGRATING.reset(token)


class RepoWriter:
    def __init__(self, root: Path, command: str, rules: dict[str, tuple[str, ...]]):
        self.root, self.command, self.rules = _real(root), command, rules

    def _target(self, op: str, rel: str) -> Path:
        import fnmatch
        target = _real(self.root / rel)
        if target != self.root and self.root not in target.parents:
            raise WriteRefused(f"{rel} is outside the repository {self.root}", hint="")
        posix = target.relative_to(self.root).as_posix()
        if not any(fnmatch.fnmatchcase(posix, g) for g in self.rules.get(op, ())):
            raise WriteRefused(f"{self.command} may not {op} {posix}",
                               hint="h2t_ops/core/repo_writers.py lists what each command writes")
        if classify(target) not in ("elsewhere", "tmp", "repo"):
            raise WriteRefused(f"{target} is a package or external place, not a repository", hint="")
        return target

    def create(self, rel: str, data) -> Path:
        t = self._target("create", rel)
        return create(t, data, place="repo", dest=True)

    def replace(self, rel: str, data) -> Path:
        t = self._target("replace", rel)
        return replace(t, data, place="repo", dest=True)

    def append(self, rel: str, line: str) -> None:
        t = self._target("append", rel)
        append(t, line, place="repo", dest=True)

    def rename(self, src_rel: str, dst_rel: str, *, git: bool) -> Path:
        src, dst = self._target("rename", src_rel), self._target("rename", dst_rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if git:
            import subprocess
            subprocess.run(["git", "mv", str(src), str(dst)], cwd=self.root, check=True,
                           capture_output=True)
        else:
            os.replace(src, dst)
        _log("rename", "repo", dst, None, key=str(src))
        return dst


def repo(root, command: str) -> RepoWriter:
    from h2t_ops.core.repo_writers import REPO_WRITERS
    if command not in REPO_WRITERS:
        raise WriteRefused(f"{command!r} is not in the repo allow-list",
                           hint="add it to h2t_ops/core/repo_writers.py with what it writes")
    return RepoWriter(Path(root), command, REPO_WRITERS[command])
```

`_DEST_FORBIDDEN` не содержит `"repo"` и `"tmp"`, поэтому `dest=True` пропускает запись внутри репо, лежащего во временном каталоге теста.

```python
# h2t_ops/core/repo_writers.py
"""What each command may write into the user's repository (#548 §7.1, table «repo»).

Globs are fnmatch on the POSIX path relative to the repository root; `*` crosses `/`.
Task 17 replaces the starting set below with the measured one and pins it with a test that
runs every command in a scratch repository.
"""
REPO_WRITERS: dict[str, dict[str, tuple[str, ...]]] = {
    "init-project": {"create": (".claude/project-id",), "replace": (".claude/project-id",)},
    "h2t-project-register": {"create": (".claude/project-id",), "replace": (".claude/project-id",)},
}
```

- [ ] **Step 3: Зелёный и красный прогоны.** `.venv/bin/pytest tests/core/test_store_managed_repo.py tests/governance/test_single_doors.py -q` → PASS. Контроль: в `RepoWriter._target` убрать проверку `fnmatch` → `test_repo_writer_honours_allow_list` FAIL. Вернуть.

- [ ] **Step 4: Commit** — `git add h2t_ops/core/store.py h2t_ops/core/repo_writers.py tests/core/test_store_managed_repo.py tests/governance/test_single_doors.py`; `feat(core): store.managed, repo allow-list, ingest door (#548)`.

### Task 6: `core/providers.py` и новый `core/secrets.py`

**Files:**
- Create: `h2t_ops/core/providers.py`
- Modify: `h2t_ops/core/secrets.py` (переписать целиком, сохранив публичные имена `load_secrets`, `resolve_notion_token`, `candidate_secret_files`)
- Create: `tests/core/test_secrets_v4.py`
- Create: `tests/governance/test_secret_names.py`
- Modify: `tests/core/test_secrets.py`, `tests/core/test_secrets_precedence.py`, `tests/test_secrets_path_parity.py` (под новый порядок; старый порядок остаётся как запасной)

**Interfaces:**
- Produces:
  - `providers.CONNECTOR_PROVIDERS: dict[str, tuple[str, ...]]`, `providers.KEY_PREFIX: dict[str, str]`, `providers.provider_of_key(key: str) -> str | None`, `providers.is_package_provider(stem: str) -> bool`, `providers.FILE_NAME = re.compile(...)`;
  - `secrets.parse_env(text: str) -> dict[str, str]` (тот же разбор, что 3.x);
  - `secrets.get(key: str) -> str | None`;
  - `secrets.load_secrets(env_file: Path | None = None) -> None`;
  - `secrets.candidate_secret_files(env_file=None) -> list[Path]`;
  - `secrets.provider_file(provider: str, *, local=False) -> Path`;
  - `secrets.read_json(name: str) -> tuple[dict | None, Path | None]` для `google.client`, `google.token`, `telegram.auth-state`;
  - `secrets.write_json(name: str, data: dict) -> Path`;
  - `secrets.write_env(provider: str, values: dict[str, str]) -> Path`;
  - `secrets.legacy_sources() -> list[tuple[str, Path]]`;
  - `secrets.resolve_notion_token() -> str`.

- [ ] **Step 1: Реестр провайдеров.**

```python
# h2t_ops/core/providers.py
"""Connector → providers, and the key prefix each provider owns (#548 §4).

A provider is the external service, not the connector: research talks to exa and jina.
"""
from __future__ import annotations

import re

CONNECTOR_PROVIDERS: dict[str, tuple[str, ...]] = {
    "notion": ("notion",), "gmail": ("google",), "calendar": ("google",), "drive": ("google",),
    "google": ("google",), "telegram": ("telegram",), "meetgeek": ("meetgeek",),
    "granola": ("granola",), "dropbox": ("dropbox",), "research": ("exa", "jina"),
    "evals": ("h2t-evals",),
}
KEY_PREFIX: dict[str, str] = {
    "notion": "NOTION_", "telegram": "TELEGRAM_", "meetgeek": "MEETGEEK_", "granola": "GRANOLA_",
    "dropbox": "DROPBOX_", "exa": "EXA_", "jina": "JINA_", "h2t-evals": "H2T_EVALS_",
}
PROVIDERS = frozenset(p for ps in CONNECTOR_PROVIDERS.values() for p in ps)
FILE_NAME = re.compile(r"^(?P<provider>[a-z0-9-]+)\.(env|client\.json|token\.json|session|auth-state\.json)$")
EXEMPT = re.compile(r"^other\.env$|\.from-[A-Za-z0-9_-]+(\.[a-z.]+)?$")


def provider_of_key(key: str) -> str | None:
    best = None
    for provider, prefix in KEY_PREFIX.items():
        if key.startswith(prefix) and (best is None or len(prefix) > len(KEY_PREFIX[best])):
            best = provider
    return best


def is_package_provider(stem: str) -> bool:
    return stem in PROVIDERS
```

- [ ] **Step 2: Тесты (красные).**

```python
# tests/core/test_secrets_v4.py
import os

import pytest

from h2t_ops.core import paths, secrets


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith(("H2T_PATH_", "EXA_", "JINA_", "NOTION_", "MEETGEEK_", "GRANOLA_",
                         "DROPBOX_", "TELEGRAM_", "H2T_EVALS_")) or k in paths.FILE_ALIASES:
            monkeypatch.delenv(k, raising=False)
    return h


def _w(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_new_provider_file_wins_and_legacy_is_not_read_for_that_provider(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-new\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\nNOTION_API_TOKEN=fake-notion\n")
    assert secrets.get("EXA_API_KEY") == "fake-new"
    assert secrets.get("NOTION_API_TOKEN") == "fake-notion"  # no notion.env yet: fallback


def test_environment_beats_files(home, monkeypatch):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-file\n")
    monkeypatch.setenv("EXA_API_KEY", "fake-env")
    assert secrets.get("EXA_API_KEY") == "fake-env"


def test_legacy_ladder_order_is_3x_order(home):
    _w(paths.legacy("secrets.h2t") / "secrets.env", "MEETGEEK_API_KEY=fake-a\n")
    _w(paths.legacy("secrets.dor"), "MEETGEEK_API_KEY=fake-b\nGRANOLA_API_KEY=fake-g\n")
    assert secrets.get("MEETGEEK_API_KEY") == "fake-a"
    assert secrets.get("GRANOLA_API_KEY") == "fake-g"


def test_override_file_still_narrows_legacy_reading(home, monkeypatch, tmp_path):
    only = tmp_path / "only.env"
    _w(only, "GRANOLA_API_KEY=fake-only\n")
    _w(paths.legacy("secrets.dor"), "GRANOLA_API_KEY=fake-b\nMEETGEEK_API_KEY=fake-m\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(only))
    assert secrets.get("GRANOLA_API_KEY") == "fake-only"
    assert secrets.get("MEETGEEK_API_KEY") is None


def test_env_parse_matches_3x_on_awkward_files():
    text = '﻿A=1\r\n# c\r\nexport B="two"\nC=\'three\'\n D = four \nbad line\n'
    assert secrets.parse_env(text) == {"A": "1", "B": "two", "C": "three", "D": "four"}


def test_load_secrets_merges_without_override(home, monkeypatch):
    _w(paths.secrets_shared() / "granola.env", "GRANOLA_API_KEY=fake-g\n")
    monkeypatch.setenv("GRANOLA_API_KEY", "fake-env")
    secrets.load_secrets()
    assert os.environ["GRANOLA_API_KEY"] == "fake-env"


def test_google_json_new_then_legacy(home):
    _w(paths.legacy("google.store") / "tokens.json", '{"refresh_token": "fake-old"}')
    data, where = secrets.read_json("google.token")
    assert data == {"refresh_token": "fake-old"} and where.name == "tokens.json"
    secrets.write_json("google.token", {"refresh_token": "fake-new"})
    data, where = secrets.read_json("google.token")
    assert data == {"refresh_token": "fake-new"} and where == paths.secrets_shared() / "google.token.json"


def test_notion_token_file_is_last_resort(home):
    _w(paths.legacy("notion.token"), "fake-file-token\n")
    assert secrets.resolve_notion_token() == "fake-file-token"
    _w(paths.secrets_shared() / "notion.env", "NOTION_API_TOKEN=fake-env-file\n")
    assert secrets.resolve_notion_token() == "fake-env-file"
```

Имя `parse_env` в 3.x не существовало: разбор жил внутри `load_secrets` (`core/secrets.py:64-71`). Первым шагом вынести его как есть, без изменения поведения. Кавычки срезаются `strip('"').strip("'")`, BOM и `export ` в 3.x **не** обрабатывались. Тест фиксирует новое поведение: BOM и `export ` распознаются. Это расширение, а не изменение: строка `export B=…` в 3.x давала ключ `export B`, который никто не читал.

```python
# tests/governance/test_secret_names.py
"""Every file the package writes into secrets/ matches the naming contract (§4, §7.3)."""
from h2t_ops.core import providers


def test_package_names_match():
    for name in ("notion.env", "exa.env", "google.client.json", "google.token.json",
                 "telegram.session", "telegram.auth-state.json", "h2t-evals.env"):
        m = providers.FILE_NAME.match(name)
        assert m and providers.is_package_provider(m["provider"]), name


def test_exemptions_and_rejections():
    assert providers.EXEMPT.search("other.env")
    assert providers.EXEMPT.search("exa.env.from-dor")
    assert not providers.FILE_NAME.match("google-calendar-mcp.json")
    assert not providers.is_package_provider("calendar")


def test_every_secret_write_uses_a_package_name(tmp_path, monkeypatch):
    """Route secrets.write_* through a recorder and check the names it produced."""
    import os
    from h2t_ops.core import paths, secrets
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_"):
            monkeypatch.delenv(k)
    secrets.write_env("exa", {"EXA_API_KEY": "fake"})
    secrets.write_json("google.token", {"refresh_token": "fake"})
    for p in paths.secrets_shared().iterdir():
        m = providers.FILE_NAME.match(p.name)
        assert m and providers.is_package_provider(m["provider"]), p.name
```

- [ ] **Step 3: Реализация `secrets.py`.**

```python
# h2t_ops/core/secrets.py
"""The only reader of secrets (#548 §4, §7.2).

New places: ~/.h2t/secrets/shared/<provider>.env and provider-format files, and
secrets/local for what must not leave the machine. Through 4.0.x the 3.x ladder is read as
a fallback — but only for a provider that has no new file yet, so a stale legacy value can
never shadow a migrated one. 4.1 deletes the fallback.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from h2t_ops.core import paths, providers, store
from h2t_ops.core.errors import ConfigError

_JSON = {"google.client": ("secrets.shared", "google.client.json"),
         "google.token": ("secrets.shared", "google.token.json"),
         "telegram.auth-state": ("secrets.local", "telegram.auth-state.json")}


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.lstrip("﻿").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        if key and key not in out:
            out[key] = val.strip().strip('"').strip("'")
    return out


def _read_env(path: Path) -> dict[str, str]:
    try:
        return parse_env(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError):
        return {}


def provider_file(provider: str, *, local: bool = False) -> Path:
    base = paths.secrets_local() if local else paths.secrets_shared()
    return base / f"{provider}.env"


def legacy_sources() -> list[tuple[str, Path]]:
    """The 3.x ladder, in its order (core/secrets.py of 3.3.0 — #432, #483)."""
    override = paths.secrets_override()
    if override is not None:
        return [("H2T_SECRETS_FILE", override)]
    d = paths.legacy("secrets.h2t")
    out = [("h2t-config", d / "secrets.env")]
    if d.is_dir():
        out += [(f"h2t-config-{p.stem}", p) for p in sorted(d.glob("*.env"), key=lambda p: p.name)
                if p.name != "secrets.env"]
    return out + [("dor-secrets", paths.legacy("secrets.dor")), ("dor", paths.legacy("secrets.dor_old"))]


def candidate_secret_files(env_file: Path | None = None) -> list[Path]:
    if env_file is not None:
        return [env_file]
    new = sorted(paths.secrets_shared().glob("*.env")) if paths.secrets_shared().is_dir() else []
    return [*new, *(p for _, p in legacy_sources())]


def _new_values() -> dict[str, str]:
    out: dict[str, str] = {}
    shared = paths.secrets_shared()
    for provider in sorted(providers.PROVIDERS) + ["other"]:
        for key, val in _read_env(shared / f"{provider}.env").items():
            out.setdefault(key, val)
    return out


def _migrated(provider: str | None) -> bool:
    name = f"{provider}.env" if provider else "other.env"
    return (paths.secrets_shared() / name).is_file()


def get(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    new = _new_values()
    if key in new:
        return new[key]
    if _migrated(providers.provider_of_key(key)):
        return None
    for _, path in legacy_sources():
        val = _read_env(path).get(key)
        if val is not None:
            return val
    return None


def load_secrets(env_file: Path | None = None) -> None:
    """Merge every known key into os.environ without overriding (3.x contract kept)."""
    if env_file is not None:
        merged = _read_env(env_file)
    else:
        merged = dict(_new_values())
        for _, path in legacy_sources():
            for key, val in _read_env(path).items():
                if key not in merged and not _migrated(providers.provider_of_key(key)):
                    merged[key] = val
    for key, val in merged.items():
        if key and key not in os.environ:
            os.environ[key] = val


def _legacy_json(name: str) -> list[Path]:
    if name == "google.client":
        return [paths.legacy("google.store") / "credentials.json",
                paths.legacy("google.gmail") / "credentials.json", paths.legacy("google.dor")]
    if name == "google.token":
        return [paths.legacy("google.store") / "tokens.json", paths.legacy("google.gmail") / "token.json"]
    if name == "telegram.auth-state":
        return [paths.legacy("telegram") / "auth_state.json"]
    raise KeyError(name)


def json_path(name: str) -> Path:
    place, file = _JSON[name]
    return paths.dir_of(place) / file


def read_json(name: str) -> tuple[dict | None, Path | None]:
    for path in (json_path(name), *_legacy_json(name)):
        if path.is_file():
            try:
                return json.loads(path.read_bytes().decode("utf-8-sig")), path
            except (ValueError, UnicodeDecodeError) as exc:
                raise ConfigError(f"{path} is not valid JSON: {exc}", hint="re-save it as UTF-8 JSON") from exc
    return None, None


def write_json(name: str, data: dict) -> Path:
    place, _ = _JSON[name]
    return store.replace(json_path(name), json.dumps(data, ensure_ascii=False, indent=2), place=place)


def write_env(provider: str, values: dict[str, str], *, local: bool = False) -> Path:
    body = "".join(f"{k}={v}\n" for k, v in values.items())
    return store.replace(provider_file(provider, local=local), body,
                         place="secrets.local" if local else "secrets.shared")


def resolve_notion_token() -> str:
    tok = get("NOTION_API_TOKEN")
    if tok:
        return tok
    if not _migrated("notion"):
        cfg = paths.legacy("notion.token")
        if cfg.is_file():
            text = cfg.read_text(encoding="utf-8").strip()
            if text:
                return text
    raise ConfigError("Notion API token not found.",
                      hint=f"Set NOTION_API_TOKEN in {provider_file('notion')}")
```

- [ ] **Step 4: Старые тесты секретов.** `tests/core/test_secrets.py` патчит удалённые константы `DEFAULT_SECRETS`, `LEGACY_SECRETS`, `H2T_CONFIG_SECRETS`. Перевести их на `HOME`/`USERPROFILE` во временный каталог и запись файлов по `paths.legacy(...)`. Утверждения о порядке 3.x сохранить: он теперь запасной. `tests/core/test_secrets_precedence.py` (дочерний интерпретатор) оставить, добавить случай «новый файл провайдера старше всех старых». `tests/test_secrets_path_parity.py` перевести на `secrets.candidate_secret_files()`.

Run: `.venv/bin/pytest tests/core/test_secrets_v4.py tests/core/test_secrets.py tests/core/test_secrets_precedence.py tests/test_secrets_path_parity.py tests/governance/test_secret_names.py tests/connectors -q` → PASS.

- [ ] **Step 5: Права на Windows — по ветке Task 1.** Если ACL профиля закрыт, в `store._ensure_dir` ничего не добавлять, а в `doctor` (Task 20) выводить «права: не проверяются на Windows (ACL профиля)». Если профиль открыт, добавить в `store` функцию `_restrict_windows(path)`: `subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{os.environ['USERNAME']}:F"], check=False, capture_output=True)`. Вызывать её для файлов и каталогов мест `secrets.*`. Тест с `skipif(sys.platform != "win32")` читает `icacls` и проверяет, что прав `Users`/`Everyone` нет.

- [ ] **Step 6: Красный контроль запасного чтения.** В `get` удалить строку `if _migrated(...): return None`. `test_new_provider_file_wins_and_legacy_is_not_read_for_that_provider` по-прежнему зелёный (новое значение и так первое), поэтому добавить контрольный тест:

```python
def test_migrated_provider_never_falls_back(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_OTHER=fake\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\n")
    assert secrets.get("EXA_API_KEY") is None
```
С удалённой строкой → FAIL `'fake-old' is not None`. Вернуть строку → PASS.

- [ ] **Step 7: Ratchet и commit.** `--check`, потолки. `git add h2t_ops/core/providers.py h2t_ops/core/secrets.py tests/core/test_secrets_v4.py tests/core/test_secrets.py tests/core/test_secrets_precedence.py tests/test_secrets_path_parity.py tests/governance/test_secret_names.py tests/governance/test_storage_ratchets.py`; `feat(core): one secrets reader over secrets/{shared,local} with a 4.0.x fallback (#548)`.

### Task 7: Песочница — аудит, фикстура, изоляция набора тестов

**Files:**
- Create: `tests/governance/audit.py`
- Create: `tests/governance/sandbox_cases.py`
- Create: `tests/governance/test_sandbox.py`
- Modify: `conftest.py` (корень)

**Interfaces:**
- Produces:
  - `audit.Recorder(guarded: list[Path], secret_dirs: list[Path])` с `active() -> ContextManager`, `violations: list[str]`, `popen: list[list[str]]`;
  - фикстура `sandbox` → `SimpleNamespace(home, lake, inbox, vault, recorder)`;
  - `sandbox_cases.CASES: list[Case]`, где `Case(id: str, run: Callable[[SimpleNamespace, MonkeyPatch], None], compat: tuple[str, ...] = ())`. Каждая задача фазы C дописывает сюда свои случаи.

- [ ] **Step 1: Аудит.**

```python
# tests/governance/audit.py
"""Who touched a file (#548 §7.3). Python-level only: C extensions that make their own
syscalls and child processes after Popen are invisible here — the directory permissions of
the sandbox are the guarantee there, and the verdict is «no bypass through Python found»."""
from __future__ import annotations

import contextlib
import os
import sys
import threading
from pathlib import Path

_DOORS = ("h2t_ops/core/store.py", "h2t_ops/core/secrets.py")
_STATE = threading.local()
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


def _stack_has_door() -> bool:
    f = sys._getframe(2)
    while f is not None:
        name = f.f_code.co_filename.replace("\\", "/")
        if name.endswith(_DOORS):
            return True
        f = f.f_back
    return False


def _paths(event: str, args: tuple) -> list[tuple[str, bool]]:
    """(path, is_write) pairs an event touches."""
    if event == "open":
        path, mode, flags = args
        if not isinstance(path, (str, bytes, os.PathLike)):
            return []
        write = bool(mode and any(c in str(mode) for c in "wax+")) or bool(flags & _WRITE_FLAGS)
        return [(os.fsdecode(path), write)]
    if event in ("os.rename", "os.link"):
        return [(os.fsdecode(args[0]), True), (os.fsdecode(args[1]), True)]
    if event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "shutil.rmtree"):
        return [(os.fsdecode(args[0]), True)] if isinstance(args[0], (str, bytes, os.PathLike)) else []
    if event in ("shutil.copyfile", "shutil.copytree", "shutil.move"):
        return [(os.fsdecode(args[0]), False), (os.fsdecode(args[1]), True)]
    if event == "sqlite3.connect":
        return [(os.fsdecode(args[0]), True)] if args and args[0] not in (":memory:", "") else []
    return []


class Recorder:
    def __init__(self, guarded: list[Path], secret_dirs: list[Path]):
        self.guarded = [Path(os.path.realpath(p)) for p in guarded]
        self.secret_dirs = [Path(os.path.realpath(p)) for p in secret_dirs]
        self.violations: list[str] = []
        self.popen: list[list[str]] = []

    def _under(self, real: Path, roots: list[Path]) -> bool:
        return any(real == r or r in real.parents for r in roots)

    def check(self, event: str, args: tuple) -> None:
        if event == "subprocess.Popen":
            self.popen.append([os.fsdecode(a) for a in (args[1] or [])])
            return
        from h2t_ops.core import store
        for raw, write in _paths(event, args):
            real = Path(os.path.realpath(raw))
            secret = self._under(real, self.secret_dirs)
            if not (write or secret) or not self._under(real, self.guarded):
                continue
            if _stack_has_door() or store.delegated(real):
                continue
            self.violations.append(f"{event} {'write' if write else 'read'} {real}")

    @contextlib.contextmanager
    def active(self):
        _STATE.rec = self
        try:
            yield self
        finally:
            _STATE.rec = None


def _hook(event: str, args: tuple) -> None:
    rec = getattr(_STATE, "rec", None)
    if rec is None or getattr(_STATE, "inside", False):
        return
    _STATE.inside = True
    try:
        rec.check(event, args)
    finally:
        _STATE.inside = False


sys.addaudithook(_hook)  # cannot be removed; it is inert unless a Recorder is active
```

- [ ] **Step 2: Фикстура и случаи.**

```python
# tests/governance/sandbox_cases.py
"""Every command that writes to disk, run under a temporary HOME (#548 §7.3).

Phase-C tasks append their cases here. A case gets the sandbox and monkeypatch, fakes its
provider exactly as that connector's own tests do, and runs the command in-process.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    id: str
    run: Callable
    compat: tuple[str, ...] = ()  # legacy files this case may write via store compat


def _store_replace_state(sb, mp):
    from h2t_ops.core import paths, store
    store.replace(paths.state_dir() / "probe.json", "{}", place="state")


CASES: list[Case] = [Case("store.replace.state", _store_replace_state)]
```

```python
# tests/governance/test_sandbox.py
import os
import stat
import sys
from types import SimpleNamespace

import pytest

from h2t_ops.core import paths
from tests.governance import audit
from tests.governance.sandbox_cases import CASES


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.ALIASES or k in paths.FILE_ALIASES:
            monkeypatch.delenv(k, raising=False)
    lake, inbox, vault = (tmp_path / n for n in ("lake", "inbox", "vault"))
    for d in (lake, inbox, vault):
        d.mkdir()
    cfg = home / ".h2t" / "config"
    cfg.mkdir(parents=True)
    (cfg / "paths.yaml").write_text(
        f"version: 1\nplaces:\n  lake: {lake}\n  inbox: {inbox}\n  vault: {vault}\n", encoding="utf-8")
    dirs = {paths.legacy_dir(n) for n in paths.LEGACY if n != "downloads"}
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    closed = [d for d in dirs if d != home and paths.root() not in (d, *d.parents)
              and d != paths.legacy("google.store")]   # the one compat mirror (§9)
    if sys.platform != "win32":
        for d in closed:
            os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
    guarded = [paths.root(), lake, inbox, vault, *paths.legacy_roots()]
    secret_dirs = [paths.root() / "secrets", *(paths.legacy(n) for n in
                   ("secrets.h2t", "secrets.dor", "secrets.dor_old", "notion.token",
                    "google.store", "google.gmail", "google.dor", "telegram"))]
    yield SimpleNamespace(home=home, lake=lake, inbox=inbox, vault=vault,
                          recorder=audit.Recorder(guarded, secret_dirs))
    if sys.platform != "win32":
        for d in closed:
            os.chmod(d, stat.S_IRWXU)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_command_touches_only_through_the_doors(case, sandbox, monkeypatch):
    with sandbox.recorder.active():
        case.run(sandbox, monkeypatch)
    assert sandbox.recorder.violations == []


def test_direct_secret_read_is_caught(sandbox):
    target = paths.secrets_shared() / "exa.env"
    target.parent.mkdir(parents=True)
    target.write_text("EXA_API_KEY=fake")
    with sandbox.recorder.active():
        target.read_text()
    assert sandbox.recorder.violations and "read" in sandbox.recorder.violations[0]


@pytest.mark.parametrize("op", ["write", "rename", "remove"])
def test_direct_mutation_inside_lake_is_caught(sandbox, op):
    f = sandbox.lake / "a.md"
    f.write_text("x")
    with sandbox.recorder.active():
        if op == "write":
            f.write_text("y")
        elif op == "rename":
            os.rename(f, sandbox.lake / "b.md")
        else:
            os.remove(f)
    assert sandbox.recorder.violations


def test_sqlite_without_delegation_is_caught(sandbox):
    import sqlite3
    db = paths.state_dir() / "x.sqlite"
    db.parent.mkdir(parents=True)
    with sandbox.recorder.active():
        sqlite3.connect(db).close()
    assert any("sqlite3.connect" in v for v in sandbox.recorder.violations)


def test_compat_write_allowed_only_for_the_google_mirror(sandbox):
    from h2t_ops.core import store
    with sandbox.recorder.active():
        store.replace(paths.legacy("google.store") / "tokens.json", "{}", place="legacy", compat=True)
        with pytest.raises(store.WriteRefused):
            store.replace(paths.legacy("telegram") / "x.json", "{}", place="legacy", compat=True)
    assert sandbox.recorder.violations == []
```

На POSIX старые каталоги закрыты на запись, кроме `google.store`: это единственное место зеркала `compat` (§9). Каталоги внутри `~/.h2t` (`secrets.h2t` и прочие) фикстура оставляет открытыми, потому что там лежат новые места.

- [ ] **Step 3: Прогон и контроль.** `.venv/bin/pytest tests/governance -q` → PASS. Контроль: в `audit._stack_has_door` вернуть всегда `True`. Все отрицательные тесты → FAIL. Вернуть.

- [ ] **Step 4: Изоляция всего набора.** В `conftest.py`, в `_isolate_home_writes`, добавить `monkeypatch.setenv("H2T_PATH_ROOT", str(root / "h2t"))`. В `_real_home_artifacts().watched` добавить реальные пути: `~/.h2t/records`, `~/.h2t/secrets`, `~/.h2t/state`, `~/.h2t/data`, `~/.h2t/layout.json`, `~/.config/google-calendar-mcp/tokens.json`. Эти пути строить из `Path.home()` в самом `conftest.py`: он вне `h2t_ops/`, ratchet его не считает. `~/.h2t/logs` добавляет Task 18, когда логи хуков переедут.

Тесты, которые ждут `~/.h2t/<класс>` под собственным `HOME`, снимают переменную сами: `monkeypatch.delenv("H2T_PATH_ROOT")`. Фикстуры `home` в задачах 3–6 уже это делают.

Run: `.venv/bin/pytest tests/ -q` → PASS, без строки `ERROR: the suite wrote into the real home`.

- [ ] **Step 5: Commit** — `git add tests/governance/audit.py tests/governance/sandbox_cases.py tests/governance/test_sandbox.py conftest.py`; `test(governance): sandbox with an audit hook over open/rename/remove/sqlite (#548)`.


## Фаза C — перевод вызывающих

Общий порядок каждой задачи фазы:

1. Написать тест поведения на новое место. Увидеть его красным на текущем коде.
2. Перевести вызовы на `paths`, `store` и `secrets`.
3. Добавить случаи в `tests/governance/sandbox_cases.py`.
4. Запустить `--check` и вписать потолки.
5. Прогнать затронутые каталоги тестов и `tests/governance`.
6. Сделать commit.

Шаги 4–6 одинаковы во всех задачах фазы и в каждой задаче названы одной строкой.

### Task 8: Google — главная копия, кэш access-токена, зеркало

**Files:**
- Modify: `h2t_ops/core/google_auth.py` (`_oauth_store_dir` `:20-31`, `_load_dotenv` `:58-64`, `_candidate_paths` `:103-123`, `_load_credentials` `:126-172`, refresh `:211-224`, `bootstrap_google_token` `:233-259`)
- Modify: `h2t_ops/connectors/meetgeek/recovery.py:36-38,266` (свой `DRIVE_CONFIG_DIR` → `google_auth.resolve_google_credentials("drive", …)`)
- Modify: `tests/core/test_google_auth.py` (патчи `Path.home` → `HOME`/`USERPROFILE` + `H2T_PATH_ROOT`)
- Modify: `tests/governance/sandbox_cases.py`

**Interfaces:**
- Consumes: `secrets.read_json("google.client" | "google.token")`, `secrets.write_json`, `secrets.json_path`, `store.replace(..., compat=True)`, `paths.state_dir()`.
- Produces: `google_auth.resolve_google_credentials(service_name, required_scopes)` (сигнатура прежняя), `google_auth.bootstrap_google_token(*, force, open_browser)` (прежняя), `google_auth.access_cache_path() -> Path` (`state/caches/google/access.json`), `google_auth.mirror_legacy(data: dict) -> str` (`"written"|"skipped-newer"|"absent"`).

Правила (§4, §9):

1. Чтение. Клиент и refresh-токен берутся через `secrets.read_json`: сначала `shared`, затем старые места 4.0.x. Access-токен с `expiry` берётся из `state/caches/google/access.json`, если он свежее того, что лежит в файле токена.
2. Обновление access-токена пишет только кэш в `state`, через `store.replace(place="state")`.
3. Файл `shared/google.token.json` переписывается, только если Google выдал **новый** refresh-токен. Сравнение по `sha256`, не по значению.
4. После любой записи главной копии — зеркало в `paths.legacy("google.store")/"tokens.json"`. Оно пишется, пока этот файл существует, через `store.replace(..., place="legacy", compat=True)`. Если старый файл новее главной копии по mtime **и** отличается по хэшу, зеркало его не трогает и возвращает `"skipped-newer"`.
5. `_load_dotenv` удаляется. Ключей Google в env-файлах нет, а `H2T_*` загружает `secrets.load_secrets`.
6. `gmail` больше не ищет `~/.config/gmail` сам. Это запасной путь `secrets.read_json`.

- [ ] **Step 1: Тесты (красные).**

```python
# tests/core/test_google_auth.py — добавить
import json
import os
from types import SimpleNamespace

from h2t_ops.core import google_auth as mod
from h2t_ops.core import paths


def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_"):
            monkeypatch.delenv(k)


def _fake(refresh_token="fake-r1"):
    state = {"refresh_token": refresh_token}
    return SimpleNamespace(valid=False, expired=True, refresh_token=refresh_token,
                           scopes=["https://www.googleapis.com/auth/calendar"],
                           refresh=lambda req: None,
                           to_json=lambda: json.dumps({"token": "fake-access", "expiry": "2099-01-01T00:00:00Z",
                                                       **state}))


def test_refresh_writes_access_to_state_and_leaves_shared_alone(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    shared = paths.secrets_shared() / "google.token.json"
    shared.parent.mkdir(parents=True)
    shared.write_text('{"refresh_token": "fake-r1"}')
    before = shared.stat().st_mtime_ns
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake())
    monkeypatch.setattr(mod, "_request", lambda: None)
    mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert mod.access_cache_path().is_file()
    assert shared.stat().st_mtime_ns == before


def test_new_refresh_token_rewrites_shared_and_mirrors(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    shared = paths.secrets_shared() / "google.token.json"
    shared.parent.mkdir(parents=True)
    shared.write_text('{"refresh_token": "fake-r1"}')
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"refresh_token": "fake-r1"}')
    os.utime(legacy, (1, 1))
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake("fake-r2"))
    monkeypatch.setattr(mod, "_request", lambda: None)
    mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert json.loads(shared.read_text())["refresh_token"] == "fake-r2"
    assert json.loads(legacy.read_text())["refresh_token"] == "fake-r2"


def test_mirror_skips_a_newer_different_legacy_file(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"refresh_token": "fake-other"}')
    os.utime(legacy, (4102444800, 4102444800))  # 2100
    assert mod.mirror_legacy({"refresh_token": "fake-r2"}) == "skipped-newer"
    assert "fake-other" in legacy.read_text()
```

`_load_credentials` меняет сигнатуру. Было `(token_path, creds_path)`, стало `(token_data: dict, client_data: dict | None)`: файлы читает `secrets`, функция только нормализует. Старые тесты, которые подставляли пути, перевести на словари. `test_refresh_rewrites_token_as_owner_only` из PR #555 переписать: утверждение про `0600` переходит на `access_cache_path()` (place `state`, а значит по umask) и на `shared/google.token.json` (`0600`).

- [ ] **Step 2: Реализация.** Ключевые места:

```python
def access_cache_path() -> Path:
    return paths.state_dir() / "caches" / "google" / "access.json"


def mirror_legacy(data: dict) -> str:
    """One-way copy of the main token to the 3.x path POS reads (§9). Removed in 4.1."""
    legacy = paths.legacy("google.store") / "tokens.json"
    if not legacy.is_file():
        return "absent"
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    main = secrets.json_path("google.token")
    old = legacy.read_bytes()
    if (main.is_file() and legacy.stat().st_mtime > main.stat().st_mtime
            and store.sha256(old) != store.sha256(main.read_bytes())):
        return "skipped-newer"
    store.replace(legacy, body, place="legacy", compat=True, mode=0o600)
    return "written"
```

Рефреш внутри `resolve_google_credentials`:

```python
new = json.loads(creds.to_json())
store.replace(access_cache_path(),
              json.dumps({"token": new.get("token"), "expiry": new.get("expiry")}), place="state")
old_refresh = (token_data or {}).get("refresh_token")
if new.get("refresh_token") and store.sha256(new["refresh_token"].encode()) != \
        store.sha256((old_refresh or "").encode()):
    keep = {k: new[k] for k in ("refresh_token", "scopes", "client_id", "client_secret", "token_uri") if k in new}
    secrets.write_json("google.token", keep)
    mirror_legacy(keep)
```

Если `token_data` пришёл из старого места, а `shared/google.token.json` ещё нет (машина не мигрировала), рефреш пишет только кэш `state`. Старый файл он **не** трогает, даже через `compat`: на немигрированной машине `tokens.json` перестаёт обновляться access-токеном. POS это не задевает, POS обновляет токен сам (§1, `app/auth/tokens.py`). Это отличие от 3.x вписать в issue POS (Task 25).

`bootstrap_google_token` пишет клиента по-прежнему не сам: клиент кладёт пользователь. Ищется клиент через `secrets.read_json("google.client")`. Подсказка `_CLIENT_HINT` называет `secrets.json_path("google.client")`. Токен пишется через `secrets.write_json("google.token", …)` + `mirror_legacy`.

- [ ] **Step 3: Случаи песочницы** — `google.refresh` (подставные `_load_credentials`/`_request` как в Step 1, вызов `resolve_google_credentials`) и `google.refresh.new-token` с `compat=("google.store/tokens.json",)`.

- [ ] **Step 4: Красный контроль зеркала.** В `mirror_legacy` убрать ветку `skipped-newer` → `test_mirror_skips_a_newer_different_legacy_file` FAIL. Вернуть.

- [ ] **Step 5: Ratchet, прогон, commit.** `.venv/bin/pytest tests/core/test_google_auth.py tests/connectors/calendar tests/connectors/gmail tests/connectors/drive tests/connectors/google tests/connectors/meetgeek tests/governance -q`; `git add h2t_ops/core/google_auth.py h2t_ops/connectors/meetgeek/recovery.py tests/core/test_google_auth.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py`; `feat(google): main token in secrets/shared, access token in state, one-way mirror (#548)`.

### Task 9: Telegram — три части

**Files:**
- Modify: `h2t_ops/connectors/telegram/client.py` (`DEFAULT_CONFIG_DIR` `:17`, `__init__` `:225-237`, `_load_config` `:240-262`, `sqlite3.connect` `:140`, `_client` `:316`, `_save_auth_state` `:373-376`, чтение `:385,:455`, `dialogs_bootstrapped` `:817`, download-media `:714`)
- Modify: `h2t_ops/connectors/telegram/commands.py:122` (help «default: ~/Downloads» → «default: the inbox place»)
- Modify: `tests/connectors/telegram/test_client.py`, `test_auth_flows.py`, `test_commands.py`
- Modify: `tests/governance/sandbox_cases.py`

**Interfaces:**
- Consumes: `secrets.get("TELEGRAM_API_ID")`, `secrets.get("TELEGRAM_API_HASH")`, `secrets.read_json/write_json("telegram.auth-state")`, `store.managed(place="secrets.local", library="telethon")`, `paths.place_or_default("inbox")`, `paths.state_dir()`.
- Produces: `TelegramClientAdapter(config_dir: Path | None = None)` — параметр остаётся для тестов. Если он задан, все пути строятся от него, как в 3.x, и пишутся с `dest=True`. Если нет, раскладка такая:

| Что | Где | Операция |
|---|---|---|
| `api_id`, `api_hash` | `secrets.get("TELEGRAM_API_ID"/"TELEGRAM_API_HASH")`; запасной путь 4.0.x — `config.json` старого каталога через новую функцию `secrets.read_json("telegram.config")` (добавить в `_JSON`/`_legacy_json`: новых мест у неё нет, только старое) | — |
| сессия | `secrets_local()/"telegram.session"`; Telethon получает базу без `.session` | `store.managed(..., library="telethon")` вокруг каждого `_client()` и вокруг `sqlite3.connect` в `_input_peer_from_sqlite` |
| состояние входа | `secrets.write_json("telegram.auth-state", …)` | `replace`, 0600 |
| `dialogs_bootstrapped` | `state_dir()/"telegram"/"dialogs_bootstrapped"` | `replace(place="state")` |
| вложения | `--out` или `place_or_default("inbox")`; при умолчании напечатать `saved to <путь> (inbox not set: h2t-ops paths set inbox <path>)` | `replace(place="inbox")` или `dest=True` для `--out` |

Запасное чтение сессии в 4.0.x идёт из `paths.legacy("telegram")/"session.session"`. Пишет Telethon в файл, который открыл. Поэтому до миграции адаптер передаёт ему старый путь в `store.managed(..., place="legacy")`, а это `_check` отвергает. Решение: до миграции Telethon работает с **копией**. Если нового файла нет, а старый есть, адаптер копирует старый в `secrets_local()/"telegram.session"` (`store.create`, 0600) и печатает одну строку `telegram: session copied to <новый путь>; the old one is left as is`. Две живые копии одного ключа на одной машине не используются одновременно: старый путь пакет больше не открывает. Так проверка «пишется только новое место» соблюдается и без миграции.

- [ ] **Step 1: Тесты (красные).** Тест `test_session_lives_in_secrets_local_with_0600`: адаптер без `config_dir`, подставной `client_cls` пишет байты в переданный путь + `.session`. Проверить, что файл лежит в `secrets_local()`, права `0600` (`skipif win32`). Тест `test_legacy_session_is_copied_once`: в старом каталоге лежит `session.session`. Первый вызов копирует, второй не копирует (сравнить `st_mtime_ns` копии), старый файл побайтно цел. Тест `test_download_media_defaults_to_inbox`. Тест `test_api_keys_from_secrets_env`: `telegram.env` с `TELEGRAM_API_ID=1`, `TELEGRAM_API_HASH=fake`.

- [ ] **Step 2: Реализация** по таблице. `int(api_id)`: в env-файле значение строковое, а Telethon ждёт `int`. Ошибка разбора → `ConfigError(f"TELEGRAM_API_ID in {secrets.provider_file('telegram')} is not a number")`.

- [ ] **Step 3: Случаи песочницы** — `telegram.auth-start` (подставной клиент, `auth start --phone +100`), `telegram.download-media.inbox`, `telegram.session.copy-from-legacy`.

- [ ] **Step 4: Красный контроль.** Убрать `store.managed` вокруг `sqlite3.connect` в `_input_peer_from_sqlite`. Случай песочницы, который доходит до этой функции (`telegram.messages` с подставной сессией SQLite), → FAIL с `sqlite3.connect`. Вернуть.

- [ ] **Step 5: Ratchet, прогон** (`tests/connectors/telegram tests/governance`), **commit** — `feat(telegram): keys in telegram.env, session in secrets/local, marker in state (#548)`.

### Task 10: Ключи остальных провайдеров через `secrets`

**Files:**
- Modify: `h2t_ops/connectors/research/client.py:67-110` (свой `_read_env_file`, `resolve_secret` → `secrets.get`), `research/fetch.py:634` (`JINA_API_KEY` из окружения → `secrets.get`), `research/provider_routing.py` (строка с `H2T_SECRETS_FILE` → подсказка через `secrets.provider_file`)
- Modify: `h2t_ops/connectors/dropbox/client.py:31,47-57,99-100` (`PROVIDER_ENV_FILE`, `_load_provider_env` → удалить; `secrets.get`)
- Modify: `h2t_ops/connectors/meetgeek/client.py:43`, `meetgeek/pipeline.py:366-372`, `granola/client.py:55`, `notion` (ничего, если уже через `resolve_notion_token`)
- Modify: `h2t_ops/lifecycle/eval/session.py:28-55` (`_DEFAULT_SECRETS`, `_load_secrets` → `secrets.get` по ключам `H2T_EVALS_*`; запасной порядок для evals — сначала `paths.legacy("secrets.dor_old")`, как в 3.x), `lifecycle/eval/status.py:42`
- Modify: `h2t_ops/setup/legacy.py:639-668` (запись секретов `h2t-ops setup` → `secrets.write_env`)
- Modify: `conftest.py` (`_neutralize_eval_secrets` патчит удалённую константу `_DEFAULT_SECRETS`; заменить на `monkeypatch.setattr(secrets, "legacy_sources", lambda: [])` для evals-ветки или на пустой `HOME` — выбрать то, что держит тест `tests/lifecycle/eval` зелёным, и записать выбор в docstring фикстуры)
- Modify: подсказки коннекторов, где названы файлы (`meetgeek` hint про `~/.h2t/config/secrets/meetgeek.md`, `research` hint со списком файлов): называть `secrets.provider_file(<провайдер>)`
- Modify: тесты этих коннекторов, где патчатся удалённые константы

**Interfaces:**
- Consumes: `secrets.get`, `secrets.provider_file`, `secrets.write_env`, `providers.CONNECTOR_PROVIDERS`.
- Produces: `secrets.get_evals(key: str) -> str | None` — ключи `H2T_EVALS_*`. Порядок: окружение → `shared/h2t-evals.env` → `~/.dor/secrets.env` → остальная лестница (§8, строка `H2T_EVALS_*`).

- [ ] **Step 1: Тест паритета (красный).** `tests/governance/test_one_secret_reader.py` проходит по `providers.CONNECTOR_PROVIDERS` и для каждого провайдера кладёт фиктивный ключ только в `shared/<провайдер>.env`. Затем вызывает функцию, которой коннектор берёт ключ: `research.client.resolve_secret("EXA_API_KEY")`, `research.fetch._jina_key()` (выделить из `:634`), `dropbox.client._token_config()`, `meetgeek.client._api_key()`, `granola.client._api_key()`, `secrets.resolve_notion_token()`, `eval.session._load_secrets()["H2T_EVALS_TOKEN"]`, `telegram` (Task 9). Утверждение: каждая видит значение. На текущем коде FAIL у research (чтение файлов мимо `secrets`), dropbox (свой файл), jina (только окружение) и evals (только `~/.dor`).

- [ ] **Step 2: Реализация.** Функции-обёртки `_api_key()` выделить там, где ключ сегодня читается строкой в `__init__`. Это одна строка `return secrets.get("MEETGEEK_API_KEY")`. Сообщения об отсутствии ключа сохранить, путь в них взять из `secrets.provider_file(...)`.

- [ ] **Step 3: Случаи песочницы** — `research.resolve`, `dropbox.init`, `evals.load` (каждый только читает ключ).

- [ ] **Step 4: Ratchet, прогон** (`tests/connectors tests/lifecycle/eval tests/test_setup_secrets.py tests/test_setup_doctor_checks.py tests/governance`), **commit** — `refactor(secrets): every connector reads keys through core.secrets (#548)`.

### Task 11: Lake — Granola и MeetGeek

**Files:**
- Create: `h2t_ops/core/lake.py`
- Modify: `h2t_ops/connectors/granola/sync.py` (`CURSOR_PATH_DEFAULT` `:23`, `lake = Path(to)…` `:88-89`, `manifest_path` `:100`, `_write_pair` `:61-65`, дозапись `:144-147`, курсор `:159-160`)
- Modify: `h2t_ops/connectors/granola/commands.py` (`--to` становится необязательным; по умолчанию `lake/granola`)
- Modify: `h2t_ops/connectors/meetgeek/recovery.py:97-105` (`lake_root`), `meetgeek/pipeline.py:26-28` (курсор), `meetgeek/commands.py:294,302` (`--out` вебхуков), записи `recovery.py`, `pipeline.py` (22 строки по инвентарю)
- Create: `tests/core/test_lake_manifest.py`
- Modify: `tests/connectors/granola/*`, `tests/connectors/meetgeek/*`

**Interfaces:**
- Consumes: `paths.place_or_default("lake")`, `paths.state_dir()`, `store.create/replace/append`.
- Produces:

```python
# h2t_ops/core/lake.py
class ConnectorDir:
    def __init__(self, provider: str, root: Path | None = None): ...
    manifest: Path                       # <root>/manifest.jsonl
    def owned(self) -> dict[str, str]    # rel path → sha256 from the last committed row per path
    def publish(self, files: dict[str, bytes], *, op_id: str) -> list[str]   # protocol §7.1
    def recover(self) -> list[str]       # pending rows without committed: own only hash-matched files
def cursor_path(provider: str) -> Path   # state/cursors/<provider>.json
def write_cursor(provider: str, data: dict) -> Path
```

Протокол `publish` (§7.1):

1. Посчитать хэши.
2. `store.append(manifest, {"op": op_id, "state": "pending", "files": {rel: {"sha256": h, "owned_before": rel in owned}}})`.
3. Для каждого файла: если он уже свой, `store.replace(place="lake")`. Если новый, `store.create(place="lake")`. `AlreadyExists` на новом пути: файл чужой. Ничего не писать, запомнить отказ.
4. `store.append(manifest, {"op": op_id, "state": "committed", "files": {rel: sha256 итогового файла}, "refused": [...]})`.
5. Вернуть список отказов. Курсор сдвигает вызывающий, только после возврата.

Строки манифеста 3.x у Granola имеют свой формат: `_synced_versions` читает `:35-58`. `owned()` понимает оба. Старая строка без поля `state` считается `committed` для путей, которые в ней названы. Это записано в docstring.

- [ ] **Step 1: Тесты протокола (красные).**

```python
# tests/core/test_lake_manifest.py
import json
import os

import pytest

from h2t_ops.core import lake, paths, store


@pytest.fixture
def lk(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.ALIASES:
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("H2T_PATH_LAKE", str(tmp_path / "lake"))
    return lake.ConnectorDir("granola")


def _rows(d):
    return [json.loads(x) for x in d.manifest.read_text().splitlines()]


def test_publish_new_then_replace_own(lk):
    assert lk.publish({"n1.md": b"v1"}, op_id="a") == []
    assert lk.publish({"n1.md": b"v2"}, op_id="b") == []
    assert (lk.root / "n1.md").read_bytes() == b"v2"
    assert [r["state"] for r in _rows(lk)] == ["pending", "committed", "pending", "committed"]


def test_foreign_file_on_a_new_path_is_refused_and_untouched(lk):
    (lk.root).mkdir(parents=True)
    (lk.root / "n1.md").write_bytes(b"hand-made")
    assert lk.publish({"n1.md": b"v1"}, op_id="a") == ["n1.md"]
    assert (lk.root / "n1.md").read_bytes() == b"hand-made"


@pytest.mark.parametrize("stop_after", ["pending", "files"])
def test_interrupted_publish_recovers_only_hash_matched(lk, monkeypatch, stop_after):
    real_create = store.create
    calls = []

    def boom(*a, **kw):
        calls.append(1)
        if stop_after == "pending":
            raise KeyboardInterrupt
        real_create(*a, **kw)
        raise KeyboardInterrupt

    monkeypatch.setattr(store, "create", boom)
    with pytest.raises(KeyboardInterrupt):
        lk.publish({"n1.md": b"v1"}, op_id="a")
    monkeypatch.setattr(store, "create", real_create)
    assert lk.recover() == (["n1.md"] if stop_after == "files" else [])
    assert ("n1.md" in lk.owned()) == (stop_after == "files")


def test_pending_does_not_own_a_file_with_another_hash(lk, monkeypatch):
    monkeypatch.setattr(store, "create", lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        lk.publish({"n1.md": b"v1"}, op_id="a")
    (lk.root / "n1.md").write_bytes(b"someone else")   # appears during the outage
    assert lk.recover() == []
    assert "n1.md" not in lk.owned()


def test_legacy_granola_rows_count_as_committed(lk):
    lk.root.mkdir(parents=True)
    lk.manifest.write_text(json.dumps({"note_id": "n1", "path": "n1.md", "sha256": "x"}) + "\n")
    assert "n1.md" in lk.owned()
```

Последний тест опирается на формат строки 3.x. Перед написанием `owned()` открыть `granola/sync.py:35-58` и `:144-147`, взять из них точные имена полей и поправить фикстуру теста под них. В плане они названы предположительно.

- [ ] **Step 2: Реализация** `core/lake.py` по протоколу. Затем Granola: `_write_pair` → `ConnectorDir.publish({f"{note_id}.md": …, f"{note_id}.json": …})`; курсор → `lake.write_cursor("granola", …)` после `publish`. Затем MeetGeek: `lake_root()` → `paths.place_or_default("lake")[0] / "meetgeek"`; `uploads_staging_root` и `staging_dir` остаются под ним; курсор → `lake.cursor_path("meetgeek")`; `--out` вебхуков по умолчанию → `lake/meetgeek/webhooks`. Записи загрузок MeetGeek (журнал загрузок по машинам, `recovery.py`) — через `ConnectorDir("meetgeek").publish` для файлов и `store.append` для журнала.

Курсоры 3.x лежат в `~/.dor/lake/_cursors`. Если `state/cursors/<провайдер>.json` нет, а старый есть, коннектор читает старый (запасное чтение 4.0.x), а пишет новый.

- [ ] **Step 3: Случаи песочницы** — `granola.sync` (подставной клиент из `tests/connectors/granola`), `granola.sync.foreign-file`, `meetgeek.download`, `meetgeek.webhooks.write`.

- [ ] **Step 4: Красный контроль.** В `publish` поменять порядок шагов 3 и 2 (сначала файлы, потом `pending`). `test_interrupted_publish_recovers_only_hash_matched[files]` → FAIL. Вернуть.

- [ ] **Step 5: Ratchet, прогон** (`tests/core/test_lake_manifest.py tests/connectors/granola tests/connectors/meetgeek tests/governance`), **commit** — `feat(lake): connector manifest protocol, lake place default, cursors in state (#548)`.

### Task 12: Вложения и выводы — Drive, Gmail, Notion, Dropbox, research, evals, creative

**Files:**
- Modify: `h2t_ops/connectors/drive/client.py:1357,1433` (`Path.cwd()/name` → `place_or_default("inbox")`), `drive/commands.py:229-232`
- Modify: `h2t_ops/connectors/gmail/client.py` (2 записи по инвентарю), `notion/commands.py` (4), `dropbox/client.py` (8)
- Modify: `h2t_ops/connectors/research/client.py:31,177-192` (`DEFAULT_OUTPUT_DIR` → `data_dir()/"research"`; запасное чтение `paths.legacy("research")` для `research list/maintenance`), `research/store.py` (6), `research/visual_ocr.py` (4, `shutil.copy2` `:273`), `research/fetch.py` (2), `research/maintenance.py` (1), `research/exa.py:1147`
- Modify: `h2t_ops/lifecycle/eval/session.py:266-288` (`_write_local` → `records("evals", machine)/<skill>/<run>.json` через `store.create`), `:299-315` (спул → `store.managed(paths.evals_spool()…, library="h2t_evals")`), `lifecycle/eval/status.py:48`, `connectors/evals/commands.py:16-18`
- Modify: `h2t_ops/tools/creative/cli.py:20-21` (`~/.h2t/creative/profiles` → `data_dir()/"creative"/"profiles"`, запасное чтение старого), `setup/sync.py:677`
- Modify: соответствующие тесты

**Interfaces:**
- Consumes: `paths.place_or_default`, `paths.expand_user_dest`, `paths.records`, `paths.evals_spool`, `store.*`.
- Produces: правило для всех команд с `--dest`/`--out`/позиционным `DEST`. Путь пользователя проходит через `paths.expand_user_dest`, запись идёт с `dest=True`. Без пути: `place_or_default(<место>)` и строка `saved to <путь>` в человеческом выводе. В `--json` то же самое — поле `path`, и при умолчании ещё `"defaulted": true`.

Где какое место по умолчанию (§6 п. 1):

| Команда | Место |
|---|---|
| `drive download`, `drive export`, `gmail` вложения, `telegram download-media`, `dropbox download`, `notion` экспорт | `inbox` |
| `research` | `data/research` |
| `granola`, `meetgeek` | `lake/<провайдер>` (Task 11) |

`drive download` в 3.x без пути писал в текущий каталог. Это меняется на `inbox`. В CHANGELOG (Task 25) вписать строку «без пути — в inbox, а не в текущий каталог; `--dest .` возвращает прежнее».

- [ ] **Step 1: Тесты (красные)** — по одному на команду. Без пути файл оказывается в `inbox` из `paths.yaml`, а в выводе есть `"defaulted": false`. Без `paths.yaml` файл оказывается в `~/.h2t/data/inbox` и `"defaulted": true`. `--dest` внутрь `~/.h2t/secrets` даёт `WriteRefused`, код выхода 3. Для evals: запись сессии создаёт `records/evals/<машина>/<скилл>/<прогон>.json`, а повтор с тем же `run_id` даёт `AlreadyExists` → отдельный файл `<прогон>-2.json`. Повтор не перезаписывает: `records` пишется через `create`.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Случаи песочницы** — `drive.download.default`, `drive.download.dest`, `research.save`, `evals.write-local`, `evals.spool` (подставной `EvalClient`, который открывает SQLite по переданному пути), `creative.profiles-dir`.

- [ ] **Step 4: Ratchet, прогон** (`tests/connectors tests/lifecycle/eval tests/tools/creative tests/governance`), **commit** — `feat(storage): default places for downloads, research, evals, creative profiles (#548)`.

### Task 13: Сессии и activity

**Files:**
- Modify: `h2t_ops/lifecycle/handoff.py` (`default_markdown_dir` `:57-61`, `write_handoff` `:184-284`, `_write_json_atomic` `:157-160` — удалить, шаблон `:229-244`)
- Modify: `h2t_ops/lifecycle/activity/writer.py:62-90` (`_spool_path`, запись)
- Create: `h2t_ops/lifecycle/session_record.py`
- Modify: `plugins/h2t-core/skills/handoff/SKILL.md` (шаги 6–7: `latest.json` → путь md), `plugins/h2t-core/skills/session-start/SKILL.md` (если упоминает `latest.json`)
- Modify: `tests/lifecycle/test_handoff_writer.py`, `tests/lifecycle/test_handoff_gather_round_trip.py`, `tests/lifecycle/activity/test_writer.py`, `tests/core/test_session_identity_roundtrip.py`, `tests/core/test_handoff_identity_from_cwd.py`

**Interfaces:**
- Produces:

```python
# h2t_ops/lifecycle/session_record.py
FIELDS = ("session_id", "machine", "project", "domain", "date", "updated_at", "branch",
          "commits", "done", "remains", "artifacts", "migrated_from")

def render(meta: dict, body: bytes) -> bytes        # b"---\n" + yaml + b"---\n" + body
def parse(raw: bytes) -> tuple[dict, bytes]          # raises ValueError on a broken header
def session_path(machine: str, project: str, session_id: str) -> Path
```

- `write_handoff(...)` → прежний словарь, `latest` = путь md (R10). md пишется через `store.replace(place="records.sessions")`: повторный handoff той же сессии обновляет её запись (§5). При `--markdown-dir` md пишется по этому пути с `dest=True`.
- `writer.log_session_start/end` → `store.append(paths.activity_file(machine), …, place="records.activity")`. Если задан `H2T_ACTIVITY_SPOOL` (R5), `dir_of` уже указывает на его каталог, и классификация совпадает.

- [ ] **Step 1: Тесты (красные).**

```python
# tests/lifecycle/test_session_record.py
import pytest

from h2t_ops.lifecycle import session_record as sr


def test_round_trip_keeps_body_bytes():
    body = "# Session: s\r\n\nтело\n".encode("utf-8")
    meta = {"session_id": "s", "machine": "m", "project": "p", "done": "a\nb"}
    raw = sr.render(meta, body)
    got, got_body = sr.parse(raw)
    assert got_body == body and got["done"] == "a\nb" and got["machine"] == "m"


@pytest.mark.parametrize("raw", [b"---\nsession_id: [\n---\nx", b"---\nno end", b"plain md"])
def test_broken_header_raises(raw):
    with pytest.raises(ValueError):
        sr.parse(raw)
```

В `tests/lifecycle/test_handoff_writer.py` нужны четыре теста:

- `default_markdown_dir("repo")` равен `paths.records("sessions", "test-machine") / "repo"`;
- handoff пишет md с frontmatter, где `machine`, `project`, `domain`, `updated_at` и `branch` заполнены, а `latest.json` не появляется;
- повторный handoff с тем же `session_id` оставляет один файл с новым `done`;
- `H2T_SESSION_ROOT` по-прежнему уважается (псевдоним).

В `tests/lifecycle/activity/test_writer.py`: запись попадает в `records/activity/<машина>.jsonl`, а при заданном `H2T_ACTIVITY_SPOOL` — в него.

- [ ] **Step 2: Реализация.**
  - `branch`: `git rev-parse --abbrev-ref HEAD` в cwd.
  - `commits`: `git log -5 --format=%h`, через `gather.runner._run_one`, таймаут 5 с. Ошибка git даёт пустые поля, handoff не роняет (правило gates.md).
  - `updated_at`: UTC ISO с `Z`.
  - Тело md — прежний шаблон `:229-244`, чтобы читатель-человек видел то же, что в 3.x.

- [ ] **Step 3: Скиллы.**
  - `handoff/SKILL.md` Step 7 печатает строку `✓ Latest index: {latest_path}`. Заменить её на `✓ Запись: {markdown_path}` и убрать абзац про `index_truncated`.
  - Найти остальные упоминания: `grep -rn "latest.json" plugins/`.
  - После правки `tests/core/test_skill_*` прогнать отдельно.

- [ ] **Step 4: Случаи песочницы** — `handoff.write`, `handoff.write.again`, `activity.start`.

- [ ] **Step 5: Ratchet, прогон** (`tests/lifecycle tests/core tests/governance`), **commit** — `feat(sessions): handoff writes a self-describing md under records/, activity per machine (#548)`.

### Task 14: Индекс `state/index.sqlite`

**Files:**
- Create: `h2t_ops/lifecycle/index/__init__.py`, `schema.py`, `build.py`, `query.py`
- Create: `tests/lifecycle/index/test_index.py`

**Interfaces:**
- Consumes: `session_record.parse`, `paths.records`, `paths.config_dir`, `paths.state_dir`, `store.managed`, `store.remove`.
- Produces:

```python
SCHEMA_VERSION = 1
@contextmanager
def connect(*, refresh: bool = True) -> Iterator[sqlite3.Connection]
def rebuild() -> dict                                  # {"sessions": n, "projects": n, "problems": n}
def latest_sessions(project_ids: list[str], limit: int = 5) -> list[dict]
def ontology() -> tuple[dict, dict]                     # (repo_mapping_doc, domains_doc)
def problems() -> list[dict]                            # [{"path", "error"}]
```

Схема (`schema.py`):

```sql
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE stamps(path TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER);
CREATE TABLE projects(id TEXT PRIMARY KEY, domain TEXT, label TEXT, type TEXT, github TEXT);
CREATE TABLE repos(pattern TEXT, kind TEXT, project TEXT, domain TEXT);
CREATE TABLE sessions(path TEXT PRIMARY KEY, dir TEXT, session_id TEXT, machine TEXT,
                      project TEXT, domain TEXT, date TEXT, updated_at TEXT, branch TEXT,
                      last_commit TEXT, done TEXT, remains TEXT, artifacts TEXT, conflict INTEGER);
CREATE INDEX sessions_project ON sessions(project, updated_at);
CREATE TABLE registry_history(line INTEGER PRIMARY KEY, ts TEXT, machine TEXT, project TEXT,
                              status TEXT, raw TEXT);
CREATE TABLE problems(path TEXT PRIMARY KEY, error TEXT);
```

`meta` хранит `schema_version`, а также `repo_mapping` и `domains` как JSON, разобранный из YAML. YAML разбирает только `build.py` (§5).

Обновление перед запросом (`connect(refresh=True)`):

1. Взять `stat` (`st_mtime_ns`, `st_size`) каждого файла онтологии: `domains.yaml`, `repo-mapping.yaml`. Изменился — перечитать оба.
2. Взять `stat` каждого листового каталога `records/sessions/<машина>/<проект>/`. Изменился или новый — перечитать все `*.md` в нём, кроме `*.from-*`. Файл `*.sync-conflict-*` индексировать с `conflict=1`. Исчезнувший каталог — удалить его строки.
3. Взять `stat` файла `records/imports/dor-registry.jsonl`. Изменился — перечитать.
4. md, который не разбирается, попадает в `problems`, а не в `sessions`.

Если версия схемы не совпала или `sqlite3.DatabaseError`: закрыть, `store.remove(place="state")` для базы и её `-journal`, собрать заново. Открывать только внутри `store.managed(index_path, place="state", library="sqlite3")`.

- [ ] **Step 1: Тесты (красные).**
  - `test_rebuild_reads_frontmatter_of_every_machine`.
  - `test_new_file_from_another_machine_is_seen_on_next_connect`: создать каталог `records/sessions/laptop/p/` после первой сборки.
  - `test_yaml_edit_in_place_is_seen`: переписать `domains.yaml` тем же размером другим содержимым и выставить новый mtime через `os.utime`. Индекс видит правку.
  - `test_broken_frontmatter_is_skipped_and_reported`: Review Focus 3.
  - `test_schema_mismatch_rebuilds`: записать в `meta` `schema_version=0`.
  - `test_corrupt_db_rebuilds`: записать в файл базы мусор.
  - `test_sync_conflict_file_is_flagged`.
  - `test_latest_sessions_orders_across_machines_by_updated_at`.
  - Контроль: тест на время. Индекс по 320 сгенерированным md строится быстрее 3 с (бюджет §11.2), повторный `connect` без изменений — быстрее 0,1 с. Пометить `@pytest.mark.slow`.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Красный контроль.** В шаге 1 обновления смотреть mtime каталога `config/` вместо файлов → `test_yaml_edit_in_place_is_seen` FAIL. Вернуть.

- [ ] **Step 4: Случаи песочницы** — `index.rebuild`, `index.connect.refresh`.

- [ ] **Step 5: Ratchet, прогон** (`tests/lifecycle/index tests/governance`), **commit** — `feat(index): derived SQLite index over session md and ontology (#548)`.

### Task 15: Онтология через индекс

**Files:**
- Modify: `h2t_ops/lifecycle/gather/project.py:17-29` (`_get_config_root`, `_load_yaml` → `index.ontology()`)
- Modify: `h2t_ops/lifecycle/detect_project.py:185-194,260-267` (то же)
- Modify: `h2t_ops/lifecycle/apply_registration.py:25,42-148` (`_backup` через `shutil.copy2` → `store.replace(place="config")` копии `*.yaml.bak`; запись YAML → строка из ruamel в `store.replace(place="config")`; `.claude/project-id` → `store.repo(cwd, "h2t-project-register").replace(...)`)
- Modify: `h2t_ops/lifecycle/scaffold_project.py` — только регистрация (остальное в Task 17)
- Modify: `tests/lifecycle/test_apply_registration.py`, `test_detect_project.py`, `tests/lifecycle/gather/test_project.py`, `tests/core/test_init_project_registration.py`

**Interfaces:**
- Consumes: `index.ontology()`, `store.replace(place="config")`, `store.repo`.
- Produces: прежние сигнатуры `identify_project(cwd)`, `detect_project(cwd, config_root=None)`, `apply_registration(...)`. Явный `config_root` читается **напрямую** через `build.load_ontology(config_root)` — функцию сборщика без индекса. Только явный: так тесты и `--config-root` работают на чужом каталоге без пересборки базы машины.

- [ ] **Step 1: Тест единственного читателя (красный).** `tests/governance/test_one_ontology_parser.py`: `grep` по `h2t_ops/` для `yaml.safe_load|YAML\(\)` в связке с `domains.yaml|repo-mapping.yaml`. Разрешены только `lifecycle/index/build.py` (разбор) и `apply_registration.py` (запись через ruamel). Сейчас FAIL: `gather/project.py`, `detect_project.py`.

- [ ] **Step 2: Реализация.** Регистрация: после записи YAML через `store` индекс сам увидит изменение по `stat` при следующем `connect`. Отдельный вызов не нужен, но тест `test_registration_is_visible_to_identify_project_at_once` это проверяет: регистрация, затем сразу `identify_project`.

- [ ] **Step 3: Случаи песочницы** — `register.apply` (временный репо и `config`), `detect.project`.

- [ ] **Step 4: Ratchet, прогон** (`tests/lifecycle tests/core/test_init_project_registration.py tests/governance`), **commit** — `refactor(ontology): one parser in the index builder; registration writes through store (#548)`.

### Task 16: `session-start` — последняя сессия проекта со всех машин

**Files:**
- Modify: `h2t_ops/lifecycle/gather/sessions.py:13-136` (`_session_root`, `_legacy_session_root`, `find_session_files`, `find_latest_session_index` → индекс)
- Modify: `h2t_ops/lifecycle/session_start.py:105-106`
- Modify: `h2t_ops/lifecycle/gather/briefing.py:117,149-193`
- Modify: `tests/lifecycle/gather/test_sessions.py`, `test_sessions_lookup.py`, `test_briefing_previous_session.py`, `tests/lifecycle/test_handoff_gather_round_trip.py`

**Interfaces:**
- Produces: `find_latest_session_index(*repo_names) -> dict | None`. Ключи прежние (`summary_short`, `next_actions`, `artifacts`, `updated_at`, `markdown_path`, `truncated`) плюс `machine`, `branch`, `last_commit`, `here: dict | None` (последняя сессия этой машины, если последняя вообще была на другой). `find_session_files` возвращает пути md из индекса в прежнем порядке «новые первыми».

Брифинг (§5):

```text
### Previous Session  (automata, 2 дня назад)
ветка feat/x, последний коммит a1b2c3d
- Summary: …
- Next: …
⚠ на automata работали позже, чем здесь (macbook-pro-3, 5 дней назад) — git fetch
```

Строка `⚠` выводится, только если `machine != paths.machine_name()` **и** на этой машине есть сессия того же проекта старше. Возраст: «сегодня», «вчера», «N дн. назад» по `updated_at`. Лимит 1800 символов и маркер обрезки сохраняются.

Запасное чтение 4.0.x: если в индексе нет ни одной сессии проекта, а старые каталоги (`paths.legacy("sessions.h2t")`, `paths.legacy("sessions.dor")`) существуют, работает прежняя логика 3.x чтения `latest.json` и md — она переезжает в `gather/sessions_legacy.py`. Тогда брифинг получает строку `ℹ сессии ещё в старом месте — h2t-setup sync перенесёт их`.

- [ ] **Step 1: Тесты (красные).**
  - `test_previous_session_names_machine_and_age`.
  - `test_warning_only_when_other_machine_is_newer`.
  - `test_other_projects_never_appear`.
  - `test_legacy_fallback_before_migration`.
  - Тест полного круга `handoff` → `gather`: `test_handoff_gather_round_trip.py`, дочерний процесс с `HOME`/`USERPROFILE` во временном каталоге. Брифинг содержит `done` только что записанной сессии и имя машины.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Ratchet, прогон** (`tests/lifecycle tests/core tests/hooks tests/governance`), **commit** — `feat(session-start): latest session of this project from any machine (#548)`.

### Task 17: Запись в репо

**Files:**
- Modify: `h2t_ops/core/repo_writers.py` (полный список)
- Modify: `h2t_ops/lifecycle/scaffold_project.py` (15 строк записи), `tools/docs/docs_init.py` (11), `tools/docs/lint.py` (13), `tools/docs/gitignore_hygiene.py` (3), `tools/docs/index_builder.py` (4), `tools/docs/index.py` (1), `tools/docs/retire.py` (2), `tools/docs/new_doc.py` (2), `tools/docs/common.py` (2), `tools/docs/closure.py` (3), `tools/agent_profile/apply_agent_profile.py` (3), `tools/runbook/new_runbook.py` (2), `hooks/plan_closer.py` (1), `hooks/post_git_commit_docs_lint.py` (3), `tools/drawio/generate.py` (4), `tools/drawio/export.py` (1), `tools/creative/assembler.py` (10), `lifecycle/project_audit_report.py` (1)
- Create: `tests/governance/test_repo_writers.py`

**Interfaces:**
- Consumes: `store.repo(root, command)`; `store.replace(..., dest=True)` для drawio и creative (R7).
- Produces: `REPO_WRITERS` с ключами-командами. Список шаблонов замеряется, а не угадывается.

- [ ] **Step 1: Замер.** Для каждой команды из таблицы §7.1 и каждой строки из списка файлов выше: запустить её во временном git-репо (команды и аргументы — из её тестов в `tests/tools`, `tests/lifecycle`, `tests/hooks`) и собрать `git status --porcelain --untracked-files=all` до и после. Итог — таблица `команда → пути`. Вписать её в отчёт `docs/reports/2026-MM-DD-storage-repo-writers.md`: команда, что пишет, правило перезаписи. Отчёт сверяет таблицу §7.1 с фактом. Расхождения вписать в §7.1 спеки.

- [ ] **Step 2: Тест (красный).** `tests/governance/test_repo_writers.py` параметризован по таблице Step 1. Каждая команда идёт во временном репо, под `Recorder` из Task 7, с `guarded=[repo]`. Утверждения:
  - нарушений аудита нет: все записи шли через `store`;
  - каждый изменённый путь подходит под шаблоны `REPO_WRITERS[команда]`.

  На текущем коде FAIL по первому утверждению.

- [ ] **Step 3: Реализация.** Каждая запись → `store.repo(<корень>, "<команда>").<операция>(...)`. Ключевые случаи:

  | Команда | Корень | Особенность |
  |---|---|---|
  | `scaffold_project` | `project_dir` | `.git/info/exclude` (`:490`) — операция `append` для шаблона `.git/info/exclude` |
  | `docs-lint` `git mv` (`lint.py:980,1063`, `retire.py:176`) | репо | `RepoWriter.rename(..., git=True)` |
  | `lint.py:888` | — | `--save <файл>` пишет по пути пользователя: `dest=True` |
  | отчёты `lint.py:1021,1147` | репо, `docs/.artifacts/**` или где укажет замер | — |
  | `post_git_commit_docs_lint.py` | репо, из `git rev-parse --show-toplevel` | хук |
  | `plan_closer` | репо, `docs/superpowers/**` | хук |

  Важно: `plan_closer` сегодня ставит `status: done` спеке при каждом merge, и это неверно до выпуска 4.0.0 (память сессии). Поведение не менять, только маршрут записи.

- [ ] **Step 4: Ratchet, прогон** (`tests/tools tests/lifecycle tests/hooks tests/scaffold tests/governance`), **commit** — `refactor(repo): every write into a user repository goes through the allow-list (#548)`.

### Task 18: Установка, хуки, логи, временные файлы

**Files:**
- Modify: `h2t_ops/setup/state.py` (`run_dir` → `paths.run_dir`; `_atomic_write` → `store.replace(place="run")`)
- Modify: `h2t_ops/setup/sync.py:264-277` (снимок → `store.replace(place="run")` и `store.replace(…place="run")` вместо `shutil.copyfile`), `:499-596` (`claude-pending.json` → `store.replace/remove(place="run")`), `:618-677` (кэш плагинов `_remove_tree` → `store.remove_tree(place="harness")`), `:830` (constraints)
- Modify: `h2t_ops/setup/legacy.py:424-434` (`settings.json` Claude → `store.replace(place="harness")`), `:818-826` (`versions_file`)
- Modify: `h2t_ops/hook_entry.py:48-57`, `hooks/grade_guard.py:34,74-82`, `hooks/plain_guard.py:35,104-112` (логи → `store.append(paths.logs_dir()/…, place="logs")`)
- Modify: `h2t_ops/hooks/gather.py:68-81` (блокировка в `tmp` → `store.replace(place="tmp")`)
- Modify: `h2t_ops/deploy/executor.py:229-231` (`tempfile.TemporaryDirectory` → `store.scratch()`, запись входа → `store.replace(place="tmp")`)
- Modify: `conftest.py` (в наблюдаемые пути добавить `~/.h2t/logs`)
- Create: `tests/setup/test_bootstrap_round_trip.py`

**Interfaces:**
- Consumes: `paths.run_dir`, `paths.dir_of("harness")`, `store.*`.
- Produces: тест полного круга бутстрапа (§7.3). `hooks/run` запускается против `install.env`, который записал `state.commit` через `paths.run_dir()`.

- [ ] **Step 1: Тест полного круга (красный по замыслу — на текущем коде он зелёный, поэтому красный прогон делается порчей).**

```python
# tests/setup/test_bootstrap_round_trip.py
import os
import subprocess
import sys
from pathlib import Path

import pytest

from h2t_ops.setup import state

RUN = Path(__file__).resolve().parents[2] / "plugins" / "h2t-core" / "hooks" / "run"


@pytest.mark.skipif(sys.platform == "win32", reason="covered by tests/hooks/test_hooks_run.py on Git Bash")
def test_hooks_run_reads_what_state_wrote(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "elsewhere"))  # must not move run/
    hook = tmp_path / "bin" / "h2t-hook"
    hook.parent.mkdir()
    hook.write_text("#!/bin/sh\necho HOOK-RAN \"$@\"\n")
    hook.chmod(0o755)
    version = (RUN.parent.parent / "release.env").read_text().split("VERSION=")[1].split()[0]
    state.commit(state.Install(version=version, generation="g1", tool_root=str(tmp_path),
                               entrypoints={"h2t-hook": str(hook)}))
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(RUN.parent.parent)}
    out = subprocess.run(["bash", str(RUN), "session-start"], input="{}", text=True,
                         capture_output=True, env=env, timeout=30)
    assert "HOOK-RAN session-start" in out.stdout, out.stderr
```

Имя хука и аргументы `hooks/run` сверить с `tests/hooks/test_hooks_run.py:80`. Порча для красного прогона: в `paths.run_dir()` вернуть `root() / "run"`. Тест → FAIL: `install.env` ушёл в `H2T_PATH_ROOT`, а bash читает `$HOME/.h2t/run`. Вернуть.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Случаи песочницы** — `setup.state.commit`, `setup.sync.snapshot` (подставные `uv` и `claude` из `tests/setup/test_sync_converges.py`), `hook.log-failure`, `hook.gather.lock`, `deploy.executor.input`.

- [ ] **Step 4: Ratchet, прогон** (`tests/setup tests/hooks tests/deploy tests/core tests/governance`), **commit** — `refactor(setup,hooks): install state, snapshots, logs and temp files through store (#548)`.

### Task 19: `h2t-ops paths` и `h2t-ops index`

**Files:**
- Create: `h2t_ops/core/paths_cli.py`
- Modify: `h2t_ops/cli.py:20-29` (`sub.add_parser("paths")`, `sub.add_parser("index")`), `:165-183` (ветки `dispatch` перед `_MIGRATED`)
- Create: `tests/cli/test_paths_cli.py`

**Interfaces:**
- Produces:
  - `h2t-ops paths list [--json]`. По строке на место: `id`, путь, `kind`, `sync`, существует ли и источник (`env`, `alias`, `paths.yaml`, `default`).
  - `h2t-ops paths get <id>`. Принимает id места, `secret:<провайдер>` (путь `shared/<провайдер>.env`; `secret:google.token` → `google.token.json`, `secret:google.client` → `google.client.json`) или `data:<имя>`. Печатает только путь.
  - `h2t-ops paths set <место> <путь>`. Только `lake`, `inbox`, `vault`, `kb`. Проверка `paths_config()` на итоговом документе до записи. Запись через ruamel с сохранением комментариев, `store.replace(place="config")`.
  - `h2t-ops index rebuild [--json]`, `h2t-ops index query --project <id> [--json]`.
  - Коды выхода: ошибка разбора аргументов — 2, неизвестное место — 2, пересечение мест — 3.

- [ ] **Step 1: Тесты (красные)** — по команде. В `paths set` пересечение не меняет файл (сравнить байты до и после). Комментарий пользователя в `paths.yaml` сохраняется.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Случаи песочницы** — `paths.set`, `index.rebuild`.

- [ ] **Step 4: Ratchet, прогон** (`tests/cli tests/governance`), **commit** — `feat(cli): h2t-ops paths and index (#548)`.


## Фаза D — `doctor` и миграция

### Task 20: `doctor` — проверка состояния хранения

**Files:**
- Create: `h2t_ops/setup/storage_doctor.py`
- Modify: `h2t_ops/cli.py:34` (`_doctor` печатает блок `storage:` после `secrets:`)
- Create: `tests/setup/test_storage_doctor.py`

**Interfaces:**
- Produces: `Finding(level: str, code: str, text: str)`, где `level` — `"error"|"warn"|"info"`; `check() -> list[Finding]`; `sync_status(place_id: str) -> tuple[str, str]`, где статус — `"confirmed"|"declared"|"unknown"`, а вторая строка — признак.

Проверки §7.4, по коду:

| code | level | Как проверяется |
|---|---|---|
| `secret-tracked` | error | `git -C <config> ls-files` → любой путь под `secrets/`; затем по каждому отслеживаемому файлу `git show :<путь>` → строки `KEY=непусто`, где `providers.provider_of_key(KEY)` не `None`. Печатаются путь и имя ключа |
| `local-in-sync` | error | для `secrets.local`, `state`, `logs`, `run/rollback` — `realpath`, затем вверх по дереву `.stfolder`/`.dropbox` или объявление в `paths.yaml: sync:` |
| `legacy-only` | warn | данные есть в `paths.legacy(...)`, а в новом месте нет: по одному на класс |
| `sync-conflict` | warn | `*.sync-conflict-*` в `records/`, `secrets/`, `config/` |
| `unknown-root-entry` | warn | имя в корне `~/.h2t`, которого нет среди мест и `layout.json` |
| `index-schema` | warn | версия схемы в `meta` ≠ `SCHEMA_VERSION` |
| `old-env-name` | warn | `paths.alias_in_use()` |
| `place-missing` | warn | место из `paths.yaml` не существует |
| `place-unset` | info | `lake`, `inbox` не заданы |
| `google-mirror-newer` | warn | старый `tokens.json` новее главной копии и отличается по хэшу |
| `from-copies` | info | файлы `*.from-*` в `secrets/shared`: имя, ключ, `sha256[:12]` |
| `windows-perms` | info | на Windows: «права не проверяются (ACL профиля)» — по ветке Task 1 |
| `perms` | error | на POSIX: файл в `secrets/**` не `0600` или каталог не `0700` |

`sync_status` отвечает «подтверждено» (найден маркер), «объявлено» (только `paths.yaml`) или «неизвестно». Строки вывода:

```text
storage: layout 1, root ~/.h2t
storage: sync records = confirmed (.stfolder at ~/.h2t/records), secrets.shared = declared (syncthing), secrets.local = unknown
storage: ERROR local-in-sync: ~/.h2t/state lies inside a Syncthing folder (~/.h2t/.stfolder)
storage: warn legacy-only: sessions are only in ~/.dor/sessions — h2t-setup sync moves them
```

- [ ] **Step 1: Тесты (красные)** — по одному на `code`. Каждый строит минимальное состояние во временном `HOME`, включая git-репо `config` с отслеживаемым `secrets/x.env` и ключом `EXA_API_KEY=fake`. Отдельный тест `test_report_never_prints_a_value`: значение `fake-SECRET-VALUE-123` из всех файлов не встречается в выводе.

- [ ] **Step 2: Реализация.** `doctor` по-прежнему выходит с 0 (#451).

- [ ] **Step 3: Прогон** (`tests/setup tests/test_setup_doctor_checks.py`), **commit** — `feat(doctor): storage checks — tracked secrets, sync placement, legacy data, conflicts (#548)`.

### Task 21: Движок миграции — журнал, фазы, откат

**Files:**
- Create: `h2t_ops/setup/layout/__init__.py`, `journal.py`, `engine.py`, `rollback.py`
- Modify: `h2t_ops/setup/cli.py:21-106` (флаги `sync`: `--machine NAME`, `--rollback-layout`, `--sync-paused`)
- Modify: `h2t_ops/setup/sync.py:879-951` (`run`: после шага 7 вызов `layout.engine.migrate(report, machine=…)`; `dev_sync` `:814` — тот же вызов)
- Create: `tests/setup/layout/test_engine.py`

**Interfaces:**
- Produces:

```python
# journal.py
class Journal:
    def __init__(self, run_id: str): ...        # run/rollback/<run_id>/journal.jsonl, dir 0700
    def created(self, path: Path, source: str, sha256: str) -> None
    def phase_done(self, phase: str) -> None
    def done_phases(self) -> set[str]
    def entries(self) -> list[dict]
    @staticmethod
    def latest() -> "Journal | None"             # unfinished first, else the newest finished

# engine.py
PHASES: tuple[str, ...] = ("snapshot", "secrets", "sessions", "telegram", "evals", "activity",
                           "cursors", "registry", "data", "paths_yaml", "index", "verify", "markers")
def migrate(report, *, machine: str | None = None) -> None
def put(journal: Journal, target: Path, data: bytes, *, place: str, source: str,
        from_name: str | None = None) -> Path     # create, or keep both on a different hash

# rollback.py
def rollback(*, sync_paused: bool) -> dict        # {"removed": [...], "kept": [...], "layout": prev}
```

Правила движка:

- `migrate` ничего не делает, если `layout.json` уже `1` и незавершённого журнала нет. Тогда в отчёт идёт `notes += ["layout 1: already"]`.
- Незавершённый журнал продолжается с первой фазы, которой нет в `done_phases()`.
- Каждая фаза — функция `phase_<имя>(ctx)`, где `ctx` содержит `journal`, `machine`, `baseline`. Ошибка фазы → `report.failed.append(("layout 1: <фаза>", <подсказка>))`, остальные фазы не идут, журнал остаётся незавершённым.
- `put(...)` реализует правило «тот же хэш — тот же файл, другой — сохраняются оба»:
  - цели нет: `store.create`, затем `journal.created(...)`;
  - цель есть, хэш тот же: ничего;
  - хэш другой: `store.create(target.with_name(f"{target.name}.from-{source}"))`, затем `journal.created`; если и такой файл уже есть с тем же хэшем — ничего.
- Фаза `snapshot` проверяет свободное место (`shutil.disk_usage(paths.root().parent).free` больше суммы размеров источников × 2) и имя машины (§5):
  - в `sessions.h2t` или `sessions.dor` есть подпапки, но нет подпапки `paths.machine_name()`, и `--machine` не задан → фаза падает с подсказкой `h2t-setup sync --machine <имя>`;
  - `--machine` задан → `store.replace(state/machine.json, {"name": …})`.
- Фаза `verify` — Task 22.
- Фаза `markers` пишет `MOVED-TO.txt` под `store.migrating()` в каждый старый каталог, из которого что-то перенесено (текст: новое место и дата). Затем `layout.json = {"layout": 1, "machine": …, "migrated_at": …, "journal": run_id}` через `store.replace(place=…)`.
  - `layout.json` лежит в корне `root()`, вне классов. Для него вводится место вида `file`: `Place("layout", "file", "run", "never")`. `paths.dir_of("layout")` возвращает `layout_file()`, `store._PACKAGE` получает `"layout"`, а классификация совпадает по точному пути. Строка в блок `yaml places` спеки: `- {id: layout, kind: file, class: run, sync: never}`. Это правка §3 спеки внутри этой задачи, иначе тест таблицы мест красный.
- Каталоги `run/rollback/<id>` завершённых миграций старше 30 дней `migrate` удаляет при следующем запуске: `store.remove_tree(place="run")`. Незавершённые не трогаются никогда (§7.5).
- `rollback` выполняется внутри `store.migrating()`: только так `remove(..., journal=True)` проходит для `MOVED-TO.txt` в старых каталогах.
- `rollback(sync_paused=False)` → `UsageError` с текстом §7.5 про паузу синхронизации. При `True`: для каждой строки `created` из журнала — если текущий хэш совпал, `store.remove(..., journal=True)`, иначе путь идёт в `kept`. Затем `layout.json` возвращается к прежнему значению: оно записано в журнал фазой `snapshot`. `MOVED-TO.txt` удаляются тем же способом: они тоже в журнале.

- [ ] **Step 1: Тесты движка (красные)**, на подставных фазах:
  - `test_phases_run_in_order_and_mark_done`.
  - `test_interrupted_migration_resumes_without_duplicates` (Review Focus 2): подставная фаза `sessions` падает с `KeyboardInterrupt` после первого `put`; второй `migrate` начинает с `sessions`, файлов `*.from-*` нет.
  - `test_put_keeps_both_on_different_hash`.
  - `test_rollback_removes_only_unchanged_journal_files`: файл из журнала изменён после миграции → остаётся; сессия, записанная после миграции, остаётся (§12).
  - `test_rollback_requires_sync_paused`.
  - `test_machine_name_ambiguity_stops`: подпапки `automata` и `macbook-pro-3`, hostname `other` → фаза падает и называет обе подпапки в подсказке.
  - `test_rollback_dir_is_0700` (`skipif win32`).
  - `test_old_finished_rollback_dirs_are_pruned_after_30_days`: незавершённый журнал того же возраста остаётся.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Подключение к `sync`.** В `sync.run` после шага 7: если `cli_ok`, вызвать `layout.engine.migrate(report, machine=ns.machine)`. Флаг `--rollback-layout` обходит шаги 3–8 и сразу вызывает `rollback`. Тест в `tests/setup/test_sync_converges.py`: прогон `sync.run` на подставных `uv`/`claude` создаёт `layout.json`, а повторный прогон оставляет `notes` с `layout 1: already`.

- [ ] **Step 4: Прогон** (`tests/setup tests/governance`), **commit** — `feat(setup): layout migration engine with a journal, resume and rollback (#548)`.

### Task 22: Фаза секретов и сверка

**Files:**
- Create: `h2t_ops/setup/layout/secrets_phase.py`, `h2t_ops/setup/layout/verify.py`
- Create: `tests/setup/layout/test_secrets_phase.py`

**Interfaces:**
- Consumes: `secrets.legacy_sources`, `secrets.parse_env`, `providers.*`, `engine.put`, `paths.legacy`.
- Produces: `phase_secrets(ctx)`, `baseline() -> set[tuple[str, str]]`, `verify_secrets(baseline) -> list[str]` (пустой список — сверка прошла).

Источники и старшинство (§8 п. 2, R6):

```python
# secrets_phase.py
def ladder() -> list[tuple[str, Path]]:
    """Senior first. Independent of H2T_SECRETS_FILE except that its file is one more source."""
    out = []
    override = paths.secrets_override()
    if override is not None:
        out.append(("secretsfile", override))
    d = paths.legacy("secrets.h2t")
    out.append(("h2t-config", d / "secrets.env"))
    if d.is_dir():
        out += [(f"h2t-config-{p.stem}", p) for p in sorted(d.glob("*.env"), key=lambda p: p.name)
                if p.name != "secrets.env"]
    out += [("dor-secrets", paths.legacy("secrets.dor")), ("dor", paths.legacy("secrets.dor_old"))]
    return [(name, p) for name, p in out if p.is_file()]


def evals_ladder(lad):
    """H2T_EVALS_*: ~/.dor/secrets.env first — the only file evals read in 3.x."""
    return sorted(lad, key=lambda kv: kv[0] != "dor")


def plan_env() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]], list[Path]]:
    """-> (winners per target file, losers per target file per source, foreign files to copy)."""
    winners: dict[str, dict[str, str]] = {}
    losers: dict[str, dict[str, dict[str, str]]] = {}
    foreign: list[Path] = []
    existing = {p.name: secrets.parse_env(p.read_text(encoding="utf-8"))
                for p in paths.secrets_shared().glob("*.env")} if paths.secrets_shared().is_dir() else {}
    lad = ladder()
    for src, path in lad:
        stem = path.stem
        if path.parent == paths.legacy("secrets.h2t") and stem != "secrets" \
                and not providers.is_package_provider(stem):
            foreign.append(path)
    def target_of(key):
        prov = providers.provider_of_key(key)
        return f"{prov}.env" if prov else "other.env"
    sources = {src: secrets.parse_env(p.read_text(encoding="utf-8")) for src, p in lad}
    foreign_srcs = {src for src, p in lad if p in foreign}
    keys = {k for vals in sources.values() for k in vals}
    for key in sorted(keys):
        tgt = target_of(key)
        order = evals_ladder(lad) if key.startswith("H2T_EVALS_") else lad
        candidates = [(src, sources[src][key]) for src, _ in order if key in sources[src]]
        if tgt == "other.env":
            candidates = [c for c in candidates if c[0] not in foreign_srcs]
            if not candidates:
                continue
        if key in existing.get(tgt, {}):
            win_src, win_val = "existing", existing[tgt][key]
        else:
            win_src, win_val = candidates[0]
        winners.setdefault(tgt, {})[key] = win_val
        for src, val in candidates:
            if src != win_src and val != win_val:
                losers.setdefault(tgt, {}).setdefault(src, {})[key] = val
    return winners, losers, foreign
```

Дальше фаза делает следующее.

1. Notion. `paths.legacy("notion.token")` даёт кандидата `NOTION_API_TOKEN` с источником `notion-token`, младшего всех env-файлов.
2. Telegram. `config.json` → `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` в `telegram.env`, источник `telegram-config`. Сессия → `local/telegram.session`, auth-state → `local/telegram.auth-state.json`: байтовые копии через `put`, права 0600.
3. Google. Клиент: `google.store/credentials.json` > `google.gmail/credentials.json` > `google.dor`. Токен: `google.store/tokens.json` > `google.gmail/token.json`. Байтовые копии через `put`. Проигравшие идут в `google.client.json.from-<источник>`.
4. Победители пишутся в файл провайдера. Если файла нет, `put` создаёт его. Если файл есть, но в нём не хватает ключей (новые ключи из старых мест), он пишется через `store.replace` с объединением. Существующие значения не трогаются: они старшие. Прежнее содержимое (хэш) записывается в журнал.
5. Проигравшие пишутся в `<цель>.from-<источник>` через `put`.
6. Чужие файлы копируются `put` под своим именем.

Сверка (`verify.py`, фаза `verify`, §8 п. 6):

```python
def pairs(env: dict[str, str]) -> set[tuple[str, str]]:
    return {(k, hashlib.sha256(v.encode()).hexdigest()) for k, v in env.items()}


def baseline() -> set[tuple[str, str]]:
    """Taken BEFORE any write: every old source under translated names, plus existing new
    files and their .from- copies."""
    out: set[tuple[str, str]] = set()
    for _, p in secrets_phase.ladder():
        out |= pairs(secrets.parse_env(p.read_text(encoding="utf-8")))
    out |= pairs(secrets_phase.translated_extras())   # notion token, telegram api_id/hash
    shared = paths.secrets_shared()
    if shared.is_dir():
        for p in shared.iterdir():
            if p.name.endswith(".env") or ".env.from-" in p.name:
                out |= pairs(secrets.parse_env(p.read_text(encoding="utf-8")))
    return out


def verify_secrets(before: set[tuple[str, str]]) -> list[str]:
    after: set[tuple[str, str]] = set()
    for p in paths.secrets_shared().iterdir():
        if p.name.endswith(".env") or ".env.from-" in p.name:
            after |= pairs(secrets.parse_env(p.read_text(encoding="utf-8")))
    problems = [f"lost {k} (sha256 {h[:12]})" for k, h in sorted(before - after)]
    problems += [f"appeared {k} (sha256 {h[:12]})" for k, h in sorted(after - before)]
    winners, _, _ = secrets_phase.plan_env()
    for tgt, vals in winners.items():
        got = secrets.parse_env((paths.secrets_shared() / tgt).read_text(encoding="utf-8"))
        problems += [f"{tgt}: {k} is not the senior value" for k, v in vals.items() if got.get(k) != v]
    return problems
```

`baseline()` снимается в фазе `snapshot` и сохраняется в журнал как список пар `(ключ, хэш)`; значения туда не попадают. Байтовые копии (JSON Google, сессия Telegram) сверяются по `sha256` файла с источником.

- [ ] **Step 1: Тесты (красные).**
  - `test_full_precedence_order`: один и тот же ключ `MEETGEEK_API_KEY` в семи источниках с разными значениями; победитель — по порядку §8 п. 2; шесть проигравших — в `meetgeek.env.from-*`.
  - `test_evals_prefers_dor_secrets_env`.
  - `test_existing_new_file_wins_on_rerun`: пользователь поменял ключ в новом файле, в старых источниках этого значения нет. Повторный `migrate` значение не трогает, а сверка проходит.
  - `test_secrets_file_override_is_one_more_source`: при заданном `H2T_SECRETS_FILE` остальные места всё равно обойдены.
  - `test_unknown_keys_go_to_other_env`.
  - `test_foreign_env_is_copied_whole_and_feeds_provider_keys` (R6).
  - `test_telegram_and_notion_are_translated`.
  - `test_verify_catches_a_lost_value`: порча — после фазы удалить строку из `exa.env`; `verify_secrets` возвращает `lost EXA_API_KEY`.
  - `test_google_byte_copies_verified_by_hash`.
  - `test_no_value_in_journal_or_report`: значение `fake-SECRET-xyz` не встречается в `journal.jsonl`, в `report.as_dict()` и в `logs/writes.jsonl`.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Красный контроль сверки.** В `verify_secrets` удалить строку `problems = [f"lost …"]` → `test_verify_catches_a_lost_value` FAIL. Вернуть.

- [ ] **Step 4: Прогон** (`tests/setup/layout tests/governance`), **commit** — `feat(setup): layout 1 secrets phase with full precedence and value-set verification (#548)`.

### Task 23: Остальные фазы `layout 1`

**Files:**
- Create: `h2t_ops/setup/layout/phases.py`
- Create: `tests/setup/layout/test_phases.py`

**Interfaces:**
- Consumes: `engine.put`, `session_record.render/parse`, `index.rebuild`, `paths.*`.
- Produces: `phase_sessions`, `phase_telegram` (только `dialogs_bootstrapped` → `state/telegram/`; сессия и auth-state ушли в фазу секретов), `phase_evals`, `phase_activity`, `phase_cursors`, `phase_registry`, `phase_data`, `phase_paths_yaml`, `phase_index`.

| Фаза | Источник | Куда | Проверка |
|---|---|---|---|
| `sessions` | `legacy("sessions.h2t")/<машина>/**/*.md`, `legacy("sessions.dor")/<машина>/**/*.md`; других машин — **нет** | `records/sessions/<машина>/<проект>/<stem>.md` | тело после frontmatter побайтно равно источнику; `migrated_from: <путь>@<sha256>` |
| `telegram` | `legacy("telegram")/dialogs_bootstrapped` | `state/telegram/dialogs_bootstrapped` | хэш |
| `evals` | `legacy("evals")/<скилл>/sessions/*.json`; `legacy("evals")/.h2t_evals_spool.db` (+ `-wal`, `-shm`, если есть) | `records/evals/<машина>/<скилл>/<файл>`; `state/evals-spool.sqlite` | хэш |
| `activity` | `legacy("activity")/spool.jsonl` | `records/activity/<машина>.jsonl` | хэш |
| `cursors` | `legacy("lake.dor")/_cursors/{granola,meetgeek}.json` | `state/cursors/<провайдер>.json` | хэш |
| `registry` | `legacy("registry.dor")` | `records/imports/dor-registry.jsonl` | хэш |
| `data` | `legacy("research")/**`, `legacy("creative")/**` (R9) | `data/research/**`, `data/creative/profiles/**` | хэш |
| `paths_yaml` | — (R2) | `config/paths.yaml`, только если его нет: `lake`, `vault`, `inbox` для существующих `legacy("lake.dor")`, `legacy("vault.dor")`, `legacy("downloads")` | `paths_config()` разбирает файл без ошибки |
| `index` | — | `index.rebuild()` | число сессий в индексе = числу md фазы `sessions` |

Frontmatter перенесённой сессии собирается так.

1. `session_id` = `stem`; `project` = имя каталога; `machine` = `ctx.machine`.
2. Из `latest.json` того же каталога, только если его `session_id == stem`, берутся `summary_short` → `done`, `next_actions` → `remains`, `updated_at`, `artifacts`.
3. Из заголовка md (`**Date:**`, `**Domain:**`, `**Project:**`) берутся `date`, `domain`. При расхождении с каталогом `project` берётся из каталога.
4. Если `updated_at` нет, он равен `date` + `T00:00:00Z`, а если нет и даты — mtime файла.

Один и тот же md может лежать и в `~/.h2t/sessions`, и в `~/.dor/sessions`. Если тела одинаковы, это один файл, по правилу `put`. Если тела разные, создаётся `<stem>.from-dor.md` (индекс его пропускает), и `doctor` показывает его как `from-copies`.

- [ ] **Step 1: Тесты (красные)** — по фазе. Сквозной `test_layout1_end_to_end_on_a_3x_home`:
  - фикстура строит `HOME` с раскладкой 3.x по описанию §1: две машины в `~/.dor/sessions`, одна в `~/.h2t/sessions`, Telegram, Google, evals, activity, курсоры, registry, research, creative;
  - `migrate` с `machine="macbook-pro-3"`;
  - сессии `automata` не скопированы;
  - `layout.json == 1`;
  - `doctor` без `error`;
  - `MOVED-TO.txt` лежит в каждом старом каталоге с данными;
  - старые файлы побайтно целы: хэши до и после совпадают;
  - откат удаляет всё созданное, и хэши старых файлов снова совпадают.

  Контрольный тест (§12) — `test_old_dirs_renamed_connectors_still_work`. После миграции старые каталоги переименовываются в `*.gone`. Затем `secrets.get` для каждого провайдера, `google_auth.resolve_google_credentials` (на подставном рефреше) и `TelegramClientAdapter()._load_config()` по-прежнему находят значения.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Прогон** (`tests/setup tests/governance tests/lifecycle`), **commit** — `feat(setup): layout 1 phases — sessions, telegram, evals, activity, cursors, registry, data (#548)`.

### Task 24: Сторожа на ноль

**Files:**
- Modify: `tests/governance/test_storage_ratchets.py` (все потолки 0)
- Modify: `tests/governance/sandbox_cases.py` (полнота)
- Create: `tests/governance/test_sandbox_covers_every_writer.py`

**Interfaces:** —

- [ ] **Step 1: Потолки.** `.venv/bin/python scripts/storage_map.py`. Каждая строка, которая ещё не равна 0, — недоделка одной из задач 8–19: найти по `hits(...)`, перевести, вписать 0. Строки, которые сканер ловит ложно, переписываются так, чтобы сканер их не видел. Обычно это строка документации в docstring вида `"~/.dor/..."`: перефразировать или собрать из `paths`. Добавлять файлы в `ALLOWED` нельзя.

- [ ] **Step 2: Полнота песочницы (красный).** Тест читает список модулей, у которых сканер на `main` 70214177 нашёл записи: 46 файлов, список зашит в тест из инвентаря плана. Затем проверяет, что для каждого есть хотя бы один `Case`, у которого в `id` есть префикс подсистемы. Запуск сразу красный, если какой-то модуль без случая. Дописать недостающие случаи.

- [ ] **Step 3: Полный прогон.** `.venv/bin/pytest tests/ -q`, `.venv/bin/pytest lib/ -q`, `uvx ruff@0.16.4 check plugins/ lib/ h2t_ops/ tests/ scripts/`, `.venv/bin/pytest -m slow tests/lifecycle/index -q`. Всё зелёное. Строки `ERROR: the suite wrote into the real home` нет.

- [ ] **Step 4: Вопрос «что сторож не видит»** (verification.md). Три `grep` по всему дереву, не только по `h2t_ops/`:
  - `grep -rn "Path.home()\|expanduser" plugins/ lib/ scripts/ --include=*.py`;
  - `grep -rn "\.dor/\|\.config/" plugins/ --include=*.md`;
  - `grep -rn "open(" h2t_ops/ --include=*.py | grep -v "store.py\|secrets.py"`.

  Найденное разобрать: исправить или записать причину в отчёт задачи 25.

- [ ] **Step 5: Commit** — `test(governance): ratchets at zero, sandbox covers every writer (#548)`.

## Фаза R — документация, перенос, выпуск

### Task 25: Документация и issues в POS и rejuve

**Files:**
- Modify: `README.md:119-124` (раздел «Known Limitations» → «Где хранятся данные»: дерево §3, `paths.yaml`, `h2t-setup sync`, откат)
- Modify: `CHANGELOG.md:85-88` (раздел 4.0.0: строка про #548 → описание раскладки и миграции; строка про `drive download` по умолчанию в `inbox`; про `latest.json`; про псевдонимы переменных)
- Modify: `plugins/**/SKILL.md` и `references/*.md` — 22 упоминания старых мест по замеру плана (`grep -rn "latest.json\|secrets.env\|\.config/telegram\|google-calendar-mcp" plugins/ --include=*.md`) и всё найденное в Task 24 Step 4
- Modify: `.claude/rules/external-dependencies.md` (переменные `H2T_KB_ROOT`, `H2T_SESSION_ROOT`, `H2T_ACTIVITY_SPOOL`, `H2T_SECRETS_FILE` → `H2T_PATH_*` и псевдонимы)
- Modify: `CLAUDE.md` (строка про `~/.h2t/config/secrets` в описании контекста, если есть)
- Create: тексты issues в scratchpad: `issue-pos.md`, `issue-rejuve.md`

- [ ] **Step 1: Тексты.** Каждое упоминание старого места в скилле заменяется командой `h2t-ops paths get <id>`, а не новым путём. Так текст не устареет при следующем переносе.

- [ ] **Step 2: Тест ссылок на старые места в скиллах.** `tests/governance/test_skills_name_no_legacy_paths.py`: `grep` по `plugins/**/*.md` для `~/.dor/`, `~/.config/(google-calendar-mcp|gmail|notion|telegram)`, `~/.h2t/sessions`, `~/.h2t/config/secrets` даёт 0. Исключение — строки, которые описывают миграцию: они содержат слово `legacy` или `3.x`.

- [ ] **Step 3: Issues — тексты.** Для POS: таблица §9, ещё три пункта.
  - `mentions_cache.json` с #403 никто не пишет; упоминания брать из `h2t-ops telegram mentions --json`.
  - На немигрированной машине `tokens.json` перестаёт обновляться access-токеном, на мигрированной обновляется зеркалом только при новом refresh-токене. POS должен обновлять access-токен сам (`app/auth/tokens.py` уже так делает — проверить запросы к Gmail после истечения).
  - Контракт: `h2t-ops paths get secret:google.token`; старый путь поддерживается до 4.1.

  Для rejuve: ключи — в `~/.h2t/secrets/shared/<провайдер>.env`, путь даёт `h2t-ops paths get secret:<провайдер>`; `~/.h2t/config/secrets/*.env` остаются копиями до 4.1.

- [ ] **Step 4: [владелец] Завести issues.** Показать владельцу оба текста. По его «да» выполнить `gh issue create --repo lichtpfad/POS --title "pos: Read the Google token through h2t-ops paths" --body-file …` и то же для rejuve (точный slug репо rejuve спросить у владельца). Перед этим `gh issue list --search` на дубликаты.

- [ ] **Step 5: Commit** — `docs(storage): layout, migration and contracts in README, CHANGELOG and skills (#548)`.

### Task 26: Живой перенос двух машин и приёмка **[владелец]**

Порядок §8 «Порядок у автора»; ветка проб Task 1 (11.1) может поменять порядок шагов 2–3.

- [ ] **Step 1: Мак, перед переносом.** `h2t-ops doctor` → сохранить вывод. Хэш-манифест старых мест: `find ~/.dor ~/.config/{google-calendar-mcp,gmail,notion,telegram} ~/.h2t/{sessions,activity,evals,research,creative,config/secrets} -type f -exec shasum -a 256 {} +`, вывод только в scratchpad, значения файлов не печатаются.

- [ ] **Step 2: Мак, перенос.** `h2t-setup dev-sync` (editable из ветки), затем `h2t-setup sync`. Если требует имя машины — `--machine macbook-pro-3`. Проверка:
  - `h2t-ops doctor` без `ERROR`;
  - `h2t-ops paths list`;
  - `h2t-ops index query --project h2t-skills`;
  - хэш-манифест старых мест не изменился (сравнить `diff` двух файлов манифеста, без вывода значений).

- [ ] **Step 3: Мак, Syncthing [владелец].** Владелец добавляет в Syncthing папки `~/.h2t/secrets/shared` и `~/.h2t/records`. `doctor` → синхронизация `records`, `secrets.shared` = `confirmed`.

- [ ] **Step 4: Ноутбук [владелец].** Тот же шаг 2 на ноутбуке (через канал `3dwalker`, как Task 1). Сессии ноутбука с мая приезжают на мак: `h2t-ops index query --project <id>` на маке показывает машину `automata`.

- [ ] **Step 5: Приёмка §12** — по пункту, с выводом:
  - [ ] `session-start` в одном репо на обеих машинах показывает последнюю сессию проекта с именем машины, чужих проектов нет, предупреждение — при расхождении.
  - [ ] `doctor` чистый, синхронизация «подтверждено» или «объявлено».
  - [ ] каждый коннектор: `h2t-ops <коннектор> --help` и одна безопасная команда чтения (`notion search`, `calendar events --days 1`, `gmail search --limit 1`, `telegram dialogs --limit 1`, `granola list --limit 1`, `meetgeek meetings --limit 1`, `research` — `doctor`), ключи сверены по хэшу с манифестом шага 1.
  - [ ] контроль: старые каталоги переименованы (`mv ~/.config/telegram ~/.config/telegram.gone` и т.д.) — коннекторы работают; вернуть имена.
  - [ ] сторожа §7.3 зелёные на CI (ubuntu и windows).
  - [ ] откат на тестовом `HOME` (не на живом): `HOME=$SP/home h2t-setup sync`, сессия после миграции, `--rollback-layout --sync-paused` — сессия осталась.
  - [ ] новый пользователь: `HOME=$SP/empty h2t-setup sync` → нет `~/.dor`, нет `~/.config/<программа>`.

- [ ] **Step 6: Отчёт** — `docs/reports/2026-MM-DD-storage-acceptance.md`; commit.

### Task 27: Выпуск 4.0.0 **[владелец]**

Выпуск — задачи 18–19 плана подсистемы 1 (`docs/superpowers/plans/2026-10-16-package-architecture.md`). Этот план добавляет к ним одно условие: Task 26 завершена.

- [ ] **Step 1: PR этой подсистемы → `main`.** Ветка от `main`, все коммиты задач 2–25. Описание PR — список задач и вывод Task 24 Step 3. Merge — по слову владельца. Предупреждение из памяти: хук `plan_closer` после merge поставит этому плану и спеке `status: done` — откатить, пока 4.0.0 не выпущен.
- [ ] **Step 2: Задача 18 плана подсистемы 1** (`release.py prepare 4.0.0` → PR → merge → tag `v4.0.0` → workflow выпуска).
- [ ] **Step 3: Задача 19 плана подсистемы 1** (живая приёмка выпуска) + обновить трекер #541 и закрыть #548 (`gh issue close 548 --comment "Fixed in <sha>"`).
