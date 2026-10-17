from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# The canonical copy moved into the package (plan Task 8); the plugin keeps its mirror
# for the 3.x scripts until Task 12, which deletes both the mirror and this test.
PACKAGE_LIB = ROOT / "h2t_ops" / "lifecycle"
VENDORED_LIB = ROOT / "plugins" / "h2t-core" / "lib"
# Packages the plugin ships alongside its scripts. `eval` was the only one under a
# parity test until gather/ drifted for four months in both directions (#354).
VENDORED_PACKAGES = ["eval", "gather", "activity"]
# The one difference the two copies may carry: the package copy is imported as
# `h2t_ops.lifecycle.<pkg>`, the plugin mirror as `lib.<pkg>` (or top-level `<pkg>`).
PACKAGE_PREFIX = "h2t_ops.lifecycle."
VENDORED_PREFIX = "lib."


def _modules(directory: Path) -> list[str]:
    """Non-test modules under one package, subpackages included.

    rglob, not glob: a nested package added to one copy would otherwise never be
    compared. Test files are excluded because the two copies legitimately carry different
    ones — the package keeps none (they live in tests/lifecycle/), the plugin ships two.
    """
    return sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*.py")
        if not path.name.startswith("test_")
    )


def _cases() -> list[tuple[str, str]]:
    return [(pkg, name) for pkg in VENDORED_PACKAGES for name in _modules(VENDORED_LIB / pkg)]


def normalized(text: str) -> str:
    return text.replace(PACKAGE_PREFIX, VENDORED_PREFIX)


@pytest.mark.parametrize("package", VENDORED_PACKAGES)
def test_both_copies_ship_the_same_modules(package):
    assert _modules(PACKAGE_LIB / package) == _modules(VENDORED_LIB / package)


@pytest.mark.parametrize(("package", "name"), _cases())
def test_vendored_lib_parity(package, name):
    """The vendored plugin copy (the 3.x runtime path) must match the package copy."""
    package_path = PACKAGE_LIB / package / name
    assert package_path.is_file(), (
        f"plugins/h2t-core/lib/{package}/{name} has no counterpart in h2t_ops/lifecycle/{package}/; "
        "the vendored copy must not carry modules the package copy lacks"
    )
    vendored = (VENDORED_LIB / package / name).read_text(encoding="utf-8")
    assert normalized(package_path.read_text(encoding="utf-8")) == vendored, (
        f"h2t_ops/lifecycle/{package}/{name} drifted from plugins/h2t-core/lib/{package}/{name} "
        f"beyond the {PACKAGE_PREFIX!r} <-> {VENDORED_PREFIX!r} import prefix; re-sync"
    )


def test_normalization_is_only_the_import_prefix():
    """Control: the normalizer must not hide a difference that is not the prefix."""
    assert normalized("from h2t_ops.lifecycle.gather import x") == "from lib.gather import x"
    assert normalized("return a + 1") != "return a + 2"
