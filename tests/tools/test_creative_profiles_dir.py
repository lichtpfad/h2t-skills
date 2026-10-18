"""User profiles live in `~/.h2t/data/creative/profiles/`, searched before the shipped ones.

style-create used to write new profiles into `$(h2t-creative root)/profiles`, which was
the plugin cache: every update wiped them. The ruling (#548 option A, one root `~/.h2t`)
moves new profiles to the user directory; shipped profiles stay in the package. 4.0 puts
that directory under data/ (#548 §3) and still finds a profile in the 3.x directory,
`~/.h2t/creative/profiles/`, until the migration moves it.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from h2t_ops.resources import resource_dir
from h2t_ops.tools.creative import assembler, cli

SHIPPED = resource_dir("creative") / "profiles"


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    # cli.main assigns the module constant; restore it for the next test.
    monkeypatch.setattr(assembler, "PROFILES_DIR", assembler.PROFILES_DIR)
    return home


def _recipe(tmp_path: Path) -> Path:
    recipe = tmp_path / "recipe.yaml"
    recipe.write_text("title: T\nsections:\n  - component: hero\n    content:\n"
                      "      headline: H\n", encoding="utf-8")
    return recipe


def test_profiles_dir_is_under_the_user_home(home, capsys):
    assert cli.main(["profiles-dir"]) == 0
    assert Path(capsys.readouterr().out.strip()) == home / ".h2t" / "data" / "creative" / "profiles"


def test_root_still_names_the_shipped_resources(home, capsys):
    assert cli.main(["root"]) == 0
    assert Path(capsys.readouterr().out.strip()) == resource_dir("creative")


@pytest.mark.parametrize("where", [(".h2t", "data", "creative", "profiles"),
                                   (".h2t", "creative", "profiles")], ids=["4.0", "3.x"])
def test_a_user_profile_is_found_before_the_shipped_ones(home, tmp_path, where):
    mine = home.joinpath(*where) / "my-style"
    shutil.copytree(SHIPPED / "h2t-default", mine)
    (mine / "palettes" / "default.css").write_text(
        ":root { --color-bg: #123456; }\n", encoding="utf-8")
    out = tmp_path / "dist"
    assert cli.main(["assemble", "--profile", "my-style", "--type", "landing",
                     "--recipe", str(_recipe(tmp_path)), "--out", str(out)]) == 0
    assert "#123456" in (out / "profile.css").read_text(encoding="utf-8")


def test_a_shipped_profile_still_assembles_with_no_user_dir(home, tmp_path):
    out = tmp_path / "dist"
    assert cli.main(["assemble", "--profile", "h2t-default", "--type", "landing",
                     "--recipe", str(_recipe(tmp_path)), "--out", str(out)]) == 0
    assert (out / "index.html").is_file()
    # The --out files go through store (R7), which logs them under ~/.h2t/logs (§7.2);
    # what must not appear is the profile directory.
    assert not (home / ".h2t" / "data" / "creative").exists(), "assembling must not create the user directory"
    assert not (home / ".h2t" / "creative").exists()


def test_an_unknown_profile_fails(home, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["assemble", "--profile", "nope", "--type", "landing",
                  "--recipe", str(_recipe(tmp_path)), "--out", str(tmp_path / "d")])
    assert exc.value.code == 1
    assert "nope" in capsys.readouterr().err
