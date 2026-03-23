"""
Flow Control & Variable actions — loop, conditional, variable manipulation.

This module registers the 7 "flow control" action types that are shown
in the Action Editor UI but previously had no Action subclass, causing
a crash when users tried to create them.
"""

import json
import logging
import operator as op
from typing import Any

from core.action import Action, register_action

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Comment / Label — pure annotation, no side-effects
# ---------------------------------------------------------------------------
@register_action("comment")
class CommentAction(Action):
    """A no-op label or section marker for readability."""

    def __init__(self, text: str = "", **kw: Any) -> None:
        super().__init__(**kw)
        self.text = text

    def execute(self) -> bool:
        return True  # no-op

    def _get_params(self) -> dict[str, Any]:
        return {"text": self.text}

    def _set_params(self, p: dict[str, Any]) -> None:
        self.text = p.get("text", "")

    def get_display_name(self) -> str:
        snippet = self.text[:40] + "…" if len(self.text) > 40 else self.text
        return f"💬 {snippet}" if snippet else "💬 Comment"


# ---------------------------------------------------------------------------
# Set Variable — assign / compute a context variable
# ---------------------------------------------------------------------------
_OPS = {
    "set": None,
    "increment": lambda cur, _: (float(cur) if cur else 0) + 1,
    "decrement": lambda cur, _: (float(cur) if cur else 0) - 1,
    "add":       lambda cur, v: (float(cur) if cur else 0) + float(v),
    "subtract":  lambda cur, v: (float(cur) if cur else 0) - float(v),
    "multiply":  lambda cur, v: (float(cur) if cur else 0) * float(v),
    "divide":    lambda cur, v: (float(cur) if cur else 0) / float(v) if float(v) != 0 else 0,
    "modulo":    lambda cur, v: (float(cur) if cur else 0) % float(v) if float(v) != 0 else 0,
}


@register_action("set_variable")
class SetVariableAction(Action):
    """Set or compute a variable in ExecutionContext."""

    def __init__(self, var_name: str = "", value: str = "",
                 operation: str = "set", **kw: Any) -> None:
        super().__init__(**kw)
        self.var_name = var_name
        self.value = value
        self.operation = operation

    def execute(self) -> bool:
        from core.engine_context import get_context
        ctx = get_context()
        if not ctx or not self.var_name:
            return False

        # Interpolate value (supports ${var} references)
        resolved = ctx.interpolate(self.value) if self.value else ""

        if self.operation == "set":
            ctx.set_var(self.var_name, resolved)
        elif self.operation == "eval":
            # Safe eval of simple math expressions
            try:
                result = eval(resolved, {"__builtins__": {}}, {})  # noqa: S307
                ctx.set_var(self.var_name, result)
            except Exception as exc:
                logger.warning("eval(%s) failed: %s", resolved, exc)
                return False
        else:
            fn = _OPS.get(self.operation)
            if fn:
                current = ctx.get_var(self.var_name, 0)
                try:
                    result = fn(current, resolved)
                    # Store as int if whole number, else float
                    if isinstance(result, float) and result == int(result):
                        result = int(result)
                    ctx.set_var(self.var_name, result)
                except (ValueError, TypeError, ZeroDivisionError) as exc:
                    logger.warning("set_variable %s failed: %s",
                                   self.operation, exc)
                    return False

        logger.debug("Variable '%s' = %s (op=%s)",
                     self.var_name, ctx.get_var(self.var_name), self.operation)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"var_name": self.var_name, "value": self.value,
                "operation": self.operation}

    def _set_params(self, p: dict[str, Any]) -> None:
        self.var_name = p.get("var_name", "")
        self.value = p.get("value", "")
        self.operation = p.get("operation", "set")

    def get_display_name(self) -> str:
        if self.operation == "set":
            return f"📊 {self.var_name} = {self.value}"
        return f"📊 {self.var_name} ← {self.operation}({self.value})"


# ---------------------------------------------------------------------------
# Split String — split variable by delimiter, store Nth field
# ---------------------------------------------------------------------------
@register_action("split_string")
class SplitStringAction(Action):
    """Split a variable's value by delimiter and store one field."""

    def __init__(self, source_var: str = "", delimiter: str = ",",
                 field_index: int = 0, target_var: str = "",
                 **kw: Any) -> None:
        super().__init__(**kw)
        self.source_var = source_var
        self.delimiter = delimiter
        self.field_index = field_index
        self.target_var = target_var

    def execute(self) -> bool:
        from core.engine_context import get_context
        ctx = get_context()
        if not ctx or not self.source_var or not self.target_var:
            return False
        raw = str(ctx.get_var(self.source_var, ""))
        parts = raw.split(self.delimiter)
        if 0 <= self.field_index < len(parts):
            ctx.set_var(self.target_var, parts[self.field_index].strip())
            return True
        logger.warning("split_string: index %d out of range (%d parts)",
                       self.field_index, len(parts))
        return False

    def _get_params(self) -> dict[str, Any]:
        return {"source_var": self.source_var, "delimiter": self.delimiter,
                "field_index": self.field_index, "target_var": self.target_var}

    def _set_params(self, p: dict[str, Any]) -> None:
        self.source_var = p.get("source_var", "")
        self.delimiter = p.get("delimiter", ",")
        self.field_index = p.get("field_index", 0)
        self.target_var = p.get("target_var", "")

    def get_display_name(self) -> str:
        return (f"✂ Split {self.source_var}[{self.field_index}] "
                f"→ {self.target_var}")


