"""Deterministic Windows error-code interpretation (no guessing, no model).

Understands decimal, hex, and signed-32-bit spellings of Win32 codes and
HRESULTs. A curated table maps common codes to symbolic names; anything
outside the table is reported as unrecognized, never invented.
"""

from __future__ import annotations

# Curated common codes: win32 -> (symbolic name, description).
WIN32_ERRORS: dict[int, tuple[str, str]] = {
    0: ("ERROR_SUCCESS", "The operation completed successfully."),
    1: ("ERROR_INVALID_FUNCTION", "Incorrect function."),
    2: ("ERROR_FILE_NOT_FOUND", "The system cannot find the file specified."),
    3: ("ERROR_PATH_NOT_FOUND", "The system cannot find the path specified."),
    5: ("ERROR_ACCESS_DENIED", "Access is denied."),
    6: ("ERROR_INVALID_HANDLE", "The handle is invalid."),
    32: ("ERROR_SHARING_VIOLATION", "The process cannot access the file because it is being used by another process."),
    53: ("ERROR_BAD_NETPATH", "The network path was not found."),
    87: ("ERROR_INVALID_PARAMETER", "The parameter is incorrect."),
    123: ("ERROR_INVALID_NAME", "The filename, directory name, or volume label syntax is incorrect."),
    267: ("ERROR_DIRECTORY", "The directory name is invalid."),
    1053: ("ERROR_SERVICE_REQUEST_TIMEOUT", "The service did not respond to the start or control request in a timely fashion."),
    1056: ("ERROR_SERVICE_ALREADY_RUNNING", "An instance of the service is already running."),
    1058: ("ERROR_SERVICE_DISABLED", "The service cannot be started, either because it is disabled or because it has no enabled devices associated with it."),
    1060: ("ERROR_SERVICE_DOES_NOT_EXIST", "The specified service does not exist as an installed service."),
    1062: ("ERROR_SERVICE_NOT_ACTIVE", "The service has not been started."),
}


class ErrorCodeError(ValueError):
    pass


def _to_unsigned32(value: int | str) -> int:
    if isinstance(value, bool):
        raise ErrorCodeError("Boolean is not an error code.")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip().lower()
        if not text:
            raise ErrorCodeError("Empty error-code value.")
        try:
            number = int(text, 0)
        except ValueError as exc:
            raise ErrorCodeError(f"Could not parse {value!r} as a number.") from exc
    else:
        raise ErrorCodeError(f"Unsupported error-code type {type(value).__name__}.")
    if number < -(2**31) or number > 0xFFFFFFFF:
        raise ErrorCodeError(f"Value {value!r} is outside the 32-bit range.")
    return number & 0xFFFFFFFF


def interpret(value: int | str) -> dict[str, object]:
    """Return the deterministic decoding of a Win32/HRESULT value."""
    unsigned = _to_unsigned32(value)
    signed = unsigned - 0x100000000 if unsigned & 0x80000000 else unsigned
    result: dict[str, object] = {
        "input": str(value),
        "unsigned": unsigned,
        "signed": signed,
        "hex": f"0x{unsigned:08X}",
        "family": "unknown",
        "win32_code": None,
        "name": None,
        "description": None,
    }
    win32_code: int | None = None
    if unsigned >> 16 == 0x8007:
        result["family"] = "hresult"
        win32_code = unsigned & 0xFFFF
    elif unsigned < 65536:
        result["family"] = "win32"
        win32_code = unsigned
    elif unsigned & 0x80000000:
        result["family"] = "hresult"
        result["facility"] = (unsigned >> 16) & 0x7FF
        result["code_bits"] = unsigned & 0xFFFF
    if win32_code is not None:
        result["win32_code"] = win32_code
        known = WIN32_ERRORS.get(win32_code)
        if known is not None:
            result["name"], result["description"] = known
        else:
            result["note"] = "Meaning not in the local table; not guessed."
    else:
        result["note"] = "No Win32 mapping recognized; not guessed."
    return result
