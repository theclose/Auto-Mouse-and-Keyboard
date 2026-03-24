# Contributing to AutoMacro

## Code Style

This project uses automated formatting and linting:

- **[Black](https://github.com/psf/black)** — Auto-formatting (line length: 120)
- **[Ruff](https://github.com/astral-sh/ruff)** — Linting (E/F/W/I rules)
- **[Mypy](https://mypy-lang.org/)** — Optional type checking

```bash
# Format before committing
python -m black core/ gui/ modules/ main.py

# Check for lint issues
python -m ruff check core/ gui/ modules/ main.py

# Auto-fix lint issues
python -m ruff check --fix core/ gui/ modules/ main.py
```

## Testing

Run the full test suite before submitting changes:

```bash
python -m pytest tests/ -q
```

All 558 tests must pass. Tests run headless via `QT_QPA_PLATFORM=offscreen`.

## Adding a New Action Type

1. Create the action class in the appropriate `modules/*.py` file
2. Use `@register_action("type_name")` decorator — see `core/action.py`
3. Never duplicate `action_type` strings across files
4. Follow the Composite Pattern for flow control actions

## Silent Failure Prevention Checklist

When modifying existing features, verify:

- [ ] **Dimension check**: Does this change add a new data dimension? Audit all consumers
- [ ] **Return guards**: Do all early returns provide user feedback or logging?
- [ ] **Exception handling**: No bare `except: pass` — at minimum use `logger.debug()`
- [ ] **State sync**: Mutations call `_mark_dirty()`, UI updates call `_refresh_table()`
- [ ] **Composite awareness**: Test with LoopBlock/IfImageFound (nested sub-actions)
- [ ] **Undo integration**: Data mutations wrapped in `QUndoCommand` or `CompositeChildrenCommand`

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design documentation.
