import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup


class TestStarterKitSetup(unittest.TestCase):
    def test_validate_extensions_passes(self) -> None:
        errors = setup.validate_extensions()
        self.assertEqual(errors, [])

    def test_discover_themes_and_plugins(self) -> None:
        themes = setup.discover_themes()
        plugins = setup.discover_plugins()
        for tid in (
            "minimalist",
            "indie-maker",
            "developer-portfolio",
            "terminal-hacker",
            "research-student",
            "dracula",
            "catppuccin",
            "serein",
            "pinkie",
        ):
            self.assertIn(tid, themes)
        for pid in (
            "blog-rss",
            "youtube-rss",
            "spotify-now-playing",
            "wakatime-stats",
            "github-stats",
            "skill-icons",
            "typing-svg",
            "activity-graph",
            "social-badges",
            "profile-views",
            "sponsor-badge",
            "snake-contribution",
        ):
            self.assertIn(pid, plugins)

    def test_compose_profile_replaces_placeholders_and_collects_workflows(self) -> None:
        readme, workflows = setup.compose_profile(
            username="octocat",
            theme_id="indie-maker",
            plugin_ids=["blog-rss", "youtube-rss", "github-stats"],
            variables={
                "BLOG_RSS_URL": "https://octocat.dev/rss.xml",
                "YOUTUBE_CHANNEL_ID": "UC123456",
            },
        )
        self.assertIn("# Hey, I'm octocat", readme)
        self.assertIn("streak-stats.demolab.com?user=octocat", readme)
        self.assertNotIn("{{PLUGINS}}", readme)
        self.assertNotIn("{{USERNAME}}", readme)

        wf_dict = dict(workflows)
        self.assertIn("blog-rss-sync.yml", wf_dict)
        self.assertIn("https://octocat.dev/rss.xml", wf_dict["blog-rss-sync.yml"])
        self.assertIn("youtube-rss-sync.yml", wf_dict)
        self.assertIn("UC123456", wf_dict["youtube-rss-sync.yml"])

    def test_cli_writes_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc = setup.main(
                [
                    "--username",
                    "octocat",
                    "--theme",
                    "minimalist",
                    "--plugins",
                    "blog-rss,skill-icons",
                    "--output-dir",
                    tmp,
                ]
            )
            self.assertEqual(rc, 0)
            out = Path(tmp)
            self.assertTrue((out / "README.md").exists())
            self.assertTrue((out / ".github" / "workflows" / "blog-rss-sync.yml").exists())

    def test_invalid_username_fails(self) -> None:
        with self.assertRaises(ValueError):
            setup.compose_profile(
                username="bad username!",
                theme_id="minimalist",
                plugin_ids=[],
                variables={},
            )

    def test_interactive_wizard_returns_expected_choices(self) -> None:
        expected_theme = sorted(setup.discover_themes().keys())[2]
        answers = iter(["octocat", "3", "3", ""])
        with patch("builtins.input", lambda _prompt="": next(answers)):
            username, theme_id, plugin_ids, variables = setup.interactive_wizard()
        self.assertEqual(username, "octocat")
        self.assertEqual(theme_id, expected_theme)
        self.assertEqual(plugin_ids, ["github-stats"])
        self.assertEqual(variables, {})

    def test_sync_readme_catalog_updates_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_readme = Path(tmp) / "README.md"
            fake_readme.write_text(
                "# Test\n\n<!-- THEMES-TABLE:START -->\nold\n<!-- THEMES-TABLE:END -->\n\n<!-- PLUGINS-TABLE:START -->\nold\n<!-- PLUGINS-TABLE:END -->\n",
                encoding="utf-8",
            )
            changed = setup.sync_readme_catalog(
                readme_path=fake_readme,
                catalog_path=Path(tmp) / "catalog.json",
            )
            self.assertTrue(changed)
            content = fake_readme.read_text(encoding="utf-8")
            self.assertIn("dracula", content)
            self.assertIn("blog-rss", content)
            self.assertFalse(
                setup.sync_readme_catalog(
                    readme_path=fake_readme,
                    catalog_path=Path(tmp) / "catalog.json",
                )
            )

    def test_typing_lines_spaces_are_encoded_in_markdown(self) -> None:
        readme, _ = setup.compose_profile(
            username="octocat",
            theme_id="minimalist",
            plugin_ids=["typing-svg"],
            variables={"TYPING_LINES": "Hello World;Open Source Builder"},
        )
        self.assertIn("lines=Hello+World;Open+Source+Builder", readme)
        self.assertNotIn("{{", readme)

    def test_all_plugins_compose_without_unreplaced_placeholders(self) -> None:
        all_pids = list(setup.discover_plugins().keys())
        readme, workflows = setup.compose_profile(
            username="octocat",
            theme_id="indie-maker",
            plugin_ids=all_pids,
            variables={},
        )
        self.assertIsNone(re.search(r"(?<!\$)\{\{[A-Z0-9_]+\}\}", readme))
        for name, wf_content in workflows:
            self.assertIsNone(
                re.search(r"(?<!\$)\{\{[A-Z0-9_]+\}\}", wf_content),
                f"Unreplaced placeholder in {name}",
            )

    def test_parse_vars_rejects_newlines(self) -> None:
        with self.assertRaises(ValueError):
            setup.parse_vars(["BLOG_RSS_URL=https://example.com\nmalicious: true"])


if __name__ == "__main__":
    unittest.main()