# ---------------------------------------------------------------------------
# Loop Block — repeat N times (children support in Phase 1)
# ---------------------------------------------------------------------------
@register_action("loop_block")
class LoopBlockAction(Action):
    """Repeat action group N times. Currently a marker; Phase 1 adds children."""

    def __init__(self, iterations: int = 1, **kw: Any) -> None:
        super().__init__(**kw)
        self.iterations = max(0, iterations)  # 0 = infinite

    def execute(self) -> bool:
        # Phase 0: just a marker — engine doesn't recurse yet.
        # Phase 1 will make engine handle children.
        logger.debug("LoopBlock marker (iterations=%d)", self.iterations)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"iterations": self.iterations}

    def _set_params(self, p: dict[str, Any]) -> None:
        self.iterations = max(0, p.get("iterations", 1))

    def get_display_name(self) -> str:
        if self.iterations == 0:
            return "🔁 Loop ∞"
        return f"🔁 Loop ×{self.iterations}"


# ---------------------------------------------------------------------------
# Comparison helpers (shared by if_variable, if_pixel_color)
# ---------------------------------------------------------------------------
_CMP_OPS = {
    "==": op.eq, "!=": op.ne,
    ">": op.gt, "<": op.lt,
    ">=": op.ge, "<=": op.le,
}


def _smart_compare(a: Any, b: str, operator_str: str) -> bool:
    """Compare values, attempting numeric comparison first."""
    cmp_fn = _CMP_OPS.get(operator_str, op.eq)
    # Try numeric comparison
    try:
        return cmp_fn(float(a), float(b))
    except (ValueError, TypeError):
        pass
    # Fallback to string comparison
    return cmp_fn(str(a), b)


# ---------------------------------------------------------------------------
# If Variable — conditional check on a context variable
# ---------------------------------------------------------------------------
@register_action("if_variable")
class IfVariableAction(Action):
    """Evaluate a condition on a context variable.

    If condition is TRUE → action.run() returns True.
    If condition is FALSE → execute else_action (if provided), return False.
    Phase 1 will add children for THEN/ELSE blocks.
    """

    def __init__(self, var_name: str = "", operator: str = "==",
                 compare_value: str = "", else_action_json: str = "",
                 **kw: Any) -> None:
        super().__init__(**kw)
        self.var_name = var_name
        self.operator = operator
        self.compare_value = compare_value
        self.else_action_json = else_action_json

    def execute(self) -> bool:
        from core.engine_context import get_context
        ctx = get_context()
        if not ctx:
            return False
        actual = ctx.get_var(self.var_name, "")
        # Interpolate compare_value for ${var} support
        expected = ctx.interpolate(self.compare_value)
        result = _smart_compare(actual, expected, self.operator)
        logger.debug("if_variable: %s(%s) %s %s → %s",
                     self.var_name, actual, self.operator, expected, result)

        if not result and self.else_action_json.strip():
            self._run_else_action()
        return result

    def _run_else_action(self) -> None:
        """Execute inline else action from JSON."""
        try:
            data = json.loads(self.else_action_json)
            else_action = Action.from_dict(data)
            else_action.run()
        except Exception as exc:
            logger.warning("if_variable else_action failed: %s", exc)

    def _get_params(self) -> dict[str, Any]:
        return {"var_name": self.var_name, "operator": self.operator,
                "compare_value": self.compare_value,
                "else_action_json": self.else_action_json}

    def _set_params(self, p: dict[str, Any]) -> None:
        self.var_name = p.get("var_name", "")
        self.operator = p.get("operator", "==")
        self.compare_value = p.get("compare_value", "")
        self.else_action_json = p.get("else_action_json", "")

    def get_display_name(self) -> str:
        return f"❓ If {self.var_name} {self.operator} {self.compare_value}"


