# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-dir spec for FieldRook-Collector.exe (M025 ALPHA).

Build via ``packaging/collector/Build-Collector.ps1`` (it pins the
PyInstaller version and sets dist/work paths). Direct use also works::

    pyinstaller --clean --noconfirm packaging/collector/FieldRook-Collector.spec

Contract notes (M025):

- one-dir (``exclude_binaries=True`` + ``COLLECT``): no per-launch unpack
  cost, smaller AV-heuristic surface than one-file;
- ``console=True``: the consent screen must stay visible;
- ``upx=False``: reproducible output, no UPX packing;
- hidden imports list every ``collector.*`` module explicitly so the
  function-local imports in ``archive.py`` (``hashverify``, ``manifest``)
  can never be missed by static analysis.
"""

from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = str(SPEC_DIR.parent.parent)

block_cipher = None


a = Analysis(
    [str(SPEC_DIR / "collector_entry.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        "collector",
        "collector.__main__",
        "collector.archive",
        "collector.chunker",
        "collector.collect_windows",
        "collector.hashverify",
        "collector.manifest",
        "collector.redact_import",
    ],
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
    name="FieldRook-Collector",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
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
    upx=False,
    upx_exclude=[],
    name="FieldRook-Collector",
)
