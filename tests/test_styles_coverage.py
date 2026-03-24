"""
Tests for gui.styles — theme generation, font size, system theme detection.
"""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui.styles import (
    get_theme, get_system_theme,
    DARK_THEME, LIGHT_THEME, DARK_COLORS, LIGHT_COLORS,
    _build_theme,
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
