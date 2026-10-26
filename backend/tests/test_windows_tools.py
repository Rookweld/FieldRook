"""Windows tool helpers: enum mapping and availability probing."""

from app.diagnostics.windows_tools import (
    ALLOWLISTED_COMMANDS,
    _service_type_name,
    _service_type_value,
    _status_name,
    powershell_available,
)


def test_status_enum_numbers_map_to_names() -> None:
    assert _status_name(1) == "Stopped"
    assert _status_name(4) == "Running"
    assert _status_name(7) == "Paused"


def test_status_strings_pass_through() -> None:
    assert _status_name("Running") == "Running"
    assert _status_name("1") == "Stopped"
    assert _status_name("") == "Unknown"


def test_service_type_flags_map_to_names() -> None:
    assert _service_type_name(32) == "Win32ShareProcess"
    assert _service_type_name(16) == "Win32OwnProcess"
    assert _service_type_name(272) == "InteractiveProcess | Win32OwnProcess"
    assert _service_type_name("Win32ShareProcess") == "Win32ShareProcess"
    assert _service_type_name("") == "Unknown"


def test_service_type_unknown_bits_surfaced_not_guessed() -> None:
    assert _service_type_name(1024) == "1024"
    assert _service_type_name(0) == "Unknown"


def test_service_type_numeric_value_preserved() -> None:
    assert _service_type_value(32) == 32
    assert _service_type_value("16") == 16
    assert _service_type_value("Win32ShareProcess") is None
    assert _service_type_value("") is None


def test_allowlist_is_read_only() -> None:
    joined = " ".join(ALLOWLISTED_COMMANDS).lower()
    for forbidden in ("stop-", "start-service", "restart-", "set-", "remove-", "new-"):
        assert forbidden not in joined


def test_powershell_probe_returns_bool() -> None:
    assert isinstance(powershell_available(), bool)
