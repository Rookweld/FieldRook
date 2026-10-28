"""New BETA diagnostics: fixture-mode tests + guarded live probes.

Live probes run only when PowerShell exists and only for safe, read-only
commands; they assert loose shapes, never exact machine state.
"""

import pytest

from app.diagnostics.windows_devices import (
    PROPOSED_ALLOWLIST_ADDITIONS as DEV_ALLOWLIST,
)
from app.diagnostics.windows_devices import (
    ListDevicesArgs,
    ListVolumesArgs,
    get_fixture_devices,
    get_fixture_volumes,
    list_devices_fixture,
    list_volumes_fixture,
    validate_device_status,
    validate_limit,
)
from app.diagnostics.windows_office import (
    PROPOSED_ALLOWLIST_ADDITIONS as OFFICE_ALLOWLIST,
)
from app.diagnostics.windows_office import (
    GetOfficeConfigArgs,
    ListOfficeInstallsArgs,
    get_fixture_office_config,
    get_fixture_office_installs,
    get_office_config_fixture,
    list_office_installs_fixture,
)
from app.diagnostics.windows_tools import powershell_available


def test_devices_fixture_shapes() -> None:
    devices = list_devices_fixture()
    assert len(devices) == 3
    first = devices[0]
    assert set(first) == {"name", "instance_id", "device_class", "status", "problem_code", "has_problem"}
    assert first["has_problem"] is False
    troubled = [device for device in devices if device["has_problem"]]
    assert len(troubled) == 1
    assert troubled[0]["problem_code"] == 28
    assert list_devices_fixture() == devices


def test_devices_fixture_filters_and_caps() -> None:
    assert len(list_devices_fixture(status="OK")) == 1
    assert len(list_devices_fixture(status="error")) == 1
    assert len(list_devices_fixture(limit=2)) == 2
    assert list_devices_fixture(limit=1, status="Degraded")[0]["device_class"] == "Printer"
    assert get_fixture_devices() == list_devices_fixture(limit=100)


def test_devices_validation() -> None:
    assert validate_device_status("") == ""
    assert validate_device_status("ok") == "OK"
    with pytest.raises(ValueError):
        validate_device_status("exploding")
    with pytest.raises(ValueError):
        validate_limit(0)
    with pytest.raises(ValueError):
        validate_limit(101)
    with pytest.raises(ValueError):
        list_devices_fixture(status="bogus")
    ListDevicesArgs.model_validate({"limit": 10, "status": "OK"})
    ListVolumesArgs.model_validate({})
    with pytest.raises(Exception):
        ListDevicesArgs.model_validate({"limit": 10, "extra": 1})


def test_volumes_fixture_shapes() -> None:
    volumes = list_volumes_fixture()
    assert len(volumes) == 2
    system = volumes[0]
    assert system["drive"] == "C:"
    assert system["filesystem"] == "NTFS"
    assert system["size_bytes"] > 0
    assert 0 <= system["used_pct"] <= 100
    assert system["free_bytes"] < system["size_bytes"]
    assert get_fixture_volumes() == volumes


def test_office_installs_fixture_shapes() -> None:
    installs = list_office_installs_fixture()
    assert len(installs) == 2
    first = installs[0]
    assert set(first) == {"display_name", "display_version", "publisher", "install_date"}
    assert "Microsoft" in first["display_name"]
    assert get_fixture_office_installs() == installs
    ListOfficeInstallsArgs.model_validate({})


def test_office_config_fixture_shapes() -> None:
    config = get_office_config_fixture()
    assert config["installed"] is True
    assert config["version"].startswith("16.0.")
    assert config["products"] == ["O365ProPlusRetail"]
    assert get_fixture_office_config() == config
    GetOfficeConfigArgs.model_validate({})


def test_proposed_allowlist_is_read_only() -> None:
    joined = " ".join([*DEV_ALLOWLIST, *OFFICE_ALLOWLIST]).lower()
    for forbidden in ("stop-", "start-service", "restart-", "set-", "remove-", "new-"):
        assert forbidden not in joined
    assert DEV_ALLOWLIST == ("Get-PnpDevice", "Get-CimInstance Win32_LogicalDisk")
    assert OFFICE_ALLOWLIST == ("Get-ItemProperty Uninstall/Office", "Get-ItemProperty ClickToRun/Configuration")


def test_new_scripts_are_read_only() -> None:
    import app.diagnostics.windows_devices as dev
    import app.diagnostics.windows_office as office

    scripts = [dev._DEVICES_SCRIPT, dev._VOLUMES_SCRIPT, office._INSTALLS_SCRIPT, office._C2R_SCRIPT]
    assert len(scripts) == 4
    for script in scripts:
        lowered = script.lower()
        for forbidden in ("stop-", "start-service", "restart-", "set-", "remove-", "new-"):
            assert forbidden not in lowered
        assert "convertto-json" in lowered


def _needs_live() -> None:
    if not powershell_available():
        pytest.skip("PowerShell unavailable; fixture mode only.")


def test_live_devices_shape_when_available() -> None:
    _needs_live()
    from app.diagnostics.windows_devices import list_devices_live

    devices = list_devices_live(30.0, limit=5)
    assert isinstance(devices, list)
    assert len(devices) <= 5
    for device in devices:
        assert set(device) == {"name", "instance_id", "device_class", "status", "problem_code", "has_problem"}


def test_live_volumes_shape_when_available() -> None:
    _needs_live()
    from app.diagnostics.windows_devices import list_volumes_live

    volumes = list_volumes_live(30.0)
    assert isinstance(volumes, list)
    for volume in volumes:
        assert volume["drive"]
        assert volume["size_bytes"] is None or volume["size_bytes"] >= 0


def test_live_office_shapes_when_available() -> None:
    _needs_live()
    from app.diagnostics.windows_office import get_office_config_live, list_office_installs_live

    installs = list_office_installs_live(30.0)
    assert isinstance(installs, list)
    for install in installs:
        assert install["display_name"]
    config = get_office_config_live(30.0)
    assert isinstance(config.get("installed"), bool)
    assert set(config) == {"installed", "version", "channel", "products", "installation_path"}
