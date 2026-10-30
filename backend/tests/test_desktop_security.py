"""Desktop localhost hardening (M025 BETA security contract).

- `Sec-Fetch-Site` enforcement in `LocalOriginMiddleware`: a present header
  decides (same-origin/same-site allowed, everything else 403); a missing
  header falls back to the Origin/Referer check, and fully headerless
  requests stay allowed because non-browser clients (curl, TestClient, the
  desktop launcher probe) send neither header.
- `TrustedHostMiddleware` over the localhost set (+ `testserver` in dev so
  the suite's default TestClient host keeps working; frozen is strict).
"""

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app, create_app, trusted_hosts

client = TestClient(app)

INVESTIGATION_FORM = {"problem": "Desktop security probe."}


def _inv_id() -> str:
    started = client.post("/api/investigations", data=INVESTIGATION_FORM)
    assert started.status_code == 200
    return str(started.json()["investigation_id"])


def test_sec_fetch_site_cross_site_mutation_rejected() -> None:
    """The headerless bypass fix: cross-site browser POSTs fail even with no Origin."""
    refused = client.post(
        "/api/investigations",
        data=INVESTIGATION_FORM,
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert refused.status_code == 403


@pytest.mark.parametrize("site", ["same-origin", "same-site", "Same-Origin"])
def test_sec_fetch_site_local_mutation_allowed(site: str) -> None:
    allowed = client.post(
        "/api/investigations",
        data=INVESTIGATION_FORM,
        headers={"Sec-Fetch-Site": site},
    )
    assert allowed.status_code == 200


@pytest.mark.parametrize("site", ["none", "cross-site ", "bogus"])
def test_sec_fetch_site_other_values_rejected(site: str) -> None:
    refused = client.post(
        "/api/investigations",
        data=INVESTIGATION_FORM,
        headers={"Sec-Fetch-Site": site},
    )
    assert refused.status_code == 403


def test_headerless_post_still_allowed_for_non_browser_clients() -> None:
    """Documented allowance: curl/TestClient/launcher send no fetch metadata."""
    response = client.post("/api/investigations", data=INVESTIGATION_FORM)
    assert response.status_code == 200


def test_evil_origin_still_rejected_without_fetch_site() -> None:
    refused = client.post(
        "/api/investigations",
        data=INVESTIGATION_FORM,
        headers={"Origin": "https://evil.example"},
    )
    assert refused.status_code == 403


def test_sec_fetch_site_decides_before_origin() -> None:
    """Fetch metadata wins when both are present (scripts can spoof neither)."""
    allowed = client.post(
        "/api/investigations",
        data=INVESTIGATION_FORM,
        headers={"Sec-Fetch-Site": "same-origin", "Origin": "https://evil.example"},
    )
    assert allowed.status_code == 200
    refused = client.post(
        "/api/investigations",
        data=INVESTIGATION_FORM,
        headers={"Sec-Fetch-Site": "cross-site", "Origin": "http://localhost:5173"},
    )
    assert refused.status_code == 403


def test_cross_site_action_endpoints_rejected() -> None:
    inv_id = _inv_id()
    refused = client.post(
        f"/api/investigations/{inv_id}/proposals",
        json={"action_id": "recover_demo_worker", "target": "demo-worker", "reason": "CSRF."},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert refused.status_code == 403


def test_sec_fetch_site_ignores_case_and_whitespace() -> None:
    allowed = client.post(
        "/api/investigations",
        data=INVESTIGATION_FORM,
        headers={"sec-fetch-site": "  SAME-SITE  "},
    )
    assert allowed.status_code == 200


@pytest.mark.parametrize("host", ["localhost", "localhost:8123", "127.0.0.1", "127.0.0.1:8000"])
def test_trusted_host_allows_localhost_set(host: str) -> None:
    response = client.get("/api/status", headers={"Host": host})
    assert response.status_code == 200


def test_trusted_host_allows_testserver_in_dev() -> None:
    """Dev/test allowance: Starlette TestClient's default Host is `testserver`."""
    assert "testserver" in trusted_hosts()
    response = client.get("/api/status")  # default Host: testserver
    assert response.status_code == 200


def test_trusted_host_rejects_off_host() -> None:
    """DNS-rebinding guard: Host headers outside the localhost set fail."""
    refused = client.get("/api/status", headers={"Host": "evil.example"})
    assert refused.status_code == 400
    refused_post = client.post(
        "/api/investigations", data=INVESTIGATION_FORM, headers={"Host": "attacker.test:8000"}
    )
    assert refused_post.status_code == 400


def test_trusted_host_strict_when_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frozen builds drop the `testserver` allowance (strict localhost)."""
    monkeypatch.setattr(app_main, "is_frozen", lambda: True)
    assert "testserver" not in trusted_hosts()
    frozen_app = create_app(dist_dir=False)
    frozen_client = TestClient(frozen_app)
    assert frozen_client.get("/api/status").status_code == 400
    assert frozen_client.get("/api/status", headers={"Host": "127.0.0.1"}).status_code == 200