# ---------------------------------------------------------------------------
# If Image Found — conditional check on image existence
# ---------------------------------------------------------------------------
@register_action("if_image_found")
class IfImageFoundAction(Action):
    """Check if an image exists on screen.

    If found → return True + store match in context.
    If NOT found → execute else_action (if provided), return False.
    """

    def __init__(self, image_path: str = "", confidence: float = 0.8,
                 timeout_ms: int = 5000, else_action_json: str = "",
                 **kw: Any) -> None:
        super().__init__(**kw)
        self.image_path = image_path
        self.confidence = confidence
        self.timeout_ms = timeout_ms
        self.else_action_json = else_action_json

    def execute(self) -> bool:
        from modules.image import ImageFinder
        from core.engine_context import get_context

        finder = ImageFinder()
        # Wait loop with timeout
        import time
        deadline = time.perf_counter() + self.timeout_ms / 1000.0
        result = None

        while time.perf_counter() < deadline:
            result = finder.find(self.image_path, confidence=self.confidence)
            if result is not None:
                break
            time.sleep(0.1)

        if result is not None:
            ctx = get_context()
            if ctx:
                ctx.set_image_match(self.image_path, result)
            logger.debug("if_image_found: FOUND %s", self.image_path)
            return True

        logger.debug("if_image_found: NOT FOUND %s (timeout %dms)",
                     self.image_path, self.timeout_ms)
        if self.else_action_json.strip():
            self._run_else_action()
        return False

    def _run_else_action(self) -> None:
        try:
            data = json.loads(self.else_action_json)
            else_action = Action.from_dict(data)
            else_action.run()
        except Exception as exc:
            logger.warning("if_image_found else_action failed: %s", exc)

    def _get_params(self) -> dict[str, Any]:
        return {"image_path": self.image_path, "confidence": self.confidence,
                "timeout_ms": self.timeout_ms,
                "else_action_json": self.else_action_json}

    def _set_params(self, p: dict[str, Any]) -> None:
        self.image_path = p.get("image_path", "")
        self.confidence = p.get("confidence", 0.8)
        self.timeout_ms = p.get("timeout_ms", 5000)
        self.else_action_json = p.get("else_action_json", "")

    def get_display_name(self) -> str:
        from pathlib import Path
        name = Path(self.image_path).name if self.image_path else "?"
        return f"🔍 If image: {name}"


# ---------------------------------------------------------------------------
# If Pixel Color — conditional check on pixel color at coordinates
# ---------------------------------------------------------------------------
@register_action("if_pixel_color")
class IfPixelColorAction(Action):
    """Check if pixel at (x, y) matches expected color within tolerance."""

    def __init__(self, x: int = 0, y: int = 0,
                 color: str = "#000000", tolerance: int = 10,
                 timeout_ms: int = 5000, else_action_json: str = "",
                 **kw: Any) -> None:
        super().__init__(**kw)
        self.x = x
        self.y = y
        self.color = color
        self.tolerance = tolerance
        self.timeout_ms = timeout_ms
        self.else_action_json = else_action_json

    def _parse_color(self) -> tuple[int, int, int]:
        """Parse '#RRGGBB' or 'R,G,B' to (r, g, b)."""
        c = self.color.strip()
        if c.startswith("#") and len(c) == 7:
            return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        parts = c.split(",")
        if len(parts) == 3:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        return (0, 0, 0)

    def execute(self) -> bool:
        import time
        try:
            import pyautogui
        except ImportError:
            logger.error("pyautogui not available for pixel check")
            return False

        target_r, target_g, target_b = self._parse_color()
        deadline = time.perf_counter() + self.timeout_ms / 1000.0

        while time.perf_counter() < deadline:
            try:
                pixel = pyautogui.pixel(self.x, self.y)
                r, g, b = pixel[0], pixel[1], pixel[2]
                if (abs(r - target_r) <= self.tolerance and
                        abs(g - target_g) <= self.tolerance and
                        abs(b - target_b) <= self.tolerance):
                    from core.engine_context import get_context
                    ctx = get_context()
                    if ctx:
                        ctx.set_pixel_color(self.x, self.y, r, g, b)
                    return True
            except Exception:
                pass
            time.sleep(0.1)

        logger.debug("if_pixel_color: no match at (%d,%d) for %s",
                     self.x, self.y, self.color)
        if self.else_action_json.strip():
            try:
                data = json.loads(self.else_action_json)
                Action.from_dict(data).run()
            except Exception as exc:
                logger.warning("if_pixel_color else_action failed: %s", exc)
        return False

    def _get_params(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "color": self.color,
                "tolerance": self.tolerance, "timeout_ms": self.timeout_ms,
                "else_action_json": self.else_action_json}

    def _set_params(self, p: dict[str, Any]) -> None:
        self.x = p.get("x", 0)
        self.y = p.get("y", 0)
        self.color = p.get("color", "#000000")
        self.tolerance = p.get("tolerance", 10)
        self.timeout_ms = p.get("timeout_ms", 5000)
        self.else_action_json = p.get("else_action_json", "")

    def get_display_name(self) -> str:
        return f"🎨 If pixel ({self.x},{self.y}) = {self.color}"
