#!/usr/bin/env python3
"""Zero-dependency CLI to compose a GitHub Profile README from extensible themes and plugins."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
THEMES_DIR = ROOT_DIR / "themes"
PLUGINS_DIR = ROOT_DIR / "plugins"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def load_json(path: Path) -> dict[str, Any]:
    """Load and parse a JSON manifest file."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Manifest must be a JSON object: {path}")
    return data


def discover_themes(themes_dir: Path = THEMES_DIR) -> dict[str, dict[str, Any]]:
    """Discover all themes in themes/<id>/theme.json."""
    themes: dict[str, dict[str, Any]] = {}
    if not themes_dir.exists():
        return themes
    for item in sorted(themes_dir.iterdir()):
        if not item.is_dir():
            continue
        manifest_path = item / "theme.json"
        if manifest_path.exists():
            data = load_json(manifest_path)
            themes[item.name] = {**data, "_dir": item}
    return themes


def discover_plugins(plugins_dir: Path = PLUGINS_DIR) -> dict[str, dict[str, Any]]:
    """Discover all plugins in plugins/<id>/plugin.json."""
    plugins: dict[str, dict[str, Any]] = {}
    if not plugins_dir.exists():
        return plugins
    for item in sorted(plugins_dir.iterdir()):
        if not item.is_dir():
            continue
        manifest_path = item / "plugin.json"
        if manifest_path.exists():
            data = load_json(manifest_path)
            plugins[item.name] = {**data, "_dir": item}
    return plugins


def validate_extensions(
    themes_dir: Path = THEMES_DIR,
    plugins_dir: Path = PLUGINS_DIR,
) -> list[str]:
    """Validate all theme and plugin manifests and required files. Returns list of errors."""
    errors: list[str] = []

    if not themes_dir.exists():
        errors.append(f"Missing themes directory: {themes_dir}")
    else:
        for item in sorted(themes_dir.iterdir()):
            if not item.is_dir():
                continue
            manifest = item / "theme.json"
            template = item / "README.template.md"
            if not manifest.exists():
                errors.append(f"Theme '{item.name}' is missing theme.json")
                continue
            try:
                data = load_json(manifest)
            except Exception as exc:
                errors.append(f"Theme '{item.name}' invalid JSON: {exc}")
                continue
            for key in ("id", "name", "description", "author"):
                if not data.get(key):
                    errors.append(f"Theme '{item.name}' theme.json missing '{key}'")
            if not template.exists():
                errors.append(f"Theme '{item.name}' is missing README.template.md")
            else:
                text = template.read_text(encoding="utf-8")
                if "{{PLUGINS}}" not in text:
                    errors.append(f"Theme '{item.name}' README.template.md must include '{{{{PLUGINS}}}}' slot")

    if not plugins_dir.exists():
        errors.append(f"Missing plugins directory: {plugins_dir}")
    else:
        for item in sorted(plugins_dir.iterdir()):
            if not item.is_dir():
                continue
            manifest = item / "plugin.json"
            snippet = item / "snippet.md"
            if not manifest.exists():
                errors.append(f"Plugin '{item.name}' is missing plugin.json")
                continue
            try:
                data = load_json(manifest)
            except Exception as exc:
                errors.append(f"Plugin '{item.name}' invalid JSON: {exc}")
                continue
            for key in ("id", "name", "description", "author"):
                if not data.get(key):
                    errors.append(f"Plugin '{item.name}' plugin.json missing '{key}'")
            if not snippet.exists():
                errors.append(f"Plugin '{item.name}' is missing snippet.md")
            else:
                snippet_text = snippet.read_text(encoding="utf-8")
                defaults = data.get("defaults", {}) or {}
                wf_path = item / "workflow.yml"
                combined_text = snippet_text
                wf_name = str(data.get("workflow_file", f"{item.name}.yml"))
                if Path(wf_name).name != wf_name or ".." in wf_name or not wf_name.endswith((".yml", ".yaml")):
                    errors.append(f"Plugin '{item.name}' has unsafe workflow_file '{wf_name}'")
                if wf_path.exists():
                    wf_text = wf_path.read_text(encoding="utf-8")
                    combined_text += "\n" + wf_text
                    for required_key in ("name:", "on:", "jobs:"):
                        if required_key not in wf_text:
                            errors.append(f"Plugin '{item.name}' workflow.yml missing '{required_key}'")
                for ph in re.findall(r"\{\{([A-Z0-9_]+)\}\}", combined_text):
                    if ph != "USERNAME" and ph not in defaults:
                        errors.append(
                            f"Plugin '{item.name}' uses '{{{{{ph}}}}}' without a default in plugin.json"
                        )

    return errors


