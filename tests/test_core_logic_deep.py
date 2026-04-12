"""
Deep core logic tests — covers engine, execution_context, scheduler, action,
memory_manager, secure, profiler edge cases and paths missed by existing tests.

Focus: conditional branches, error paths, boundary values, thread safety.
"""

import copy
import json
import os
import threading
import time

import pytest

# Ensure composite action types are registered before tests
import core.scheduler  # noqa: F401 — registers loop_block, if_*, set_variable, etc.

# ============================================================
# 1. ExecutionContext — deep coverage
# ============================================================


class TestExecutionContextDeep:
    """Cover variable interpolation, ROI, snapshot/restore, thread safety."""

    def _ctx(self):
        from core.execution_context import ExecutionContext
        return ExecutionContext()

    # -- Variable interpolation --
    def test_interpolate_user_var(self):
        ctx = self._ctx()
        ctx.set_var("name", "Alice")
        assert ctx.interpolate("Hello ${name}!") == "Hello Alice!"

    def test_interpolate_missing_var_left_as_is(self):
        ctx = self._ctx()
        assert ctx.interpolate("${missing}") == "${missing}"

    def test_interpolate_system_var_iteration(self):
        ctx = self._ctx()
        ctx.iteration_count = 42
        assert ctx.interpolate("iter=${__iteration__}") == "iter=42"

    def test_interpolate_system_var_action_count(self):
        ctx = self._ctx()
        ctx.action_count = 7
        assert ctx.interpolate("done=${__action_count__}") == "done=7"

    def test_interpolate_system_var_error_count(self):
        ctx = self._ctx()
        ctx.error_count = 3
        assert ctx.interpolate("errs=${__error_count__}") == "errs=3"

    def test_interpolate_last_img_xy_no_match(self):
        ctx = self._ctx()
        assert ctx.interpolate("x=${__last_img_x__}") == "x=0"
        assert ctx.interpolate("y=${__last_img_y__}") == "y=0"

    def test_interpolate_last_img_xy_with_match(self):
        ctx = self._ctx()
        ctx.set_image_match("t.png", (100, 200, 50, 50))
        assert ctx.interpolate("x=${__last_img_x__}") == "x=125"
        assert ctx.interpolate("y=${__last_img_y__}") == "y=225"

    def test_interpolate_timestamp(self):
        ctx = self._ctx()
        result = ctx.interpolate("t=${__timestamp__}")
        ts = result.split("=")[1]
        assert ts.isdigit()

    def test_interpolate_multiple_vars(self):
        ctx = self._ctx()
        ctx.set_var("a", 1)
        ctx.set_var("b", 2)
        assert ctx.interpolate("${a}+${b}") == "1+2"

    def test_interpolate_no_pattern(self):
        ctx = self._ctx()
        assert ctx.interpolate("plain text") == "plain text"

    # -- Image result chaining --
    def test_image_match_stores_and_retrieves(self):
        ctx = self._ctx()
        ctx.set_image_match("test.png", (10, 20, 30, 40))
        assert ctx.get_image_match("test.png") == (10, 20, 30, 40)

    def test_image_match_wrong_template(self):
        ctx = self._ctx()
        ctx.set_image_match("a.png", (1, 2, 3, 4))
        assert ctx.get_image_match("b.png") is None

    def test_image_match_no_match(self):
        ctx = self._ctx()
        assert ctx.get_image_match() is None

    def test_image_center(self):
        ctx = self._ctx()
        ctx.set_image_match("t.png", (100, 200, 60, 80))
        assert ctx.get_image_center("t.png") == (130, 240)

    def test_image_center_no_match(self):
        ctx = self._ctx()
        assert ctx.get_image_center() is None

    # -- ROI --
    def test_suggest_roi_insufficient_data(self):
        ctx = self._ctx()
        ctx.set_image_match("t.png", (100, 100, 50, 50))
        assert ctx.suggest_roi("t.png") is None

    def test_suggest_roi_with_history(self):
        ctx = self._ctx()
        for i in range(3):
            ctx.set_image_match("t.png", (100 + i, 200 + i, 50, 50))
        roi = ctx.suggest_roi("t.png", margin=100)
        assert roi is not None
        assert roi[2] > 50 and roi[3] > 50

    def test_suggest_roi_cached(self):
        ctx = self._ctx()
        for i in range(3):
            ctx.set_image_match("t.png", (100, 200, 50, 50))
        r1 = ctx.suggest_roi_cached("t.png")
        r2 = ctx.suggest_roi_cached("t.png")
        assert r1 == r2

    def test_roi_history_capped_at_10(self):
        ctx = self._ctx()
        for i in range(15):
            ctx.set_image_match("t.png", (i * 10, i * 10, 50, 50))
        assert len(ctx._roi_history["t.png"]) == 10

    # -- Pixel --
    def test_pixel_color_set_get(self):
        ctx = self._ctx()
        ctx.set_pixel_color(10, 20, 255, 128, 0)
        assert ctx.get_pixel_color() == (10, 20, 255, 128, 0)

    def test_pixel_color_none_initially(self):
        ctx = self._ctx()
        assert ctx.get_pixel_color() is None

    # -- Stats --
    def test_record_action_success(self):
        ctx = self._ctx()
        ctx.record_action(True)
        assert ctx.action_count == 1 and ctx.error_count == 0

    def test_record_action_failure(self):
        ctx = self._ctx()
        ctx.record_action(False)
        assert ctx.action_count == 1 and ctx.error_count == 1

    def test_elapsed_seconds_zero(self):
        ctx = self._ctx()
        ctx.start_time = 0.0
        assert ctx.get_elapsed_seconds() == 0.0

    def test_elapsed_seconds_after_reset(self):
        ctx = self._ctx()
        ctx.reset()
        time.sleep(0.01)
        assert ctx.get_elapsed_seconds() > 0

    # -- Snapshot / Restore --
    def test_snapshot_restore_roundtrip(self):
        ctx = self._ctx()
        ctx.reset()
        ctx.set_var("x", 42)
        ctx.set_var("name", "test")
        ctx.set_image_match("t.png", (1, 2, 3, 4))
        ctx.record_action(True)
        ctx.record_action(False)
        snap = ctx.snapshot()

        ctx2 = self._ctx()
        ctx2.restore(snap)
        assert ctx2.get_var("x") == 42
        assert ctx2.action_count == 2
        assert ctx2.error_count == 1

    def test_restore_empty_snapshot(self):
        ctx = self._ctx()
        ctx.restore({})
        assert ctx.action_count == 0

    # -- Reset --
    def test_reset_clears_everything(self):
        ctx = self._ctx()
        ctx.set_var("x", 1)
        ctx.set_image_match("t.png", (1, 2, 3, 4))
        ctx.set_pixel_color(1, 2, 3, 4, 5)
        ctx.record_action(True)
        ctx.reset()
        assert ctx.get_var("x") is None
        assert ctx.get_image_match() is None
        assert ctx.action_count == 0

    # -- Thread safety --
    def test_concurrent_access(self):
        ctx = self._ctx()
        ctx.reset()
        errors = []

        def writer():
            for i in range(100):
                try:
                    ctx.set_var(f"v{i}", i)
                    ctx.record_action(True)
                except Exception as e:
                    errors.append(e)

        def reader():
            for i in range(100):
                try:
                    ctx.get_all_vars()
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ============================================================
# 2. MacroEngine — edge cases
# ============================================================


