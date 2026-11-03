"""M028.B Evidence Lens: backend linkage contracts the Lens depends on.

The Lens itself compares persisted data client-side; these tests pin the
server-side linkage it consumes: refresh_of/refresh records from reverify
and cross-package recollection, same-host gating, and error preservation.
All fixture/simulated, no network.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.investigations.store import store
from app.main import app
from collector import archive
from collector import manifest as colmanifest

client = TestClient(app)
HASH_A = "aa" * 32
HASH_B = "bb" * 32


def _new_investigation(problem: str, **extra: object) -> dict:
    data: dict[str, object] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200
    return response.json()


def _entry(
    entry_id: str,
    category: str,
    data: dict,
    tool: str | None = None,
    args: dict | None = None,
    error: str | None = None,
) -> dict:
    return colmanifest.build_entry(
        entry_id,
        category,
        data,
        source_suffix="live",
        tool_name=tool,
        tool_args=args if args is not None else ({} if tool is not None else None),
        error=error,
    )


def _make_package(
    tmp_path: Path,
    entries: list[dict],
    hostname_hash: str,
    name: str,
    created_at: str | None = None,
) -> Path:
    manifest = colmanifest.build_manifest(
        hostname_hash=hostname_hash,
        os_info={"platform": "win32", "version": "11", "build": "26100"},
        evidence=entries,
        target_hint="lens-pc",
        created_at=created_at,
    )
    errors, _ = colmanifest.validate_manifest(manifest)
    assert errors == []
    dest = tmp_path / name
    archive.create_package(manifest, {}, dest)
    return dest


def _import(inv_id: str, package: Path, name: str = "pkg.zip"):
    with package.open("rb") as handle:
        return client.post(
            f"/api/investigations/{inv_id}/import-collector",
            files={"file": (name, handle, "application/zip")},
            data={"share_consent": "true"},
        )


def _os_data(build: str) -> dict:
    return {"caption": "Microsoft Windows 11 Pro", "version": "10.0.26100", "build_number": build}


def _dns_data() -> dict:
    return {"interfaces": [{"interface": "Wi-Fi", "servers": ["192.168.1.1"]}]}


def test_single_snapshot_creates_no_refresh_links(tmp_path: Path) -> None:
    """One package cannot produce a comparison: no refresh records, no links."""
    body = _new_investigation("Lens probe: single snapshot.", target="remote")
    inv_id = body["investigation_id"]
    package = _make_package(
        tmp_path,
        [
            _entry("c-os", "os_info", _os_data("26100"), tool="get_os_info"),
            _entry("c-dns", "dns_config", _dns_data(), tool="get_dns_config"),
        ],
        HASH_A,
        "a.zip",
    )
    response = _import(inv_id, package)
    assert response.status_code == 200
    again = response.json()
    assert again["refreshes"] == []
    for item in again["evidence"]:
        assert item["refresh_of"] is None
    assert len(again["collector_packages"]) == 1
    record = again["collector_packages"][0]
    assert record["package_id"]
    assert record["hostname_hash"] == HASH_A
    assert len(record["evidence_ids"]) == 2
    assert again["target_identity"]["hostname_hash"] == HASH_A


def test_two_same_host_snapshots_link_and_compare(tmp_path: Path) -> None:
    """Same machine + same tool/args links recollections with real verdicts."""
    body = _new_investigation("Lens probe: two snapshots.", target="remote")
    inv_id = body["investigation_id"]
    package_a = _make_package(
        tmp_path,
        [
            _entry("c-os", "os_info", _os_data("26100"), tool="get_os_info"),
            _entry("c-dns", "dns_config", _dns_data(), tool="get_dns_config"),
        ],
        HASH_A,
        "a.zip",
        created_at="2026-10-30T10:00:00+00:00",
    )
    package_b = _make_package(
        tmp_path,
        [
            _entry("c-os", "os_info", _os_data("26200"), tool="get_os_info"),
            _entry("c-dns", "dns_config", _dns_data(), tool="get_dns_config"),
        ],
        HASH_A,
        "b.zip",
        created_at="2026-10-31T10:00:00+00:00",
    )
    assert _import(inv_id, package_a).status_code == 200
    response = _import(inv_id, package_b)
    assert response.status_code == 200
    again = response.json()

    assert len(again["collector_packages"]) == 2
    pkg_a, pkg_b = again["collector_packages"]
    assert pkg_a["package_id"] != pkg_b["package_id"]
    assert pkg_b["hostname_hash"] == HASH_A

    by_id = {item["id"]: item for item in again["evidence"]}
    assert len(again["refreshes"]) == 2
    by_tool = {refresh["tool_name"]: refresh for refresh in again["refreshes"]}

    changed = by_tool["get_os_info"]
    assert changed["verdict"] == "changed"
    assert changed["old_evidence_id"] in pkg_a["evidence_ids"]
    assert changed["new_evidence_id"] in pkg_b["evidence_ids"]
    assert any("build_number" in change for change in changed["changes"])
    assert by_id[changed["new_evidence_id"]]["refresh_of"] == changed["old_evidence_id"]

    same = by_tool["get_dns_config"]
    assert same["verdict"] == "unchanged"
    assert same["changes"] == []
    assert by_id[same["new_evidence_id"]]["refresh_of"] == same["old_evidence_id"]

    # Every lens-consumed field is populated on both records.
    for refresh in again["refreshes"]:
        assert refresh["old_collected_at"]
        assert refresh["new_collected_at"]
        assert refresh["compared_at"]
        assert isinstance(refresh["affected_causes"], list)


def test_mismatched_host_import_rejected_atomically(tmp_path: Path) -> None:
    """A package from another computer never joins the case."""
    body = _new_investigation("Lens probe: host mismatch.", target="remote")
    inv_id = body["investigation_id"]
    package_a = _make_package(
        tmp_path, [_entry("c-os", "os_info", _os_data("26100"), tool="get_os_info")], HASH_A, "a.zip"
    )
    package_b = _make_package(
        tmp_path, [_entry("c-os", "os_info", _os_data("26100"), tool="get_os_info")], HASH_B, "b.zip"
    )
    assert _import(inv_id, package_a).status_code == 200
    before = store.get(inv_id)
    assert before is not None
    n_evidence = len(before.evidence)

    response = _import(inv_id, package_b)
    assert response.status_code == 409
    assert "not this case's computer" in response.json()["detail"]

    after = store.get(inv_id)
    assert after is not None
    assert len(after.evidence) == n_evidence
    assert len(after.collector_packages) == 1
    assert after.refreshes == []


def test_reverify_refresh_carries_lens_fields() -> None:
    """Reverify linkage exposes every field the Lens renders."""
    body = _new_investigation("DNS does not resolve anything since this morning.")
    inv_id = body["investigation_id"]
    old = next(item for item in body["evidence"] if item["category"] == "dns_config")

    response = client.post(f"/api/investigations/{inv_id}/reverify", json={"evidence_id": old["id"]})
    assert response.status_code == 200
    again = response.json()

    assert len(again["refreshes"]) == 1
    refresh = again["refreshes"][0]
    assert refresh["old_evidence_id"] == old["id"]
    assert refresh["tool_name"] == "get_dns_config"
    assert refresh["verdict"] == "unchanged"
    assert refresh["old_collected_at"] == old["collected_at"]
    assert refresh["new_collected_at"]
    assert refresh["compared_at"]
    by_id = {item["id"]: item for item in again["evidence"]}
    assert by_id[refresh["new_evidence_id"]]["refresh_of"] == old["id"]
    assert by_id[old["id"]]["data"] == old["data"]


def test_imported_error_entry_preserved_with_provenance(tmp_path: Path) -> None:
    """Failed collector readings import as errors with their timestamps."""
    body = _new_investigation("Lens probe: error entry.", target="remote")
    inv_id = body["investigation_id"]
    package = _make_package(
        tmp_path,
        [
            _entry(
                "c-err",
                "service_list",
                {},
                tool="list_services",
                error="simulated collector fault",
            )
        ],
        HASH_A,
        "err.zip",
    )
    response = _import(inv_id, package)
    assert response.status_code == 200
    again = response.json()
    imported = [item for item in again["evidence"] if item["source"].startswith("collector:")]
    assert len(imported) == 1
    assert imported[0]["error"] == "simulated collector fault"
    assert imported[0]["collected_at"]
    provenance = imported[0]["data"].get("provenance", {})
    assert provenance.get("collected_at")
    assert imported[0]["refresh_of"] is None


def test_unavailable_refresh_shape(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A failed re-collection keeps history and links the failed reading."""
    body = _new_investigation(
        "Is the Windows Update service healthy?", service_name="wuauserv"
    )
    inv_id = body["investigation_id"]
    old = next(item for item in body["evidence"] if item["category"] == "service_details")

    monkeypatch.setenv("FIELDROOK_FIXTURE_MISSING_SERVICES", "wuauserv")
    response = client.post(f"/api/investigations/{inv_id}/reverify", json={"evidence_id": old["id"]})
    assert response.status_code == 200
    again = response.json()

    refresh = again["refreshes"][0]
    assert refresh["verdict"] == "unavailable"
    assert refresh["new_evidence_id"] is not None
    assert refresh["new_collected_at"]
    by_id = {item["id"]: item for item in again["evidence"]}
    assert by_id[refresh["new_evidence_id"]]["error"] is not None
    assert by_id[refresh["new_evidence_id"]]["refresh_of"] == old["id"]
    assert by_id[old["id"]]["error"] is None
