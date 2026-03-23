"""
Macro execution engine.
Runs a list of Actions in a worker thread with pause/resume/stop support,
progress signals, and fail-safe emergency stop.
"""

import copy
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, QObject, pyqtSignal, QMutex, QWaitCondition

from core.action import Action
from core.execution_context import ExecutionContext

logger = logging.getLogger(__name__)


class MacroEngine(QThread):
    """
    Executes a list of Actions sequentially in a background thread.

    Signals
    -------
    started_signal   : emitted when execution begins
    stopped_signal   : emitted when execution ends (normally or stopped)
    error_signal     : str – emitted on error with a description
    progress_signal  : int, int – (current_index, total_actions)
    action_signal    : str – display name of the action being executed
    loop_signal      : int, int – (current_loop, total_loops)
    """

    started_signal = pyqtSignal()
    stopped_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    action_signal = pyqtSignal(str)
    loop_signal = pyqtSignal(int, int)
    step_signal = pyqtSignal(int, str)  # L6: (action_index, display_name)

    def __init__(self, parent: 'QObject | None' = None) -> None:
        super().__init__(parent)

        self._actions: list[Action] = []
        self._loop_count: int = 1          # 0 = infinite
        self._loop_delay_ms: int = 0
        self._stop_on_error: bool = False
        self._speed_factor: float = 1.0

        # Thread-safety primitives
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self._is_paused = False
        self._is_stopped = False
        self._stop_event = threading.Event()
        # L6: Step-by-step debug mode
        self._step_mode = False

    # -- public API ----------------------------------------------------------
    def load_actions(self, actions: list[Action]) -> None:
        """Set the action list to execute (deep copy for thread safety)."""
        self._actions = copy.deepcopy(actions)

    def set_loop(self, count: int = 1, delay_ms: int = 0,
                 stop_on_error: bool = False) -> None:
        """Configure looping. count=0 means infinite."""
        self._loop_count = max(0, count)
        self._loop_delay_ms = max(0, delay_ms)
        self._stop_on_error = stop_on_error

    def set_speed_factor(self, factor: float) -> None:
        """Set playback speed multiplier (0.1 – 10.0)."""
        self._speed_factor = max(0.1, min(10.0, factor))

    def pause(self) -> None:
        self._mutex.lock()
        self._is_paused = True
        self._mutex.unlock()
        logger.info("Engine paused")

    def resume(self) -> None:
        self._mutex.lock()
        self._is_paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        logger.info("Engine resumed")

    def stop(self) -> None:
        self._mutex.lock()
        self._is_stopped = True
        self._is_paused = False
        self._step_mode = False
        self._stop_event.set()
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        logger.info("Engine stop requested")

    def set_step_mode(self, enabled: bool) -> None:
        """L6: Enable/disable step-by-step execution."""
        self._step_mode = enabled
        logger.info("Step mode: %s", "ON" if enabled else "OFF")

    def step_next(self) -> None:
        """L6: Resume to execute the next single action (used in step mode)."""
        self._mutex.lock()
        self._is_paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()

    @property
    def is_running(self) -> bool:
        return self.isRunning() and not self._is_stopped

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    # -- thread entry --------------------------------------------------------
    def run(self) -> None:
        """Main execution loop – runs in the worker thread."""
        self._is_stopped = False
        self._is_paused = False
        self._stop_event.clear()
        # Hoist imports for hot loop (OPT-3)
        from core.engine_context import set_speed, scaled_sleep, set_stop_event, set_context
        self._scaled_sleep = scaled_sleep
        set_speed(self._speed_factor)
        set_stop_event(self._stop_event)
        # Create execution context for result chaining
        self._exec_ctx = ExecutionContext()
        self._exec_ctx.reset()
        set_context(self._exec_ctx)
        self.started_signal.emit()
        logger.info("Engine started – %d actions, %s loops",
                    len(self._actions),
                    "∞" if self._loop_count == 0 else self._loop_count)

        try:
            loop_iter = 0
            total_loops = self._loop_count if self._loop_count > 0 else -1

            while not self._is_stopped:
                loop_iter += 1
                self.loop_signal.emit(loop_iter, total_loops)

                if not self._run_action_list():
                    return  # stopped or fatal error

                # --- loop control ---
                if self._loop_count > 0 and loop_iter >= self._loop_count:
                    break

                if not self._wait_loop_delay():
                    return  # stopped during delay

        except Exception as exc:
            logger.error("Engine fatal error: %s", exc, exc_info=True)
            self.error_signal.emit(f"Fatal: {exc}")
        finally:
            self.stopped_signal.emit()
            logger.info("Engine finished")

    def _check_pause_or_stop(self) -> bool:
        """Handle pause/stop. Returns False if stopped."""
        self._mutex.lock()
        while self._is_paused and not self._is_stopped:
            self._pause_condition.wait(self._mutex)
        self._mutex.unlock()
        return not self._is_stopped

    def _execute_single_action(self, idx: int, action: 'Action') -> bool:
        """Execute one action. Returns False if engine should stop."""
        self.progress_signal.emit(idx + 1, len(self._actions))
        self.action_signal.emit(action.get_display_name())
        logger.info("Executing [%d/%d]: %s",
                     idx + 1, len(self._actions),
                     action.get_display_name())

        try:
            success = action.run()
            if self._exec_ctx:
                self._exec_ctx.record_action(success)
            if not success:
                self.error_signal.emit(
                    f"Action failed: {action.get_display_name()}")
                if self._stop_on_error:
                    logger.info("Stopping on error (stop_on_error=True)")
                    return False
            # L6: Step mode — pause after each action
            if self._step_mode and not self._is_stopped:
                self.step_signal.emit(idx, action.get_display_name())
                self._mutex.lock()
                self._is_paused = True
                while self._is_paused and not self._is_stopped:
                    self._pause_condition.wait(self._mutex)
                self._mutex.unlock()
        except Exception as exc:
            error_msg = f"Error in {action.get_display_name()}: {exc}"
            logger.error(error_msg, exc_info=True)
            self.error_signal.emit(error_msg)
            if self._stop_on_error:
                return False
        return True

    def _run_action_list(self) -> bool:
        """Run all actions once. Returns False if stopped."""
        for idx, action in enumerate(self._actions):
            if not self._check_pause_or_stop():
                return False
            if not self._execute_single_action(idx, action):
                return False
        return True

    def _wait_loop_delay(self) -> bool:
        """Interruptible sleep for loop delay. Returns False if stopped."""
        if self._loop_delay_ms <= 0:
            return True
        sleep_end = time.perf_counter() + self._loop_delay_ms / 1000.0
        while time.perf_counter() < sleep_end:
            if self._is_stopped:
                return False
            self._scaled_sleep(min(0.1, sleep_end - time.perf_counter()))
        return True

    # -- macro file I/O -------------------------------------------------------
    MACRO_VERSION = "1.1"

    @staticmethod
    def save_macro(filepath: str, actions: list[Action],
                   name: str = "Untitled",
                   loop_count: int = 1,
                   loop_delay_ms: int = 0) -> None:
        """Save a macro to a JSON file."""
        data = {
            "name": name,
            "version": MacroEngine.MACRO_VERSION,
            "settings": {
                "loop_count": loop_count,
                "delay_between_loops": loop_delay_ms,
            },
            "actions": [a.to_dict() for a in actions],
        }
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        logger.info("Macro saved to %s (%d actions)", filepath, len(actions))

    @staticmethod
    def load_macro(filepath: str) -> tuple[list[Action], dict[str, Any]]:
        """
        Load a macro from a JSON file.
        Returns (actions_list, settings_dict).
        Raises ValueError if file is corrupt or invalid.
        """
        path = Path(filepath)
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"Cannot read macro file: {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Macro file is corrupt (invalid JSON): {exc}"
            ) from exc

        if not isinstance(data, dict) or "actions" not in data:
            raise ValueError(
                "Macro file has invalid format (missing 'actions' key)"
            )

        actions: list[Action] = []
        for i, a in enumerate(data.get("actions", [])):
            try:
                actions.append(Action.from_dict(a))
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("Skipping invalid action #%d: %s", i, exc)

        settings = data.get("settings", {})
        settings["name"] = data.get("name", "Untitled")
        logger.info("Macro loaded from %s (%d actions)",
                    filepath, len(actions))
        return actions, settings
