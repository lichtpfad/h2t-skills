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
        self.assertEqual(result["error"]["code"], "UNKNOWN_WORK_CONTEXT")


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


class TestWorkContextRefs(unittest.TestCase):
    """Tests for profile:/overlay: ref syntax and bare-name fallback."""

    CATALOG_WITH_OVERLAP = {
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
            "dev": {
                "description": "dev",
                "enable": ["h2t-core", "h2t-dev", "superpowers"],
                "disable": ["h2t-creative", "marketing-playbook"],
            },
            "creative": {
                "description": "Full creative base profile",
                "enable": ["h2t-core", "h2t-creative", "superpowers"],
                "disable": ["marketing-playbook"],
            },
        },
        "overlays": {
            "creative": {
                "description": "Light creative overlay",
                "enable": ["h2t-creative"],
                "disable": [],
            },
            "github-heavy": {
                "description": "PR workflows",
                "enable": ["h2t-dev"],
                "disable": [],
            },
        },
    }

    def _resolve(self, base, overlays):
        return ap.resolve_effective_profile(self.CATALOG_WITH_OVERLAP, base, overlays)

    def test_profile_ref_resolves_base_profile(self):
        result = self._resolve("dev", ["profile:creative"])
        self.assertNotIn("error", result)
        self.assertIn("h2t-core@lichtpfad", result["enabled"])
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])

    def test_overlay_ref_resolves_overlay_only(self):
        result = self._resolve("dev", ["overlay:creative"])
        self.assertNotIn("error", result)
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])

    def test_bare_name_prefers_overlay_over_base_profile(self):
        result = self._resolve("dev", ["creative"])
        self.assertNotIn("error", result)
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])

    def test_profile_ref_for_missing_profile_returns_error(self):
        result = self._resolve("dev", ["profile:nonexistent"])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_PROFILE_CONTEXT")

    def test_overlay_ref_for_missing_overlay_returns_error(self):
        result = self._resolve("dev", ["overlay:nonexistent"])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_OVERLAY")

    def test_bare_unknown_name_returns_error(self):
        result = self._resolve("dev", ["totallyunknown"])
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_WORK_CONTEXT")

    def test_mixed_refs_resolve_in_order(self):
        result = self._resolve("dev", ["profile:creative", "overlay:github-heavy"])
        self.assertNotIn("error", result)
        self.assertIn("h2t-creative@lichtpfad", result["enabled"])
        self.assertIn("h2t-dev@lichtpfad", result["enabled"])


