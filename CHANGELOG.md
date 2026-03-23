# Changelog

All notable changes to AutoMacro are documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/) + [Semantic Versioning](https://semver.org/).

## [3.0.1] - 2026-03-23

### Fixed
- **Sprint 0:** Repaired 5 broken test files (262→403 tests)
  - Added v3.0 tree view attributes to MainWindow test stubs
  - Fixed `_create_default_icon` → `_create_icon` rename in tray tests
  - Fixed pyautogui lazy-load mock path (`modules.mouse._pag`)
  - Updated capture button text detection for Vietnamese UI
  - Fixed Vietnamese status text assertions (Đang chạy, Đã dừng)
  - Patched QMessageBox.warning in engine callback tests

### Added
- **Sprint 1:** 2 new test files (+45 tests → 448 total)
  - `test_action_tree_model.py` (31 tests): tree model v3.0 coverage
  - `test_retry_secure.py` (14 tests): retry decorator + DPAPI encryption
- **Sprint 2:** Security hardening
  - `_validate_path()`: path traversal prevention for `WriteToFile` and `RunMacro`
  - `.json` extension validation for `RunMacro`
  - Docstrings added to `scheduler.py` (~25 methods)
  - `README.md` and `CHANGELOG.md` project documentation

## [3.0.0] - 2026-03-23

### Added
- **v3.0 Phase 1-3:** QTreeView alongside QTableWidget
  - `ActionTreeModel` — QAbstractItemModel for hierarchical display
  - Composite action tree view (LoopBlock, IfImageFound, IfPixelColor, IfVariable)
  - THEN/ELSE branch visualization
  - Toggle between table view and tree view
  - Tree node drag-drop support
- **Variable Inspector:** Live variable panel during execution
- **Step-through Mode:** Single-step debugging for macros
- **GUI Consistency Audit:** 7 fixes for action tree + GUI consistency
  - `has_branches` property on composite actions
  - Fixed `_selected_row()`/`_selected_rows()` for tree mode
  - Expanded `_TYPE_ICONS` to cover all 31 types
  - Fixed `CheckState` comparison for enum vs string
- **Context Image Preservation:** Mouse action editor preserves `context_image`
- Full Vietnamization of all UI labels

## [2.0.0] - 2026-03-17

### Added
- Composite Pattern for flow control (LoopBlock, If* actions)
- Variable system with `ExecutionContext`
- Undo/Redo via Qt QUndoStack
- AutoSave manager (60s timer)
- CrashHandler with auto-recovery
- Memory monitoring + cleanup
- Performance profiler
- Retry decorator for transient failures
- DPAPI-encrypted text input
- Dark theme with glassmorphism
- System tray with state indicator
- Recording panel with pause/resume
- Coordinate picker with magnifier
- Image capture overlay (screen snip)
- Help dialog with action documentation
- 31 registered action types

## [1.0.0] - 2026-03-12

### Added
- Initial release with basic mouse/keyboard automation
- PyQt6 desktop UI
- JSON macro save/load
- pyautogui integration
