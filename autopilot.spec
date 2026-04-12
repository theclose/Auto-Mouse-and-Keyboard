# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AutoPilot.

Build command:
    pyinstaller autopilot.spec

Output: dist/AutoPilot/AutoPilot.exe (one-dir)
For single exe: change to a.exe with --onefile flag
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('macros/example.json', 'macros'),
    ],
    hiddenimports=[
        # version
        'version',
        # core
        'core.action',
        'core.app_paths',
        'core.autosave',
        'core.crash_handler',
        'core.engine',
        'core.engine_context',
        'core.event_bus',
        'core.execution_context',
        'core.hotkey_manager',
        'core.macro_templates',
        'core.memory_manager',
        'core.profiler',
        'core.recorder',
        'core.retry',
        'core.scheduler',
        'core.secure',
        'core.smart_hints',
        'core.undo_commands',
        # gui
        'gui.__init__',
        'gui.action_editor',
        'gui.action_tree_model',
        'gui.constants',
        'gui.coordinate_picker',
        'gui.help_content',
        'gui.help_dialog',
        'gui.image_capture',
        'gui.image_preview_widget',
        'gui.main_window',
        'gui.no_scroll_widgets',
        'gui.region_picker',
        'gui.panels',
        'gui.panels.action_list_panel',
        'gui.panels.execution_panel',
        'gui.panels.log_panel',
        'gui.panels.minimap_panel',
        'gui.panels.playback_panel',
        'gui.panels.properties_panel',
        'gui.panels.variable_panel',
        'gui.recording_panel',
        'gui.settings_dialog',
        'gui.styles',
        'gui.tray',
        # modules
        'modules.image',
        'modules.keyboard',
        'modules.mouse',
        'modules.pixel',
        'modules.screen',
        'modules.system',
        # platform
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'PyQt5', 'PySide2', 'PySide6', 'flet', 'flet_core'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutoPilot',
)
