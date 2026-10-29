"""Frozen entry point for FieldRook-Collector.exe (M025 ALPHA).

PyInstaller one-dir entry script. Imports the stdlib-only ``collector``
package (found via ``pathex`` = repo root in the spec) and runs the
identical CLI as ``python -m collector``: same commands (``collect`` |
``validate``), same exit codes, same consent double-gate.

No behavior lives here: this module only forwards to
:func:`collector.__main__.main`.
"""

from collector.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
