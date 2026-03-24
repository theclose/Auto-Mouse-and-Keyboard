"""
Scheduler — Flow Control & Variable Actions (Composite Pattern).

This module registers **7 action types** that handle flow control and
variable manipulation in macros. These are the "composite" / "control flow"
actions, as opposed to the "atomic" actions in modules/ (mouse, keyboard, etc).

╔══════════════════════════════════════════════════════════════════════╗
║  IMPORTANT: These 7 types are the ONLY registrations for their     ║
║  action_type strings. Do NOT create duplicate @register_action()   ║
║  for these types in modules/ — it will cause silent overwrite.     ║
╚══════════════════════════════════════════════════════════════════════╝

Registered Action Types:
    ┌──────────────────┬───────────────┬──────────────────────────────┐
    │ Type String      │ Class         │ Description                  │
    ├──────────────────┼───────────────┼──────────────────────────────┤
    │ loop_block       │ LoopBlock     │ Repeat sub-actions N times   │
    │ if_image_found   │ IfImageFound  │ Conditional: image on screen │
    │ if_pixel_color   │ IfPixelColor  │ Conditional: pixel matches   │
    │ if_variable      │ IfVariable    │ Conditional: variable check  │
    │ set_variable     │ SetVariable   │ Set/compute context variable │
    │ split_string     │ SplitString   │ Split variable by delimiter  │
    │ comment          │ Comment       │ No-op label / section marker │
    └──────────────────┴───────────────┴──────────────────────────────┘

Architecture Notes:
    - LoopBlock, IfImageFound, IfPixelColor, IfVariable implement the
      Composite Pattern: they contain child Action lists (_sub_actions,
      _then_actions, _else_actions) and execute them recursively.
    - Child actions are serialized in to_dict() as nested lists.
    - The engine runs a flat list, but composite actions handle their
      own recursion inside execute(). Phase 3 (TreeView) will make
      this explicit in the GUI.

Action Editor Compatibility:
    - Conditional actions accept `else_action_json` kwarg from the
      Action Editor's _collect_params() (inline JSON for else branch).
    - IfPixelColor also accepts `color` string ('#RRGGBB' or 'R,G,B')
      as alternative to separate r, g, b integer params.

See Also:
    - core/action.py — Action base class, registry, serialization
    - gui/action_editor.py — UI builders for each action type
    - core/engine.py — Macro execution engine (flat list runner)
"""

import logging
import threading
from typing import Any

from core.action import Action, register_action

logger = logging.getLogger(__name__)

# B5: Recursion depth guard for nested composite actions
MAX_COMPOSITE_DEPTH = 16
_depth_local = threading.local()


def _get_depth() -> int:
    return getattr(_depth_local, "depth", 0)


def _inc_depth() -> int:
    """Increment depth counter and return new value."""
    d = _get_depth() + 1
    _depth_local.depth = d
    return d


def _dec_depth() -> None:
    _depth_local.depth = max(0, _get_depth() - 1)


