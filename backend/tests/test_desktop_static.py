"""Desktop single-process serving (M025 BETA): UI at / + JSON API side by side.

`create_app()` serves the built UI when a dist dir is present and stays a
pure JSON API otherwise. The `StaticFiles` mount must come AFTER all
`/api/*` routers so API routes always win.
"""

from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app, create_app

INDEX_HTML = "<!doctype html><html><body>FieldRook test UI</body></html>\n"
APP_JS = "console.log('test');\n"


def _write_dist(root: Path) -> Path:
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "app.js").write_text(APP_JS, encoding="utf-8")
    return dist


def test_root_serves_index_when_dist_present(tmp_path: Path) -> None:
    dist = _write_dist(tmp_path)
    client = TestClient(create_app(dist_dir=dist))
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "FieldRook test UI" in response.text


def test_static_assets_served_from_dist(tmp_path: Path) -> None:
    dist = _write_dist(tmp_path)
    client = TestClient(create_app(dist_dir=dist))
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.content == (dist / "assets" / "app.js").read_bytes()


def test_api_routes_win_over_static_mount(tmp_path: Path) -> None:
    """Mount order: /api/* routers match before the / static mount."""
    dist = _write_dist(tmp_path)
    client = TestClient(create_app(dist_dir=dist))
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["service"] == "fieldrook-api"
    assert client.get("/no-such-ui-route").status_code == 404


def test_root_json_tagline_without_dist() -> None:
    client = TestClient(create_app(dist_dir=False))
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"name": "FieldRook", "tagline": "Diagnose. Verify. Resolve."}


def test_incomplete_dist_falls_back_to_json_api(tmp_path: Path) -> None:
    """A dist dir without index.html is not a UI (dev-API mode)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "assets").mkdir()
    client = TestClient(create_app(dist_dir=dist))
    assert client.get("/").json()["tagline"] == "Diagnose. Verify. Resolve."


def test_default_app_serves_either_mode() -> None:
    """Smoke: the shared app serves / as HTML (dist built) or JSON (dev)."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(("text/html", "application/json"))


def test_ui_mount_adds_no_api_routes(tmp_path: Path) -> None:
    """UI mode and dev-API mode expose identical API routes (mount adds none)."""
    dist = _write_dist(tmp_path)

    def api_routes(application) -> set:  # type: ignore[no-untyped-def]
        return {
            (route.path, tuple(sorted(route.methods or ())))
            for route in application.routes
            if isinstance(route, APIRoute)
        }

    assert api_routes(create_app(dist_dir=dist)) == api_routes(create_app(dist_dir=False))
