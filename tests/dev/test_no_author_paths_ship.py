"""No shipped file may name a directory that exists on one machine (#434).

#434 was filed for this and read as done. Nothing was watching, so twelve occurrences
survived — and three of them were behaviour, not prose: the `kb` skill defaulted its
knowledge base to `C:/dev/research-kb`, and `project-audit` defaulted `projects.yaml`
to `C:/dev/h2t-landings/`. On every machine but one those resolve to nothing, and the
failure lands far from its cause.

This is a ratchet, not a wall. `EXPECTED` lists what is still there with the reason,
and `test_known_debt_is_not_stale` fails when an entry is fixed without being removed —
otherwise the list outlives the problem and the next reader trusts it.
"""

import re
from collections import Counter
from pathlib import Path, PurePath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
# Everything that ships. `plugins/` alone was the first version of this list, and
# `h2t_ops/` — the package behind the nine CLI entry points, the first thing a stranger
# installs — was outside it. The hint in `visual_ocr.py` telling them to install from
# `C:/dev/h2t-tools` was found by a grep, not by this test.
# Two patterns, two scopes, because they are two different problems.
#
# A home directory with a person's name in it is personal data wherever it sits, and
# publication makes the whole tree readable — 185 occurrences lived under docs/, tests/
# and tools/ while the first version of this file walked four directories holding none
# of them (#417).
#
# `C:/dev` is a portability defect in code and merely noise in prose. Enforcing it over
# docs/ would mean rewriting several hundred lines of historical reports to no benefit;
# the audit that counted them said the same.
CODE_ROOTS = [ROOT / "plugins", ROOT / "h2t_ops", ROOT / "lib", ROOT / "scripts"]
PROSE_ROOTS = [ROOT / "docs", ROOT / "tests", ROOT / "tools",
                # The two files a stranger opens first, and the only shipped prose that
                # lived outside every root above (#443).
                ROOT / "README.md", ROOT / "CLAUDE.md", ROOT / "CONTRIBUTING.md"]

DEV_ROOT_PATH = re.compile(r"[A-Za-z]:[\\/]dev\b", re.IGNORECASE)
# Two or more characters in the home-directory name: `/Users/x/` is a placeholder in a
# fixture, a real account name is a person.
PLACEHOLDER_HOMES = r"(?:user|users|testuser|someone|username|me|you|example|dev|<user>)"
HOME_PATH = re.compile(
    rf"/(?:Users|home)/(?!{PLACEHOLDER_HOMES}/)[A-Za-z_][A-Za-z0-9_-]+/", re.IGNORECASE
)

# A drive-letter dev root, or a home directory with a name in it.
# Two or more characters in the home-directory name: `/Users/x/` is a placeholder in a
# fixture, a real account name is a person. A one-letter home does not exist on any machine
# this could leak.
AUTHOR_PATH = re.compile(
    r"[A-Za-z]:[\\/]dev\b|/(?:Users|home)/[A-Za-z_][A-Za-z0-9_-]+/", re.IGNORECASE
)

SKIP_NAMES = {"CHANGELOG.md"}
SCANNED_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".sh", ""}

# path -> why an author path is expected there. Two kinds, and the distinction matters:
# prose recording a default that was removed, and fixtures that assert an old Windows
# path still resolves — the second is not debt, it is the portability proof.
EXPECTED = {
    "h2t_ops/lifecycle/detect_project.py":
        "comment recording the C:/dev anchor these patterns replaced",
    "plugins/h2t-core/skills/scaffold-project/SKILL.md":
        "prose recording the removed C:/dev/{id} default",
}


def _rel_key(path: PurePath, root: PurePath) -> str:
    """The key `EXPECTED` is looked up by, and it must be spelled the same on every runner.

    `str()` on a `WindowsPath` yields backslashes while `EXPECTED` is written with forward
    slashes, so on the Windows leg every allow-listed file missed the lookup at once and
    both assertions below fired from opposite directions — one naming the five as
    offenders, the other naming the same five as already clean (#471).
    """
    return path.relative_to(root).as_posix()


def _offenders(roots, pattern) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for root in roots:
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = sorted(root.rglob("*"))
        else:
            continue
        for path in candidates:
            if not path.is_file() or path.name in SKIP_NAMES:
                continue
            if path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if path.lstat().st_mode & 0o170000 == 0o120000:
                continue
            hits = [
                f"{lineno}: {line.strip()[:110]}"
                for lineno, line in enumerate(text.splitlines(), 1)
                if not line.lstrip().startswith("echo ") and pattern.search(line)
            ]
            if hits:
                found[_rel_key(path, ROOT)] = hits
    return found


