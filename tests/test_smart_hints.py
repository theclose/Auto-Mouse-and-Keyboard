"""
Tests for core.smart_hints — analyze_hints rule engine.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Import action modules to register types
import core.scheduler  # noqa: F401 — registers loop_block, if_*, set_variable, comment
import modules.image  # noqa: F401 — registers wait_for_image, click_on_image, etc.
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.system  # noqa: F401 — registers activate_window, run_command, etc.
from core.action import get_action_class
from core.smart_hints import analyze_hints


def _make(action_type: str, **kwargs):
    """Helper: create an action with given type and params."""
    cls = get_action_class(action_type)
    action = cls()
    action.delay_after = kwargs.pop("delay_after", 100)
    action.description = kwargs.pop("description", "")
    if kwargs:
        try:
            action._set_params(kwargs)
        except Exception:
            for k, v in kwargs.items():
                setattr(action, k, v)
    return action


class TestEmptyList:
    def test_empty_returns_empty(self):
        assert analyze_hints([]) == []


class TestRule1_ClickAfterActivateWindow:
    def test_mouse_after_activate_no_delay_gives_hint(self):
        actions = [
            _make("activate_window", title="Test", delay_after=0),
            _make("mouse_click", x=100, y=100, delay_after=50),
        ]
        hints = analyze_hints(actions)
        assert any("Delay" in h["message"] and h["level"] == "tip"
                    for h in hints)

    def test_mouse_after_activate_with_delay_no_hint(self):
        actions = [
            _make("activate_window", title="Test", delay_after=0),
            _make("mouse_click", x=100, y=100, delay_after=500),
        ]
        hints = analyze_hints(actions)
        rule1 = [h for h in hints if "ActivateWindow" in h.get("message", "")]
        assert len(rule1) == 0


class TestRule2_TypeTextAfterActivateWindow:
    def test_type_after_activate_no_delay(self):
        actions = [
            _make("activate_window", title="Test", delay_after=0),
            _make("type_text", text="hello", delay_after=50),
        ]
        hints = analyze_hints(actions)
        assert any("TypeText" in h["message"] for h in hints)

    def test_type_after_activate_with_delay(self):
        actions = [
            _make("activate_window", title="Test", delay_after=0),
            _make("type_text", text="hello", delay_after=300),
        ]
        hints = analyze_hints(actions)
        rule2 = [h for h in hints if "TypeText" in h.get("message", "")
                 and "ActivateWindow" in h.get("message", "")]
        assert len(rule2) == 0


class TestRule3_LowTimeout:
    def test_wait_image_low_timeout(self):
        actions = [
            _make("wait_for_image", timeout_ms=1000, delay_after=0),
        ]
        hints = analyze_hints(actions)
        assert any("timeout" in h["message"].lower() and h["level"] == "warning"
                    for h in hints)

    def test_wait_image_normal_timeout(self):
        actions = [
            _make("wait_for_image", timeout_ms=5000, delay_after=0),
        ]
        hints = analyze_hints(actions)
        timeout_hints = [h for h in hints if "timeout" in h.get("message", "").lower()]
        assert len(timeout_hints) == 0


class TestRule4_InfiniteLoop:
    def test_infinite_loop_no_break(self):
        loop = _make("loop_block", delay_after=0)
        loop.repeat_count = 0  # LoopBlock uses repeat_count (0 = infinite)
        loop.children = []
        actions = [loop]
        hints = analyze_hints(actions)
        assert any("vô hạn" in h["message"] for h in hints)

    def test_finite_loop_no_warning(self):
        loop = _make("loop_block", delay_after=0)
        loop.repeat_count = 5  # LoopBlock uses repeat_count (not loop_count)
        loop.children = []
        actions = [loop]
        hints = analyze_hints(actions)
        loop_hints = [h for h in hints if "vô hạn" in h.get("message", "")]
        assert len(loop_hints) == 0


class TestRule5_DuplicateDelays:
    def test_consecutive_delays(self):
        actions = [
            _make("delay", duration_ms=1000, delay_after=0),
            _make("delay", duration_ms=2000, delay_after=0),
        ]
        hints = analyze_hints(actions)
        assert any("gộp" in h["message"] for h in hints)

    def test_non_consecutive_delays(self):
        actions = [
            _make("delay", duration_ms=1000, delay_after=0),
            _make("mouse_click", x=0, y=0, delay_after=0),
            _make("delay", duration_ms=2000, delay_after=0),
        ]
        hints = analyze_hints(actions)
        merge_hints = [h for h in hints if "gộp" in h.get("message", "")]
        assert len(merge_hints) == 0


class TestRule6_ImageNoTemplate:
    def test_wait_image_no_path(self):
        action = _make("wait_for_image", delay_after=0)
        # WaitForImage stores path in image_path (not template_path)
        action.image_path = ""
        hints = analyze_hints([action])
        assert any("ảnh mẫu" in h["message"] and h["level"] == "error"
                    for h in hints)

    def test_wait_image_with_path_no_hint(self):
        action = _make("wait_for_image", delay_after=0)
        action.image_path = "some_template.png"
        hints = analyze_hints([action])
        no_template_hints = [h for h in hints if "ảnh mẫu" in h.get("message", "")]
        assert len(no_template_hints) == 0


class TestRule7_UnsetVariable:
    def test_if_variable_not_set_before(self):
        action = _make("if_variable", delay_after=0)
        action.var_name = "counter"
        actions = [action]
        hints = analyze_hints(actions)
        assert any("chưa được set" in h["message"] for h in hints)

    def test_if_variable_set_before(self):
        set_var = _make("set_variable", var_name="counter",
                        value="0", operation="set", delay_after=0)
        if_var = _make("if_variable", delay_after=0)
        if_var.var_name = "counter"
        hints = analyze_hints([set_var, if_var])
        unset_hints = [h for h in hints if "chưa được set" in h.get("message", "")]
        assert len(unset_hints) == 0


class TestGlobalHints:
    def test_high_total_delay(self):
        actions = [_make("delay", duration_ms=100, delay_after=5000)
                   for _ in range(7)]  # 7 * 5000 = 35000ms
        hints = analyze_hints(actions)
        assert any("Tổng delay" in h["message"] for h in hints)

    def test_many_actions_suggest_submacro(self):
        actions = [_make("delay", duration_ms=10, delay_after=0)
                   for _ in range(55)]
        hints = analyze_hints(actions)
        assert any("sub-macro" in h["message"] for h in hints)


class TestHintStructure:
    def test_hint_has_required_keys(self):
        actions = [
            _make("delay", duration_ms=1000, delay_after=0),
            _make("delay", duration_ms=2000, delay_after=0),
        ]
        hints = analyze_hints(actions)
        for h in hints:
            assert "level" in h
            assert "icon" in h
            assert "message" in h
            assert h["level"] in ("tip", "warning", "error")
