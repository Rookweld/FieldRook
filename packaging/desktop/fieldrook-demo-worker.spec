# PyInstaller one-dir spec: fieldrook-demo-worker (M025 BETA desktop runtime).
# Stdlib-only background process, shipped as data inside the server bundle
# (see fieldrook-server.spec). Console OFF: it is detached by design and
# logs to the demo-state dir; it must never flash a window.
# Run from this directory:
#   pyinstaller --distpath <out>\dist --workpath <out>\work fieldrook-demo-worker.spec

import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
REPO_ROOT = os.path.abspath(os.path.join(SPEC_DIR, "..", ".."))

a = Analysis(
    [os.path.join(REPO_ROOT, "demo_worker", "worker.py")],
    pathex=[os.path.join(REPO_ROOT, "demo_worker")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="fieldrook-demo-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="fieldrook-demo-worker",
)