def test_no_author_dev_root_in_shipped_code():
    offenders = {k: v for k, v in _offenders(CODE_ROOTS, DEV_ROOT_PATH).items()
                 if k not in EXPECTED}
    assert not offenders, "a dev root that exists on one machine:\n" + "\n".join(
        f"  {rel}\n    " + "\n    ".join(lines) for rel, lines in offenders.items()
    )


def test_no_home_directory_names_anywhere():
    """A person's home directory is personal data in prose as much as in code."""
    roots = CODE_ROOTS + PROSE_ROOTS
    offenders = {k: v for k, v in _offenders(roots, HOME_PATH).items() if k not in EXPECTED}
    assert not offenders, "a home directory naming a person:\n" + "\n".join(
        f"  {rel}\n    " + "\n    ".join(lines) for rel, lines in offenders.items()
    )


def test_expected_list_is_not_stale():
    """An entry that is now clean means the list lies to the next reader."""
    seen = set(_offenders(CODE_ROOTS, DEV_ROOT_PATH)) | set(
        _offenders(CODE_ROOTS + PROSE_ROOTS, HOME_PATH))
    clean = set(EXPECTED) - seen
    assert not clean, f"EXPECTED names files that are already clean: {sorted(clean)}"


def test_offender_keys_are_posix_on_any_platform():
    """A Windows runner must produce the same key a POSIX runner does.

    `PureWindowsPath` models that runner from here: `str()` on it yields backslashes,
    which is the whole of #471's first defect.
    """
    win = PureWindowsPath(r"C:\\repo\\plugins\\h2t-core\\skills\\x\\scripts\\y.py")
    assert _rel_key(win, PureWindowsPath(r"C:\\repo")) == "plugins/h2t-core/skills/x/scripts/y.py"


# --- Author values (#581) -------------------------------------------------------------
# Always upstream, wherever they appear.
UPSTREAM = re.compile(r"lichtpfad/h2t-(?:skills|snap)\b|@lichtpfad\b|cache/lichtpfad/")
TOKENS = re.compile(
    r"\blichtpfad\b|hou2touch|personal-os|crypto-(?:regime|orchestrator|machine)|rejuve|quant-kb"
    r"|QATAL|Mamuta|Zilberman|Bezalel|AICF|Motion Designer, Berlin|pfad-extension"
    r"|\bh2t-(?:ai|business|client|dcc|evals|factory|infra|landings|tools|transcription"
    r"|vision|voice)\b|~/\.dor\b|[\"']\.dor[\"']", re.IGNORECASE)
# A 3.x .dor place named outside migration code, as a call argument or in a tuple that is
# iterated into legacy(). Not counted when it is the argument of the gated legacy_read().
DOR_KEY = re.compile(r"(?<!legacy_read\()[\"'](?:secrets\.dor|secrets\.dor_old|google\.dor|"
                     r"sessions\.dor|registry\.dor|lake\.dor)[\"']")
# Migration code is where .dor belongs: exact files and one prefix.
MIGRATION_FILES = {"h2t_ops/setup/legacy.py", "h2t_ops/setup/storage_doctor.py",
                   "scripts/storage_map.py"}
MIGRATION_PREFIXES = ("h2t_ops/setup/layout/",)
_DOR_TOKEN = re.compile(r"~/\.dor\b|[\"']\.dor[\"']", re.IGNORECASE)


def _is_migration(rel: str) -> bool:
    return rel in MIGRATION_FILES or rel.startswith(MIGRATION_PREFIXES)


def _tokens(path: Path, rel: str | None = None) -> Counter:
    """Author-value tokens in one file, counted per token, not per line."""
    if rel is None:
        try:
            rel = _rel_key(path, ROOT)
        except ValueError:
            rel = path.name
    migration = _is_migration(rel)
    counts: Counter = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = UPSTREAM.sub("", line)
        for m in TOKENS.finditer(line):
            if migration and _DOR_TOKEN.fullmatch(m.group(0)):
                continue
            counts[m.group(0).lower()] += 1
        if not migration:
            counts["dor-key"] += len(DOR_KEY.findall(line))
    return +counts


def _all_tokens() -> dict[str, Counter]:
    found: dict[str, Counter] = {}
    for root in CODE_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name in SKIP_NAMES:
                continue
            if path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            if path.lstat().st_mode & 0o170000 == 0o120000:
                continue
            try:
                counts = _tokens(path)
            except (OSError, UnicodeDecodeError):
                continue
            if counts:
                found[_rel_key(path, ROOT)] = counts
    return found


