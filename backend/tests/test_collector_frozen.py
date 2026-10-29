"""Frozen collector smoke tests (M025 ALPHA).

Exercises the PyInstaller one-dir ``FieldRook-Collector.exe`` when it has
been built (``packaging/collector/Build-Collector.ps1``). Every test skips
gracefully with a reason when the exe is absent, so the backend suite stays
green on machines that never build it.

Byte-compatibility here means: exe-produced packages pass the EXISTING
verify path (``collector.archive.extract_and_verify``) and the existing
import endpoint unchanged — the ZIP format is FROZEN
(``docs/FORGE_CONTRACTS.md`` section 2), so no byte-identical fixture
comparison is needed or wanted (package IDs and timestamps vary per run).
"""

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, REPO_ROOT)

from collector import archive  # noqa: E402

EXE_ENV_VAR = "FIELDROOK_COLLECTOR_EXE"
DEFAULT_EXE = os.path.join(
    REPO_ROOT, "dist", "collector", "FieldRook-Collector", "FieldRook-Collector.exe"
)
BUILD_HINT = "run packaging/collector/Build-Collector.ps1 to build it"
SAMPLE_BASIC = os.path.join(REPO_ROOT, "collector", "samples", "sample_basic.zip")
TIMEOUT_S = 180


def _exe_path() -> str:
    override = os.environ.get(EXE_ENV_VAR, "").strip()
    candidate = override or DEFAULT_EXE
    if not candidate or not os.path.isfile(candidate):
        pytest.skip(f"collector exe not built ({candidate or DEFAULT_EXE!r} missing); {BUILD_HINT}")
    return candidate


def _run(exe: str, *args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [exe, *args], capture_output=True, text=True, timeout=TIMEOUT_S, cwd=cwd
    )


def test_exe_help_matches_module_cli():
    exe = _exe_path()
    frozen = _run(exe, "--help")
    assert frozen.returncode == 0
    module = _run(sys.executable, "-m", "collector", "--help", cwd=REPO_ROOT)
    assert module.returncode == 0
    assert frozen.stdout == module.stdout
    assert "collect" in frozen.stdout and "validate" in frozen.stdout


def test_exe_collect_requires_yes(tmp_path):
    exe = _exe_path()
    dest = tmp_path / "pkg.zip"
    proc = _run(exe, "collect", "--out", str(dest))
    assert proc.returncode == 2
    assert "--yes" in (proc.stdout + proc.stderr)
    assert "Refusing to collect without --yes" in proc.stdout
    assert not dest.exists()


def test_exe_validate_sample():
    exe = _exe_path()
    proc = _run(exe, "validate", SAMPLE_BASIC)
    assert proc.returncode == 0
    assert proc.stdout.startswith("VALID:")


def test_exe_collect_validate_roundtrip(tmp_path):
    exe = _exe_path()
    dest = tmp_path / "frozen-pkg.zip"
    collected = _run(
        exe, "collect", "--fixture", "--yes", "--out", str(dest),
        "--hint", "frozen-smoke",
    )
    assert collected.returncode == 0, collected.stderr
    assert dest.is_file()
    validated = _run(exe, "validate", str(dest))
    assert validated.returncode == 0
    assert validated.stdout.startswith("VALID:")
    # Existing verify path (structure + file_hashes + manifest schema).
    out, loaded, _warnings = archive.extract_and_verify(dest, tmp_path / "out")
    assert out.is_dir()
    assert loaded["schema_version"] == "1.0"
    assert loaded["target_hint"] == "frozen-smoke"
    assert len(loaded["evidence"]) > 0
