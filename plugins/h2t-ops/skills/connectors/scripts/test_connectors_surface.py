from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT.parent
REPO_ROOT = ROOT.parents[3]
REMOVED_SKILL_ENTRYPOINT_RE = re.compile(
    r"h2t-ops:(calendar|drive|gmail|meetgeek|notion|telegram)\b"
)
REQUIRED_REFERENCES = {
    "calendar.md",
    "gmail.md",
    "drive.md",
    "notion.md",
    "telegram.md",
    "meetgeek.md",
    "granola.md",
    "issue-policy.md",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_active_runtime_surfaces_do_not_name_removed_skill_entrypoints():
    runtime_surfaces = [
        REPO_ROOT / "plugins" / "h2t-core" / "hooks-handlers" / "inject-h2t-context",
        REPO_ROOT / "plugins" / "h2t-ops" / "skills" / "meetgeek" / "scripts" / "recovery.py",
    ]
    for path in runtime_surfaces:
        assert path.is_file(), path
        assert REMOVED_SKILL_ENTRYPOINT_RE.search(_text(path)) is None, path


def test_connectors_skill_exists_and_is_bounded():
    skill = ROOT / "SKILL.md"
    assert skill.is_file()
    text = _text(skill)
    lines = text.splitlines()
    assert "name: h2t-ops:connectors" in text
    assert len(lines) <= 200
    assert "h2t-ops:research" in text
    assert "daily-brief" in text
    assert "Do not use raw provider APIs" in text
    assert "CLAUDE_PLUGIN_ROOT" not in text
    assert "CLAUDE_SKILL_DIR" not in text
    assert "Provider URL trigger contract" in text
    for domain in (
        "drive.google.com",
        "docs.google.com/document/d/",
        "docs.google.com/spreadsheets/d/",
        "docs.google.com/presentation/d/",
        "calendar.google.com",
        "meet.google.com",
        "mail.google.com",
        "notion.so",
        "t.me",
    ):
        assert domain in text
    assert "Do not use Fetch/WebFetch/Playwright as the primary path" in text


def test_connector_references_exist():
    refs = ROOT / "references"
    assert refs.is_dir()
    found = {path.name for path in refs.glob("*.md")}
    assert REQUIRED_REFERENCES <= found


def test_skill_references_section_lists_every_reference_file():
    """A reference on disk that SKILL.md never links is unreachable for the agent."""
    on_disk = {path.name for path in (ROOT / "references").glob("*.md")}
    section = _text(ROOT / "SKILL.md").split("## References", 1)[1].split("\n## ", 1)[0]
    listed = set(re.findall(r"`references/([^`]+\.md)`", section))
    assert on_disk == listed, f"missing from SKILL.md: {sorted(on_disk - listed)}"


def test_issue_policy_contains_privacy_checklist():
    policy = _text(ROOT / "references" / "issue-policy.md")
    assert "No tokens/API keys/cookies/session files" in policy
    assert "No raw email bodies, transcripts, calendar descriptions, chat text" in policy
    assert "type:bug|feature" in policy
    assert "h2t-ops" in policy


def test_connector_references_have_required_sections():
    for name in REQUIRED_REFERENCES - {"issue-policy.md"}:
        text = _text(ROOT / "references" / name)
        assert "## Intent Map" in text, name
        assert "## Safety" in text, name
        assert "## Commands" in text, name
        assert "## Auth" in text, name
        assert "## Common Failures" in text, name


def test_readiness_slash_command_is_not_in_bash_fence():
    for name in REQUIRED_REFERENCES - {"issue-policy.md"}:
        text = _text(ROOT / "references" / name)
        assert "```text\n/h2t-core:setup connectors-check\n```" in text, name
        assert "```bash\n/h2t-core:setup connectors-check\n```" not in text, name


def test_gmail_reference_uses_positional_send_and_draft_syntax():
    text = _text(ROOT / "references" / "gmail.md")
    assert 'h2t-ops gmail send person@example.com "Subject" "Body" --json' in text
    assert 'h2t-ops gmail draft person@example.com "Subject" "Body" --json' in text
    assert "h2t-ops gmail send --to" not in text
    assert "h2t-ops gmail draft --to" not in text


def test_notion_reference_uses_positional_create_and_sync_syntax():
    text = _text(ROOT / "references" / "notion.md")
    assert 'h2t-ops notion create PAGE_ID "Title" --content "Body" --json' in text
    assert "h2t-ops notion sync PAGE_ID ./notion-page.md --json" in text
    assert "h2t-ops notion create --parent" not in text
    assert "h2t-ops notion sync PAGE_ID --dest" not in text


def test_notion_reference_treats_sync_as_local_file_write():
    text = _text(ROOT / "references" / "notion.md")
    assert (
        "Get, blocks, database reads, search-workspace, graph, find-databases, "
        "and sync are read-oriented."
    ) not in text
    assert "Sync reads from Notion but writes markdown to a local filesystem destination" in text
    assert "explicit user intent and an explicit destination path" in text
    assert "Create and update are Notion provider writes" in text


def test_notion_reference_uses_canonical_search_workspace_syntax():
    text = _text(ROOT / "references" / "notion.md")
    assert "h2t-ops notion search-workspace --object all --limit 25 --json" in text
    assert 'h2t-ops notion search-workspace "query" --max' not in text
    assert 'h2t-ops notion search-workspace "project" --max' not in text


def test_notion_reference_distinguishes_database_query_from_get_database():
    text = _text(ROOT / "references" / "notion.md")
    assert (
        "| query/filter database | "
        "`h2t-ops notion search DATABASE_ID --limit 25 --json` |"
    ) in text
    assert (
        "| get database items | "
        "`h2t-ops notion get-database DATABASE_ID --limit 25 --json` |"
    ) in text
    assert "| query database | `h2t-ops notion get-database" not in text


def test_meetgeek_reference_uses_limit_for_list_syntax():
    text = _text(ROOT / "references" / "meetgeek.md")
    assert "h2t-ops meetgeek list --limit 20 --json" in text
    assert "h2t-ops meetgeek list --max" not in text


def test_telegram_reference_uses_chat_id_for_mentions_syntax():
    text = _text(ROOT / "references" / "telegram.md")
    assert (
        "h2t-ops telegram mentions --chat-id CHAT_ID_FROM_DIALOGS --days 7 "
        "--limit 20 --json"
    ) in text
    assert "h2t-ops telegram mentions --limit" not in text


def test_final_skill_inventory_after_deprecation_gate():
    active = {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    assert active == {"connectors", "daily-brief", "research", "deploy"}


def test_granola_reference_documents_sync_and_transcript_privacy():
    text = _text(ROOT / "references" / "granola.md")
    assert "h2t-ops granola sync --to" in text
    assert "h2t-ops granola transcript NOTE_ID_FROM_LIST --format md" in text
    # Webhook management is read-only in this connector; secrets must never be echoed.
    assert "h2t-ops granola webhooks" in text
    assert "whsec_" not in text


def test_skill_routes_granola_note_urls():
    text = _text(ROOT / "SKILL.md")
    assert "notes.granola.ai" in text
    assert "Granola" in text
