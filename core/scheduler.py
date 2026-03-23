"""
Scheduler – loop and conditional logic for macro execution.
Provides wrapper actions for repeat loops and image-based conditionals.
"""

import logging
import threading
from typing import Any

from core.action import Action, register_action

logger = logging.getLogger(__name__)


@register_action("loop_block")
class LoopBlock(Action):
    """
    Repeats a sub-list of actions N times (0 = infinite until stopped).
    This is used in the action list as a logical grouping.
    In practice, the engine handles looping at the top level,
    but this allows nested loops inside a macro.
    """

    def __init__(self, iterations: int = 1, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.iterations = max(0, iterations)
        self._sub_actions: list[Action] = []
        self._cancel_event = threading.Event()

    def add_action(self, action: Action) -> None:
        self._sub_actions.append(action)

    def cancel(self) -> None:
        """Cancel an ongoing infinite loop."""
        self._cancel_event.set()

    def execute(self) -> bool:
        from core.engine_context import is_stopped, get_context
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
                if ctx.get_var('__break__'):
                    ctx.set_var('__break__', False)
                    logger.info("LoopBlock: break at iteration %d", count)
                    break

            for action in self._sub_actions:
                if self._cancel_event.is_set() or is_stopped():
                    return True
                # Check __continue__ → skip rest of iteration
                if ctx and ctx.get_var('__continue__'):
                    ctx.set_var('__continue__', False)
                    break
                success = action.run()
                if not success:
                    return False
            if self.iterations > 0 and count >= self.iterations:
                break
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "iterations": self.iterations,
            "sub_actions": [a.to_dict() for a in self._sub_actions],
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.iterations = params.get("iterations", 1)
        self._sub_actions = [
            Action.from_dict(a) for a in params.get("sub_actions", [])
        ]

    def get_display_name(self) -> str:
        n = "∞" if self.iterations == 0 else str(self.iterations)
        return f"Loop ×{n} ({len(self._sub_actions)} actions)"


@register_action("if_image_found")
class IfImageFound(Action):
    """
    Conditional: if image is found on screen → run then_actions,
    else → run else_actions.
    """

    def __init__(self, image_path: str = "", confidence: float = 0.8,
                 timeout_ms: int = 5000, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.image_path = image_path
        self.confidence = confidence
        self.timeout_ms = timeout_ms
        self._then_actions: list[Action] = []
        self._else_actions: list[Action] = []

    def add_then_action(self, action: Action) -> None:
        self._then_actions.append(action)

    def add_else_action(self, action: Action) -> None:
        self._else_actions.append(action)

    def execute(self) -> bool:
        from modules.image import get_image_finder
        from core.engine_context import is_stopped, get_context
        finder = get_image_finder()

        # Support ${var} in image_path (e.g. "screens/${screen_id}.png")
        img_path = self.image_path
        ctx = get_context()
        if ctx and '${' in img_path:
            img_path = ctx.interpolate(img_path)

        result = finder.find_on_screen(
            img_path,
            confidence=self.confidence,
            timeout_ms=self.timeout_ms,
        )
        if result is not None:
            logger.info("Image found at %s – running THEN branch", result)
            for action in self._then_actions:
                if is_stopped():
                    return True
                if not action.run():
                    return False
        else:
            logger.info("Image NOT found – running ELSE branch")
            for action in self._else_actions:
                if is_stopped():
                    return True
                if not action.run():
                    return False
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "confidence": self.confidence,
            "timeout_ms": self.timeout_ms,
            "then_actions": [a.to_dict() for a in self._then_actions],
            "else_actions": [a.to_dict() for a in self._else_actions],
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.image_path = params.get("image_path", "")
        self.confidence = params.get("confidence", 0.8)
        self.timeout_ms = params.get("timeout_ms", 5000)
        self._then_actions = [
            Action.from_dict(a) for a in params.get("then_actions", [])
        ]
        self._else_actions = [
            Action.from_dict(a) for a in params.get("else_actions", [])
        ]

    def get_display_name(self) -> str:
        name = self.image_path.split("\\")[-1].split("/")[-1] or "?"
        return f"If '{name}' found → {len(self._then_actions)} actions"


@register_action("if_pixel_color")
class IfPixelColor(Action):
    """Conditional: if pixel matches color → then_actions, else → else_actions."""

    def __init__(self, x: int = 0, y: int = 0,
                 r: int = 0, g: int = 0, b: int = 0,
                 tolerance: int = 10, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.r = r
        self.g = g
        self.b = b
        self.tolerance = tolerance
        self._then_actions: list[Action] = []
        self._else_actions: list[Action] = []

    def add_then_action(self, action: Action) -> None:
        self._then_actions.append(action)

    def add_else_action(self, action: Action) -> None:
        self._else_actions.append(action)

    def execute(self) -> bool:
        from modules.pixel import get_pixel_checker
        from core.engine_context import is_stopped
        pc = get_pixel_checker()
        matched = pc.check_color(self.x, self.y, self.r, self.g, self.b,
                                 self.tolerance)
        branch = self._then_actions if matched else self._else_actions
        label = "THEN" if matched else "ELSE"
        logger.info("IfPixelColor(%d,%d) RGB(%d,%d,%d) → %s (%d actions)",
                     self.x, self.y, self.r, self.g, self.b,
                     label, len(branch))
        for action in branch:
            if is_stopped():
                return True
            if not action.run():
                return False
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "x": self.x, "y": self.y,
            "r": self.r, "g": self.g, "b": self.b,
            "tolerance": self.tolerance,
            "then_actions": [a.to_dict() for a in self._then_actions],
            "else_actions": [a.to_dict() for a in self._else_actions],
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.r = params.get("r", 0)
        self.g = params.get("g", 0)
        self.b = params.get("b", 0)
        self.tolerance = params.get("tolerance", 10)
        self._then_actions = [
            Action.from_dict(a) for a in params.get("then_actions", [])
        ]
        self._else_actions = [
            Action.from_dict(a) for a in params.get("else_actions", [])
        ]

    def get_display_name(self) -> str:
        return (f"If pixel({self.x},{self.y}) = RGB({self.r},{self.g},{self.b})"
                f" → {len(self._then_actions)} actions")


@register_action("if_variable")
class IfVariable(Action):
    """
    Conditional: compare a context variable to a value.
    Operators: ==, !=, >, <, >=, <=
    """

    def __init__(self, var_name: str = "", operator: str = "==",
                 compare_value: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.var_name = var_name
        self.operator = operator
        self.compare_value = compare_value
        self._then_actions: list[Action] = []
        self._else_actions: list[Action] = []

    def add_then_action(self, action: Action) -> None:
        self._then_actions.append(action)

    def add_else_action(self, action: Action) -> None:
        self._else_actions.append(action)

    def execute(self) -> bool:
        from core.engine_context import get_context, is_stopped
        ctx = get_context()
        var_val = ctx.get_var(self.var_name) if ctx else None

        # Try numeric comparison
        try:
            a = float(var_val) if var_val is not None else 0
            b = float(self.compare_value) if self.compare_value else 0
        except (ValueError, TypeError):
            a = str(var_val) if var_val is not None else ""
            b = self.compare_value

        op = self.operator
        if op == "==":
            matched = (a == b)
        elif op == "!=":
            matched = (a != b)
        elif op == ">":
            matched = (a > b)
        elif op == "<":
            matched = (a < b)
        elif op == ">=":
            matched = (a >= b)
        elif op == "<=":
            matched = (a <= b)
        else:
            logger.warning("Unknown operator '%s', defaulting to ==", op)
            matched = (a == b)

        branch = self._then_actions if matched else self._else_actions
        label = "THEN" if matched else "ELSE"
        logger.info("IfVariable ${%s} %s %s → %s → %d actions",
                     self.var_name, op, self.compare_value, label, len(branch))

        for action in branch:
            if is_stopped():
                return True
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
        self._then_actions = [
            Action.from_dict(a) for a in params.get("then_actions", [])
        ]
        self._else_actions = [
            Action.from_dict(a) for a in params.get("else_actions", [])
        ]

    def get_display_name(self) -> str:
        return f"If ${{{self.var_name}}} {self.operator} {self.compare_value}"


@register_action("set_variable")
class SetVariable(Action):
    """Set or modify a context variable. Operations: set, increment, decrement, add."""

    def __init__(self, var_name: str = "", value: str = "",
                 operation: str = "set", **kwargs: Any) -> None:
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
            # Add arbitrary value (from var or literal)
            current = ctx.get_var(self.var_name, 0)
            add_val = self.value
            if '${' in add_val:
                add_val = ctx.interpolate(add_val)
            try:
                ctx.set_var(self.var_name, float(current) + float(add_val))
            except (ValueError, TypeError):
                logger.warning("Cannot add '%s' to '%s'", add_val, current)
        else:
            logger.warning("Unknown operation '%s'", self.operation)

        logger.info("SetVariable ${%s} %s %s → %s",
                     self.var_name, self.operation, self.value,
                     ctx.get_var(self.var_name))
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "var_name": self.var_name,
            "value": self.value,
            "operation": self.operation,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.var_name = params.get("var_name", "")
        self.value = params.get("value", "")
        self.operation = params.get("operation", "set")

    def get_display_name(self) -> str:
        if self.operation == "set":
            return f"${{{self.var_name}}} = {self.value}"
        elif self.operation == "increment":
            return f"${{{self.var_name}}} += {self.value or 1}"
        elif self.operation == "decrement":
            return f"${{{self.var_name}}} -= {self.value or 1}"
        elif self.operation == "add":
            return f"${{{self.var_name}}} += {self.value}"
        return f"${{{self.var_name}}} {self.operation} {self.value}"


@register_action("split_string")
class SplitString(Action):
    """Split a variable by delimiter and store a specific field.

    Example: variable="a,b,c", delimiter=",", field_index=1 → stores "b"
    """

    def __init__(self, source_var: str = "", delimiter: str = ",",
                 field_index: int = 0, target_var: str = "",
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.source_var = source_var
        self.delimiter = delimiter
        self.field_index = field_index
        self.target_var = target_var

    def execute(self) -> bool:
        from core.engine_context import get_context
        ctx = get_context()
        if not ctx:
            return True

        value = ctx.get_var(self.source_var, "")
        if not isinstance(value, str):
            value = str(value)

        parts = value.split(self.delimiter)
        if 0 <= self.field_index < len(parts):
            result = parts[self.field_index].strip()
            ctx.set_var(self.target_var, result)
            logger.info("Split ${%s}[%d] → ${%s} = '%s'",
                         self.source_var, self.field_index,
                         self.target_var, result[:50])
            return True
        else:
            logger.warning("Field %d out of range (%d fields in '%s')",
                           self.field_index, len(parts), value[:50])
            ctx.set_var(self.target_var, "")
            return True  # Don't fail — just empty

    def _get_params(self) -> dict[str, Any]:
        return {
            "source_var": self.source_var,
            "delimiter": self.delimiter,
            "field_index": self.field_index,
            "target_var": self.target_var,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.source_var = params.get("source_var", "")
        self.delimiter = params.get("delimiter", ",")
        self.field_index = params.get("field_index", 0)
        self.target_var = params.get("target_var", "")

    def get_display_name(self) -> str:
        return (f"Split ${{{self.source_var}}}[{self.field_index}]"
                f" → ${{{self.target_var}}}")


