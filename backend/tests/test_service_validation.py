"""Service identifier validation: only safe names reach the command layer."""

import pytest

from app.diagnostics.service_allowlist import InvalidServiceNameError, validate_service_name


@pytest.mark.parametrize(
    "name", ["wuauserv", "BITS", "Winmgmt", "Spooler", "a", "A-1_2.3", "x" * 64]
)
def test_valid_names_pass_through(name: str) -> None:
    assert validate_service_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
        "a" * 65,
        "foo bar",
        "foo;bar",
        "a$b",
        "a'b",
        'a"b',
        "a|b",
        "a&b",
        "../x",
        "a`b",
        "a(b)",
        "a*b",
        None,
        123,
    ],
)
def test_invalid_names_rejected(name: object) -> None:
    with pytest.raises(InvalidServiceNameError):
        validate_service_name(name)


def test_surrounding_whitespace_stripped() -> None:
    assert validate_service_name("  wuauserv ") == "wuauserv"
