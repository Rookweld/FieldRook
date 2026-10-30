# PyInstaller one-dir spec: FieldRook-Server (M025 BETA desktop runtime).
# Built by build.ps1 (which builds the worker one-dir first, then points
# WORKER_DIST_DIR at it so the worker ships as data inside the server
# bundle at <bundle>/demo-worker/fieldrook-demo-worker.exe).
# Console ON by contract: startup/shutdown errors must be visible in the
# window AND logged to %LOCALAPPDATA%\FieldRook\logs.
# Run from this directory:
#   pyinstaller --distpath <out>\dist --workpath <out>\work fieldrook-server.spec

import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
REPO_ROOT = os.path.abspath(os.path.join(SPEC_DIR, "..", ".."))
WORKER_DIST_DIR = os.environ.get("FIELDROOK_WORKER_DIST", "")

datas = [
    (os.path.join(REPO_ROOT, "frontend", "dist"), "frontend-dist"),
    (os.path.join(REPO_ROOT, "VERSION"), "."),
]
if WORKER_DIST_DIR and os.path.isdir(WORKER_DIST_DIR):
    datas.append((os.path.join(WORKER_DIST_DIR, "*"), "demo-worker"))

a = Analysis(
    [os.path.join(SPEC_DIR, "fieldrook-server-entry.py")],
    pathex=[os.path.join(REPO_ROOT, "backend"), REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Collector package (stdlib-only, statically imported; belt and braces
        # next to the runtime sys.path fallback in collector_import.py).
        "collector",
        "collector.archive",
        "collector.chunker",
        "collector.hashverify",
        "collector.manifest",
        "collector.redact_import",
        # Uvicorn server pieces PyInstaller cannot see statically.
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "multipart",
    ],
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
    name="FieldRook-Server",
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
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FieldRook-Server",
)
