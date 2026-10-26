"""Evidence collection in deterministic fixture mode."""

from app.config import Settings
from app.diagnostics.collector import collect_diagnostics, list_services_collected


def _settings() -> Settings:
    return Settings(
        model_api_key=None,
        model_base_url="https://api.meta.ai/v1",
        model_name="muse-spark-1.3",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=5.0,
    )


def test_fixture_bundle_shape() -> None:
    bundle = collect_diagnostics("wuauserv", _settings())
    assert bundle.mode == "fixture"
    assert bundle.service_name == "wuauserv"
    assert [item.category for item in bundle.items] == [
        "service_status",
        "startup_type",
        "event_log",
    ]
    assert [item.id for item in bundle.items] == ["ev-1", "ev-2", "ev-3"]
    assert all(item.source.startswith("fixture:") for item in bundle.items)
    assert all(item.error is None for item in bundle.items)
    assert all(item.collected_at is not None for item in bundle.items)
    assert bundle.items[0].data["status"] == "Stopped"
    assert bundle.items[1].data["startup_type"] == "Manual"
    assert bundle.items[2].data["matched"] == 2


def test_fixture_collection_is_deterministic() -> None:
    first = collect_diagnostics("Spooler", _settings())
    second = collect_diagnostics("Spooler", _settings())
    assert [item.data for item in first.items] == [item.data for item in second.items]
    assert [item.error for item in first.items] == [item.error for item in second.items]


def test_unknown_service_yields_honest_no_data_items() -> None:
    bundle = collect_diagnostics("NoSuchSvc123", _settings())
    assert bundle.mode == "fixture"
    assert len(bundle.items) == 3
    assert all(item.error for item in bundle.items)
    assert bundle.warnings


def test_fixture_service_list_contains_known_services() -> None:
    response = list_services_collected(_settings())
    assert response.mode == "fixture"
    names = {service.name for service in response.services}
    assert {"wuauserv", "Spooler", "BITS"} <= names
