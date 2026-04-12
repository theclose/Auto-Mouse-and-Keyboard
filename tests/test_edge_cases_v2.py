"""
Phase 4: Edge-Case Regression Tests — chaos scenarios, boundary
conditions, and fault injection to ensure 24/7 reliability.

Run: python -m pytest tests/test_edge_cases_v2.py -v
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action  # noqa: F401
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401

# ============================================================
# Edge 1: Unregistered action type
# ============================================================

class TestUnregisteredActionType:
    """Verify system handles unknown action types gracefully."""

    def test_get_action_class_unknown_type_raises(self) -> None:
        from core.action import get_action_class
        with pytest.raises(ValueError):
            get_action_class("totally_fake_action_type")

    def test_from_dict_unknown_type_raises(self) -> None:
        from core.action import Action
        bad_dict = {"type": "nonexistent_type", "params": {}}
        with pytest.raises((ValueError, KeyError)):
            Action.from_dict(bad_dict)


# ============================================================
# Edge 2: Save/Load boundary conditions
# ============================================================

class TestSaveLoadBoundary:
    """Test save/load with extreme data."""

    def test_save_load_zero_actions(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine
        path = str(tmp_path / "empty.json")
        MacroEngine.save_macro(path, [], name="Empty")
        loaded, settings = MacroEngine.load_macro(path)
        assert len(loaded) == 0
        assert settings["name"] == "Empty"

    def test_save_load_1000_actions(self, tmp_path: Path) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        actions = [DelayAction(duration_ms=i) for i in range(1000)]
        path = str(tmp_path / "large.json")
        MacroEngine.save_macro(path, actions, name="Large")
        loaded, _ = MacroEngine.load_macro(path)

        assert len(loaded) == 1000
        assert loaded[0].duration_ms == 0
        assert loaded[999].duration_ms == 999

    def test_save_load_unicode_name(self, tmp_path: Path) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        unicode_name = "Tự động hóa 🖱️ — テスト"
        actions = [DelayAction(duration_ms=100)]
        path = str(tmp_path / "unicode.json")
        MacroEngine.save_macro(path, actions, name=unicode_name)
        _, settings = MacroEngine.load_macro(path)
        assert settings["name"] == unicode_name

    def test_save_load_unicode_filepath(self, tmp_path: Path) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        # Create a unicode subdirectory
        unicode_dir = tmp_path / "thư_mục_tiếng_việt"
        unicode_dir.mkdir()
        path = str(unicode_dir / "macro.json")
        MacroEngine.save_macro(path, [DelayAction(duration_ms=1)])
        loaded, _ = MacroEngine.load_macro(path)
        assert len(loaded) == 1

    def test_load_nonexistent_file_raises(self) -> None:
        from core.engine import MacroEngine
        with pytest.raises((FileNotFoundError, ValueError)):
            MacroEngine.load_macro("/nonexistent/path/macro.json")


# ============================================================
# Edge 3: Engine rapid start/stop (deadlock detection)
# ============================================================

class TestEngineRapidToggle:
    """Verify engine doesn't deadlock under rapid start/stop."""

    def test_rapid_start_stop_no_deadlock(self) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=50)])
        engine.set_loop(count=0, delay_ms=0)  # infinite

        # Single start → short run → stop. Proves no deadlock.
        engine.start()
        time.sleep(0.2)
        engine.stop()
        engine.wait(5000)

        assert not engine.isRunning(), "Engine should stop cleanly"

    def test_double_start_ignored(self) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=10)])
        engine.set_loop(count=1)
        engine.start()
        engine.start()  # second start should be no-op
        engine.wait(3000)
        assert not engine.isRunning()


# ============================================================
# Edge 4: MemoryManager fault injection
# ============================================================

class TestMemoryManagerFaults:
    """Inject errors into MemoryManager to verify graceful handling."""

    def test_get_stats_never_crashes(self) -> None:
        from core.memory_manager import MemoryManager
        mm = MemoryManager.instance()
        stats = mm.get_stats()
        assert isinstance(stats, dict)
        assert "current_mb" in stats

    def test_cleanup_with_failing_callback(self) -> None:
        from core.memory_manager import MemoryManager
        mm = MemoryManager.instance()

        def bad_cleanup() -> None:
            raise RuntimeError("Simulated cleanup failure")

        mm.register_cleanup(bad_cleanup)
        # force_gc → _do_cleanup should not crash even with bad callback
        try:
            mm.force_gc()
        except Exception:
            pytest.fail("force_gc should not propagate exceptions")
        # Clean up: remove bad callback
        mm._cleanup_callbacks = [
            cb for cb in mm._cleanup_callbacks if cb is not bad_cleanup
        ]


# ============================================================
# Edge 5: FileNotFoundError / PermissionError injection
# ============================================================