def parse_vars(raw_vars: list[str]) -> dict[str, str]:
    """Parse KEY=VALUE pairs from --var arguments."""
    parsed: dict[str, str] = {}
    for entry in raw_vars:
        if "=" not in entry:
            raise ValueError(f"Invalid --var '{entry}'. Expected KEY=VALUE format.")
        key, value = entry.split("=", 1)
        key = key.strip()
        val = value.strip()
        if not key:
            raise ValueError(f"Empty key in --var '{entry}'.")
        if "\n" in val or "\r" in val:
            raise ValueError(f"Invalid newline character in --var '{key}'.")
        parsed[key] = val
    return parsed


def render_placeholders(text: str, variables: dict[str, str]) -> str:
    """Replace {{KEY}} placeholders using provided variables (supports nested {{USERNAME}})."""
    rendered = text
    for _ in range(2):
        for key, value in variables.items():
            val = value
            if key == "TYPING_LINES" and " " in val:
                val = val.replace(" ", "+")
            rendered = rendered.replace(f"{{{{{key}}}}}", val)
    return rendered


def compose_profile(
    *,
    username: str,
    theme_id: str,
    plugin_ids: list[str],
    variables: dict[str, str],
    themes_dir: Path = THEMES_DIR,
    plugins_dir: Path = PLUGINS_DIR,
) -> tuple[str, list[tuple[str, str]]]:
    """Render README.md content and collect (workflow_filename, workflow_content) pairs."""
    if not USERNAME_PATTERN.match(username):
        raise ValueError(f"Invalid GitHub username '{username}'.")

    themes = discover_themes(themes_dir)
    if theme_id not in themes:
        available = ", ".join(themes.keys()) or "(none)"
        raise ValueError(f"Unknown theme '{theme_id}'. Available: {available}")

    plugins = discover_plugins(plugins_dir)
    for pid in plugin_ids:
        if pid not in plugins:
            available = ", ".join(plugins.keys()) or "(none)"
            raise ValueError(f"Unknown plugin '{pid}'. Available: {available}")

    merged_vars: dict[str, str] = {"USERNAME": username}
    theme_defaults = themes[theme_id].get("defaults", {})
    if isinstance(theme_defaults, dict):
        for k, v in theme_defaults.items():
            merged_vars[str(k)] = str(v)
    for pid in plugin_ids:
        defaults = plugins[pid].get("defaults", {})
        if isinstance(defaults, dict):
            for k, v in defaults.items():
                merged_vars.setdefault(str(k), str(v))
    merged_vars.update(variables)

    plugin_blocks: list[str] = []
    workflows: list[tuple[str, str]] = []

    for pid in plugin_ids:
        pdir: Path = plugins[pid]["_dir"]
        snippet = (pdir / "snippet.md").read_text(encoding="utf-8").strip()
        plugin_blocks.append(render_placeholders(snippet, merged_vars))

        wf_path = pdir / "workflow.yml"
        if wf_path.exists():
            wf_name = str(plugins[pid].get("workflow_file", f"{pid}.yml"))
            if Path(wf_name).name != wf_name or ".." in wf_name:
                raise ValueError(f"Unsafe workflow_file '{wf_name}' in plugin '{pid}'.")
            wf_content = render_placeholders(wf_path.read_text(encoding="utf-8"), merged_vars)
            workflows.append((wf_name, wf_content))

    plugins_section = "\n\n".join(plugin_blocks)
    theme_dir: Path = themes[theme_id]["_dir"]
    template_text = (theme_dir / "README.template.md").read_text(encoding="utf-8")

    output = template_text.replace("{{PLUGINS}}", plugins_section)
    output = render_placeholders(output, merged_vars)
    output = re.sub(r"\n{3,}", "\n\n", output).strip() + "\n"
    return output, workflows


