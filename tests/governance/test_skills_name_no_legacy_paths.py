"""Shipped skill text names no 3.x storage place (#548 Task 25).

A skill that spells a path goes stale on the next move; it asks `h2t-ops paths get <id>`
instead. The old places are taken from paths.LEGACY and the old variables from
paths.OLD_ENV, so a place added there is checked here without editing this file.

Scope: every Markdown file under plugins/ except CHANGELOG.md, which is history
(plugins/h2t-core/CHANGELOG.md, plugins/h2t-ops/CHANGELOG.md describe old releases). A line
that describes the migration says so with `legacy` or `3.x` and is allowed.
"""
import re
from pathlib import Path

from h2t_ops.core import paths

ROOT = Path(__file__).resolve().parents[2]
_HOME = r"(?:~|\$HOME|\$\{HOME\})/"
# A file entry counts by its directory (~/.config/notion, not only …/token), and ~/.dor as a
# whole, slash or not: the vault's default lives there too, and a skill asks for it by id.
_OLD_PLACES = sorted({re.escape("/".join(parts[:-1] if name in paths.LEGACY_FILES else parts))
                      for name, parts in paths.LEGACY.items()
                      if name != "downloads" and parts[0] != ".dor"} | {re.escape(".dor")})
LEGACY = re.compile(_HOME + "(?:" + "|".join(_OLD_PLACES) + r")\b"
                    + "|\\b(?:" + "|".join(sorted(paths.OLD_ENV)) + ")\\b")
ALLOWED = re.compile(r"legacy|3\.x")


def _shipped_docs() -> list[Path]:
    return sorted(p for p in (ROOT / "plugins").rglob("*.md") if p.name != "CHANGELOG.md")


def _hits(files) -> list[str]:
    out = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY.search(line) and not ALLOWED.search(line):
                out.append(f"{f.relative_to(ROOT).as_posix()}:{n}: {line.strip()}")
    return out


def test_pattern_covers_the_known_spellings():
    for text in ("~/.dor/secrets.env", "$HOME/.config/google-calendar-mcp/tokens.json",
                 "~/.config/telegram/config.json", "~/.h2t/sessions/mac/", "~/.h2t/config/secrets/x.env",
                 "~/.h2t/creative/profiles", "H2T_SESSION_ROOT", "H2T_SECRETS_FILE",
                 "~/.config/notion/config.json", "no `~/.dor` write"):
        assert LEGACY.search(text), text
    for text in ("~/.h2t/config/user.yaml", "~/.h2t/run/install.env", "~/Downloads", "~/.dorx",
                 "h2t-ops paths get secret:google.token"):
        assert not LEGACY.search(text), text


def test_scope_reads_skills_and_references():
    files = {p.relative_to(ROOT).as_posix() for p in _shipped_docs()}
    assert "plugins/h2t-ops/skills/connectors/references/notion.md" in files
    assert "plugins/h2t-core/skills/handoff/SKILL.md" in files
    assert not any(f.endswith("CHANGELOG.md") for f in files)


def test_shipped_skills_name_no_legacy_paths():
    hits = _hits(_shipped_docs())
    assert not hits, ("skill text names a 3.x place; ask `h2t-ops paths get <id>` instead:\n"
                      + "\n".join(hits))
