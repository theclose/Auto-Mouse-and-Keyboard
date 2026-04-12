"""
Application path resolution — single source of truth.

Provides APP_DIR, LOG_DIR, CONFIG_PATH for both:
  - Development: paths relative to project root
  - Frozen EXE: paths relative to exe's parent directory

This module must NOT import from main.py or create side-effects.
"""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle: use exe's parent directory
    APP_DIR = Path(sys.executable).parent
else:
    # Development: project root = parent of core/
    APP_DIR = Path(__file__).resolve().parent.parent

LOG_DIR = APP_DIR / "logs"
CONFIG_PATH = APP_DIR / "config.json"
MACROS_DIR = APP_DIR / "macros"
TEMPLATES_DIR = APP_DIR / "templates"
