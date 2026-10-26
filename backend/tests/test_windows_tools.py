"""Windows tool helpers: enum mapping and availability probing."""

from app.diagnostics.windows_tools import ALLOWLISTED_COMMANDS, _status_name, powershell_available


def test_status_enum_numbers_map_to_names() -> None:
    assert _status_name(1) == "Stopped"
    assert _status_name(4) == "Running"
    assert _status_name(7) == "Paused"


def test_status_strings_pass_through() -> None:
    assert _status_name("Running") == "Running"
    assert _status_name("1") == "Stopped"
    assert _status_name("") == "Unknown"


def test_allowlist_is_read_only() -> None:
    joined = " ".join(ALLOWLISTED_COMMANDS).lower()
    for forbidden in ("stop-", "start-service", "restart-", "set-", "remove-", "new-"):
        assert forbidden not in joined


def test_powershell_probe_returns_bool() -> None:
    assert isinstance(powershell_available(), bool)
