# PyInstaller spec: macOS .app for `python -m gui` (ADB-only UI).
# Build: pyinstaller yulang_gui.spec
# Requires: pip install pyinstaller (from the same venv as the project).

from pathlib import Path

# PyInstaller injects SPECPATH when executing this file (__file__ is not defined here).
ROOT = Path(SPECPATH).resolve()

block_cipher = None

a = Analysis(
    [str(ROOT / "gui" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "templates" / "adb"), "templates/adb")],
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="YulangADB",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name="YulangADB",
)

app = BUNDLE(
    coll,
    name="YulangADB.app",
    icon=None,
    bundle_identifier="local.yulang.adb",
)
