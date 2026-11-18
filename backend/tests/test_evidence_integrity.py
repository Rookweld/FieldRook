"""M033-F: deterministic, source-aware inference audit.

The code under test MUST NOT silently rewrite a technician observation,
cause, hypothesis, or measured evidence. Heuristic warnings are not facts.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.analysis.evidence_integrity import (
    audit_reassessment,
    format_audit_note,
    summarize_sources,
)


def report(**overrides):
    base = dict(
        verdict="An application-specific cause is still unverified.",
        weakened=[],
        next_step="Compare an authorized read-only observation.",
    )
    base.update(overrides)
    return base


def codes(payload, **kwargs):
    return {
        finding.code for finding in audit_reassessment(
            payload,
            problem=kwargs.pop("problem", "A laptop application fails."),
            observation=kwargs.pop("observation", "No new information yet."),
            **kwargs,
        )
    }


def test_does_not_mutate_model_response() -> None:
    raw = report(
        verdict="The camera issue is consistent across multiple devices.",
        weakened=["Camera driver conflict"],
    )
    untouched = deepcopy(raw)
    assert "unverified-multi-host-claim" in codes(
        raw, observation="The built-in Camera app is black on the same laptop."
    )
    assert raw == untouched


def test_distinguishes_two_apps_from_two_physical_devices() -> None:
    assert "unverified-multi-host-claim" in codes(
        report(verdict="The problem is consistent across multiple applications and devices."),
        observation="The built-in Camera app also shows a black screen.",
        problem="The laptop camera is black in Teams.",
    )


def test_multiple_devices_explicitly_reported_no_false_flag() -> None:
    assert "unverified-multi-host-claim" not in codes(
        report(verdict="The problem occurs across multiple devices."),
        observation="Two separate laptops in the same office both exhibit the issue.",
    )


def test_speculation_about_other_devices_not_reported_as_measurement() -> None:
    assert "unverified-multi-host-claim" not in codes(
        report(verdict="This might occur across multiple devices."),
        observation="Two applications show the same black screen.",
    )


def test_no_device_cardinality_claim_no_warning() -> None:
    assert not codes(
        report(verdict="The built-in Camera app and Teams both show a black image."),
        observation="The built-in Camera app also shows a black screen.",
    )


def test_ping_timeout_cannot_prove_application_service_state() -> None:
    assert "icmp-not-service-proof" in codes(
        report(verdict="The license server is unreachable due to network configuration problems."),
        problem="SolidEdge fails to check out a license.",
        observation="Ping to license-srv01 times out; IT reports server is up.",
    )


def test_ping_only_indicates_reachability_not_mandatory_failure_flag() -> None:
    assert "icmp-not-service-proof" not in codes(
        report(verdict="The ICMP test timed out. The licensing service remains unverified."),
        observation="Ping to license-srv01 times out.",
    )


def test_service_status_cannot_be_proven_by_missing_ping_alone() -> None:
    assert "icmp-not-service-proof" in codes(
        report(verdict="Ping proves the application service is down."),
        observation="The license server ping times out.",
    )


def test_confirmed_service_result_not_misread_as_ping_only() -> None:
    # A new host measurement may be relevant evidence, but this reviewer
    # intentionally does not reason about whether the measurement is enough.
    fresh = SimpleNamespace(
        id="e-9", source="tool:get_service:live", tool_name="get_service",
        category="service_status", error=None, data={"state": "stopped"},
    )
    assert "icmp-not-service-proof" not in codes(
        report(verdict="The licensing service is down after an authorized host check."),
        observation="Ping to license-srv01 times out.",
        evidence=[fresh], new_evidence_ids={"e-9"},
    )


def test_new_driver_change_downgrade_gets_review_not_auto_block() -> None:
    assert "correlated-change-weakened" in codes(
        report(
            verdict="The new information suggests the driver is not likely.",
            weakened=["Network adapter driver conflict"],
        ),
        observation="Windows Update installed a new network adapter driver yesterday.",
    )


def test_explicit_reversal_does_not_trigger_change_overlap_warning() -> None:
    assert "correlated-change-weakened" not in codes(
        report(
            verdict="The previous driver issue appears to be resolved.",
            weakened=["Network adapter driver conflict"],
        ),
        observation="The network adapter driver was rolled back and the problem resolved.",
    )


def test_unrelated_weakening_has_no_correlated_change_warning() -> None:
    assert "correlated-change-weakened" not in codes(
        report(weakened=["Storage volume corruption"]),
        observation="Windows Update installed a new network adapter driver.",
    )


def test_string_instead_of_list_is_ignored_safely() -> None:
    assert not codes(
        report(weakened="Network driver conflict"),
        observation="Windows installed a new network driver.",
    )


def test_none_response_produces_no_findings() -> None:
    assert not codes(None)


def test_private_evidence_not_written_in_activity_note() -> None:
    content = "C:\\Users\\SecretPerson\\financial\\folder.txt"
    findings = audit_reassessment(
        report(verdict="Observed across multiple devices: " + content),
        problem="One laptop fails. " + content,
        observation="The Camera app also fails.",
    )
    note = format_audit_note(findings)
    assert "unverified-multi-host-claim" in note
    assert content not in note
    assert "no hypothesis status changed" in note.lower()


def test_source_counts_reports_vs_measured_vs_failed() -> None:
    items = [
        SimpleNamespace(id="e1", source="tool:get_os_info:live", tool_name="get_os_info",
                        category="os_info", data={"os": "Windows"}, error=None),
        SimpleNamespace(id="e2", source="tool:get_service:live", tool_name="get_service",
                        category="service", data={}, error="Timeout"),
        SimpleNamespace(id="e3", source="report:technician", tool_name=None,
                        category="observation", data={"claim": "It fails"}, error=None),
    ]
    info = summarize_sources(items, "The app fails.")
    assert info.measured_host_items == 1
    assert info.failed_host_items == 1
    assert info.non_host_items == 1
    assert info.technician_report_present


def test_no_tool_measurement_claim_from_fixture() -> None:
    fixture = SimpleNamespace(
        id="e1", source="fixture:services", tool_name="get_service",
        category="service", data={"state": "running"}, error=None,
    )
    info = summarize_sources([fixture], "")
    assert not info.measured_host_items
    assert info.non_host_items == 1


def test_old_tool_measurement_is_not_fresh_evidence() -> None:
    old = SimpleNamespace(
        id="e-old", source="tool:get_service:live", tool_name="get_service",
        category="service_status", data={"state": "stopped"}, error=None,
    )
    assert "icmp-not-service-proof" in codes(
        report(verdict="The licensing service is unreachable due to network misconfiguration."),
        observation="Ping to the license server times out.",
        evidence=[old], new_evidence_ids=set(),
    )


@pytest.mark.parametrize("payload", [
    {"verdict": None, "weakened": None},
    {"verdict": "", "weakened": [None, 123]},
    {"verdict": "A possible problem.", "weakened": 42},
])
def test_malformed_model_data_does_not_crash(payload) -> None:
    assert isinstance(
        audit_reassessment(
            payload,
            problem="A laptop camera is black.",
            observation="A camera driver was newly installed.",
        ), tuple,
    )


def test_unrelated_new_os_measurement_does_not_prove_license_service() -> None:
    os_info = SimpleNamespace(
        id="e-os", source="tool:get_os_info:live", tool_name="get_os_info",
        category="os_info", data={"edition": "Windows 11"}, error=None,
    )
    assert "icmp-not-service-proof" in codes(
        report(verdict="The licensing server is unreachable due to a network configuration problem."),
        problem="CAD license checkout fails.",
        observation="Ping to license-srv01 times out.",
        evidence=[os_info], new_evidence_ids={"e-os"},
    )


def test_new_generic_device_measurement_cannot_prove_multiple_devices() -> None:
    os_info = SimpleNamespace(
        id="e-os", source="tool:get_os_info:live", tool_name="get_os_info",
        category="os_info", data={"edition": "Windows 11"}, error=None,
    )
    assert "unverified-multi-host-claim" in codes(
        report(verdict="The camera fault has been observed across multiple devices."),
        observation="Windows Camera and Teams are black on the laptop.",
        evidence=[os_info], new_evidence_ids={"e-os"},
    )


def test_service_specific_measurement_does_not_prove_network_root_cause() -> None:
    result = SimpleNamespace(
        id="e-status", source="tool:get_service:live", tool_name="get_service",
        category="service_status", data={"state": "stopped"}, error=None,
    )
    assert "icmp-not-service-proof" in codes(
        report(verdict="The license server is unreachable due to misconfigured networking."),
        observation="Ping to the license server times out.",
        evidence=[result], new_evidence_ids={"e-status"},
    )
