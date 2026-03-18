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
        ('macros', 'macros'),
    ],
    hiddenimports=[
        'modules.mouse',
        'modules.keyboard',
        'modules.image',
        'modules.pixel',
        'modules.screen',
        'core.scheduler',
        'core.action',
        'core.engine',
        'core.recorder',
        'core.memory_manager',
        'core.hotkey_manager',
        'core.crash_handler',
        'core.profiler',
        'core.autosave',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas'],
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
