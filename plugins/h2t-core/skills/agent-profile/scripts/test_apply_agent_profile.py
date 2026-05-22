"""Tests for apply_agent_profile.py — run with: python test_apply_agent_profile.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent))

import apply_agent_profile as ap


MINIMAL_CATALOG = {
    "version": 1,
    "pluginIds": {
        "h2t-core": "h2t-core@lichtpfad",
        "h2t-ops": "h2t-ops@lichtpfad",
        "h2t-dev": "h2t-dev@lichtpfad",
        "h2t-creative": "h2t-creative@lichtpfad",
        "superpowers": "superpowers@superpowers-plugins",
        "marketing-playbook": "marketing-playbook@marketing-playbook-plugins",
        "lead-search": "lead-search@lead-search-plugins",
    },
    "baseProfiles": {
        "pos": {
            "description": "Personal OS repository work",
            "enable": ["h2t-core", "h2t-ops", "h2t-dev", "superpowers"],
            "disable": ["h2t-creative", "marketing-playbook"],
        },
        "dev": {
            "description": "Plugin/codebase development",
            "enable": ["h2t-core", "h2t-dev", "superpowers"],
            "disable": ["h2t-creative", "marketing-playbook"],
        },
    },
    "overlays": {
        "marketing": {
            "description": "Marketing, copy, lead-gen",
            "enable": ["marketing-playbook", "lead-search"],
            "disable": [],
        },
        "creative": {
            "description": "Visual/design work",
            "enable": ["h2t-creative"],
            "disable": [],
        },
        "minimal": {
            "description": "Core only",
            "enable": ["h2t-core"],
            "disable": ["h2t-ops", "h2t-dev", "h2t-creative", "marketing-playbook", "lead-search"],
        },
    },
}


# ── T1: Pure merge logic ────────────────────────────────────────────────────

class TestLoadCatalog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "agent-profiles.json"
        self.path.write_text(json.dumps(MINIMAL_CATALOG))

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_catalog_rejects_unknown_plugin_alias(self):
        bad = dict(MINIMAL_CATALOG)
        bad["baseProfiles"] = {
            "bad": {"description": "x", "enable": ["nonexistent"], "disable": []}
        }
        self.path.write_text(json.dumps(bad))
        result = ap.load_catalog(self.path)
        self.assertIn("error", result)

    def test_load_catalog_returns_dict_with_version(self):
        result = ap.load_catalog(self.path)
        self.assertEqual(result.get("version"), 1)
        self.assertNotIn("error", result)


class TestResolveMerge(unittest.TestCase):
    def test_resolve_base_profile_to_enabled_plugins(self):
        result = ap.resolve_effective_profile(MINIMAL_CATALOG, "pos", [])
        enabled = result["enabled"]
        self.assertIn("h2t-core@lichtpfad", enabled)
        self.assertIn("h2t-ops@lichtpfad", enabled)
        disabled = result["disabled"]
        self.assertIn("h2t-creative@lichtpfad", disabled)

    def test_overlay_enable_wins_over_base_disable(self):
        # creative overlay enables h2t-creative which pos disables
        result = ap.resolve_effective_profile(MINIMAL_CATALOG, "pos", ["creative"])
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])
        self.assertNotIn("h2t-creative@lichtpfad", result["disabled"])

    def test_later_overlay_disable_wins(self):
        # minimal overlay disables h2t-ops; apply after creative
        result = ap.resolve_effective_profile(MINIMAL_CATALOG, "pos", ["creative", "minimal"])
        self.assertIn("h2t-ops@lichtpfad", result["disabled"])

    def test_unknown_base_profile_returns_error_payload(self):
        result = ap.resolve_effective_profile(MINIMAL_CATALOG, "nonexistent", [])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_PROFILE")

    def test_unknown_overlay_returns_error_payload(self):
        result = ap.resolve_effective_profile(MINIMAL_CATALOG, "pos", ["nosuchoverlay"])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_OVERLAY")


# ── T2: Settings read/write ─────────────────────────────────────────────────

class TestSettingsReadWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / ".claude").mkdir()
        # Write catalog
        catalog_dir = self.cwd / "catalog"
        catalog_dir.mkdir()
        self.catalog_path = catalog_dir / "agent-profiles.json"
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))

    def tearDown(self):
        self.tmp.cleanup()

    def _apply(self, base, overlays=None, dry_run=False):
        return ap.apply_profile(
            self.cwd, base, overlays or [], catalog_path=self.catalog_path, dry_run=dry_run
        )

    def test_apply_creates_agent_profile_json(self):
        self._apply("pos")
        binding_path = self.cwd / ".claude" / "agent-profile.json"
        self.assertTrue(binding_path.exists())
        data = json.loads(binding_path.read_text())
        self.assertEqual(data["base"], "pos")

    def test_apply_preserves_unknown_settings_keys(self):
        settings_path = self.cwd / ".claude" / "settings.json"
        settings_path.write_text(json.dumps({
            "permissions": {"allow": ["Bash(git:*)"]},
            "hooks": {},
            "mcpServers": {"myserver": {"command": "python"}},
        }))
        self._apply("pos")
        data = json.loads(settings_path.read_text())
        self.assertIn("permissions", data)
        self.assertEqual(data["permissions"]["allow"], ["Bash(git:*)"])
        self.assertIn("hooks", data)
        self.assertIn("mcpServers", data)

    def test_apply_updates_only_enabled_plugins_and_marker(self):
        self._apply("pos")
        settings_path = self.cwd / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text())
        self.assertIn("enabledPlugins", data)
        self.assertIn("h2tAgentProfile", data)
        # enabledPlugins must not contain raw aliases, only resolved IDs
        for key in data["enabledPlugins"]:
            self.assertIn("@", key, f"Plugin id missing @ suffix: {key}")

    def test_apply_does_not_modify_permissions(self):
        settings_path = self.cwd / ".claude" / "settings.json"
        original_perms = {"allow": ["Bash(git:*)", "Bash(python:*)"]}
        settings_path.write_text(json.dumps({"permissions": original_perms}))
        self._apply("pos")
        data = json.loads(settings_path.read_text())
        self.assertEqual(data["permissions"], original_perms)

    def test_reset_returns_to_base_without_overlays(self):
        # First apply with overlay
        self._apply("pos", ["creative"])
        # Then reset
        ap.reset_profile(self.cwd, catalog_path=self.catalog_path)
        binding = json.loads((self.cwd / ".claude" / "agent-profile.json").read_text())
        self.assertEqual(binding["overlays"], [])

    def test_add_overlay_updates_binding_and_settings(self):
        self._apply("pos")
        ap.add_overlay(self.cwd, "marketing", catalog_path=self.catalog_path)
        binding = json.loads((self.cwd / ".claude" / "agent-profile.json").read_text())
        self.assertIn("marketing", binding["overlays"])
        settings = json.loads((self.cwd / ".claude" / "settings.json").read_text())
        self.assertTrue(settings["enabledPlugins"].get("marketing-playbook@marketing-playbook-plugins"))

    def test_add_multiple_overlays_stacks_work_contexts_for_one_repo(self):
        self._apply("pos")
        ap.add_overlay(self.cwd, "marketing", catalog_path=self.catalog_path)
        ap.add_overlay(self.cwd, "creative", catalog_path=self.catalog_path)

        binding = json.loads((self.cwd / ".claude" / "agent-profile.json").read_text())
        self.assertEqual(binding["base"], "pos")
        self.assertEqual(binding["overlays"], ["marketing", "creative"])

        settings = json.loads((self.cwd / ".claude" / "settings.json").read_text())
        self.assertTrue(settings["enabledPlugins"].get("marketing-playbook@marketing-playbook-plugins"))
        self.assertTrue(settings["enabledPlugins"].get("lead-search@lead-search-plugins"))
        self.assertTrue(settings["enabledPlugins"].get("h2t-creative@lichtpfad"))

    def test_remove_overlay_updates_binding_and_settings(self):
        self._apply("pos", ["marketing"])
        ap.remove_overlay(self.cwd, "marketing", catalog_path=self.catalog_path)
        binding = json.loads((self.cwd / ".claude" / "agent-profile.json").read_text())
        self.assertNotIn("marketing", binding["overlays"])
        settings = json.loads((self.cwd / ".claude" / "settings.json").read_text())
        # marketing-playbook should be false or absent after removal
        mp_id = "marketing-playbook@marketing-playbook-plugins"
        self.assertFalse(settings["enabledPlugins"].get(mp_id, False))


# ── T3: CLI modes ───────────────────────────────────────────────────────────

class TestCLIModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / ".claude").mkdir()
        self.catalog_path = self.cwd / "catalog" / "agent-profiles.json"
        self.catalog_path.parent.mkdir()
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, args):
        return ap.run_cli(args, catalog_path=self.catalog_path)

    def test_cli_status_without_profile_returns_unconfigured(self):
        result = self._run(["status", "--cwd", str(self.cwd)])
        self.assertEqual(result["status"], "unconfigured")

    def test_cli_diff_does_not_write_files(self):
        self._run(["diff", "--cwd", str(self.cwd), "--base", "pos"])
        profile_path = self.cwd / ".claude" / "agent-profile.json"
        self.assertFalse(profile_path.exists())

    def test_cli_sync_uses_existing_binding(self):
        binding = {"base": "pos", "overlays": [], "catalogVersion": 1, "updatedAt": "2026-05-21"}
        (self.cwd / ".claude" / "agent-profile.json").write_text(json.dumps(binding))
        result = self._run(["sync", "--cwd", str(self.cwd)])
        self.assertIn("enabledPlugins", result)

    def test_cli_doctor_reports_without_installing(self):
        result = self._run(["doctor", "--cwd", str(self.cwd)])
        # doctor must not return an "installed" action
        self.assertNotIn("installed", result)
        self.assertIn("checks", result)

    def test_cli_outputs_json(self):
        result = self._run(["status", "--cwd", str(self.cwd)])
        # result must be a dict (JSON-serialisable)
        self.assertIsInstance(result, dict)
        json.dumps(result)  # must not raise


class TestCLIRecommend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / ".claude").mkdir()
        self.catalog_path = self.cwd / "catalog" / "agent-profiles.json"
        self.catalog_path.parent.mkdir()
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))

    def tearDown(self):
        self.tmp.cleanup()

    def test_cli_recommend_plugin_repo_returns_dev(self):
        # Create plugin marker
        (self.cwd / ".claude-plugin").mkdir()
        (self.cwd / ".claude-plugin" / "marketplace.json").write_text("{}")
        result = ap.run_cli(["recommend", "--cwd", str(self.cwd)], catalog_path=self.catalog_path)
        self.assertEqual(result["recommended"], "dev")

    def test_cli_recommend_unknown_returns_mixed(self):
        result = ap.run_cli(["recommend", "--cwd", str(self.cwd)], catalog_path=self.catalog_path)
        self.assertEqual(result["recommended"], "mixed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
