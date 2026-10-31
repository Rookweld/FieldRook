"""M028.C Network Lab: allowlist, target isolation, provenance labels.

Covers the read-only network instrument contract against the EXISTING safe
API path (POST .../reverify): no new endpoint is added by M028.C, so these
tests pin the guards the Network Lab UI relies on:

- only registered network tools exist (no ping/traceroute/port-scan);
- local re-checks work and carry tool/source/collected_at provenance;
- remote/unknown targets refuse host re-measurement (409);
- collector (other-computer) items refuse host re-measurement (422);
- invalid stored args fail closed (422 schema / recorded error);
- fixture-vs-live provenance suffixes stay parseable.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.diagnostics.windows_net import validate_hostname
from app.investigations.store import store
from app.main import app
from app.tools.registry import REGISTRY

client = TestClient(app)

# Mission allowlist: the ONLY network tool names the Network Lab may cite.
# NOTE: the mission brief spells the DNS test "resolve_hostname"; that is the
# internal live helper in windows_net.py. The registered tool name is
# "test_dns_resolution" and that is what the UI and tests must use.
NETWORK_TOOLS = {
    "get_network_adapters": "net_adapters",
    "get_ip_config": "ip_config",
    "get_dns_config": "dns_config",
    "get_connections": "connections",
    "test_dns_resolution": "dns_test",
}

FORBIDDEN_NAME_PARTS = ("ping", "traceroute", "trace_route", "portscan", "port_scan", "nmap")


def _investigate(problem: str, **extra: object) -> dict:
    data: dict[str, object] = {"problem": problem}
    data.update(extra)
    response = client.post("/api/investigations", data=data)
    assert response.status_code == 200, response.text
    return response.json()


def _network_items(body: dict) -> list[dict]:
    return [item for item in body["evidence"] if item["category"] in set(NETWORK_TOOLS.values())]


def _reverify(inv_id: str, evidence_id: str):
    return client.post(
        f"/api/investigations/{inv_id}/reverify", json={"evidence_id": evidence_id}
    )


def _set_target(inv_id: str, target: str):
    return client.post(
        f"/api/investigations/{inv_id}/target", json={"target": target}
    )


# ---------- allowlist: no invented network tools ----------


def test_network_tool_allowlist_exact() -> None:
    for name, category in NETWORK_TOOLS.items():
        assert name in REGISTRY, f"registered network tool missing: {name}"
        assert REGISTRY[name].category == category
    for name in REGISTRY:
        lowered = name.lower()
        for part in FORBIDDEN_NAME_PARTS:
            assert part not in lowered, f"forbidden network tool in registry: {name}"


def test_tools_endpoint_advertises_no_false_actions() -> None:
    response = client.get("/api/tools")
    assert response.status_code == 200
    names = [row["name"] for row in response.json()]
    for expected in NETWORK_TOOLS:
        assert expected in names
    for name in names:
        lowered = name.lower()
        for part in FORBIDDEN_NAME_PARTS:
            assert part not in lowered, f"forbidden tool advertised: {name}"


# ---------- local re-check: works, provenance intact ----------


def test_reverify_network_evidence_local_ok() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    items = _network_items(body)
    assert items, "expected network evidence for a DNS-symptom case"
    old = next(item for item in items if item["tool_name"] in NETWORK_TOOLS)

    response = _reverify(body["investigation_id"], old["id"])
    assert response.status_code == 200, response.text
    again = response.json()

    by_id = {item["id"]: item for item in again["evidence"]}
    assert by_id[old["id"]]["data"] == old["data"]
    assert by_id[old["id"]]["collected_at"] == old["collected_at"]

    refresh = next(
        r for r in again["refreshes"] if r["old_evidence_id"] == old["id"]
    )
    new_item = by_id[refresh["new_evidence_id"]]
    assert new_item["refresh_of"] == old["id"]
    assert new_item["tool_name"] == old["tool_name"]
    # Provenance label the Network Lab parses: tool:<name>:<live|fixture>.
    assert re.fullmatch(
        r"tool:[a-z_]+:(live|fixture)", new_item["source"]
    ), new_item["source"]
    assert refresh["verdict"] in ("changed", "unchanged", "unavailable")
    assert refresh["new_collected_at"]


def test_network_source_labels_are_parseable() -> None:
    body = _investigate("My VPN connects but the intranet never loads.")
    items = _network_items(body)
    assert items, "expected network evidence for a VPN-symptom case"
    for item in items:
        source = item["source"] or ""
        assert source.startswith("tool:") or source.startswith("collector:"), source
        if source.startswith("tool:"):
            assert re.fullmatch(r"tool:[a-z_]+:(live|fixture)", source), source
        assert item["collected_at"]
        assert item["tool_name"] in NETWORK_TOOLS


# ---------- target guards: never measure this host as another computer ----------


def _local_item_id_then_retarget(body: dict, target: str) -> tuple[str, str]:
    items = _network_items(body)
    assert items
    old = next(item for item in items if item["tool_name"] in NETWORK_TOOLS)
    response = _set_target(body["investigation_id"], target)
    assert response.status_code == 200, response.text
    assert response.json()["target"] == target
    return body["investigation_id"], old["id"]


def test_reverify_network_refused_for_remote_target() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    inv_id, item_id = _local_item_id_then_retarget(body, "remote")
    response = _reverify(inv_id, item_id)
    assert response.status_code == 409, response.text
    assert "remote" in response.json()["detail"]


def test_reverify_network_refused_for_unknown_target() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    inv_id, item_id = _local_item_id_then_retarget(body, "unknown")
    response = _reverify(inv_id, item_id)
    assert response.status_code == 409, response.text


def test_reverify_collector_network_item_refused() -> None:
    """Seeded collector-sourced network item: host re-run refused (422)."""
    body = _investigate("DNS does not resolve anything since this morning.")
    state = store.get(body["investigation_id"])
    assert state is not None
    seeded = state.add_evidence(
        category="net_adapters",
        source="collector:m028-test-pkg:zeta",
        data={"summary": "Seeded other-computer adapters.", "adapters": []},
        tool_name="get_network_adapters",
        tool_args={},
    )
    store.save(state)

    response = _reverify(body["investigation_id"], seeded.id)
    assert response.status_code == 422, response.text
    assert "collector" in response.json()["detail"].lower()


# ---------- invalid input fails closed, never executes ----------


def test_reverify_network_rejects_schema_invalid_stored_args() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    state = store.get(body["investigation_id"])
    assert state is not None
    seeded = state.add_evidence(
        category="dns_test",
        source="tool:test_dns_resolution:fixture",
        data={"summary": "Seeded bad-args DNS test."},
        tool_name="test_dns_resolution",
        tool_args={"hostname": 12345},
    )
    store.save(state)

    response = _reverify(body["investigation_id"], seeded.id)
    assert response.status_code == 422, response.text


def test_reverify_network_records_error_for_unresolvable_hostname() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    state = store.get(body["investigation_id"])
    assert state is not None
    seeded = state.add_evidence(
        category="dns_test",
        source="tool:test_dns_resolution:fixture",
        data={"summary": "Seeded bad-hostname DNS test."},
        tool_name="test_dns_resolution",
        tool_args={"hostname": "not a host!!"},
    )
    store.save(state)

    response = _reverify(body["investigation_id"], seeded.id)
    assert response.status_code == 200, response.text
    again = response.json()
    refresh = next(
        r for r in again["refreshes"] if r["old_evidence_id"] == seeded.id
    )
    assert refresh["verdict"] == "unavailable"
    by_id = {item["id"]: item for item in again["evidence"]}
    assert by_id[refresh["new_evidence_id"]]["error"]


@pytest.mark.parametrize(
    "bad",
    ["", "  ", "not a host", "host!", "-leading.com", "x" * 254, "a;b", "h..ost"],
)
def test_validate_hostname_rejects_bad_input(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_hostname(bad)


@pytest.mark.parametrize("good", ["example.com", "host1", "a-b.local", "x.y.z"])
def test_validate_hostname_accepts_good_input(good: str) -> None:
    assert validate_hostname(good) == good


def test_reverify_unknown_network_evidence_404() -> None:
    body = _investigate("DNS does not resolve anything since this morning.")
    response = _reverify(body["investigation_id"], "ev-999999")
    assert response.status_code == 404
