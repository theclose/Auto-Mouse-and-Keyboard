"""
Action system using the Command pattern.
Each action is a self-contained command that can be serialized/deserialized,
executed, and composed into macro sequences.
"""

import logging
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

_id_counter = 0

def _next_id() -> str:
    """Fast lightweight ID (no cryptographic overhead)."""
    global _id_counter
    _id_counter += 1
    return f"{_id_counter:06x}"
from typing import Any


# ---------------------------------------------------------------------------
# Action Registry – maps type strings to Action subclasses
# ---------------------------------------------------------------------------
_ACTION_REGISTRY: dict[str, type["Action"]] = {}


def register_action(action_type: str) -> Any:
    """Decorator to register an Action subclass in the global registry.

    WARNING: If `action_type` is already registered by a DIFFERENT class,
    a warning is logged. The last registration wins (Python import order).
    This was the root cause of the else_action_json crash: scheduler.py
    overwrote flow_control.py's registration silently.
    """
    def decorator(cls: type["Action"]) -> type["Action"]:
        existing = _ACTION_REGISTRY.get(action_type)
        if existing is not None and existing is not cls:
            logger.warning(
                "⚠️  DUPLICATE registration for '%s': %s.%s OVERWRITES %s.%s",
                action_type,
                cls.__module__, cls.__name__,
                existing.__module__, existing.__name__,
            )
        _ACTION_REGISTRY[action_type] = cls
        cls.ACTION_TYPE = action_type
        return cls
    return decorator


def get_action_class(action_type: str) -> type["Action"]:
    """Look up an Action class by its type string."""
    if action_type not in _ACTION_REGISTRY:
        raise ValueError(f"Unknown action type: '{action_type}'. "
                         f"Available: {list(_ACTION_REGISTRY.keys())}")
    return _ACTION_REGISTRY[action_type]


def get_all_action_types() -> list[str]:
    """Return a sorted list of all registered action type strings."""
    return sorted(_ACTION_REGISTRY.keys())


def audit_registry() -> dict[str, str]:
    """Return {type_name: 'module.ClassName'} for all registered actions.

    Call at startup to log the full registry for diagnostics.
    Example output: {'mouse_click': 'modules.mouse.MouseClick', ...}
    """
    return {
        atype: f"{cls.__module__}.{cls.__name__}"
        for atype, cls in sorted(_ACTION_REGISTRY.items())
    }


