# -*- mode: python ; coding: utf-8 -*-
#
# xWavetable - PyInstaller Spec-Datei
# ====================================
# Erstellt eine eigenstaendige .exe (Windows) oder Binary (Linux/macOS).
#
# Build-Befehl (aus dem Ordner mit dieser .spec und xwavetable_app.py):
#
#   pip install pyinstaller
#   pyinstaller xWavetable.spec
#
# Die fertige .exe liegt danach unter:  dist/xWavetable.exe
#
# Optional: tkinterdnd2 fuer Drag & Drop miteinbauen:
#   pip install tkinterdnd2
#   -> PyInstaller findet es dann automatisch.

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# tkinterdnd2-Daten mitpacken, falls installiert
datas = []
hiddenimports = []
try:
    import tkinterdnd2
    datas += collect_data_files('tkinterdnd2')
    hiddenimports += collect_submodules('tkinterdnd2')
except ImportError:
    pass

a = Analysis(
    ['xwavetable_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + ['numpy', 'tkinter', 'tkinter.ttk',
                                    'tkinter.scrolledtext', 'tkinter.filedialog',
                                    'tkinter.messagebox'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'PIL', 'PyQt5', 'PyQt6', 'wx',
              'IPython', 'jupyter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='xWavetable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,            # UPX-Komprimierung (ca. 30% kleiner), optional
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # kein schwarzes Konsolenfenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='xwavetable.ico',   # <-- muss im selben Ordner wie die .spec liegen
)
