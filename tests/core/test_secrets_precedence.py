"""Pin the order in which h2t_ops.core.secrets looks for a key (#541).

Each case runs the loader in a child interpreter whose HOME and USERPROFILE point at an
empty tmp dir, so nothing of the developer's home can answer. In 4.0 the 3.x ladder is the
fallback behind secrets/shared (#548); H2T_SECRETS_FILE is not read (R5). Values are fake and
compared by sha256[:8]; they are never printed.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
KEY = "H2T_PIN_DUMMY_NAME"
NOTION = "NOTION_API_TOKEN"

CHILD = """
import hashlib, os, sys
from pathlib import Path
from h2t_ops.core import secrets
explicit = os.environ.pop("PIN_EXPLICIT", "")
if sys.argv[1] == "notion":
    val = secrets.resolve_notion_token()
    name = "NOTION_API_TOKEN"
else:
    secrets.load_secrets(Path(explicit) if explicit else None)
    val = os.environ.get("H2T_PIN_DUMMY_NAME", "")
print(hashlib.sha256(val.encode()).hexdigest()[:8])
"""


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def put(path: Path, label: str, key: str = KEY) -> str:
    """Write `key=<fake value>` to path; return the fake value."""
    value = f"fake-{label}-{path.name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{key}={value}\n", encoding="utf-8")
    return value


def run(home: Path, *, env: dict[str, str] | None = None, mode: str = "load") -> str:
    clean = {
        k: v
        for k, v in os.environ.items()
        if k not in {KEY, NOTION, "H2T_SECRETS_FILE", "PIN_EXPLICIT", "PYTHONPATH"}
        and not k.startswith("H2T_PATH_")
    }
    clean.update(HOME=str(home), USERPROFILE=str(home), PYTHONPATH=str(REPO))
    clean.update(env or {})
    out = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, mode],
        env=clean, cwd=home, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


def places(home: Path) -> dict[str, Path]:
    cfg = home / ".h2t" / "config" / "secrets"
    return {
        "new": home / ".h2t" / "secrets" / "shared" / "other.env",
        "documented": cfg / "secrets.env",
        "dir_a": cfg / "a-provider.env",
        "dir_z": cfg / "z-provider.env",
        "shared": home / ".dor" / "secrets" / "secrets.env",
        "legacy": home / ".dor" / "secrets.env",
    }


def populate(home: Path, names: list[str]) -> dict[str, str]:
    p = places(home)
    return {n: put(p[n], n) for n in names}


def test_control_child_sees_the_tmp_home(home: Path) -> None:
    """Positive control: the only way a value can arrive is through the patched HOME."""
    home.mkdir()
    v = populate(home, ["legacy"])
    assert run(home) == h(v["legacy"])
    empty = home.parent / "empty-home"
    empty.mkdir()
    assert run(empty) == h("")


def test_env_beats_documented(home: Path) -> None:
    v = populate(home, ["documented", "shared", "legacy"])
    assert run(home, env={KEY: "fake-env"}) == h("fake-env")
    assert run(home) == h(v["documented"])


def test_documented_beats_dir_siblings(home: Path) -> None:
    v = populate(home, ["documented", "dir_a", "dir_z"])
    assert run(home) == h(v["documented"])


def test_dir_siblings_alphabetical(home: Path) -> None:
    v = populate(home, ["dir_z", "dir_a"])
    assert run(home) == h(v["dir_a"])


def test_dir_siblings_beat_shared(home: Path) -> None:
    v = populate(home, ["dir_z", "shared", "legacy"])
    assert run(home) == h(v["dir_z"])


def test_documented_beats_shared_without_siblings(home: Path) -> None:
    v = populate(home, ["documented", "shared"])
    assert run(home) == h(v["documented"])


def test_shared_beats_legacy(home: Path) -> None:
    v = populate(home, ["shared", "legacy"])
    assert run(home) == h(v["shared"])


def test_legacy_is_the_last_resort(home: Path) -> None:
    v = populate(home, ["legacy"])
    assert run(home) == h(v["legacy"])


def test_new_file_beats_every_old_one(home: Path) -> None:
    v = populate(home, ["new", "documented", "dir_a", "shared", "legacy"])
    assert run(home) == h(v["new"])


def test_new_provider_file_beats_every_old_one_for_its_key(home: Path) -> None:
    exa = "EXA_API_KEY"
    for name in ("documented", "shared", "legacy"):
        put(places(home)[name], name, key=exa)
    new = put(home / ".h2t" / "secrets" / "shared" / "exa.env", "new", key=exa)
    got = subprocess.run(
        [sys.executable, "-I", "-c",
         "import hashlib; from h2t_ops.core import secrets; "
         "print(hashlib.sha256((secrets.get('EXA_API_KEY') or '').encode()).hexdigest()[:8])"],
        env={**{k: v for k, v in os.environ.items() if k != exa and not k.startswith("H2T_PATH_")},
             "HOME": str(home), "USERPROFILE": str(home)},
        cwd=home, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert got == h(new)


def test_secrets_file_variable_is_not_read(home: Path, tmp_path: Path) -> None:
    v = populate(home, ["documented", "dir_a", "shared", "legacy"])
    override = tmp_path / "elsewhere" / "o.env"
    put(override, "override")
    assert run(home, env={"H2T_SECRETS_FILE": str(override)}) == h(v["documented"])


def test_secrets_file_variable_missing_changes_nothing(home: Path, tmp_path: Path) -> None:
    v = populate(home, ["documented", "shared", "legacy"])
    gone = tmp_path / "nope.env"
    assert run(home, env={"H2T_SECRETS_FILE": str(gone)}) == h(v["documented"])


def test_explicit_path_beats_everything(home: Path, tmp_path: Path) -> None:
    populate(home, ["new", "documented"])
    override = tmp_path / "o.env"
    put(override, "override")
    explicit = tmp_path / "e.env"
    v = put(explicit, "explicit")
    got = run(home, env={"H2T_SECRETS_FILE": str(override), "PIN_EXPLICIT": str(explicit)})
    assert got == h(v)


def test_notion_files_beat_token_file(home: Path) -> None:
    token_file = home / ".config" / "notion" / "token"
    token_file.parent.mkdir(parents=True)
    token_file.write_text("fake-token-file\n", encoding="utf-8")
    put(places(home)["legacy"], "legacy", key=NOTION)
    assert run(home, mode="notion") == h("fake-legacy-secrets.env")
    assert run(home, env={NOTION: "fake-env"}, mode="notion") == h("fake-env")


def test_notion_token_file_is_after_all_secrets_files(home: Path) -> None:
    token_file = home / ".config" / "notion" / "token"
    token_file.parent.mkdir(parents=True)
    token_file.write_text("fake-token-file\n", encoding="utf-8")
    assert run(home, mode="notion") == h("fake-token-file")
