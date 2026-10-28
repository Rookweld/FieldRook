"""Lead wiring tests: tool registry, import endpoint, knowledge reference API."""

import pytest

from app.tools.registry import REGISTRY, ToolCallError, prepare_call, tool_schemas

NEW_TOOLS = {
    "list_devices": "pnp_devices",
    "list_volumes": "volumes",
    "list_office_installs": "office_installs",
    "get_office_config": "office_config",
}


def test_registry_has_18_tools() -> None:
    assert len(REGISTRY) == 18


def test_new_tools_prepare_and_validate() -> None:
    spec, args = prepare_call("list_devices", {"limit": 10, "status": "OK"})
    assert spec.name == "list_devices"
    assert spec.category == "pnp_devices"
    assert args.limit == 10
    with pytest.raises(ToolCallError):
        prepare_call("list_devices", {"limit": 500})
    with pytest.raises(ToolCallError):
        prepare_call("list_devices", {"limit": 10, "bogus": 1})
    with pytest.raises(ToolCallError):
        prepare_call("no_such_tool", {})


def test_new_tool_fixtures_run() -> None:
    for name, category in NEW_TOOLS.items():
        spec = REGISTRY[name]
        assert spec.category == category
        _, args = prepare_call(name, {})
        output = spec.run_fixture(args)
        assert output.source == "fixture"
        assert output.error is None
        assert output.data
    names = {schema["function"]["name"] for schema in tool_schemas()}
    assert set(NEW_TOOLS) <= names


# --------------------------------------------------------------------------
# Collector import endpoint
# --------------------------------------------------------------------------

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app  # noqa: E402  (registers collector_import router)
from collector import archive, chunker  # noqa: E402
from collector import manifest as colmanifest  # noqa: E402

client = TestClient(app)


def _make_package(tmp_path: Path, entries: list[dict], hostname_hash: str = "ee" * 32) -> Path:
    manifest = colmanifest.build_manifest(
        hostname_hash=hostname_hash,
        os_info={"platform": "win32", "version": "11", "build": "26100"},
        evidence=entries,
        target_hint="audit-pc",
    )
    errors, _ = colmanifest.validate_manifest(manifest)
    assert errors == []
    dest = tmp_path / "pkg.zip"
    archive.create_package(manifest, {}, dest)
    return dest


def _new_investigation(problem: str = "Import probe.") -> str:
    response = client.post("/api/investigations", data={"problem": problem})
    assert response.status_code == 200
    return response.json()["investigation_id"]


def test_import_happy_path(tmp_path: Path) -> None:
    entry = colmanifest.build_entry(
        "local-1", "service_status",
        {"service": "wuauserv", "state": "Stopped"},
        tool_name="list_services", tool_args={"limit": 5},
    )
    package = _make_package(tmp_path, [entry])
    inv_id = _new_investigation()
    with package.open("rb") as handle:
        response = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("pkg.zip", handle, "application/zip")},
            data={"share_consent": "true"},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["collector_packages"]) == 1
    pkg = body["collector_packages"][0]
    assert pkg["evidence_ids"]
    assert body["target_identity"]["hostname_hash"] == "ee" * 32
    assert body["target_identity"]["hint"] == "audit-pc"
    imported = [e for e in body["evidence"] if e["source"].startswith("collector:")]
    assert len(imported) == 1
    assert imported[0]["tool_name"] == "list_services"
    assert imported[0]["tool_args"] == {"limit": 5}
    assert imported[0]["data"]["provenance"]["collector"]["package_id"] == pkg["package_id"]
    kinds = [a["kind"] for a in body["activity"]]
    assert "collector_import" in kinds


def test_import_requires_consent_and_zip(tmp_path: Path) -> None:
    entry = colmanifest.build_entry("local-1", "service_status", {"a": 1})
    package = _make_package(tmp_path, [entry])
    inv_id = _new_investigation()
    with package.open("rb") as handle:
        denied = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("pkg.zip", handle, "application/zip")},
            data={"share_consent": "false"},
        )
    assert denied.status_code == 400
    fake = tmp_path / "fake.zip"
    fake.write_bytes(b"not a zip at all")
    with fake.open("rb") as handle:
        bad = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("fake.zip", handle, "application/zip")},
            data={"share_consent": "true"},
        )
    assert bad.status_code == 422
    missing = client.post(
        f"/api/investigations/inv-nope/import-collector", data={"share_consent": "true"}
    )
    assert missing.status_code == 404