# path -> (token -> count, reason). A reason of "upstream" is permanent; every other reason
# names the PR or issue that removes the entry.
AUTHOR_DEBT: dict[str, tuple[dict[str, int], str]] = {
    "h2t_ops/connectors/dropbox/client.py":
        ({"hou2touch": 2, "lichtpfad": 1}, "PR 6"),
    "h2t_ops/connectors/evals/commands.py":
        ({"lichtpfad": 1}, "upstream"),
    "h2t_ops/connectors/gmail/signature.py":
        ({"hou2touch": 1}, "PR 6"),
    "h2t_ops/connectors/meetgeek/recovery.py":
        ({"dor-key": 1}, "PR 9"),
    "h2t_ops/connectors/research/visual_ocr.py":
        ({"h2t-tools": 2}, "PR 6"),
    "h2t_ops/core/google_auth.py":
        ({"lichtpfad": 1}, "PR 9"),
    "h2t_ops/core/lake.py":
        ({"dor-key": 2, "~/.dor": 2}, "PR 9"),
    "h2t_ops/core/paths.py":
        ({"\".dor\"": 7, "dor-key": 11, "~/.dor": 7}, "LEGACY table; vault default (D1)"),
    "h2t_ops/core/providers.py":
        ({"h2t-evals": 2}, "PR 9"),
    "h2t_ops/core/secrets.py":
        ({"dor-key": 7, "h2t-evals": 3, "~/.dor": 1}, "PR 9"),
    "h2t_ops/core/settings.py":
        ({"h2t-evals": 1}, "upstream"),
    "h2t_ops/core/store.py":
        ({"~/.dor": 1}, "PR 9"),
    "h2t_ops/hooks/layout_precommit.py":
        ({"h2t-transcription": 1}, "PR 4"),
    "h2t_ops/hooks/plan_closer.py":
        ({"h2t-business": 1}, "PR 4"),
    "h2t_ops/hooks/secrets_precommit.py":
        ({"h2t-transcription": 1}, "PR 4"),
    "h2t_ops/hooks/structure_guard.py":
        ({"h2t-transcription": 1}, "PR 4"),
    "h2t_ops/lifecycle/detect_project.py":
        ({"h2t-vision": 2, "hou2touch": 8, "personal-os": 1}, "PR 3"),
    "h2t_ops/lifecycle/eval/session.py":
        ({"h2t-ai": 1, "h2t-evals": 2}, "PR 4"),
    "h2t_ops/lifecycle/eval/status.py":
        ({"h2t-evals": 1}, "PR 4"),
    "h2t_ops/lifecycle/gather/README.md":
        ({"personal-os": 1}, "PR 3"),
    "h2t_ops/lifecycle/gather/sessions_legacy.py":
        ({"dor-key": 1, "~/.dor": 1}, "PR 9"),
    "h2t_ops/lifecycle/gather/user.py":
        ({"hou2touch": 1, "personal-os": 1}, "PR 3"),
    "h2t_ops/lifecycle/project_audit_report.py":
        ({"h2t-landings": 1}, "#632"),
    "h2t_ops/lifecycle/project_audit_scan.py":
        ({"h2t-landings": 2}, "#632"),
    "h2t_ops/lifecycle/pulse/transcript.py":
        ({"h2t-infra": 1, "lichtpfad": 1}, "PR 4"),
    "h2t_ops/lifecycle/scaffold_project.py":
        ({"h2t-infra": 1}, "PR 3"),
    "h2t_ops/resources/agent_profile/agent-profiles.json":
        ({"h2t-dcc": 13}, "#614"),
    "h2t_ops/resources/creative/profiles/h2t-default/DESIGN.md":
        ({"hou2touch": 1}, "PR 7"),
    "h2t_ops/resources/creative/profiles/h2t-graphs/DESIGN.md":
        ({"lichtpfad": 1}, "PR 7"),
    "h2t_ops/resources/creative/profiles/h2t-pfad/DESIGN.md":
        ({"lichtpfad": 1}, "PR 7"),
    "h2t_ops/resources/docs/standards/api-contracts.md":
        ({"h2t-evals": 1}, "PR 7"),
    "h2t_ops/resources/docs/standards/code-organization.md":
        ({"h2t-ai": 1}, "PR 7"),
    "h2t_ops/resources/docs/standards/documentation-structure.md":
        ({"crypto-regime": 1, "h2t-ai": 4, "h2t-evals": 2, "h2t-transcription": 2, "h2t-vision": 1, "rejuve": 1}, "PR 7"),
    "h2t_ops/resources/docs/standards/git-naming-conventions.md":
        ({"h2t-ai": 1, "h2t-business": 1, "h2t-client": 1, "h2t-dcc": 1, "h2t-evals": 1, "h2t-factory": 1, "h2t-landings": 1, "h2t-tools": 1, "h2t-transcription": 1, "h2t-vision": 1, "h2t-voice": 1}, "PR 7"),
    "h2t_ops/resources/docs/standards/naming-conventions.md":
        ({"crypto-regime": 1, "quant-kb": 1}, "PR 7"),
    "h2t_ops/setup/harness_claude.py":
        ({"lichtpfad": 3}, "upstream"),
    "h2t_ops/setup/layout/phases.py":
        ({"personal-os": 3}, "PR 9"),
    "h2t_ops/setup/legacy.py":
        ({"lichtpfad": 1}, "upstream"),
    "h2t_ops/setup/storage_doctor.py":
        ({"h2t-transcription": 1}, "PR 6"),
    "h2t_ops/setup/sync.py":
        ({"lichtpfad": 7}, "upstream"),
    "h2t_ops/tools/docs/common.py":
        ({"h2t-ai": 1, "h2t-business": 1, "h2t-client": 1, "h2t-dcc": 1, "h2t-evals": 2, "h2t-factory": 1, "h2t-landings": 1, "h2t-tools": 1, "h2t-transcription": 2, "h2t-vision": 2, "h2t-voice": 1}, "PR 2"),
    "h2t_ops/tools/docs/docs_init.py":
        ({"h2t-landings": 1}, "PR 2"),
    "h2t_ops/tools/docs/lint.py":
        ({"h2t-landings": 2, "lichtpfad": 1}, "PR 2"),
    "h2t_ops/tools/docs/migrate_legacy_labels.py":
        ({"lichtpfad": 4}, "PR 2"),
    "h2t_ops/tools/docs/new_doc.py":
        ({"lichtpfad": 1}, "PR 2"),
    "h2t_ops/tools/docs/sync_labels.py":
        ({"lichtpfad": 1}, "PR 2"),
    "lib/practice_harvest/lineage.py":
        ({"crypto-regime": 3}, "PR 6"),
    "plugins/h2t-arch/.claude-plugin/plugin.json":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-arch/skills/diagram-node/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-arch/skills/drawio/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-core/.claude-plugin/plugin.json":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-core/skills/agent-profile/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-core/skills/agent-profile/references/agent-profiles.json":
        ({"h2t-dcc": 13}, "#614"),
    "plugins/h2t-core/skills/autonomous-run/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-core/skills/autonomous-run/references/gates.md":
        ({"crypto-regime": 1}, "PR 6"),
    "plugins/h2t-core/skills/dev-overview/SKILL.md":
        ({"h2t-ai": 1, "hou2touch": 1, "lichtpfad": 2}, "#612"),
    "plugins/h2t-core/skills/handoff/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-core/skills/handoff/references/handoff-example.md":
        ({"h2t-evals": 2, "h2t-transcription": 3, "hou2touch": 1}, "PR 6"),
    "plugins/h2t-core/skills/init-project/SKILL.md":
        ({"h2t-factory": 1, "hou2touch": 1, "lichtpfad": 1}, "PR 3"),
    "plugins/h2t-core/skills/init-project/references/truth-gate.md":
        ({"crypto-machine": 1, "h2t-infra": 1}, "PR 6"),
    "plugins/h2t-core/skills/project-audit/SKILL.md":
        ({"h2t-landings": 4, "lichtpfad": 1}, "#632"),
    "plugins/h2t-core/skills/report-issue/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-core/skills/scaffold-project/SKILL.md":
        ({"h2t-voice": 1, "hou2touch": 1, "lichtpfad": 2, "personal-os": 1}, "PR 3"),
    "plugins/h2t-core/skills/session-start/SKILL.md":
        ({"h2t-ai": 1, "lichtpfad": 1}, "PR 3"),
    "plugins/h2t-core/skills/setup/SKILL.md":
        ({"lichtpfad": 2}, "upstream"),
    "plugins/h2t-core/skills/snap/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-creative/.claude-plugin/plugin.json":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-creative/agents/browser-qa.md":
        ({"h2t-tools": 1}, "PR 7"),
    "plugins/h2t-creative/profiles/h2t-default/DESIGN.md":
        ({"hou2touch": 1}, "PR 7"),
    "plugins/h2t-creative/profiles/h2t-graphs/DESIGN.md":
        ({"lichtpfad": 1}, "PR 7"),
    "plugins/h2t-creative/profiles/h2t-pfad/DESIGN.md":
        ({"lichtpfad": 1}, "PR 7"),
    "plugins/h2t-creative/recipes/landing-course.yaml":
        ({"motion designer, berlin": 1}, "PR 7"),
    "plugins/h2t-creative/skills/deck/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-creative/skills/design/SKILL.md":
        ({"lichtpfad": 1, "pfad-extension": 2}, "#463"),
    "plugins/h2t-creative/skills/landing/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-creative/skills/style-create/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-creative/skills/style-validate/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-dev/.claude-plugin/plugin.json":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-dev/README.md":
        ({"h2t-ai": 1}, "PR 7"),
    "plugins/h2t-dev/references/standards/api-contracts.md":
        ({"h2t-evals": 1}, "PR 7"),
    "plugins/h2t-dev/references/standards/code-organization.md":
        ({"h2t-ai": 1}, "PR 7"),
    "plugins/h2t-dev/references/standards/documentation-structure.md":
        ({"crypto-regime": 1, "h2t-ai": 4, "h2t-evals": 2, "h2t-transcription": 2, "h2t-vision": 1, "rejuve": 1}, "PR 7"),
    "plugins/h2t-dev/references/standards/git-naming-conventions.md":
        ({"h2t-ai": 1, "h2t-business": 1, "h2t-client": 1, "h2t-dcc": 1, "h2t-evals": 1, "h2t-factory": 1, "h2t-landings": 1, "h2t-tools": 1, "h2t-transcription": 1, "h2t-vision": 1, "h2t-voice": 1}, "PR 7"),
    "plugins/h2t-dev/references/standards/naming-conventions.md":
        ({"crypto-regime": 1, "quant-kb": 1}, "PR 7"),
    "plugins/h2t-dev/skills/docs-lint/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-dev/skills/docs-sync-labels/SKILL.md":
        ({"h2t-ai": 2, "lichtpfad": 3}, "PR 2"),
    "plugins/h2t-dev/skills/github-issues/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-dev/skills/milestone-closure/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-dev/skills/pre-merge-check/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-ops/.claude-plugin/plugin.json":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-ops/skills/connectors/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-ops/skills/connectors/references/dropbox.md":
        ({"hou2touch": 11, "lichtpfad": 1}, "PR 6"),
    "plugins/h2t-ops/skills/connectors/references/meetgeek.md":
        ({"h2t-transcription": 1}, "PR 6"),
    "plugins/h2t-ops/skills/connectors/references/notion.md":
        ({"h2t-business": 1, "lichtpfad": 1}, "PR 6"),
    "plugins/h2t-ops/skills/daily-brief/SKILL.md":
        ({"aicf": 1, "bezalel": 1, "lichtpfad": 1, "mamuta": 1, "qatal": 1, "zilberman": 1}, "PR 5"),
    "plugins/h2t-ops/skills/deploy/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-ops/skills/kb/SKILL.md":
        ({"lichtpfad": 1}, "upstream"),
    "plugins/h2t-ops/skills/research/REPORT-SPEC.md":
        ({"h2t-evals": 1, "rejuve": 1}, "PR 6"),
    "plugins/h2t-ops/skills/research/SKILL.md":
        ({"crypto-orchestrator": 1, "lichtpfad": 1, "rejuve": 1}, "PR 6"),
    "plugins/h2t-ops/skills/research/examples.md":
        ({"rejuve": 21}, "PR 6"),
}


