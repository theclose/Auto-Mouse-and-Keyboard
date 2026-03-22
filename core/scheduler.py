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
        from core.engine_context import is_stopped
        self._cancel_event.clear()
        count = 0
        while True:
            if self._cancel_event.is_set() or is_stopped():
                logger.info("LoopBlock cancelled after %d iterations", count)
                return True
            count += 1
            for action in self._sub_actions:
                if self._cancel_event.is_set() or is_stopped():
                    return True
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
        from modules.image import ImageFinder
        finder = ImageFinder()
        result = finder.find_on_screen(
            self.image_path,
            confidence=self.confidence,
            timeout_ms=self.timeout_ms,
        )
        if result is not None:
            logger.info("Image found at %s – running THEN branch", result)
            for action in self._then_actions:
                if not action.run():
                    return False
        else:
            logger.info("Image NOT found – running ELSE branch")
            for action in self._else_actions:
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