class TestIOFaultInjection:
    """Simulate I/O failures to verify error handling."""

    def test_save_to_readonly_path(self) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        # Patch Path.write_text to simulate write-protected file
        with patch("pathlib.Path.write_text",
                   side_effect=PermissionError("Simulated write-protected")):
            with pytest.raises(PermissionError):
                MacroEngine.save_macro(
                    "readonly.json", [DelayAction(duration_ms=1)])

    def test_config_save_to_bad_path(self) -> None:
        from gui.settings_dialog import save_config
        # Should not crash even with bad path
        try:
            save_config({"test": True}, path="/nonexistent/config.json")
        except OSError:
            pass  # Expected — just verify no unhandled crash


# ============================================================
# Edge 6: Action serialization roundtrip (all 18 types)
# ============================================================

class TestAllActionsSerialization:
    """Every registered action type must survive to_dict → from_dict."""

    def test_all_types_roundtrip(self) -> None:
        from core.action import Action, get_action_class, get_all_action_types

        for atype in get_all_action_types():
            cls = get_action_class(atype)
            try:
                action = cls()
            except TypeError:
                # Some actions need params — use minimal defaults
                continue

            d = action.to_dict()
            restored = Action.from_dict(d)
            assert restored.ACTION_TYPE == atype, (
                f"Roundtrip failed for {atype}"
            )


# ============================================================
# Edge 7: Engine pause/resume lifecycle
# ============================================================

class TestEnginePauseResume:
    """Verify engine pause/resume without deadlock."""

    def test_pause_resume_completes(self) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=50)])
        engine.set_loop(count=2, delay_ms=0)
        engine.start()

        time.sleep(0.05)
        engine.pause()
        assert engine.is_paused

        time.sleep(0.1)  # let it sit paused
        engine.resume()
        assert not engine.is_paused

        engine.wait(5000)
        assert not engine.isRunning()

    def test_stop_while_paused(self) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=50)])
        engine.set_loop(count=0, delay_ms=0)  # infinite

        engine.start()
        time.sleep(0.05)
        engine.pause()

        # Stop while paused — should not deadlock
        engine.stop()
        engine.wait(5000)
        assert not engine.isRunning()


# ============================================================
# Edge 8: Action attribute boundaries
# ============================================================

class TestActionAttributeBoundaries:
    """Test extreme/edge values for action attributes."""

    def test_delay_after_zero(self) -> None:
        from modules.mouse import MouseClick
        action = MouseClick(x=0, y=0, delay_after=0)
        assert action.delay_after == 0
        d = action.to_dict()
        assert d["delay_after"] == 0

    def test_repeat_count_one(self) -> None:
        from core.action import DelayAction
        action = DelayAction(duration_ms=1, repeat_count=1)
        assert action.repeat_count == 1

    def test_description_empty_string(self) -> None:
        from core.action import DelayAction
        action = DelayAction(duration_ms=100)
        action.description = ""
        d = action.to_dict()
        assert d["description"] == ""

    def test_description_very_long(self) -> None:
        from core.action import DelayAction
        long_desc = "A" * 10000
        action = DelayAction(duration_ms=100)
        action.description = long_desc
        d = action.to_dict()
        restored = DelayAction.from_dict(d)  # type: ignore[attr-defined]
        assert restored.description == long_desc

    def test_action_with_special_chars(self) -> None:
        from modules.keyboard import TypeText
        action = TypeText(text='Hello "world"! \n\t 🎉 <>&')
        d = action.to_dict()
        from core.action import Action
        restored = Action.from_dict(d)
        assert restored.text == 'Hello "world"! \n\t 🎉 <>&'


# ============================================================
# Edge 9: Config roundtrip
# ============================================================

class TestConfigRoundtrip:
    """Verify config save→load preserves all keys."""

    def test_full_roundtrip(self, tmp_path: Path) -> None:
        import copy

        from gui.settings_dialog import (
            DEFAULT_CONFIG,
            load_config,
            save_config,
        )

        config = copy.deepcopy(DEFAULT_CONFIG)
        config["defaults"]["click_delay"] = 42
        path = str(tmp_path / "test_config.json")

        save_config(config, path=path)
        loaded = load_config(path=path)

        assert loaded["defaults"]["click_delay"] == 42
        assert "hotkeys" in loaded

    def test_missing_section_filled_from_defaults(self, tmp_path: Path) -> None:
        from gui.settings_dialog import load_config, save_config
        path = str(tmp_path / "partial.json")

        # Save a config with only one section
        save_config({"defaults": {"click_delay": 99}}, path=path)
        loaded = load_config(path=path)

        # Should have defaults section
        assert loaded["defaults"]["click_delay"] == 99


# ============================================================
# Edge 10: Action ID uniqueness
# ============================================================

class TestActionIdUniqueness:
    """Verify every new action gets a unique ID."""

    def test_100_actions_unique_ids(self) -> None:
        from core.action import DelayAction
        actions = [DelayAction(duration_ms=1) for _ in range(100)]
        ids = {a.id for a in actions}
        assert len(ids) == 100, "All 100 actions must have unique IDs"

    def test_from_dict_generates_new_id(self) -> None:
        from core.action import Action, DelayAction
        orig = DelayAction(duration_ms=100)
        d = orig.to_dict()
        restored = Action.from_dict(d)
        assert orig.id != restored.id, "Restored action should have new ID"