# ---------------------------------------------------------------------------
# Base Action class
# ---------------------------------------------------------------------------
class Action(ABC):
    """
    Abstract base for every automatable action.

    Subclasses must:
      - Be decorated with @register_action("type_name")
      - Implement execute()
      - Implement _get_params() and _set_params()
    """

    ACTION_TYPE: str = ""  # Set by @register_action

    def __init__(self, delay_after: int = 0, repeat_count: int = 1,
                 description: str = "", enabled: bool = True,
                 on_error: str = "stop"):
        self.id = _next_id()
        self.delay_after = delay_after        # ms to wait after execution
        self.repeat_count = max(1, repeat_count)
        self.description = description
        self.enabled = enabled
        self.on_error = on_error              # "stop" | "skip" | "retry:N"

    # -- composite interface (v3.0) ------------------------------------------
    @property
    def is_composite(self) -> bool:
        """True if this action can contain child actions.
        Override in composite subclasses (LoopBlock, If*, etc).
        """
        return False

    @property
    def children(self) -> list['Action']:
        """All child actions (flat list). For If* actions, returns then+else.
        Override in composite subclasses.
        """
        return []

    @children.setter
    def children(self, value: list['Action']) -> None:
        """Set children. Override in composites. Default: no-op."""
        pass

    @property
    def then_children(self) -> list['Action']:
        """THEN branch children for conditional actions. Default: same as children."""
        return self.children

    @then_children.setter
    def then_children(self, value: list['Action']) -> None:
        """Set THEN branch. Override in conditionals."""
        pass

    @property
    def else_children(self) -> list['Action']:
        """ELSE branch children for conditional actions. Default: empty."""
        return []

    @else_children.setter
    def else_children(self, value: list['Action']) -> None:
        """Set ELSE branch. Override in conditionals."""
        pass

    # -- abstract interface --------------------------------------------------
    @abstractmethod
    def execute(self) -> bool:
        """Run this action. Return True on success."""
        ...

    @abstractmethod
    def _get_params(self) -> dict[str, Any]:
        """Return action-specific parameters as a dict."""
        ...

    @abstractmethod
    def _set_params(self, params: dict[str, Any]) -> None:
        """Restore action-specific parameters from a dict."""
        ...

    @abstractmethod
    def get_display_name(self) -> str:
        """Human-readable summary for the action list UI."""
        ...

    # -- serialisation -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Serialise the action to a JSON-compatible dict."""
        return {
            "type": self.ACTION_TYPE,
            "params": self._get_params(),
            "delay_after": self.delay_after,
            "repeat_count": self.repeat_count,
            "description": self.description,
            "enabled": self.enabled,
            "on_error": self.on_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        """
        Deserialise an action dict into the correct Action subclass.
        This is a *factory* – call it on the base `Action` class.
        """
        action_cls = get_action_class(data["type"])
        action = action_cls.__new__(action_cls)
        Action.__init__(
            action,
            delay_after=data.get("delay_after", 0),
            repeat_count=data.get("repeat_count", 1),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            on_error=data.get("on_error", "stop"),
        )
        action._set_params(data.get("params", {}))
        return action

    # -- helpers -------------------------------------------------------------
    def _parse_retry_count(self) -> int:
        """Parse retry count from on_error='retry:N'. Returns 0 if not retry."""
        if self.on_error.startswith("retry:"):
            try:
                return max(1, int(self.on_error.split(":")[1]))
            except (IndexError, ValueError):
                return 3  # default retry count
        return 0

    def run(self) -> bool:
        """Execute the action with on_error policy support."""
        if not self.enabled:
            return True
        # Fast path: on_error='stop' (default, ~95% of actions)
        if self.on_error == 'stop':
            for _ in range(self.repeat_count):
                if not self.execute():
                    return False
                if self.delay_after > 0:
                    from core.engine_context import scaled_sleep
                    scaled_sleep(self.delay_after / 1000.0)
            return True
        # Slow path: skip/retry requires policy handling
        for _ in range(self.repeat_count):
            success = self._run_once_with_policy()
            if not success and self.on_error == "stop":
                return False
            if self.delay_after > 0:
                from core.engine_context import scaled_sleep
                scaled_sleep(self.delay_after / 1000.0)
        return True

    def _run_once_with_policy(self) -> bool:
        """Execute once, applying on_error policy."""
        retries = self._parse_retry_count()
        attempts = max(1, retries + 1) if retries > 0 else 1

        for attempt in range(attempts):
            try:
                success = self.execute()
                if success:
                    return True
                if self.on_error == "skip":
                    logger.warning("Action failed (skip): %s",
                                   self.get_display_name())
                    return True  # skip = treat as success
                if retries > 0 and attempt < attempts - 1:
                    logger.warning("Action failed, retry %d/%d: %s",
                                   attempt + 1, retries,
                                   self.get_display_name())
                    from core.engine_context import scaled_sleep
                    scaled_sleep(1.0)  # 1s between retries
                    continue
                return False  # stop
            except Exception as exc:
                logger.error("Action error: %s — %s",
                             self.get_display_name(), exc)
                if self.on_error == "skip":
                    return True
                if retries > 0 and attempt < attempts - 1:
                    logger.warning("Retry %d/%d after error",
                                   attempt + 1, retries)
                    from core.engine_context import scaled_sleep
                    scaled_sleep(1.0)
                    continue
                return False
        return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.get_display_name()}>"


# ---------------------------------------------------------------------------
# Delay action (built-in utility action)
# ---------------------------------------------------------------------------
@register_action("delay")
class DelayAction(Action):
    """Wait for a specified number of milliseconds. Supports ${var} in duration."""

    def __init__(self, duration_ms: int = 1000, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.duration_ms = max(0, duration_ms)
        self._dynamic_ms: str = ""  # e.g. "${delay_var}"

    def execute(self) -> bool:
        from core.engine_context import scaled_sleep, get_context
        ms = self.duration_ms
        if self._dynamic_ms:
            ctx = get_context()
            if ctx:
                resolved = ctx.interpolate(self._dynamic_ms)
                try:
                    ms = int(float(resolved))
                except (ValueError, TypeError):
                    ms = self.duration_ms
        scaled_sleep(ms / 1000.0)
        return True

    def _get_params(self) -> dict[str, Any]:
        p = {"duration_ms": self.duration_ms}
        if self._dynamic_ms:
            p["dynamic_ms"] = self._dynamic_ms
        return p

    def _set_params(self, params: dict[str, Any]) -> None:
        self.duration_ms = max(0, params.get("duration_ms", 1000))
        self._dynamic_ms = params.get("dynamic_ms", "")

    def get_display_name(self) -> str:
        if self._dynamic_ms:
            return f"Delay {self._dynamic_ms}"
        return f"Delay {self.duration_ms} ms"

