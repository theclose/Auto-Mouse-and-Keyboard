"""
Tests for gui.styles — theme generation, font size, system theme detection.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui.styles import (
    ACCENT_PRESETS,
    DARK_COLORS,
    DARK_THEME,
    LIGHT_COLORS,
    LIGHT_THEME,
    _build_theme,
    get_system_theme,
    get_theme,
)


class TestGetTheme:
    def test_dark(self):
        qss = get_theme("dark")
        assert len(qss) > 100
        assert "background-color" in qss

    def test_light(self):
        qss = get_theme("light")
        assert len(qss) > 100

    def test_auto(self):
        qss = get_theme("auto")
        assert len(qss) > 100

    def test_default_font_size(self):
        qss = get_theme("dark")
        assert "font-size: 10pt" in qss

    def test_custom_font_size(self):
        qss = get_theme("dark", font_size=14)
        assert "font-size: 14pt" in qss
        assert "font-size: 10pt" not in qss

    def test_font_size_min_clamp(self):
        qss = get_theme("dark", font_size=2)
        assert "font-size: 8pt" in qss

    def test_font_size_max_clamp(self):
        qss = get_theme("dark", font_size=99)
        assert "font-size: 16pt" in qss

    def test_font_size_8(self):
        qss = get_theme("dark", font_size=8)
        assert "font-size: 8pt" in qss

    def test_font_size_16(self):
        qss = get_theme("dark", font_size=16)
        assert "font-size: 16pt" in qss

    def test_font_size_10_no_change(self):
        qss10 = get_theme("dark", font_size=10)
        qss_default = get_theme("dark")
        assert qss10 == qss_default


class TestPrebuiltThemes:
    def test_dark_theme_exists(self):
        assert len(DARK_THEME) > 100

    def test_light_theme_exists(self):
        assert len(LIGHT_THEME) > 100

    def test_dark_has_dark_bg(self):
        assert DARK_COLORS["bg_primary"] in DARK_THEME

    def test_light_has_light_bg(self):
        assert LIGHT_COLORS["bg_primary"] in LIGHT_THEME

    def test_themes_differ(self):
        assert DARK_THEME != LIGHT_THEME


class TestBuildTheme:
    def test_builds_from_colors(self):
        qss = _build_theme(DARK_COLORS)
        assert isinstance(qss, str)
        assert len(qss) > 100

    def test_all_colors_substituted(self):
        qss = _build_theme(DARK_COLORS)
        # No unsubstituted Python format placeholders like {bg_primary}
        import re
        unsubstituted = re.findall(r'\{[a-z_]+\}', qss)
        assert len(unsubstituted) == 0, f"Unsubstituted: {unsubstituted}"


class TestGetSystemTheme:
    def test_returns_valid(self):
        result = get_system_theme()
        assert result in ("dark", "light")

    def test_returns_string(self):
        assert isinstance(get_system_theme(), str)


class TestAccentPresets:
    """BS-4: Verify all accent × theme combos generate valid QSS."""

    def test_all_presets_parse(self):
        """Every accent preset × dark/light must produce valid QSS."""
        for accent_name in ACCENT_PRESETS:
            for pref in ("dark", "light"):
                qss = get_theme(pref, accent=accent_name)
                assert len(qss) > 100, (
                    f"QSS too short for {accent_name}/{pref}: {len(qss)} chars"
                )

    def test_accent_color_appears_in_output(self):
        """The actual accent hex color must appear in the generated QSS."""
        for accent_name, colors in ACCENT_PRESETS.items():
            qss = get_theme("dark", accent=accent_name)
            assert colors["accent"] in qss, (
                f"Accent color {colors['accent']} missing from QSS for preset '{accent_name}'"
            )

    def test_no_unsubstituted_placeholders(self):
        """No {placeholder} should remain in any theme output."""
        import re
        for accent_name in ACCENT_PRESETS:
            for pref in ("dark", "light"):
                qss = get_theme(pref, accent=accent_name)
                unsubstituted = re.findall(r'\{[a-z_]+\}', qss)
                assert len(unsubstituted) == 0, (
                    f"Unsubstituted in {accent_name}/{pref}: {unsubstituted}"
                )
