"""
Smoke Test — Verifies MainWindow() can initialize without crashing.

This catches "phantom method" bugs like .connect(self._nonexistent_method)
that bypass unit tests because stubs skip __init__ entirely.

Uses the shared `real_main_window` fixture from conftest.py.

Run: python -m pytest tests/test_smoke.py -v
"""


class TestMainWindowSmoke:
    """Smoke tests: MainWindow initializes and has critical widgets."""

    def test_init_no_crash(self, real_main_window):
        """GATE: MainWindow() must not crash on init."""
        assert real_main_window is not None

    def test_has_critical_widgets(self, real_main_window):
        """All critical UI panels must exist after init."""
        assert hasattr(real_main_window, "_tree"), "Missing: ActionTree"
        assert hasattr(real_main_window, "_playback_panel"), "Missing: PlaybackPanel"
        assert hasattr(real_main_window, "_rec_panel"), "Missing: RecordingPanel"
        assert hasattr(real_main_window, "_exec_panel"), "Missing: ExecutionPanel"
        assert hasattr(real_main_window, "_var_panel"), "Missing: VariablePanel"
        assert hasattr(real_main_window, "_minimap"), "Missing: MiniMap"
        assert hasattr(real_main_window, "_log_panel"), "Missing: LogPanel"
        assert hasattr(real_main_window, "_right_tabs"), "Missing: Right QTabWidget"

    def test_signal_connections_exist(self, real_main_window):
        """Key signal targets must be valid methods."""
        critical_methods = [
            "_on_play", "_on_pause", "_on_stop",
            "_on_edit_action", "_on_move_up", "_on_move_down",
            "_on_duplicate", "_on_add_action", "_on_open",
            "_on_copy_actions", "_on_paste_actions", "_on_delete_action",
        ]
        for method_name in critical_methods:
            assert hasattr(real_main_window, method_name), (
                f"Missing method: {method_name} — signal connection will crash"
            )