class TestMacroEngineDeep:
    """Engine configuration, file I/O, state management."""

    def test_set_loop_clamps_negative(self):
        from core.engine import MacroEngine
        eng = MacroEngine()
        eng.set_loop(count=-5, delay_ms=-100)
        assert eng._loop_count == 0 and eng._loop_delay_ms == 0

    def test_set_speed_factor_clamps(self):
        from core.engine import MacroEngine
        eng = MacroEngine()
        eng.set_speed_factor(0.001)
        assert eng._speed_factor == 0.1
        eng.set_speed_factor(100.0)
        assert eng._speed_factor == 10.0

    def test_is_running_when_not_started(self):
        from core.engine import MacroEngine
        assert not MacroEngine().is_running

    def test_step_mode_toggle(self):
        from core.engine import MacroEngine
        eng = MacroEngine()
        eng.set_step_mode(True)
        assert eng._step_mode is True
        eng.set_step_mode(False)
        assert eng._step_mode is False

    def test_stop_resets_state(self):
        from core.engine import MacroEngine
        eng = MacroEngine()
        eng._is_paused = True
        eng._step_mode = True
        eng.stop()
        assert eng._is_stopped and not eng._is_paused and not eng._step_mode

    def test_pause_resume(self):
        from core.engine import MacroEngine
        eng = MacroEngine()
        eng.pause()
        assert eng.is_paused
        eng.resume()
        assert not eng.is_paused

    def test_checkpoint_default_none(self):
        from core.engine import MacroEngine
        assert MacroEngine().get_last_checkpoint() is None

    def test_resume_from_checkpoint(self):
        from core.engine import MacroEngine
        eng = MacroEngine()
        eng.resume_from_checkpoint({"action_idx": 5})
        assert eng._resume_from_idx == 5

    # -- Macro I/O --
    def test_save_load_roundtrip(self, tmp_path):
        from core.action import Action
        from core.engine import MacroEngine
        actions = [
            Action.from_dict({"type": "comment", "params": {"text": "hello"}}),
        ]
        filepath = str(tmp_path / "test.json")
        MacroEngine.save_macro(filepath, actions, name="Test", loop_count=3, loop_delay_ms=500)
        loaded, settings = MacroEngine.load_macro(filepath)
        assert len(loaded) == 1 and settings["name"] == "Test"

    def test_load_invalid_json(self, tmp_path):
        fp = str(tmp_path / "bad.json")
        with open(fp, "w") as f:
            f.write("{invalid json")
        from core.engine import MacroEngine
        with pytest.raises(ValueError, match="corrupt"):
            MacroEngine.load_macro(fp)

    def test_load_missing_actions_key(self, tmp_path):
        fp = str(tmp_path / "no_actions.json")
        with open(fp, "w") as f:
            json.dump({"name": "test"}, f)
        from core.engine import MacroEngine
        with pytest.raises(ValueError, match="missing"):
            MacroEngine.load_macro(fp)

    def test_load_actions_not_list(self, tmp_path):
        fp = str(tmp_path / "bad.json")
        with open(fp, "w") as f:
            json.dump({"actions": "not_a_list"}, f)
        from core.engine import MacroEngine
        with pytest.raises(ValueError, match="list"):
            MacroEngine.load_macro(fp)

    def test_load_skips_invalid_entries(self, tmp_path):
        fp = str(tmp_path / "mixed.json")
        with open(fp, "w") as f:
            json.dump({"actions": [
                {"type": "comment", "params": {"text": "ok"}},
                "not_a_dict", {"no_type": True},
            ]}, f)
        from core.engine import MacroEngine
        loaded, _ = MacroEngine.load_macro(fp)
        assert len(loaded) == 1

    def test_load_nonexistent_file(self):
        from core.engine import MacroEngine
        with pytest.raises(ValueError, match="Cannot read"):
            MacroEngine.load_macro("/nonexistent/path.json")

    def test_save_creates_parent_dirs(self, tmp_path):
        from core.action import Action
        from core.engine import MacroEngine
        nested = str(tmp_path / "a" / "b" / "test.json")
        MacroEngine.save_macro(nested, [Action.from_dict({"type": "comment", "params": {"text": "hi"}})])
        assert os.path.exists(nested)


