"""Desktop frozen-path helper (M025 BETA): dev vs frozen resolution.

Covers `app.paths`: the ONE module that knows the dev/frozen split. Frozen
behavior is simulated by monkeypatching `sys._MEIPASS` (which is exactly
what `is_frozen()` keys on) plus `LOCALAPPDATA` for the user data dir.
"""

import os
import sys
from pathlib import Path

import pytest

from app import paths
from app.config import load_settings
from app.version import FALLBACK_VERSION, get_version

REPO_ROOT = Path(__file__).resolve().parents[2]


def _freeze(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Simulate a PyInstaller bundle rooted at tmp_path/'bundle'."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert paths.is_frozen()
    assert paths.bundle_dir() == bundle
    return bundle


def test_dev_bundle_dir_is_repo_root() -> None:
    assert not paths.is_frozen()
    assert paths.bundle_dir() == REPO_ROOT
    assert (REPO_ROOT / "VERSION").is_file()


def test_user_data_dir_honors_localappdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert paths.user_data_dir() == tmp_path / "FieldRook"
    assert paths.logs_dir() == tmp_path / "FieldRook" / "logs"
    assert paths.lock_file() == tmp_path / "FieldRook" / "fieldrook.lock"


def test_db_path_override_always_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom.db"
    monkeypatch.setenv("FIELDROOK_DB_PATH", str(custom))
    assert paths.default_db_path() == custom
    _freeze(monkeypatch, tmp_path)
    assert paths.default_db_path() == custom


def test_dev_db_path_is_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIELDROOK_DB_PATH", raising=False)  # conftest pins a scratch DB
    assert paths.default_db_path() == REPO_ROOT / "backend" / "data" / "fieldrook.db"


def test_frozen_db_path_never_touches_dev_checkout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FIELDROOK_DB_PATH", raising=False)
    _freeze(monkeypatch, tmp_path)
    frozen_db = paths.default_db_path()
    assert frozen_db == tmp_path / "local" / "FieldRook" / "fieldrook.db"
    assert frozen_db != REPO_ROOT / "backend" / "data" / "fieldrook.db"


def test_demo_state_override_and_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIELDROOK_DEMO_STATE", str(tmp_path / "demo"))
    assert paths.default_demo_state_dir() == tmp_path / "demo"
    monkeypatch.delenv("FIELDROOK_DEMO_STATE")
    assert paths.default_demo_state_dir() == REPO_ROOT / "demo_worker" / "state"
    _freeze(monkeypatch, tmp_path)
    assert paths.default_demo_state_dir() == tmp_path / "local" / "FieldRook" / "demo-state"


def test_worker_command_dev_shape() -> None:
    command = paths.worker_command()
    assert command[0] == sys.executable
    assert command[1] == str(REPO_ROOT / "demo_worker" / "worker.py")


def test_worker_script_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = tmp_path / "custom_worker.py"
    script.write_text("# test worker\n", encoding="utf-8")
    monkeypatch.setenv("FIELDROOK_WORKER_SCRIPT", str(script))
    assert paths.worker_script_path() == script
    assert paths.worker_command() == [sys.executable, str(script)]
    exe = tmp_path / "custom.EXE"
    monkeypatch.setenv("FIELDROOK_WORKER_SCRIPT", str(exe))
    assert paths.worker_command() == [str(exe)]


def test_worker_command_frozen_uses_bundled_exe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FIELDROOK_WORKER_SCRIPT", raising=False)
    bundle = _freeze(monkeypatch, tmp_path)
    expected = bundle / "demo-worker" / "fieldrook-demo-worker.exe"
    assert paths.worker_exe_path() == expected
    assert paths.worker_command() == [str(expected)]


def test_frontend_dist_dev_detection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dist = tmp_path / "repo" / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(paths, "bundle_dir", lambda: tmp_path / "repo")
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert paths.frontend_dist_dir() == dist
    (dist / "index.html").unlink()
    assert paths.frontend_dist_dir() is None


def test_frontend_dist_frozen_location(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundle = _freeze(monkeypatch, tmp_path)
    assert paths.frontend_dist_dir() is None
    dist = bundle / "frontend-dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    assert paths.frontend_dist_dir() == dist


def test_dotenv_path_override_dev_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    explicit = tmp_path / "custom.env"
    monkeypatch.setenv("FIELDROOK_ENV_FILE", str(explicit))
    assert paths.dotenv_path() == explicit
    monkeypatch.delenv("FIELDROOK_ENV_FILE")
    assert paths.dotenv_path() == REPO_ROOT / ".env"
    _freeze(monkeypatch, tmp_path)
    frozen_env = paths.dotenv_path()
    assert frozen_env == tmp_path / "local" / "FieldRook" / ".env"
    assert frozen_env != REPO_ROOT / ".env"


def test_collector_search_path_matches_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert paths.collector_search_path() == REPO_ROOT
    bundle = _freeze(monkeypatch, tmp_path)
    assert paths.collector_search_path() == bundle


def test_frozen_dotenv_loads_from_user_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Frozen `load_settings()` reads the per-user .env, never repo root."""
    _freeze(monkeypatch, tmp_path)
    user_env = tmp_path / "local" / "FieldRook" / ".env"
    user_env.parent.mkdir(parents=True)
    user_env.write_text("MODEL_API_KEY=user-env-key\n", encoding="utf-8")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("FIELDROOK_OFFLINE", raising=False)
    monkeypatch.delenv("FIELDROOK_ENV_FILE", raising=False)
    settings = load_settings()
    assert settings.model_api_key == "user-env-key"


def test_version_reads_version_file() -> None:
    expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert expected
    assert get_version() == expected


def test_version_falls_back_when_unreadable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import app.version as version_module

    monkeypatch.setattr(version_module, "version_file", lambda: tmp_path / "no-such-VERSION")
    assert get_version() == FALLBACK_VERSION
