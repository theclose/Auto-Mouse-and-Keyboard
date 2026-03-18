"""
Action system using the Command pattern.
Each action is a self-contained command that can be serialized/deserialized,
executed, and composed into macro sequences.
"""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any


# ---------------------------------------------------------------------------
# Action Registry – maps type strings to Action subclasses
# ---------------------------------------------------------------------------
_ACTION_REGISTRY: dict[str, type["Action"]] = {}


def register_action(action_type: str) -> Any:
    """Decorator to register an Action subclass in the global registry."""
    def decorator(cls: type["Action"]) -> type["Action"]:
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
                 description: str = "", enabled: bool = True):
        self.id = str(uuid.uuid4())[:8]
        self.delay_after = delay_after        # ms to wait after execution
        self.repeat_count = max(1, repeat_count)
        self.description = description
        self.enabled = enabled

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
        )
        action._set_params(data.get("params", {}))
        return action

    # -- helpers -------------------------------------------------------------
    def run(self) -> bool:
        """Execute the action repeat_count times with delay_after."""
        if not self.enabled:
            return True
        for _ in range(self.repeat_count):
            success = self.execute()
            if not success:
                return False
            if self.delay_after > 0:
                from core.engine_context import scaled_sleep
                scaled_sleep(self.delay_after / 1000.0)
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.get_display_name()}>"


# ---------------------------------------------------------------------------
# Delay action (built-in utility action)
# ---------------------------------------------------------------------------
@register_action("delay")
class DelayAction(Action):
    """Wait for a specified number of milliseconds."""

    def __init__(self, duration_ms: int = 1000, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.duration_ms = max(0, duration_ms)

    def execute(self) -> bool:
        from core.engine_context import scaled_sleep
        scaled_sleep(self.duration_ms / 1000.0)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"duration_ms": self.duration_ms}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.duration_ms = max(0, params.get("duration_ms", 1000))

    def get_display_name(self) -> str:
        return f"Delay {self.duration_ms} ms"
