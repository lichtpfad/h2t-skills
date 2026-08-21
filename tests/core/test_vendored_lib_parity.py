from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ROOT_LIB = ROOT / "lib"
VENDORED_LIB = ROOT / "plugins" / "h2t-core" / "lib"
# Packages the plugin ships alongside its scripts. `eval` was the only one under a
# parity test until gather/ drifted for four months in both directions (#354).
VENDORED_PACKAGES = ["eval", "gather", "activity"]


def _vendored_modules(package: str) -> list[str]:
    """Non-test modules the plugin ships for this package, subpackages included.

    rglob, not glob: a nested package added to the vendored copy would otherwise never be
    compared. Test files are excluded because the two copies legitimately carry different
    ones — root has eight for gather/, the plugin ships two.
    """
    directory = VENDORED_LIB / package
    return sorted(
        str(path.relative_to(directory))
        for path in directory.rglob("*.py")
        if not path.name.startswith("test_")
    )


def _cases() -> list[tuple[str, str]]:
    return [(pkg, name) for pkg in VENDORED_PACKAGES for name in _vendored_modules(pkg)]


@pytest.mark.parametrize(("package", "name"), _cases())
def test_vendored_lib_parity(package, name):
    """The vendored plugin copy (the runtime path) must match canonical root."""
    root_path = ROOT_LIB / package / name
    assert root_path.is_file(), (
        f"plugins/h2t-core/lib/{package}/{name} has no counterpart in lib/{package}/; "
        "the vendored copy must not carry modules the root copy lacks"
    )
    vendored = (VENDORED_LIB / package / name).read_text(encoding="utf-8")
    assert root_path.read_text(encoding="utf-8") == vendored, (
        f"lib/{package}/{name} drifted from vendored copy; re-sync"
    )