def list_catalog(themes_dir: Path = THEMES_DIR, plugins_dir: Path = PLUGINS_DIR) -> None:
    """Print available themes and plugins."""
    themes = discover_themes(themes_dir)
    plugins = discover_plugins(plugins_dir)

    print("Available Themes:")
    for tid, data in themes.items():
        print(f"  - {tid}: {data.get('name')} — {data.get('description')} (by {data.get('author')})")

    print("\nAvailable Plugins:")
    for pid, data in plugins.items():
        wf = " [includes workflow]" if (data["_dir"] / "workflow.yml").exists() else ""
        print(f"  - {pid}: {data.get('name')}{wf} — {data.get('description')}")


def interactive_wizard(
    themes_dir: Path = THEMES_DIR,
    plugins_dir: Path = PLUGINS_DIR,
) -> tuple[str, str, list[str], dict[str, str]]:
    """Guided Q&A prompt for beginners who prefer not to pass CLI flags."""
    themes = discover_themes(themes_dir)
    plugins = discover_plugins(plugins_dir)
    theme_ids = list(themes.keys())
    plugin_ids_all = list(plugins.keys())

    print("=== Pro GitHub Starter Kit — Interactive Setup ===\n")
    username = input("1. Enter your GitHub username: ").strip()
    if not USERNAME_PATTERN.match(username):
        raise ValueError(f"Invalid GitHub username '{username}'.")

    print("\n2. Choose a Theme:")
    for idx, tid in enumerate(theme_ids, start=1):
        print(f"  [{idx}] {tid} — {themes[tid].get('description')}")
    raw_theme = input(f"Enter number [1-{len(theme_ids)}] (default 1): ").strip()
    theme_idx = int(raw_theme) - 1 if raw_theme else 0
    if not (0 <= theme_idx < len(theme_ids)):
        raise ValueError("Theme selection out of range.")
    chosen_theme = theme_ids[theme_idx]

    print("\n3. Choose Plugins (comma-separated numbers, or press Enter for none):")
    for idx, pid in enumerate(plugin_ids_all, start=1):
        print(f"  [{idx}] {pid} — {plugins[pid].get('description')}")
    raw_plugins = input("Plugins (e.g. 1,4,6): ").strip()
    chosen_plugins: list[str] = []
    if raw_plugins:
        for token in raw_plugins.split(","):
            token = token.strip()
            if not token:
                continue
            p_idx = int(token) - 1
            if not (0 <= p_idx < len(plugin_ids_all)):
                raise ValueError(f"Plugin selection '{token}' out of range.")
            pid = plugin_ids_all[p_idx]
            if pid not in chosen_plugins:
                chosen_plugins.append(pid)

    variables: dict[str, str] = {}
    for pid in chosen_plugins:
        defaults = plugins[pid].get("defaults", {})
        if isinstance(defaults, dict):
            for key, default_val in defaults.items():
                rendered_default = str(default_val).replace("{{USERNAME}}", username)
                val = input(f"  -> {pid} | {key} (Enter for '{rendered_default}'): ").strip()
                if val:
                    variables[str(key)] = val

    return username, chosen_theme, chosen_plugins, variables


