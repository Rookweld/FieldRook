"""Desktop instance identity + single release-version source (M025 ZETA).

`/api/status` answers identity: service + runtime (`"desktop"` for the
frozen packaged app, `"dev"` for source checkouts) + version. The version
has ONE source (the VERSION file via `get_version()`); the launcher uses
`runtime` to tell a Desktop instance from a dev server on the same port.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_package
from app.main import app
from app.routers import incidents
from app.version import get_version

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VERSION = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

client = TestClient(app)


def test_status_reports_release_version_and_dev_runtime() -> None:
    assert EXPECTED_VERSION
    body = client.get("/api/status").json()
    assert body["service"] == "fieldrook-api"
    assert body["version"] == EXPECTED_VERSION
    assert body["runtime"] == "dev"


def test_status_reports_desktop_runtime_when_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frozen builds identify as the Desktop runtime (launcher 'already')."""
    monkeypatch.setattr(incidents, "is_frozen", lambda: True)
    body = client.get("/api/status").json()
    assert body["runtime"] == "desktop"
    assert body["version"] == EXPECTED_VERSION


def test_package_dunder_version_matches_version_file() -> None:
    """No second version literal: the dunder follows the VERSION file too."""
    assert app_package.__version__ == EXPECTED_VERSION
    assert get_version() == EXPECTED_VERSION
