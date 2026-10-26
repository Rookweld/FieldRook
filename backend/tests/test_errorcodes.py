"""Windows error-code interpretation: deterministic, never guessed."""

import asyncio

import pytest

from app.diagnostics.errorcodes import ErrorCodeError, interpret
from app.tools.registry import ToolContext, execute_prepared, prepare_call
from app.config import Settings


def test_case001_code_decodes_to_error_directory() -> None:
    decoded = interpret(2147942667)
    assert decoded["hex"] == "0x8007010B"
    assert decoded["family"] == "hresult"
    assert decoded["win32_code"] == 267
    assert decoded["name"] == "ERROR_DIRECTORY"


def test_hex_string_and_negative_forms() -> None:
    assert interpret("0x80070005")["win32_code"] == 5
    assert interpret("0x80070005")["name"] == "ERROR_ACCESS_DENIED"
    assert interpret(-2147024891)["hex"] == "0x80070005"
    assert interpret(5)["family"] == "win32"
    assert interpret(5)["name"] == "ERROR_ACCESS_DENIED"


def test_unknown_codes_not_guessed() -> None:
    decoded = interpret(999999)
    assert decoded["name"] is None
    assert "not guessed" in str(decoded.get("note", ""))


def test_invalid_values_rejected() -> None:
    with pytest.raises(ErrorCodeError):
        interpret("bogus")
    with pytest.raises(ErrorCodeError):
        interpret(2**40)
    with pytest.raises(ErrorCodeError):
        interpret("")


def test_error_code_tool_end_to_end() -> None:
    settings = Settings(
        model_api_key=None,
        model_base_url="https://api.meta.ai/v1",
        model_name="muse-spark-1.3",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=5.0,
    )
    spec, args = prepare_call("interpret_error_code", {"value": "2147942667"})
    output, _ = asyncio.run(execute_prepared(spec, args, ToolContext(settings=settings, use_fixtures=True)))
    assert output.error is None
    assert output.data["hex"] == "0x8007010B"
    assert output.data["name"] == "ERROR_DIRECTORY"
    bad_spec, bad_args = prepare_call("interpret_error_code", {"value": "bogus"})
    bad, _ = asyncio.run(execute_prepared(bad_spec, bad_args, ToolContext(settings=settings, use_fixtures=True)))
    assert bad.error is not None