def test_author_values_match_the_debt():
    found = _all_tokens()
    expected = lambda p: AUTHOR_DEBT.get(p, ({}, ""))[0]  # noqa: E731
    diff = {p: (dict(c), expected(p)) for p, c in found.items() if dict(c) != expected(p)}
    gone = [p for p in AUTHOR_DEBT if p not in found]
    msg = ""
    if diff:
        msg += "author values differ from AUTHOR_DEBT (found vs recorded):\n" + "\n".join(
            f"  {p}\n    found    {f}\n    recorded {r}" for p, (f, r) in sorted(diff.items()))
    if gone:
        msg += "\nAUTHOR_DEBT names files that are now clean, lower AUTHOR_DEBT: " + str(sorted(gone))
    assert not diff and not gone, msg


def test_probe_counts_tokens_not_lines(tmp_path):
    """Positive control: two tokens on one line count twice; upstream spans count zero."""
    f = tmp_path / "x.py"
    f.write_text('A = "lichtpfad"; B = "hou2touch"\nURL = "lichtpfad/h2t-skills"\n'
                 'p = paths.legacy("lake.dor")\nROOTS = ("sessions.h2t", "sessions.dor")\n'
                 'q = paths.legacy_read("lake.dor")\n')
    assert _tokens(f) == Counter({"lichtpfad": 1, "hou2touch": 1, "dor-key": 2})
