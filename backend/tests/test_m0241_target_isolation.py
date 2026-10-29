"""M024.1: target isolation — no wrong-computer measurement or mixing."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.investigations.store import store
from app.main import app
from collector import archive
from collector import manifest as colmanifest

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "collector" / "samples" / "sample_basic.zip"
HASH_A = "aa" * 32
HASH_B = "bb" * 32


def _new_investigation(problem: str = "Isolation probe.", target: str = "local") -> str:
    response = client.post("/api/investigations", data={"problem": problem, "target": target})
    assert response.status_code == 200
    return response.json()["investigation_id"]


def _entry(
    entry_id: str,
    tool: str | None = "list_services",
    args: dict | None = None,
    data: dict | None = None,
) -> dict:
    return colmanifest.build_entry(
        entry_id,
        "service_list",
        data if data is not None else {"services": [{"name": "wuauserv", "state": "Running"}]},
        source_suffix="zeta",
        tool_name=tool,
        tool_args=args if args is not None else ({} if tool is not None else None),
    )


def _make_package(tmp_path: Path, entries: list[dict], hostname_hash: str, name: str) -> Path:
    manifest = colmanifest.build_manifest(
        hostname_hash=hostname_hash,
        os_info={"platform": "win32", "version": "11", "build": "26100"},
        evidence=entries,
        target_hint="iso-pc",
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


def _tool_evidence_id(inv_id: str) -> str:
    state = store.get(inv_id)
    assert state is not None
    for item in state.evidence:
        if item.tool_name and (item.source or "").startswith("tool:"):
            return item.id
    raise AssertionError("no re-runnable tool evidence collected")


# ---------- reverify ----------


def test_reverify_collector_item_refused_atomically(tmp_path: Path) -> None:
    inv_id = _new_investigation(target="remote")
    assert _import(inv_id, SAMPLE, "sample_basic.zip").status_code == 200
    state = store.get(inv_id)
    assert state is not None
    victim = next(e for e in state.evidence if (e.source or "").startswith("collector:") and e.tool_name)
    calls_before = state.tool_calls_made
    n_before = len(state.evidence)
    response = client.post(f"/api/investigations/{inv_id}/reverify", json={"evidence_id": victim.id})
    assert response.status_code == 422
    assert "cannot be" in response.json()["detail"] and "re-measured" in response.json()["detail"]
    state = store.get(inv_id)
    assert state is not None
    assert state.tool_calls_made == calls_before
    assert len(state.evidence) == n_before
    assert state.refreshes == []


def test_reverify_remote_and_unknown_targets_refused() -> None:
    for target in ("remote", "unknown"):
        inv_id = _new_investigation(target="local")
        ev_id = _tool_evidence_id(inv_id)
        flipped = client.post(f"/api/investigations/{inv_id}/target", json={"target": target})
        assert flipped.status_code == 200
        # The flip itself warns about stale host evidence (pre-existing guard).
        assert any("wrong" in w and "computer" in w for w in flipped.json()["warnings"])
        response = client.post(f"/api/investigations/{inv_id}/reverify", json={"evidence_id": ev_id})
        assert response.status_code == 409, target
        assert "another computer" in response.json()["detail"]


def test_reverify_remote_static_lookup_still_allowed() -> None:
    inv_id = _new_investigation(target="remote")
    state = store.get(inv_id)
    assert state is not None
    item = state.add_evidence(
        category="error_code",
        source="tool:interpret_error_code:fixture",
        data={"value": "5"},
        tool_name="interpret_error_code",
        tool_args={"value": "5"},
    )
    store.save(state)
    response = client.post(f"/api/investigations/{inv_id}/reverify", json={"evidence_id": item.id})
    assert response.status_code == 200, response.json()


def test_reverify_local_host_tool_allowed() -> None:
    inv_id = _new_investigation(target="local")
    ev_id = _tool_evidence_id(inv_id)
    response = client.post(f"/api/investigations/{inv_id}/reverify", json={"evidence_id": ev_id})
    assert response.status_code == 200


# ---------- importer identity ----------


def test_import_second_computer_rejected(tmp_path: Path) -> None:
    inv_id = _new_investigation(target="remote")
    pkg_a = _make_package(tmp_path, [_entry("a1")], HASH_A, "a.zip")
    assert _import(inv_id, pkg_a, "a.zip").status_code == 200
    pkg_b = _make_package(tmp_path, [_entry("b1")], HASH_B, "b.zip")
    response = _import(inv_id, pkg_b, "b.zip")
    assert response.status_code == 409
    assert "one case holds one computer" in response.json()["detail"]
    state = store.get(inv_id)
    assert state is not None
    assert len(state.collector_packages) == 1
    assert all("b1" not in (e.id or "") for e in state.evidence)
    assert state.target_identity is not None and state.target_identity.hostname_hash == HASH_A


def test_import_same_computer_recollects_with_links(tmp_path: Path) -> None:
    inv_id = _new_investigation(target="remote")
    pkg_a = _make_package(tmp_path, [_entry("a1")], HASH_A, "a.zip")
    assert _import(inv_id, pkg_a, "a.zip").status_code == 200
    changed = _entry("a2", data={"services": [{"name": "wuauserv", "state": "Stopped"}]})
    pkg_b = _make_package(tmp_path, [changed], HASH_A, "b.zip")
    response = _import(inv_id, pkg_b, "b.zip")
    assert response.status_code == 200, response.json()
    state = store.get(inv_id)
    assert state is not None
    assert len(state.collector_packages) == 2
    assert len(state.refreshes) == 1
    link = state.refreshes[0]
    assert link.verdict == "changed"
    assert link.tool_name == "list_services"
    assert any("1 recollection link(s)" in (a.detail or "") for a in state.activity)


def test_import_live_host_case_rejected(tmp_path: Path) -> None:
    inv_id = _new_investigation(target="local")
    state = store.get(inv_id)
    assert state is not None
    state.add_evidence(
        category="os_info",
        source="tool:get_os_info:live",
        data={"caption": "live host"},
        tool_name="get_os_info",
        tool_args={},
    )
    store.save(state)
    pkg = _make_package(tmp_path, [_entry("x1")], HASH_A, "x.zip")
    response = _import(inv_id, pkg, "x.zip")
    assert response.status_code == 409
    assert "mix" in response.json()["detail"]


def test_import_fixture_case_allowed(tmp_path: Path) -> None:
    # Simulated/demo cases carry no real host readings: the demo flow stays open.
    inv_id = _new_investigation(target="local")
    pkg = _make_package(tmp_path, [_entry("f1")], HASH_A, "f.zip")
    response = _import(inv_id, pkg, "f.zip")
    assert response.status_code == 200, response.json()
    state = store.get(inv_id)
    assert state is not None
    assert state.target_identity is not None and state.target_identity.hostname_hash == HASH_A


def test_recollect_identical_data_verdict_unchanged(tmp_path: Path) -> None:
    # Volatile import provenance (package id, timestamp) must not force "changed".
    inv_id = _new_investigation(target="remote")
    pkg_a = _make_package(tmp_path, [_entry("s1")], HASH_A, "a.zip")
    assert _import(inv_id, pkg_a, "a.zip").status_code == 200
    pkg_b = _make_package(tmp_path, [_entry("s1")], HASH_A, "b.zip")
    assert _import(inv_id, pkg_b, "b.zip").status_code == 200
    state = store.get(inv_id)
    assert state is not None
    assert len(state.refreshes) == 1
    assert state.refreshes[0].verdict == "unchanged"
    assert state.refreshes[0].changes == []


def test_recollect_chunked_slices_match_by_seq(tmp_path: Path) -> None:
    from collector import chunker

    big = {"tasks": [{"name": f"task-{i:04d}", "detail": "y" * 200} for i in range(200)]}
    raw_entry = {
        "id": "big",
        "category": "scheduled_tasks",
        "source_suffix": "live",
        "collected_at": colmanifest.utc_now_iso(),
        "data": big,
        "tool_name": "get_scheduled_tasks",
        "tool_args": {},
    }
    chunks, _ = chunker.chunk_entries([raw_entry])
    assert len(chunks) > 1
    inv_id = _new_investigation(target="remote")
    pkg_a = _make_package(tmp_path, chunks, HASH_A, "a.zip")
    assert _import(inv_id, pkg_a, "a.zip").status_code == 200
    pkg_b = _make_package(tmp_path, chunks, HASH_A, "b.zip")
    assert _import(inv_id, pkg_b, "b.zip").status_code == 200
    state = store.get(inv_id)
    assert state is not None
    # First chunk links cross-package; later chunks continue the in-package chain.
    assert len(state.refreshes) == 1
    assert state.refreshes[0].verdict == "unchanged"


def test_import_unknown_target_case_allowed(tmp_path: Path) -> None:
    # Unknown-target triage cases accept a first package and adopt its identity.
    inv_id = _new_investigation(target="unknown")
    pkg = _make_package(tmp_path, [_entry("u1")], HASH_A, "u.zip")
    response = _import(inv_id, pkg, "u.zip")
    assert response.status_code == 200, response.json()
    state = store.get(inv_id)
    assert state is not None
    assert state.target == "unknown"
    assert state.target_identity is not None and state.target_identity.hostname_hash == HASH_A
