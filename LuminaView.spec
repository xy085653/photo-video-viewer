# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for LuminaView
打包命令: pyinstaller LuminaView.spec
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH)  # spec 文件所在目录

a = Analysis(
    [str(PROJECT_ROOT / 'main.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # QSS 样式
        (str(PROJECT_ROOT / 'qss' / 'style.qss'), 'qss'),
        # SVG 图标（含软件图标）
        (str(PROJECT_ROOT / 'svg'), 'svg'),
    ],
    hiddenimports=[
        # PySide6 相关
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtNetwork',
        # widgets 包
        'widgets',
        'widgets.image_state',
        'widgets.toolbar',
        'widgets.folder_tree',
        'widgets.thumbnail_panel',
        'widgets.thumbnail_loader',
        'widgets.preview_panel',
        'widgets.video_player',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'email',
        'http',
        'xmlrpc',
        'pydoc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LuminaView',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlement_file=None,
    icon=str(PROJECT_ROOT / 'svg' / 'luminaview_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LuminaView',
)
