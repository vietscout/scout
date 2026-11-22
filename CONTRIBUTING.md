# Contributing Themes & Plugins

`pro-github-starter-kit` uses an extensible **Theme + Plugin** architecture (inspired by Obsidian). Anyone can contribute a new Theme or Plugin via a Pull Request without modifying `setup.py`.

---

## 1. How to Add a New Theme

Create a directory `themes/<theme-id>/` with two files:

1. **`themes/<theme-id>/theme.json`**
   ```json
   {
     "id": "your-theme-id",
     "name": "Your Theme Name",
     "description": "One-line summary of the layout style.",
     "author": "your-github-username"
   }
   ```
2. **`themes/<theme-id>/README.template.md`**
   - Use `{{USERNAME}}` wherever the user's GitHub handle should appear.
   - Include `{{PLUGINS}}` where selected plugins should be injected.
3. **Optional Preview Files:**
   - Add `themes/<theme-id>/preview.svg` (`320×180`) and `themes/<theme-id>/PREVIEW.md` — `README.md` automatically picks them up when your PR is merged!

---

## 2. How to Add a New Plugin

Create a directory `plugins/<plugin-id>/` with two required files (and an optional workflow):

1. **`plugins/<plugin-id>/plugin.json`**
   ```json
   {
     "id": "your-plugin-id",
     "name": "Your Plugin Name",
     "description": "What this block adds to the profile.",
     "author": "your-github-username",
     "workflow_file": "optional-workflow-name.yml",
     "defaults": {
       "CUSTOM_VAR": "default-value"
     }
   }
   ```
2. **`plugins/<plugin-id>/snippet.md`** — The Markdown block injected into `{{PLUGINS}}`.
3. **`plugins/<plugin-id>/workflow.yml`** *(optional)* — GitHub Actions workflow copied into `.github/workflows/` when the plugin is enabled.

---

## 3. Validate Locally Before Opening a PR

```bash
python setup.py --validate
python -m unittest discover -s tests -v
```