# ============================================================
# 3. Action — serialization edge cases
# ============================================================


class TestActionDeep:
    """Edge cases in Action.from_dict / to_dict / clone."""

    def test_from_dict_unknown_type_raises(self):
        from core.action import Action
        with pytest.raises(ValueError, match="Unknown action type"):
            Action.from_dict({"type": "unknown_xyz"})

    def test_to_dict_roundtrip(self):
        from core.action import Action
        original = Action.from_dict({
            "type": "comment", "params": {"text": "x"},
            "enabled": False, "description": "test",
        })
        d = original.to_dict()
        restored = Action.from_dict(d)
        assert restored.ACTION_TYPE == "comment"
        assert restored.enabled is False

    def test_action_enabled_default_true(self):
        from core.action import Action
        a = Action.from_dict({"type": "comment", "params": {"text": "x"}})
        assert a.enabled is True

    def test_action_composite_property(self):
        from core.action import Action
        loop = Action.from_dict({
            "type": "loop_block", "params": {"count": 3},
            "sub_actions": [{"type": "comment", "params": {"text": "inner"}}],
        })
        assert loop.is_composite is True
        comment = Action.from_dict({"type": "comment", "params": {"text": "x"}})
        assert comment.is_composite is False

    def test_action_display_name(self):
        from core.action import Action
        a = Action.from_dict({"type": "delay", "params": {"duration_ms": 500}})
        name = a.get_display_name()
        assert isinstance(name, str) and len(name) > 0

    def test_action_run_disabled(self):
        from core.action import Action
        a = Action.from_dict({"type": "comment", "params": {"text": "x"}})
        a.enabled = False
        assert a.run() is True

    def test_action_deepcopy(self):
        from core.action import Action
        a = Action.from_dict({
            "type": "loop_block", "params": {"count": 2},
            "sub_actions": [{"type": "comment", "params": {"text": "child"}}],
        })
        b = copy.deepcopy(a)
        assert b.ACTION_TYPE == a.ACTION_TYPE