class TestAddContextRef(unittest.TestCase):
    """Tests for add_overlay() with work-context refs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / ".claude").mkdir()
        self.catalog_path = self.cwd / "catalog" / "agent-profiles.json"
        self.catalog_path.parent.mkdir()
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))
        # Set base profile first
        ap.apply_profile(self.cwd, "pos", [], catalog_path=self.catalog_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_overlay_accepts_profile_ref(self):
        # "profile:dev" should be accepted because dev is a valid base profile
        result = ap.add_overlay(self.cwd, "profile:dev", catalog_path=self.catalog_path)
        self.assertNotIn("error", result)
        binding = json.loads((self.cwd / ".claude" / "agent-profile.json").read_text())
        self.assertIn("profile:dev", binding["overlays"])

    def test_add_overlay_accepts_bare_name_overlay(self):
        result = ap.add_overlay(self.cwd, "marketing", catalog_path=self.catalog_path)
        self.assertNotIn("error", result)

    def test_add_overlay_rejects_unknown_ref(self):
        result = ap.add_overlay(self.cwd, "profile:nonexistent", catalog_path=self.catalog_path)
        self.assertIn("error", result)

    def test_cli_add_accepts_context_flag(self):
        result = ap.run_cli(
            ["add", "--cwd", str(self.cwd), "--context", "profile:dev"],
            catalog_path=self.catalog_path,
        )
        self.assertNotIn("error", result)

    def test_cli_add_overlay_flag_still_works(self):
        # --overlay backward compat
        result = ap.run_cli(
            ["add", "--cwd", str(self.cwd), "--overlay", "marketing"],
            catalog_path=self.catalog_path,
        )
        self.assertNotIn("error", result)


class TestCatalogSubcommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.catalog_path = Path(self.tmp.name) / "agent-profiles.json"
        self.catalog_path.write_text(json.dumps(MINIMAL_CATALOG))

    def tearDown(self):
        self.tmp.cleanup()

    def test_catalog_list_returns_profile_and_overlay_names(self):
        result = ap.catalog_list(catalog_path=self.catalog_path)
        self.assertIn("baseProfiles", result)
        self.assertIn("overlays", result)
        self.assertIn("pos", result["baseProfiles"])

    def test_catalog_list_plugins_returns_plugin_ids(self):
        result = ap.catalog_list_plugins(catalog_path=self.catalog_path)
        self.assertIn("pluginIds", result)
        self.assertIn("h2t-core", result["pluginIds"])

    def test_catalog_add_profile_writes_new_entry(self):
        result = ap.catalog_add_profile(
            name="test-profile",
            description="Test",
            enable=["h2t-core"],
            disable=["h2t-creative"],
            catalog_path=self.catalog_path,
        )
        self.assertTrue(result.get("ok"))
        catalog = json.loads(self.catalog_path.read_text())
        self.assertIn("test-profile", catalog["baseProfiles"])

    def test_catalog_add_profile_rejects_unknown_alias(self):
        result = ap.catalog_add_profile(
            name="bad",
            description="Test",
            enable=["nonexistent-alias"],
            disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "UNKNOWN_PLUGIN_ALIAS")

    def test_catalog_add_profile_rejects_duplicate(self):
        result = ap.catalog_add_profile(
            name="pos",
            description="dup",
            enable=["h2t-core"],
            disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "PROFILE_EXISTS")

    def test_catalog_edit_profile_add_enable_removes_from_disable(self):
        # pos has h2t-creative in disable; add-enable h2t-creative must remove it
        result = ap.catalog_edit_profile(
            name="pos",
            add_enable=["h2t-creative"],
            add_disable=[],
            remove_enable=[],
            remove_disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertTrue(result.get("ok"))
        catalog = json.loads(self.catalog_path.read_text())
        self.assertIn("h2t-creative", catalog["baseProfiles"]["pos"]["enable"])
        self.assertNotIn("h2t-creative", catalog["baseProfiles"]["pos"]["disable"])

    def test_catalog_edit_rejects_unknown_alias(self):
        result = ap.catalog_edit_profile(
            name="pos",
            add_enable=["no-such-alias"],
            add_disable=[],
            remove_enable=[],
            remove_disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertIn("error", result)

    def test_catalog_add_overlay_writes_new_entry(self):
        result = ap.catalog_add_overlay(
            name="test-overlay",
            description="Test overlay",
            enable=["h2t-ops"],
            disable=[],
            catalog_path=self.catalog_path,
        )
        self.assertTrue(result.get("ok"))
        catalog = json.loads(self.catalog_path.read_text())
        self.assertIn("test-overlay", catalog["overlays"])

    def test_catalog_write_is_atomic(self):
        ap.catalog_add_profile(
            name="atomic-test",
            description="Test",
            enable=["h2t-core"],
            disable=[],
            catalog_path=self.catalog_path,
        )
        tmp_path = self.catalog_path.with_suffix(".tmp")
        self.assertFalse(tmp_path.exists())

    def test_catalog_refuses_cache_path(self):
        cache_path = Path(self.tmp.name) / "plugins" / "cache" / "agent-profiles.json"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text(json.dumps(MINIMAL_CATALOG))
        result = ap.catalog_add_profile(
            name="x", description="x", enable=[], disable=[],
            catalog_path=cache_path,
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "CACHE_PATH")


if __name__ == "__main__":
    unittest.main(verbosity=2)
