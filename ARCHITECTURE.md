# Auto Mouse & Keyboard — Architecture Guide

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                       main.py                           │
│              Entry point, hotkey setup                   │
└────────────────┬────────────────────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │    gui/main_window.py    │  ← Imports ALL modules at startup
    │  (QTableWidget, Toolbar) │
    └──┬──────┬──────┬────────┘
       │      │      │
  ┌────▼──┐ ┌─▼───┐ ┌▼────────────┐
  │action │ │rec  │ │settings     │
  │editor │ │panel│ │dialog       │
  └───────┘ └─────┘ └─────────────┘
```

## Module Architecture

### Core Layer (`core/`)

| File | Purpose | Key Classes |
|------|---------|-------------|
| `action.py` | Action base class, registry, serialization | `Action`, `register_action()`, `audit_registry()` |
| `engine.py` | Macro execution (flat list, threaded) | `MacroEngine` |
| `scheduler.py` | **7 flow control actions** (Composite Pattern) | `LoopBlock`, `IfImageFound`, `IfVariable`, etc |
| `execution_context.py` | Shared state between actions | `ExecutionContext` |
| `engine_context.py` | Thread-local context helpers | `set_speed()`, `scaled_sleep()` |
| `recorder.py` | Input recording (mouse + keyboard) | `Recorder` |
| `hotkey_manager.py` | Global hotkey registration | `HotkeyManager` |
| `undo_commands.py` | Undo/redo commands for action list | `AddActionCommand`, etc |
| `autosave.py` | Auto-save timer | `AutoSaveManager` |
| `crash_handler.py` | Global exception handler | `CrashHandler` |
| `memory_manager.py` | Memory monitoring + cleanup | `MemoryManager` |

### Modules Layer (`modules/`)

Each module registers **atomic** action types via `@register_action()`.

| File | Types | Count |
|------|-------|-------|
| `mouse.py` | mouse_click, mouse_double_click, mouse_right_click, mouse_move, mouse_drag, mouse_scroll | 6 |
| `keyboard.py` | key_press, key_combo, type_text, hotkey | 4 |
| `image.py` | wait_for_image, click_on_image, image_exists, take_screenshot | 4 |
| `pixel.py` | check_pixel_color, wait_for_color | 2 |
| `system.py` | activate_window, log_to_file, read_clipboard, read_file_line, write_to_file, secure_type_text, run_macro, capture_text | 8 |
| `screen.py` | *(utilities only, no registered types)* | 0 |
| **core/scheduler.py** | loop_block, if_image_found, if_pixel_color, if_variable, set_variable, split_string, comment | **7** |
| **Total** | | **31** |

> ⚠️ Note: `core/scheduler.py` registers 7 types but lives in `core/`, not `modules/`.
> This is intentional — these are composite/flow-control actions, not atomic actions.

## Action Registration

```python
# Every Action subclass is registered via decorator:
@register_action("mouse_click")    # ← type string
class MouseClick(Action):          # ← Python class
    ...
```

**Rules:**
1. Each `action_type` string MUST be unique across ALL modules
2. `register_action()` will **warn** if a type is registered twice (safeguard added 2026-03-23)
3. Import order determines which registration wins (last import wins)
4. All modules are imported in `gui/main_window.py` lines 50-55

## Data Flow

```
User creates action in ActionEditor
    → _collect_params() reads widgets → dict
    → get_action_class(type)(**params) → Action instance
    → Added to MainWindow._actions list
    → Displayed in QTableWidget

User clicks Play
    → MacroEngine.load_actions(deep_copy)
    → engine.run() in QThread
    → _run_action_list() iterates flat list
    → Each action.run() handles its own sub-actions (Composite Pattern)

Save/Load
    → MacroEngine.save_macro() → JSON file
    → Action.to_dict() serializes params + children
    → Action.from_dict() deserializes recursively
```

## GUI Layer (`gui/`)

| File | Purpose |
|------|---------|
| `main_window.py` | Main application window, action table, toolbar |
| `action_editor.py` | Dialog for creating/editing actions (per-type builders) |
| `settings_dialog.py` | App settings (hotkeys, defaults) |
| `recording_panel.py` | Recording controls (record/pause/stop) |
| `help_dialog.py` | Action type help/documentation |

## Key Design Patterns

1. **Command Pattern** — Each `Action` is a self-contained command
2. **Registry Pattern** — `@register_action()` decorator + `_ACTION_REGISTRY`
3. **Composite Pattern** — `LoopBlock`, `IfImageFound` etc contain child actions
4. **Builder Pattern** — `action_editor.py` has per-type `_build_*_params()` methods
5. **Undo/Redo** — Qt's `QUndoCommand` for reversible action list mutations