# ============================================================
# 4. Scheduler — composite actions
# ============================================================


class TestSchedulerDeep:
    """Composite action types."""

    def test_loop_block_serialization(self):
        from core.action import Action
        loop = Action.from_dict({
            "type": "loop_block", "params": {"count": 5},
            "sub_actions": [
                {"type": "comment", "params": {"text": "s1"}},
                {"type": "comment", "params": {"text": "s2"}},
            ],
        })
        d = loop.to_dict()
        assert d["type"] == "loop_block"

    def test_set_variable_roundtrip(self):
        from core.action import Action
        sv = Action.from_dict({"type": "set_variable", "params": {"var_name": "counter", "value": "42", "operation": "set"}})
        d = sv.to_dict()
        assert d["params"]["var_name"] == "counter"

    def test_if_variable_composite(self):
        from core.action import Action
        iv = Action.from_dict({
            "type": "if_variable",
            "params": {"variable_name": "x", "operator": "==", "compare_value": "10"},
            "then_actions": [{"type": "comment", "params": {"text": "yes"}}],
            "else_actions": [{"type": "comment", "params": {"text": "no"}}],
        })
        assert iv.is_composite

    def test_comment_run_is_noop(self):
        from core.action import Action
        c = Action.from_dict({"type": "comment", "params": {"text": "note"}})
        result = c.run()
        assert result is True or result is None

    def test_parse_else_json_empty(self):
        from core.scheduler import _parse_else_json
        result = _parse_else_json("")
        assert result == [] or result is None or len(result) == 0
        result2 = _parse_else_json("   ")
        assert result2 == [] or result2 is None or len(result2) == 0

    def test_parse_else_json_valid(self):
        from core.scheduler import _parse_else_json
        result = _parse_else_json('{"type": "comment", "params": {"text": "else"}}')
        assert len(result) == 1

    def test_parse_else_json_invalid(self):
        from core.scheduler import _parse_else_json
        result = _parse_else_json("not json")
        assert result == [] or result is None or len(result) == 0

    def test_group_action(self):
        from core.action import Action
        g = Action.from_dict({
            "type": "group", "params": {"name": "My Group"},
            "sub_actions": [{"type": "comment", "params": {"text": "inner"}}],
        })
        assert g.is_composite

    def test_split_string(self):
        from core.action import Action
        ss = Action.from_dict({"type": "split_string", "params": {"variable_name": "data", "delimiter": ",", "output_prefix": "item"}})
        assert ss.ACTION_TYPE == "split_string"


# ============================================================
# 5. MemoryManager
# ============================================================