@register_action("loop_block")
class LoopBlock(Action):
    """
    Repeats a sub-list of actions N times (0 = infinite until stopped).
    This is used in the action list as a logical grouping.
    In practice, the engine handles looping at the top level,
    but this allows nested loops inside a macro.
    """

    def __init__(self, iterations: int = 1, **kwargs: Any) -> None:
        """Initialize a loop block.

        Args:
            iterations: Number of loop iterations. 0 = infinite.
        """
        super().__init__(**kwargs)
        self.iterations = max(0, iterations)
        self._sub_actions: list[Action] = []
        self._cancel_event = threading.Event()

    def add_action(self, action: Action) -> None:
        """Append a child action to this loop."""
        self._sub_actions.append(action)

    def cancel(self) -> None:
        """Cancel an ongoing infinite loop."""
        self._cancel_event.set()

    def execute(self) -> bool:
        """Run sub-actions for the configured number of iterations.

        Supports __break__ and __continue__ context variables for flow control.
        Returns False if any sub-action fails, True otherwise.
        """
        from core.engine_context import emit_nested_step, get_context, is_stopped

        # B5: Recursion depth guard
        depth = _inc_depth()
        if depth > MAX_COMPOSITE_DEPTH:
            _dec_depth()
            logger.error("LoopBlock: max nesting depth %d exceeded", MAX_COMPOSITE_DEPTH)
            return False

        try:
            self._cancel_event.clear()
            count = 0
            while True:
                if self._cancel_event.is_set():
                    logger.info("LoopBlock cancelled after %d iterations", count)
                    return True
                if is_stopped():
                    logger.info("LoopBlock stopped after %d iterations", count)
                    return True

                count += 1
                ctx = get_context()
                if ctx:
                    ctx.iteration_count = count
                    # Check __break__ variable for programmatic break
                    if ctx.get_var("__break__"):
                        ctx.set_var("__break__", False)
                        logger.info("LoopBlock: break at iteration %d", count)
                        break

                for i, action in enumerate(self._sub_actions):
                    if self._cancel_event.is_set() or is_stopped():
                        return True
                    # Check __continue__ → skip rest of iteration
                    if ctx and ctx.get_var("__continue__"):
                        ctx.set_var("__continue__", False)
                        break
                    emit_nested_step([i], action.get_display_name())
                    success = action.run()
                    if not success:
                        return False
                if self.iterations > 0 and count >= self.iterations:
                    break
            return True
        finally:
            _dec_depth()

    def _get_params(self) -> dict[str, Any]:
        """Serialize loop params including nested sub-actions."""
        return {
            "iterations": self.iterations,
            "sub_actions": [a.to_dict() for a in self._sub_actions],
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        """Deserialize loop params and rebuild sub-action list."""
        self.iterations = params.get("iterations", 1)
        self._sub_actions = [Action.from_dict(a) for a in params.get("sub_actions", [])]
        # Ensure _cancel_event exists when deserialized via from_dict
        if not hasattr(self, "_cancel_event"):
            self._cancel_event = threading.Event()

    def get_display_name(self) -> str:
        """Return human-readable label, e.g. 'Loop ×3 (5 actions)'."""
        n = "∞" if self.iterations == 0 else str(self.iterations)
        return f"Loop ×{n} ({len(self._sub_actions)} actions)"

    # -- composite interface (v3.0) --
    @property
    def is_composite(self) -> bool:
        return True

    @property
    def children(self) -> list[Action]:
        """Return copy of sub-actions list (composite interface)."""
        return list(self._sub_actions)

    @children.setter
    def children(self, value: list[Action]) -> None:
        """Replace sub-actions list entirely."""
        self._sub_actions = list(value)

    def __deepcopy__(self, memo: dict) -> "LoopBlock":
        """Custom deepcopy: threading.Event can't be pickled, so serialize→deserialize."""
        return Action.from_dict(self.to_dict())  # type: ignore[return-value]


@register_action("if_image_found")
class IfImageFound(Action):
    """
    Conditional: if image is found on screen → run then_actions,
    else → run else_actions.
    """

    def __init__(
        self,
        image_path: str = "",
        confidence: float = 0.8,
        timeout_ms: int = 5000,
        else_action_json: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize image-based conditional.

        Args:
            image_path: Template image file path (supports ${var}).
            confidence: Match confidence threshold (0.0–1.0).
            timeout_ms: Search timeout in milliseconds.
            else_action_json: Optional inline JSON for ELSE branch.
        """
        super().__init__(**kwargs)
        self.image_path = image_path
        self.confidence = confidence
        self.timeout_ms = timeout_ms
        self._then_actions: list[Action] = []
        self._else_actions: list[Action] = []
        # Parse inline else action from action_editor
        if else_action_json and else_action_json.strip():
            try:
                import json

                data = json.loads(else_action_json)
                self._else_actions.append(Action.from_dict(data))
            except Exception:
                logger.debug("Failed to parse else_action_json", exc_info=True)

    def add_then_action(self, action: Action) -> None:
        self._then_actions.append(action)

    def add_else_action(self, action: Action) -> None:
        self._else_actions.append(action)

    def execute(self) -> bool:
        from core.engine_context import emit_nested_step, get_context, is_stopped

        # B6: Safe import — missing opencv/pillow shouldn't crash engine
        try:
            from modules.image import get_image_finder

            finder = get_image_finder()
        except (ImportError, Exception) as exc:
            logger.error("IfImageFound: cannot import image finder: %s", exc)
            return False

        # Support ${var} in image_path (e.g. "screens/${screen_id}.png")
        img_path = self.image_path
        ctx = get_context()
        if ctx and "${" in img_path:
            img_path = ctx.interpolate(img_path)

        result = finder.find_on_screen(
            img_path,
            confidence=self.confidence,
            timeout_ms=self.timeout_ms,
        )
        if result is not None:
            logger.info("Image found at %s – running THEN branch", result)
            for i, action in enumerate(self._then_actions):
                if is_stopped():
                    return True
                emit_nested_step([i], action.get_display_name())
                if not action.run():
                    return False
        else:
            logger.info("Image NOT found – running ELSE branch")
            for i, action in enumerate(self._else_actions):
                if is_stopped():
                    return True
                emit_nested_step([i], action.get_display_name())
                if not action.run():
                    return False
        return True

    def _get_params(self) -> dict[str, Any]:
        """Serialize image-conditional params including both branches."""
        return {
            "image_path": self.image_path,
            "confidence": self.confidence,
            "timeout_ms": self.timeout_ms,
            "then_actions": [a.to_dict() for a in self._then_actions],
            "else_actions": [a.to_dict() for a in self._else_actions],
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        """Deserialize image-conditional params and rebuild branches."""
        self.image_path = params.get("image_path", "")
        self.confidence = params.get("confidence", 0.8)
        self.timeout_ms = params.get("timeout_ms", 5000)
        self._then_actions = [Action.from_dict(a) for a in params.get("then_actions", [])]
        self._else_actions = [Action.from_dict(a) for a in params.get("else_actions", [])]

    def get_display_name(self) -> str:
        """Return label showing image name and THEN action count."""
        name = self.image_path.split("\\")[-1].split("/")[-1] or "?"
        return f"If '{name}' found → {len(self._then_actions)} actions"

    # -- composite interface (v3.0) --
    @property
    def is_composite(self) -> bool:
        return True

    @property
    def has_branches(self) -> bool:
        return True

    @property
    def children(self) -> list[Action]:
        return list(self._then_actions) + list(self._else_actions)

    @children.setter
    def children(self, value: list[Action]) -> None:
        """Set all children as THEN actions (ELSE must use else_children)."""
        self._then_actions = list(value)

    @property
    def then_children(self) -> list[Action]:
        return list(self._then_actions)

    @then_children.setter
    def then_children(self, value: list[Action]) -> None:
        self._then_actions = list(value)

    @property
    def else_children(self) -> list[Action]:
        return list(self._else_actions)

    @else_children.setter
    def else_children(self, value: list[Action]) -> None:
        self._else_actions = list(value)


@register_action("if_pixel_color")
class IfPixelColor(Action):
    """Conditional: if pixel matches color → then_actions, else → else_actions."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        r: int = 0,
        g: int = 0,
        b: int = 0,
        tolerance: int = 10,
        color: str = "",
        timeout_ms: int = 5000,
        else_action_json: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        # Support both r,g,b and color string from action_editor
        if color and not any([r, g, b]):
            self.r, self.g, self.b = self._parse_color_str(color)
        else:
            self.r, self.g, self.b = r, g, b
        self.tolerance = tolerance
        self._then_actions: list[Action] = []
        self._else_actions: list[Action] = []
        if else_action_json and else_action_json.strip():
            try:
                import json

                data = json.loads(else_action_json)
                self._else_actions.append(Action.from_dict(data))
            except Exception:
                logger.debug("Failed to parse else_action_json", exc_info=True)

    @staticmethod
    def _parse_color_str(color: str) -> tuple[int, int, int]:
        """Parse '#RRGGBB' or 'R,G,B' string to (r, g, b) tuple."""
        c = color.strip()
        if c.startswith("#") and len(c) == 7:
            return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        parts = c.split(",")
        if len(parts) == 3:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        return (0, 0, 0)

    def add_then_action(self, action: Action) -> None:
        self._then_actions.append(action)

    def add_else_action(self, action: Action) -> None:
        self._else_actions.append(action)

    def execute(self) -> bool:
        from core.engine_context import emit_nested_step, is_stopped
        from modules.pixel import get_pixel_checker

        pc = get_pixel_checker()
        matched = pc.check_color(self.x, self.y, self.r, self.g, self.b, self.tolerance)
        branch = self._then_actions if matched else self._else_actions
        label = "THEN" if matched else "ELSE"
        logger.info(
            "IfPixelColor(%d,%d) RGB(%d,%d,%d) → %s (%d actions)",
            self.x,
            self.y,
            self.r,
            self.g,
            self.b,
            label,
            len(branch),
        )
        for i, action in enumerate(branch):
            if is_stopped():
                return True
            emit_nested_step([i], action.get_display_name())
            if not action.run():
                return False
        return True

    def _get_params(self) -> dict[str, Any]:
        """Serialize pixel-color conditional params."""
        return {
            "x": self.x,
            "y": self.y,
            "r": self.r,
            "g": self.g,
            "b": self.b,
            "tolerance": self.tolerance,
            "then_actions": [a.to_dict() for a in self._then_actions],
            "else_actions": [a.to_dict() for a in self._else_actions],
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        """Deserialize pixel-color conditional params."""
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.r = params.get("r", 0)
        self.g = params.get("g", 0)
        self.b = params.get("b", 0)
        self.tolerance = params.get("tolerance", 10)
        self._then_actions = [Action.from_dict(a) for a in params.get("then_actions", [])]
        self._else_actions = [Action.from_dict(a) for a in params.get("else_actions", [])]

    def get_display_name(self) -> str:
        """Return label showing pixel coordinates and RGB values."""
        return f"If pixel({self.x},{self.y}) = RGB({self.r},{self.g},{self.b})" f" → {len(self._then_actions)} actions"

    # -- composite interface (v3.0) --
    @property
    def is_composite(self) -> bool:
        return True

    @property
    def has_branches(self) -> bool:
        return True

    @property
    def children(self) -> list[Action]:
        return list(self._then_actions) + list(self._else_actions)

    @children.setter
    def children(self, value: list[Action]) -> None:
        """Set all children as THEN actions (ELSE must use else_children)."""
        self._then_actions = list(value)

    @property
    def then_children(self) -> list[Action]:
        return list(self._then_actions)

    @then_children.setter
    def then_children(self, value: list[Action]) -> None:
        self._then_actions = list(value)

    @property
    def else_children(self) -> list[Action]:
        return list(self._else_actions)

    @else_children.setter
    def else_children(self, value: list[Action]) -> None:
        self._else_actions = list(value)


@register_action("if_variable")
class IfVariable(Action):
    """
    Conditional: compare a context variable to a value.
    Operators: ==, !=, >, <, >=, <=
    """

    def __init__(
        self,
        var_name: str = "",
        operator: str = "==",
        compare_value: str = "",
        else_action_json: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.var_name = var_name
        self.operator = operator
        self.compare_value = compare_value
        self._then_actions: list[Action] = []
        self._else_actions: list[Action] = []
        if else_action_json and else_action_json.strip():
            try:
                import json

                data = json.loads(else_action_json)
                self._else_actions.append(Action.from_dict(data))
            except Exception:
                logger.debug("Failed to parse else_action_json", exc_info=True)

    def add_then_action(self, action: Action) -> None:
        self._then_actions.append(action)

    def add_else_action(self, action: Action) -> None:
        self._else_actions.append(action)

    def execute(self) -> bool:
        from core.engine_context import emit_nested_step, get_context, is_stopped

        ctx = get_context()

        # P0-1: Interpolate var_name and compare_value for dynamic comparisons
        var_name = self.var_name
        compare = self.compare_value
        if ctx:
            if "${" in var_name:
                var_name = ctx.interpolate(var_name)
            if "${" in compare:
                compare = ctx.interpolate(compare)
        var_val = ctx.get_var(var_name) if ctx else None

        # Try numeric comparison
        a: Any  # float or str depending on parse success
        b: Any
        try:
            a = float(var_val) if var_val is not None else 0
            b = float(compare) if compare else 0
        except (ValueError, TypeError):
            a = str(var_val) if var_val is not None else ""
            b = compare

        op = self.operator
        if op == "==":
            matched = a == b
        elif op == "!=":
            matched = a != b
        elif op == ">":
            matched = a > b
        elif op == "<":
            matched = a < b
        elif op == ">=":
            matched = a >= b
        elif op == "<=":
            matched = a <= b
        else:
            logger.warning("Unknown operator '%s', defaulting to ==", op)
            matched = a == b

        branch = self._then_actions if matched else self._else_actions
        label = "THEN" if matched else "ELSE"
        logger.info(
            "IfVariable ${%s} %s %s → %s → %d actions", self.var_name, op, self.compare_value, label, len(branch)
        )

        for i, action in enumerate(branch):
            if is_stopped():
                return True
            emit_nested_step([i], action.get_display_name())
            if not action.run():
                return False
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "var_name": self.var_name,
            "operator": self.operator,
            "compare_value": self.compare_value,
            "then_actions": [a.to_dict() for a in self._then_actions],
            "else_actions": [a.to_dict() for a in self._else_actions],
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.var_name = params.get("var_name", "")
        self.operator = params.get("operator", "==")
        self.compare_value = params.get("compare_value", "")
        self._then_actions = [Action.from_dict(a) for a in params.get("then_actions", [])]
        self._else_actions = [Action.from_dict(a) for a in params.get("else_actions", [])]

    def get_display_name(self) -> str:
        return f"If ${{{self.var_name}}} {self.operator} {self.compare_value}"

    # -- composite interface (v3.0) --
    @property
    def is_composite(self) -> bool:
        return True

    @property
    def has_branches(self) -> bool:
        return True

    @property
    def children(self) -> list[Action]:
        return list(self._then_actions) + list(self._else_actions)

    @children.setter
    def children(self, value: list[Action]) -> None:
        """Set all children as THEN actions (ELSE must use else_children)."""
        self._then_actions = list(value)

    @property
    def then_children(self) -> list[Action]:
        return list(self._then_actions)

    @then_children.setter
    def then_children(self, value: list[Action]) -> None:
        self._then_actions = list(value)

    @property
    def else_children(self) -> list[Action]:
        return list(self._else_actions)

    @else_children.setter
    def else_children(self, value: list[Action]) -> None:
        self._else_actions = list(value)


@register_action("set_variable")
class SetVariable(Action):
    """Set or modify a context variable. Operations: set, increment, decrement, add."""

    def __init__(self, var_name: str = "", value: str = "", operation: str = "set", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.var_name = var_name
        self.value = value
        self.operation = operation  # "set" | "increment" | "decrement" | "add"

    def execute(self) -> bool:
        from core.engine_context import get_context

        ctx = get_context()
        if not ctx:
            logger.warning("SetVariable: no execution context")
            return True

        if self.operation == "set":
            # Try to store as int/float if possible
            try:
                ctx.set_var(self.var_name, int(self.value))
            except ValueError:
                try:
                    ctx.set_var(self.var_name, float(self.value))
                except ValueError:
                    ctx.set_var(self.var_name, self.value)
        elif self.operation == "increment":
            current = ctx.get_var(self.var_name, 0)
            try:
                step = int(self.value) if self.value else 1
            except ValueError:
                step = 1
            ctx.set_var(self.var_name, int(current) + step)
        elif self.operation == "decrement":
            current = ctx.get_var(self.var_name, 0)
            try:
                step = int(self.value) if self.value else 1
            except ValueError:
                step = 1
            ctx.set_var(self.var_name, int(current) - step)
        elif self.operation == "add":
            current = ctx.get_var(self.var_name, 0)
            add_val = self.value
            if "${" in add_val:
                add_val = ctx.interpolate(add_val)
            try:
                ctx.set_var(self.var_name, float(current) + float(add_val))
            except (ValueError, TypeError):
                logger.warning("Cannot add '%s' to '%s' — keeping current", add_val, current)
        elif self.operation == "subtract":
            current = ctx.get_var(self.var_name, 0)
            sub_val = self.value
            if "${" in sub_val:
                sub_val = ctx.interpolate(sub_val)
            try:
                ctx.set_var(self.var_name, float(current) - float(sub_val))
            except (ValueError, TypeError):
                logger.warning("Cannot subtract '%s' from '%s'", sub_val, current)
        elif self.operation == "multiply":
            current = ctx.get_var(self.var_name, 0)
            mul_val = self.value
            if "${" in mul_val:
                mul_val = ctx.interpolate(mul_val)
            try:
                ctx.set_var(self.var_name, float(current) * float(mul_val))
            except (ValueError, TypeError):
                logger.warning("Cannot multiply '%s' by '%s'", current, mul_val)
        elif self.operation == "divide":
            current = ctx.get_var(self.var_name, 0)
            div_val = self.value
            if "${" in div_val:
                div_val = ctx.interpolate(div_val)
            try:
                divisor = float(div_val)
                if divisor == 0:
                    logger.warning("Division by zero")
                else:
                    ctx.set_var(self.var_name, float(current) / divisor)
            except (ValueError, TypeError):
                logger.warning("Cannot divide '%s' by '%s'", current, div_val)
        elif self.operation == "modulo":
            current = ctx.get_var(self.var_name, 0)
            mod_val = self.value
            if "${" in mod_val:
                mod_val = ctx.interpolate(mod_val)
            try:
                divisor = float(mod_val)
                if divisor == 0:
                    logger.warning("Modulo by zero")
                else:
                    ctx.set_var(self.var_name, float(current) % divisor)
            except (ValueError, TypeError):
                logger.warning("Cannot modulo '%s' by '%s'", current, mod_val)
        elif self.operation == "concat":
            # P2-4: String concatenation
            current = ctx.get_var(self.var_name, "")
            add_val = self.value
            if "${" in add_val:
                add_val = ctx.interpolate(add_val)
            ctx.set_var(self.var_name, str(current) + str(add_val))
        elif self.operation == "eval":
            # 2.2: Safe expression language
            expr = self.value
            if "${" in expr:
                expr = ctx.interpolate(expr)
            try:
                result = self._safe_eval(expr)
                ctx.set_var(self.var_name, result)
            except Exception as e:
                logger.warning("Cannot evaluate '%s': %s", expr, e)
        else:
            logger.warning("Unknown operation '%s'", self.operation)

        logger.info(
            "SetVariable ${%s} %s %s → %s", self.var_name, self.operation, self.value, ctx.get_var(self.var_name)
        )
        return True

    @staticmethod
    def _safe_eval(expr: str):
        """Expression Engine v2: evaluate expressions safely via AST.

        Supports:
        - Numbers: 42, 3.14
        - Strings: 'hello', "world"
        - Arithmetic: +, -, *, /, //, **, %
        - Comparisons: ==, !=, <, >, <=, >=
        - Boolean: and, or, not
        - Functions: abs, min, max, round, len, int, float, str,
                     upper, lower, strip, replace, split, join
        - Parentheses and nested expressions

        Examples:
            '(10 + 5) * 2'          → 30.0
            'len("hello")'          → 5
            'upper("abc")'          → 'ABC'
            '10 > 5 and 3 < 7'     → True
            'abs(-42)'              → 42
            'round(3.14159, 2)'     → 3.14
            'min(1, 2, 3)'          → 1
            'replace("abc", "b", "x")' → 'axc'
        """
        import ast
        import operator

        _bin_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }
        _unary_ops = {
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
            ast.Not: operator.not_,
        }
        _cmp_ops = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
        }
        _bool_ops = {
            ast.And: lambda vals: all(vals),
            ast.Or: lambda vals: any(vals),
        }
        _safe_funcs = {
            # Math
            "abs": abs,
            "min": min,
            "max": max,
            "round": round,
            "int": lambda x: int(float(x) if isinstance(x, str) else x),
            "float": float,
            # String
            "len": len,
            "str": str,
            "upper": lambda s: str(s).upper(),
            "lower": lambda s: str(s).lower(),
            "strip": lambda s: str(s).strip(),
            "replace": lambda s, old, new: str(s).replace(old, new),
            "split": lambda s, sep=",": str(s).split(sep),
            "join": lambda sep, lst: sep.join(str(x) for x in lst),
        }

        def _eval_node(node):
            # Constants: numbers, strings, booleans, None
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float, str, bool, type(None))):
                    return node.value
                raise ValueError(f"Unsupported constant: {type(node.value)}")

            # Binary ops: 1 + 2, "a" + "b"
            if isinstance(node, ast.BinOp) and type(node.op) in _bin_ops:
                left = _eval_node(node.left)
                right = _eval_node(node.right)
                return _bin_ops[type(node.op)](left, right)

            # Unary ops: -x, not x
            if isinstance(node, ast.UnaryOp) and type(node.op) in _unary_ops:
                return _unary_ops[type(node.op)](_eval_node(node.operand))

            # Comparisons: x > 5, a == b, 1 < x < 10
            if isinstance(node, ast.Compare):
                left = _eval_node(node.left)
                for op, comparator in zip(node.ops, node.comparators):
                    right = _eval_node(comparator)
                    if type(op) not in _cmp_ops:
                        raise ValueError(f"Unsupported comparison: {type(op)}")
                    if not _cmp_ops[type(op)](left, right):
                        return False
                    left = right
                return True

            # Boolean ops: x and y, a or b
            if isinstance(node, ast.BoolOp) and type(node.op) in _bool_ops:
                values = [_eval_node(v) for v in node.values]
                return _bool_ops[type(node.op)](values)

            # Function calls: abs(-5), len("hello"), min(1,2,3)
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name):
                    raise ValueError("Only simple function names allowed")
                fname = node.func.id
                if fname not in _safe_funcs:
                    raise ValueError(f"Function '{fname}' not allowed")
                args = [_eval_node(a) for a in node.args]
                return _safe_funcs[fname](*args)

            # IfExp: x if condition else y
            if isinstance(node, ast.IfExp):
                if _eval_node(node.test):
                    return _eval_node(node.body)
                return _eval_node(node.orelse)

            # Expression wrapper
            if isinstance(node, ast.Expression):
                return _eval_node(node.body)

            raise ValueError(f"Unsupported: {ast.dump(node)}")

        tree = ast.parse(expr.strip(), mode="eval")
        return _eval_node(tree)

    def _get_params(self) -> dict[str, Any]:
        """Serialize variable assignment params."""
        return {
            "var_name": self.var_name,
            "value": self.value,
            "operation": self.operation,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        """Deserialize variable assignment params."""
        self.var_name = params.get("var_name", "")
        self.value = params.get("value", "")
        self.operation = params.get("operation", "set")

    def get_display_name(self) -> str:
        """Return label showing variable name, operation symbol, and value."""
        op_symbols = {
            "set": "=",
            "increment": "+=",
            "decrement": "-=",
            "add": "+=",
            "subtract": "-=",
            "multiply": "*=",
            "divide": "/=",
            "modulo": "%=",
            "eval": "= eval",
            "concat": "+=",
        }
        sym = op_symbols.get(self.operation, self.operation)
        val = self.value or ("1" if self.operation in ("increment", "decrement") else "")
        return f"${{{self.var_name}}} {sym} {val}"


@register_action("split_string")
class SplitString(Action):
    """Split a variable by delimiter and store a specific field.

    Example: variable="a,b,c", delimiter=",", field_index=1 → stores "b"
    """

    def __init__(
        self, source_var: str = "", delimiter: str = ",", field_index: int = 0, target_var: str = "", **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.source_var = source_var
        self.delimiter = delimiter
        self.field_index = field_index
        self.target_var = target_var

    def execute(self) -> bool:
        import csv
        import io

        from core.engine_context import get_context

        ctx = get_context()
        if not ctx:
            return True

        value = ctx.get_var(self.source_var, "")
        if not isinstance(value, str):
            value = str(value)

        # Use csv.reader for proper quote/escape handling
        if self.delimiter == ",":
            try:
                reader = csv.reader(io.StringIO(value))
                parts = next(reader)
            except (csv.Error, StopIteration):
                parts = value.split(self.delimiter)
        else:
            parts = value.split(self.delimiter)

        if 0 <= self.field_index < len(parts):
            result = parts[self.field_index].strip()
            ctx.set_var(self.target_var, result)
            logger.info(
                "Split ${%s}[%d] → ${%s} = '%s'", self.source_var, self.field_index, self.target_var, result[:50]
            )
            return True
        else:
            logger.warning("Field %d out of range (%d fields in '%s')", self.field_index, len(parts), value[:50])
            ctx.set_var(self.target_var, "")
            return True

    def _get_params(self) -> dict[str, Any]:
        """Serialize split-string params."""
        return {
            "source_var": self.source_var,
            "delimiter": self.delimiter,
            "field_index": self.field_index,
            "target_var": self.target_var,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        """Deserialize split-string params."""
        self.source_var = params.get("source_var", "")
        self.delimiter = params.get("delimiter", ",")
        self.field_index = params.get("field_index", 0)
        self.target_var = params.get("target_var", "")

    def get_display_name(self) -> str:
        """Return label showing source→target mapping."""
        return f"Split ${{{self.source_var}}}[{self.field_index}]" f" → ${{{self.target_var}}}"


@register_action("comment")
class Comment(Action):
    """L7: Visual label/separator for organizing macros. No-op at runtime."""

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.text = text

    def execute(self) -> bool:
        """No-op: comments are visual-only labels."""
        return True  # No-op

    def _get_params(self) -> dict[str, Any]:
        """Serialize comment text."""
        return {"text": self.text}

    def _set_params(self, params: dict[str, Any]) -> None:
        """Deserialize comment text."""
        self.text = params.get("text", "")

    def get_display_name(self) -> str:
        """Return formatted comment label with decorative dashes."""
        return f"── {self.text} ──" if self.text else "────────"