def test_import_rejects_tampered_package_atomically(tmp_path: Path) -> None:
    entry = colmanifest.build_entry("local-1", "service_status", {"a": 1})
    package = _make_package(tmp_path, [entry])
    # Tamper: rewrite the manifest inside the zip with different evidence.
    raw = dict(json.loads(zipfile.ZipFile(package).read("manifest.json")))
    raw["evidence"][0]["data"] = {"a": 999}
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered, "w") as handle:
        handle.writestr("manifest.json", json.dumps(raw))
    inv_id = _new_investigation()
    before = client.get(f"/api/investigations/{inv_id}").json()["evidence"]
    with tampered.open("rb") as handle:
        response = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("tampered.zip", handle, "application/zip")},
            data={"share_consent": "true"},
        )
    assert response.status_code == 422
    after = client.get(f"/api/investigations/{inv_id}").json()
    assert after["evidence"] == before
    assert after["collector_packages"] == []
    assert after["target_identity"] is None


def test_import_rejects_duplicate_package(tmp_path: Path) -> None:
    entry = colmanifest.build_entry("local-1", "service_status", {"a": 1})
    package = _make_package(tmp_path, [entry])
    inv_id = _new_investigation()
    for expected in (200, 409):
        with package.open("rb") as handle:
            response = client.post(
                f"/api/investigations/{inv_id}/import-collector",
                files={"file": ("pkg.zip", handle, "application/zip")},
                data={"share_consent": "true"},
            )
        assert response.status_code == expected


def test_unknown_tool_ref_degrades_with_warning() -> None:
    # Unit-level: manifest validation already rejects unknown tools, so this
    # exercises the router's defense-in-depth path directly (e.g. registry
    # shrinks while an older collector still emits the name).
    from app.routers.collector_import import _validate_tool_ref

    warnings: list[str] = []
    name, args = _validate_tool_ref("not_a_tool", {"x": 1}, warnings, "local-1")
    assert name is None and args is None
    assert any("unknown tool_name" in w for w in warnings)
    name, args = _validate_tool_ref("list_services", {"limit": 5}, warnings, "local-2")
    assert name == "list_services" and args == {"limit": 5}
    name, args = _validate_tool_ref("list_services", {"limit": 500}, warnings, "local-3")
    assert name is None and args is None


def test_import_chunked_document_links_refresh_chain(tmp_path: Path) -> None:
    big = {"log": "x" * (13 * 1024)}
    chunks, _ = chunker.chunk_entries([{"id": "big", "category": "log", "data": big}])
    for chunk in chunks:
        if not chunk.get("collected_at"): chunk["collected_at"] = colmanifest.utc_now_iso()
    assert len(chunks) > 1
    package = _make_package(tmp_path, chunks)
    inv_id = _new_investigation()
    with package.open("rb") as handle:
        response = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("pkg.zip", handle, "application/zip")},
            data={"share_consent": "true"},
        )
    assert response.status_code == 200
    body = response.json()
    imported = [e for e in body["evidence"] if e["source"].startswith("collector:")]
    assert len(imported) == len(chunks)
    assert imported[0]["refresh_of"] is None
    for item in imported[1:]:
        assert item["refresh_of"] is not None


def test_import_wrong_host_warns_and_keeps_target(tmp_path: Path) -> None:
    first = colmanifest.build_entry("local-1", "service_status", {"a": 1})
    package_a = _make_package(tmp_path, [first], hostname_hash="aa" * 32)
    inv_id = _new_investigation()
    with package_a.open("rb") as handle:
        first_response = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("a.zip", handle, "application/zip")},
            data={"share_consent": "true"},
        )
    assert first_response.status_code == 200
    second = colmanifest.build_entry("local-1", "service_status", {"a": 2})
    package_b = _make_package(tmp_path, [second], hostname_hash="bb" * 32)
    with package_b.open("rb") as handle:
        response = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("b.zip", handle, "application/zip")},
            data={"share_consent": "true"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["target_identity"]["hostname_hash"] == "aa" * 32
    assert len(body["collector_packages"]) == 2
    assert any("differs from this case's target" in w for w in body["warnings"])


def test_import_rejects_oversize_unchunked_entry(tmp_path: Path) -> None:
    manifest = colmanifest.build_manifest(
        hostname_hash="ee" * 32, os_info={}, evidence=[],
    )
    big_data = {"log": "y" * (13 * 1024)}
    manifest["evidence"] = [{
        "id": "big", "category": "log", "source_suffix": "live",
        "collected_at": colmanifest.utc_now_iso(), "data": big_data,
        "sha256": colmanifest.entry_hash(big_data)[0],
        "size": colmanifest.entry_hash(big_data)[1],
    }]
    dest = tmp_path / "big.zip"
    archive.create_package(manifest, {}, dest)
    inv_id = _new_investigation()
    with dest.open("rb") as handle:
        response = client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": ("big.zip", handle, "application/zip")},
            data={"share_consent": "true"},
        )
    assert response.status_code == 422
    assert "chunk" in response.json()["detail"].lower()
    assert client.get(f"/api/investigations/{inv_id}").json()["collector_packages"] == []