class TestMemoryManagerDeep:
    def test_instance_singleton(self):
        from core.memory_manager import MemoryManager
        MemoryManager._instance = None
        m1 = MemoryManager.instance()
        m2 = MemoryManager.instance()
        assert m1 is m2
        MemoryManager._instance = None

    def test_set_threshold_min(self):
        from core.memory_manager import MemoryManager
        mm = MemoryManager(threshold_mb=10)
        mm.set_threshold(1)
        assert mm._threshold_bytes == 50 * 1024 * 1024

    def test_get_memory_returns_int(self):
        from core.memory_manager import MemoryManager
        assert MemoryManager()._get_memory() > 0

    def test_get_stats(self):
        from core.memory_manager import MemoryManager
        stats = MemoryManager().get_stats()
        assert "current_mb" in stats and "threshold_mb" in stats

    def test_register_cleanup(self):
        from core.memory_manager import MemoryManager
        mm = MemoryManager()
        called = []
        mm.register_cleanup(lambda: called.append(1))
        mm._do_cleanup()
        assert len(called) == 1

    def test_force_gc(self):
        from core.memory_manager import MemoryManager
        mm = MemoryManager()
        mm.force_gc()
        assert mm._cleanup_count == 1

    def test_start_stop(self):
        from core.memory_manager import MemoryManager
        mm = MemoryManager(check_interval_s=1)
        mm.start()
        assert mm._running
        mm.stop()
        assert not mm._running


# ============================================================
# 6. Secure
# ============================================================


class TestSecureDeep:
    def test_is_encrypted_false(self):
        from core.secure import is_encrypted
        assert not is_encrypted("hello")
        assert not is_encrypted("")

    def test_is_encrypted_true(self):
        from core.secure import is_encrypted
        assert is_encrypted("DPAPI:abc123")

    def test_is_encrypted_non_string(self):
        from core.secure import is_encrypted
        assert not is_encrypted(123)  # type: ignore

    def test_encrypt_roundtrip(self):
        from core.secure import decrypt, encrypt
        plain = "test_password_123"
        encrypted = encrypt(plain)
        decrypted = decrypt(encrypted)
        assert decrypted == plain or encrypted == plain

    def test_decrypt_non_dpapi(self):
        from core.secure import decrypt
        assert decrypt("plain text") == "plain text"

    def test_decrypt_invalid_dpapi(self):
        from core.secure import decrypt
        assert isinstance(decrypt("DPAPI:invalidbase64!!!"), str)


# ============================================================
# 7. Profiler
# ============================================================


class TestProfilerDeep:
    def test_profiler_track(self):
        from core.profiler import PerformanceProfiler
        p = PerformanceProfiler()
        with p.track("test_op"):
            time.sleep(0.01)
        stats = p.get_stats("test_op")
        assert stats is not None and stats.count >= 1

    def test_profiler_nested(self):
        from core.profiler import PerformanceProfiler
        p = PerformanceProfiler()
        with p.track("outer"):
            with p.track("inner"):
                pass
        assert p.get_stats("outer") is not None
        assert p.get_stats("inner") is not None

    def test_profiler_reset(self):
        from core.profiler import PerformanceProfiler
        p = PerformanceProfiler()
        with p.track("x"):
            pass
        p.reset()
        assert p.get_stats("x") is None

    def test_profiler_report(self):
        from core.profiler import PerformanceProfiler
        p = PerformanceProfiler()
        with p.track("op1"):
            pass
        assert "op1" in p.report()

    def test_profiler_disable(self):
        from core.profiler import PerformanceProfiler
        p = PerformanceProfiler()
        p.disable()
        with p.track("skipped"):
            pass
        assert p.get_stats("skipped") is None
        p.enable()

    def test_get_profiler_singleton(self):
        from core.profiler import get_profiler
        assert get_profiler() is get_profiler()


# ============================================================
# 8. Event Bus (Qt signals)
# ============================================================


