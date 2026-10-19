"""Shipped skill text names no 3.x storage place (#548 Task 25).

A skill that spells a path goes stale on the next move; it asks `h2t-ops paths get <id>`
instead. The old places are taken from paths.LEGACY and the old variables from
paths.OLD_ENV, so a place added there is checked here without editing this file.

Scope: every Markdown file under plugins/ except CHANGELOG.md, which is history
(plugins/h2t-core/CHANGELOG.md, plugins/h2t-ops/CHANGELOG.md describe old releases), and the
top-level README.md (#564). A line that describes the migration says so with `legacy` or
`3.x` and is allowed; in README the whole paragraph is, and `~/.dor/vault` there is the
4.0 default of H2T_PATH_VAULT, which a reader needs spelled. docs/ is out of scope: specs and
plans describe 3.x by design. Windows spellings count: a backslash, %USERPROFILE%.
"""
import re
from pathlib import Path

from h2t_ops.core import paths

ROOT = Path(__file__).resolve().parents[2]
_SEP = r"[/\\]"
_HOME = r"(?:~|\$HOME|\$\{HOME\}|%USERPROFILE%|\$env:USERPROFILE)" + _SEP
# A file entry counts by its directory (~/.config/notion, not only …/token), and ~/.dor as a
# whole, slash or not: the vault's default lives there too, and a skill asks for it by id.
_OLD_PLACES = sorted({_SEP.join(map(re.escape, parts[:-1] if name in paths.LEGACY_FILES else parts))
                      for name, parts in paths.LEGACY.items()
                      if name != "downloads" and parts[0] != ".dor"} | {re.escape(".dor")})
LEGACY = re.compile(_HOME + "(?:" + "|".join(_OLD_PLACES) + r")\b"
                    + "|\\b(?:" + "|".join(sorted(paths.OLD_ENV)) + ")\\b")
ALLOWED = re.compile(r"legacy|3\.x")
VAULT_DEFAULT = re.compile(_HOME + r"\.dor" + _SEP + r"vault\b")


def _shipped_docs() -> list[Path]:
    return sorted([ROOT / "README.md",
                   *(p for p in (ROOT / "plugins").rglob("*.md") if p.name != "CHANGELOG.md")])


def _hits(files) -> list[str]:
    out = []
    for f in files:
        readme = f == ROOT / "README.md"
        lines = f.read_text(encoding="utf-8").splitlines()
        allowed = set()     # README: every line of a paragraph that says 3.x or legacy
        if readme:
            start = 0
            for i, line in enumerate([*lines, ""]):
                if not line.strip():
                    if any(ALLOWED.search(x) for x in lines[start:i]):
                        allowed.update(range(start, i))
                    start = i + 1
        for n, line in enumerate(lines, 1):
            text = VAULT_DEFAULT.sub("", line) if readme else line
            if LEGACY.search(text) and not ALLOWED.search(text) and n - 1 not in allowed:
                out.append(f"{f.relative_to(ROOT).as_posix()}:{n}: {line.strip()}")
    return out


def test_pattern_covers_the_known_spellings():
    for text in ("~/.dor/secrets.env", "$HOME/.config/google-calendar-mcp/tokens.json",
                 "~/.config/telegram/config.json", "~/.h2t/sessions/mac/", "~/.h2t/config/secrets/x.env",
                 "~/.h2t/creative/profiles", "H2T_SESSION_ROOT", "H2T_SECRETS_FILE",
                 "~/.config/notion/config.json", "no `~/.dor` write",
                 r"%USERPROFILE%\.dor\sessions", r"~\.config\telegram", r"$env:USERPROFILE\.dor",
                 r"%USERPROFILE%/.h2t/config/secrets"):
        assert LEGACY.search(text), text
    for text in ("~/.h2t/config/user.yaml", "~/.h2t/run/install.env", "~/Downloads", "~/.dorx",
                 "h2t-ops paths get secret:google.token"):
        assert not LEGACY.search(text), text


def test_scope_reads_skills_and_references():
    files = {p.relative_to(ROOT).as_posix() for p in _shipped_docs()}
    assert "plugins/h2t-ops/skills/connectors/references/notion.md" in files
    assert "plugins/h2t-core/skills/handoff/SKILL.md" in files
    assert "README.md" in files
    assert not any(f.endswith("CHANGELOG.md") for f in files)


def test_shipped_skills_name_no_legacy_paths():
    hits = _hits(_shipped_docs())
    assert not hits, ("skill text names a 3.x place; ask `h2t-ops paths get <id>` instead:\n"
                      + "\n".join(hits))


def test_a_planted_3x_path_is_reported_with_file_and_line(tmp_path, monkeypatch):
    """#564: README is read, and a Windows spelling counts. In README a paragraph that says
    3.x describes the migration as a whole, and `~/.dor/vault` is the 4.0 default of
    H2T_PATH_VAULT, not a 3.x place; neither is reported."""
    import sys
    guard = sys.modules[__name__]
    monkeypatch.setattr(guard, "ROOT", tmp_path)
    skill = tmp_path / "plugins" / "p" / "skills" / "s" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# s\n\nsessions are in %USERPROFILE%\\.dor\\sessions\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# r\n"                                                  # 1
        "\n"                                                     # 2
        "Sessions are in ~/.dor/sessions.\n"                     # 3 planted
        "\n"                                                     # 4
        "**From 3.x.** the old variables\n"                      # 5
        "`H2T_SESSION_ROOT` are not read.\n"                     # 6 the 3.x paragraph
        "\n"                                                     # 7
        "The vault defaults to `~/.dor/vault`.\n",                # 8 the 4.0 default
        encoding="utf-8")
    assert [h.split(": ", 1)[0] for h in _hits(_shipped_docs())] == [
        "README.md:3", "plugins/p/skills/s/SKILL.md:3"]