def _replace_marker_block(text: str, marker: str, body: str) -> str:
    """Replace content between <!-- MARKER:START --> and <!-- MARKER:END -->."""
    start_tag = f"<!-- {marker}:START -->"
    end_tag = f"<!-- {marker}:END -->"
    pattern = re.compile(
        re.escape(start_tag) + r".*?" + re.escape(end_tag),
        re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError(f"Missing {start_tag} / {end_tag} markers in README.md")
    replacement = f"{start_tag}\n{body.strip()}\n{end_tag}"
    return pattern.sub(lambda _: replacement, text, count=1)


def _render_grid_cells(cells: list[str], columns: int = 3) -> str:
    """Format HTML table cells into a balanced N-column GitHub Markdown gallery."""
    rows: list[str] = ["<table>"]
    width_pct = int(100 / columns)
    for idx in range(0, len(cells), columns):
        rows.append("  <tr>")
        chunk = cells[idx : idx + columns]
        for cell in chunk:
            rows.append(f'    <td align="center" valign="top" width="{width_pct}%">\n{cell}\n    </td>')
        for _ in range(columns - len(chunk)):
            rows.append(f'    <td width="{width_pct}%"></td>')
        rows.append("  </tr>")
    rows.append("</table>")
    return "\n".join(rows)


def render_themes_table(
    themes_dir: Path = THEMES_DIR,
    root_dir: Path = ROOT_DIR,
) -> str:
    """Build a 3-column visual gallery of themes from themes/*/theme.json."""
    themes = discover_themes(themes_dir)
    cells: list[str] = []
    for tid, data in themes.items():
        tdir: Path = data["_dir"]
        preview_md = f"themes/{tid}/PREVIEW.md" if (tdir / "PREVIEW.md").exists() else f"themes/{tid}/README.template.md"
        template_md = f"themes/{tid}/README.template.md"

        if (tdir / "preview.svg").exists():
            img_rel = f"themes/{tid}/preview.svg"
        elif (root_dir / "assets" / "previews" / f"{tid}.svg").exists():
            img_rel = f"assets/previews/{tid}.svg"
        else:
            img_rel = ""

        name = data.get("name", tid)
        author = str(data.get("author", "community"))
        desc = str(data.get("description", ""))
        img_tag = (
            f'      <a href="{preview_md}"><img src="{img_rel}" width="240" alt="{name} Preview"/></a><br/>\n'
            if img_rel
            else ""
        )
        cell = (
            f"{img_tag}"
            f'      <b><code>{tid}</code></b> · <a href="{preview_md}">Live Preview</a> · <a href="{template_md}">Template</a><br/>\n'
            f"      <sub>{desc} <i>(by @{author})</i></sub>"
        )
        cells.append(cell)
    return _render_grid_cells(cells, columns=3)


def render_plugins_table(
    plugins_dir: Path = PLUGINS_DIR,
    root_dir: Path = ROOT_DIR,
) -> str:
    """Build a 3-column visual gallery of plugins from plugins/*/plugin.json."""
    plugins = discover_plugins(plugins_dir)
    cells: list[str] = []
    for pid, data in plugins.items():
        pdir: Path = data["_dir"]
        desc = str(data.get("description", ""))
        author = str(data.get("author", "community"))
        wf_tag = " · <b>Auto-sync</b>" if (pdir / "workflow.yml").exists() else ""
        preview_md = f"plugins/{pid}/PREVIEW.md" if (pdir / "PREVIEW.md").exists() else f"plugins/{pid}/snippet.md"

        if (pdir / "preview.svg").exists():
            img_rel = f"plugins/{pid}/preview.svg"
        elif (root_dir / "assets" / "previews" / "plugins" / f"{pid}.svg").exists():
            img_rel = f"assets/previews/plugins/{pid}.svg"
        else:
            img_rel = ""

        name = data.get("name", pid)
        img_tag = (
            f'      <a href="{preview_md}"><img src="{img_rel}" width="240" alt="{name} Preview"/></a><br/>\n'
            if img_rel
            else ""
        )
        cell = (
            f"{img_tag}"
            f'      <b><code>{pid}</code></b> · <a href="{preview_md}">Preview</a> · <a href="plugins/{pid}/snippet.md">Snippet</a><br/>\n'
            f"      <sub>{desc}{wf_tag} <i>(by @{author})</i></sub>"
        )
        cells.append(cell)
    return _render_grid_cells(cells, columns=3)


def build_catalog_data(
    themes_dir: Path = THEMES_DIR,
    plugins_dir: Path = PLUGINS_DIR,
) -> dict[str, Any]:
    """Build JSON-serializable catalog payload for the static GitHub Pages web builder."""
    themes_raw = discover_themes(themes_dir)
    plugins_raw = discover_plugins(plugins_dir)

    themes_out: list[dict[str, Any]] = []
    for tid, data in themes_raw.items():
        tdir: Path = data["_dir"]
        themes_out.append(
            {
                "id": tid,
                "name": data.get("name", tid),
                "description": data.get("description", ""),
                "author": data.get("author", "community"),
                "defaults": data.get("defaults", {}),
                "template": (tdir / "README.template.md").read_text(encoding="utf-8"),
            }
        )

    plugins_out: list[dict[str, Any]] = []
    for pid, data in plugins_raw.items():
        pdir: Path = data["_dir"]
        wf_path = pdir / "workflow.yml"
        plugins_out.append(
            {
                "id": pid,
                "name": data.get("name", pid),
                "description": data.get("description", ""),
                "author": data.get("author", "community"),
                "defaults": data.get("defaults", {}),
                "has_workflow": wf_path.exists(),
                "workflow_file": data.get("workflow_file", f"{pid}.yml"),
                "workflow_content": wf_path.read_text(encoding="utf-8") if wf_path.exists() else "",
                "snippet": (pdir / "snippet.md").read_text(encoding="utf-8").strip(),
            }
        )

    return {"themes": themes_out, "plugins": plugins_out}


def sync_readme_catalog(
    readme_path: Path | None = None,
    themes_dir: Path = THEMES_DIR,
    plugins_dir: Path = PLUGINS_DIR,
    catalog_path: Path | None = None,
) -> bool:
    """Update auto-generated theme/plugin tables in README.md and docs/catalog.json. Returns True if changed."""
    target = readme_path or (ROOT_DIR / "README.md")
    original = target.read_text(encoding="utf-8")
    updated = _replace_marker_block(original, "THEMES-TABLE", render_themes_table(themes_dir, target.parent))
    updated = _replace_marker_block(updated, "PLUGINS-TABLE", render_plugins_table(plugins_dir, target.parent))
    changed = updated != original
    if changed:
        target.write_text(updated, encoding="utf-8")

    cat_target = catalog_path or (target.parent / "docs" / "catalog.json")
    if cat_target.parent.exists():
        new_cat = json.dumps(build_catalog_data(themes_dir, plugins_dir), indent=2, ensure_ascii=False) + "\n"
        old_cat = cat_target.read_text(encoding="utf-8") if cat_target.exists() else ""
        if new_cat != old_cat:
            cat_target.write_text(new_cat, encoding="utf-8")
            changed = True

    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compose a GitHub Profile README and workflows from modular themes and plugins."
    )
    parser.add_argument("--list", action="store_true", help="List available themes and plugins.")
    parser.add_argument("--validate", action="store_true", help="Validate all theme and plugin manifests.")
    parser.add_argument(
        "--sync-readme",
        action="store_true",
        help="Auto-update the Themes and Plugins tables in README.md from manifests.",
    )
    parser.add_argument("-i", "--interactive", action="store_true", help="Run guided interactive setup.")
    parser.add_argument("--username", help="Your GitHub username.")
    parser.add_argument("--theme", default="minimalist", help="Theme ID to use (default: minimalist).")
    parser.add_argument(
        "--plugins",
        default="",
        help="Comma-separated plugin IDs (e.g. blog-rss,github-stats).",
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        help="Custom placeholder variable in KEY=VALUE format (repeatable).",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Target directory to write README.md and .github/workflows/ (default: current directory).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview generated files without writing.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.validate:
        errors = validate_extensions()
        if errors:
            for err in errors:
                print(f"Error: {err}", file=sys.stderr)
            return 1
        print("All theme and plugin manifests are valid.")
        return 0

    if args.list:
        list_catalog()
        return 0

    if args.sync_readme:
        changed = sync_readme_catalog()
        print("Updated README.md catalog tables." if changed else "README.md catalog tables already up to date.")
        return 0

    try:
        if args.interactive or not args.username:
            username, theme_id, plugin_ids, variables = interactive_wizard()
        else:
            username = args.username
            theme_id = args.theme
            plugin_ids = [p.strip() for p in args.plugins.split(",") if p.strip()]
            variables = parse_vars(args.var)

        readme_text, workflows = compose_profile(
            username=username,
            theme_id=theme_id,
            plugin_ids=plugin_ids,
            variables=variables,
        )

        out_root = Path(args.output_dir).resolve()
        readme_path = out_root / "README.md"
        wf_dir = out_root / ".github" / "workflows"

        if args.dry_run:
            print(f"[dry-run] Would write {readme_path} ({len(readme_text)} bytes)")
            for wf_name, _ in workflows:
                print(f"[dry-run] Would write {wf_dir / wf_name}")
            return 0

        out_root.mkdir(parents=True, exist_ok=True)
        readme_path.write_text(readme_text, encoding="utf-8")
        print(f"Generated {readme_path}")

        if workflows:
            wf_dir.mkdir(parents=True, exist_ok=True)
            for wf_name, wf_content in workflows:
                target = wf_dir / wf_name
                target.write_text(wf_content, encoding="utf-8")
                print(f"Generated {target}")

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