class TestEventBusDeep:
    def test_singleton(self):
        from core.event_bus import AppEventBus
        AppEventBus.reset()
        b1 = AppEventBus.instance()
        b2 = AppEventBus.instance()
        assert b1 is b2
        AppEventBus.reset()

    def test_has_engine_signals(self):
        from core.event_bus import AppEventBus
        AppEventBus.reset()
        bus = AppEventBus.instance()
        assert hasattr(bus, "engine_started")
        assert hasattr(bus, "engine_stopped")
        assert hasattr(bus, "engine_error")
        assert hasattr(bus, "engine_progress")
        AppEventBus.reset()

    def test_has_ui_signals(self):
        from core.event_bus import AppEventBus
        AppEventBus.reset()
        bus = AppEventBus.instance()
        assert hasattr(bus, "macro_loaded")
        assert hasattr(bus, "macro_saved")
        assert hasattr(bus, "actions_changed")
        assert hasattr(bus, "theme_changed")
        AppEventBus.reset()

    def test_reset_clears_instance(self):
        from core.event_bus import AppEventBus
        AppEventBus.reset()
        b1 = AppEventBus.instance()
        AppEventBus.reset()
        b2 = AppEventBus.instance()
        assert b1 is not b2
        AppEventBus.reset()


# ============================================================
# 9. Undo Commands
# ============================================================


class TestUndoCommandsDeep:
    def test_delete_undo(self):
        from core.action import Action
        from core.undo_commands import DeleteActionsCommand
        actions = [Action.from_dict({"type": "comment", "params": {"text": str(i)}}) for i in range(5)]
        cmd = DeleteActionsCommand(actions, [1, 3])
        cmd.redo()
        assert len(actions) == 3
        cmd.undo()
        assert len(actions) == 5

    def test_duplicate_undo(self):
        from core.action import Action
        from core.undo_commands import DuplicateActionCommand
        actions = [Action.from_dict({"type": "comment", "params": {"text": "a"}})]
        dup = Action.from_dict(actions[0].to_dict())
        cmd = DuplicateActionCommand(actions, 0, dup)
        cmd.redo()
        assert len(actions) == 2
        cmd.undo()
        assert len(actions) == 1

    def test_move_swap_undo(self):
        from core.action import Action
        from core.undo_commands import MoveActionCommand
        actions = [
            Action.from_dict({"type": "comment", "params": {"text": "a"}}),
            Action.from_dict({"type": "comment", "params": {"text": "b"}}),
            Action.from_dict({"type": "comment", "params": {"text": "c"}}),
        ]
        original_texts = [a.text for a in actions]
        cmd = MoveActionCommand(actions, 0, 1)
        cmd.redo()
        # After swap: b, a, c
        assert actions[0].text == "b"
        cmd.undo()
        restored_texts = [a.text for a in actions]
        assert original_texts == restored_texts

    def test_toggle_enabled(self):
        from core.action import Action
        from core.undo_commands import ToggleEnabledCommand
        actions = [Action.from_dict({"type": "comment", "params": {"text": "a"}})]
        assert actions[0].enabled is True
        cmd = ToggleEnabledCommand(actions, [0])
        cmd.redo()
        assert actions[0].enabled is False
        cmd.undo()
        assert actions[0].enabled is True

    def test_add_batch(self):
        from core.action import Action
        from core.undo_commands import AddBatchCommand
        actions = [Action.from_dict({"type": "comment", "params": {"text": "a"}})]
        batch = [Action.from_dict({"type": "comment", "params": {"text": f"b{i}"}}) for i in range(3)]
        cmd = AddBatchCommand(actions, batch)
        cmd.redo()
        assert len(actions) == 4
        cmd.undo()
        assert len(actions) == 1


# ============================================================
# 10. Engine Context globals
# ============================================================


class TestEngineContextGlobals:
    def test_set_get_speed(self):
        from core.engine_context import get_speed, set_speed
        set_speed(2.0)
        assert get_speed() == 2.0
        set_speed(1.0)

    def test_scaled_sleep(self):
        from core.engine_context import scaled_sleep, set_speed, set_stop_event
        set_speed(10.0)
        stop_event = threading.Event()
        set_stop_event(stop_event)
        start = time.perf_counter()
        scaled_sleep(0.1)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.05
        set_speed(1.0)

    def test_set_context(self):
        from core.engine_context import get_context, set_context
        from core.execution_context import ExecutionContext
        ctx = ExecutionContext()
        set_context(ctx)
        assert get_context() is ctx
