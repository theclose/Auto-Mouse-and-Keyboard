"""
Tests for core.macro_templates — template loading and action creation.
"""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Import action modules
# Import action modules to register all types before testing templates
import core.scheduler  # noqa: F401 — registers set_variable, delay, loop
import modules.image  # noqa: F401 — registers wait_for_image, click_on_image
import modules.keyboard  # noqa: F401 — registers type_text
import modules.mouse  # noqa: F401 — registers mouse_click
import modules.screen  # noqa: F401 — registers take_screenshot
import modules.system  # noqa: F401 — registers read_file_line, write_to_file
from core.action import Action
from core.macro_templates import (
    BUILTIN_TEMPLATES,
    create_actions_from_template,
    get_templates,
)


class TestBuiltinTemplates:
    def test_has_10_builtin_templates(self):
        assert len(BUILTIN_TEMPLATES) == 10

    def test_templates_have_required_keys(self):
        for t in BUILTIN_TEMPLATES:
            assert "name" in t
            assert "description" in t
            assert "actions" in t
            assert isinstance(t["actions"], list)
            assert len(t["actions"]) > 0

    def test_template_names(self):
        names = [t["name"] for t in BUILTIN_TEMPLATES]
        assert any("Form" in n for n in names)
        assert any("Image" in n for n in names)
        assert any("Login" in n for n in names)
        assert any("Screenshot" in n for n in names)
        assert any("CSV" in n for n in names)
        assert any("Retry" in n for n in names)
        assert any("Clicker" in n or "Click tự động" in n for n in names)
        assert any("Clipboard" in n or "Copy-Paste" in n for n in names)
        assert any("Restart" in n or "Giám sát" in n for n in names)
        assert any("Batch" in n or "Nhập hàng loạt" in n for n in names)

    def test_actions_have_type(self):
        for t in BUILTIN_TEMPLATES:
            for a in t["actions"]:
                assert "type" in a, f"Missing 'type' in template '{t['name']}'"


class TestGetTemplates:
    def test_returns_at_least_builtin(self):
        templates = get_templates()
        assert len(templates) >= 6

    def test_returns_list(self):
        assert isinstance(get_templates(), list)

    def test_custom_template_loading(self, tmp_path, monkeypatch):
        """Test loading custom templates from templates/ directory."""
        # Create a temporary templates directory
        custom = {
            "name": "Custom Template",
            "description": "Test custom template",
            "actions": [
                {"type": "delay", "duration_ms": 100}
            ],
        }
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "custom.json").write_text(
            json.dumps(custom), encoding="utf-8")

        # Monkeypatch TEMPLATES_DIR to use tmp_path/templates
        import core.app_paths
        monkeypatch.setattr(core.app_paths, "TEMPLATES_DIR", templates_dir)

        templates = get_templates()
        assert len(templates) >= 7
        assert any(t["name"] == "Custom Template" for t in templates)

    def test_invalid_json_file_skipped(self, tmp_path, monkeypatch):
        """Invalid JSON files should be skipped, not crash."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "bad.json").write_text("NOT JSON!", encoding="utf-8")

        import core.app_paths
        monkeypatch.setattr(core.app_paths, "TEMPLATES_DIR", templates_dir)

        templates = get_templates()
        # Should still return builtin templates without crash
        assert len(templates) >= 6


class TestCreateActionsFromTemplate:
    def test_form_filling_template(self):
        template = BUILTIN_TEMPLATES[0]  # Form Filling
        actions = create_actions_from_template(template)
        assert len(actions) == len(template["actions"])
        assert all(isinstance(a, Action) for a in actions)

    def test_actions_have_delay(self):
        template = BUILTIN_TEMPLATES[0]
        actions = create_actions_from_template(template)
        for i, action in enumerate(actions):
            expected = template["actions"][i].get("delay_after", 100)
            assert action.delay_after == expected

    def test_actions_have_description(self):
        template = BUILTIN_TEMPLATES[0]
        actions = create_actions_from_template(template)
        for i, action in enumerate(actions):
            expected = template["actions"][i].get("description", "")
            assert action.description == expected

    def test_all_builtin_templates_produce_actions(self):
        for template in BUILTIN_TEMPLATES:
            actions = create_actions_from_template(template)
            assert len(actions) > 0, f"Template '{template['name']}' produced 0 actions"

    def test_unknown_type_skipped(self):
        template = {
            "name": "test",
            "actions": [
                {"type": "nonexistent_action_xyz", "delay_after": 0},
                {"type": "delay", "duration_ms": 100, "delay_after": 0},
            ]
        }
        actions = create_actions_from_template(template)
        assert len(actions) == 1  # Only delay created

    def test_empty_template(self):
        template = {"name": "empty", "actions": []}
        actions = create_actions_from_template(template)
        assert len(actions) == 0
