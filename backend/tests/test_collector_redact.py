"""Redaction core (collector/redact_import.py, contracts D4/D8)."""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from collector import redact_import as redact


def test_secret_key_value_pairs():
    assert redact.redact_text("password: hunter2", username="") == "[secret redacted]"
    assert redact.redact_text("token=abc123", username="") == "[secret redacted]"
    assert redact.redact_text("api_key : shh", username="") == "[secret redacted]"
    assert redact.redact_text("pwd: hunter2", username="") == "[secret redacted]"
    assert "hunter2" not in redact.redact_text("--pwd hunter2", username="")


def test_secret_flag_form():
    cleaned = redact.redact_text("run --password hunter2 now", username="")
    assert "hunter2" not in cleaned
    assert "[secret redacted]" in cleaned


def test_email_redacted():
    assert redact.redact_text("mail ops@example.com today", username="") == (
        "mail [email redacted] today"
    )


def test_domain_user_redacted():
    assert redact.redact_text("owner CORP\\FieldTech here", username="") == (
        "owner [user redacted] here"
    )


def test_os_username_masked_when_long_enough():
    assert redact.redact_text("ran by FieldTech", username="FieldTech") == (
        "ran by [user redacted]"
    )
    # Short names (<3 chars) are not masked (false-positive guard).
    assert redact.redact_text("ran by ab", username="ab") == "ran by ab"


def test_default_username_path_does_not_crash():
    assert isinstance(redact.redact_text("hello"), str)
    assert isinstance(redact.redact_value({"a": 1}), str)


def test_hostname_replaced_with_hint():
    cleaned = redact.redact_text(
        "failed on FIELD-PC-042 today", hostname="field-pc-042",
        hint="front-desk-pc", username="",
    )
    assert "FIELD-PC-042" not in cleaned
    assert "[host front-desk-pc]" in cleaned


def test_hostname_replaced_without_hint():
    cleaned = redact.redact_text("failed on h1", hostname="h1", username="")
    assert cleaned == "failed on [host redacted]"


def test_hash_hostname_deterministic_and_case_insensitive():
    first = redact.hash_hostname("Field-PC-042")
    assert re.fullmatch(r"[0-9a-f]{64}", first)
    assert first == redact.hash_hostname("field-pc-042")
    assert first == redact.hash_hostname("  FIELD-PC-042  ")


def test_sanitize_hint():
    assert redact.sanitize_hint(None) is None
    assert redact.sanitize_hint("") is None
    assert redact.sanitize_hint("  front-desk-pc ", "field-pc-042") == "front-desk-pc"
    try:
        redact.sanitize_hint("field-pc-042", "FIELD-PC-042")
    except ValueError:
        pass
    else:
        raise AssertionError("hint equal to hostname must raise")
    try:
        redact.sanitize_hint("pc field-pc-042 x", "field-pc-042")
    except ValueError:
        pass
    else:
        raise AssertionError("hint containing hostname must raise")
    try:
        redact.sanitize_hint("x" * 129)
    except ValueError:
        pass
    else:
        raise AssertionError("overlong hint must raise")


def test_build_identity():
    identity = redact.build_identity("Field-PC-042", "front-desk-pc")
    assert identity["hostname_hash"] == redact.hash_hostname("field-pc-042")
    assert identity["target_hint"] == "front-desk-pc"
    try:
        redact.build_identity("   ")
    except ValueError:
        pass
    else:
        raise AssertionError("empty hostname must raise")


def test_redact_value_scalars():
    assert redact.redact_value(None, username="") == ""
    assert redact.redact_value(True, username="") == "true"
    assert redact.redact_value(42, username="") == "42"
    assert redact.redact_value(1.5, username="") == "1.5"
    assert redact.redact_value(["a@b.com", "ok"], username="") == (
        "[[email redacted], ok]"
    )
    long_list = redact.redact_value(list(range(20)), username="")
    assert long_list.count(",") == 7  # capped at 8 items


def test_redact_value_truncates():
    assert redact.redact_value("x" * 300, max_chars=200, username="").endswith("…")
    assert len(redact.redact_value("x" * 300, max_chars=200, username="")) == 200


def test_counts_track_substitutions():
    _, count = redact.redact_text_with_count(
        "a@b.com and password: x", username=""
    )
    assert count == 2
    _, count = redact.redact_text_with_count("nothing sensitive", username="")
    assert count == 0
    _, count = redact.redact_value_with_count("a@b.com", username="")
    assert count == 1


def test_redact_data_recurses_and_preserves_types():
    payload = {
        "msg": "contact a@b.com",
        "nested": [{"n": 1}, ("x", "password: p")],
        "count": 3,
        "flag": False,
        "nothing": None,
    }
    cleaned, count = redact.redact_data(payload, username="")
    assert cleaned["msg"] == "contact [email redacted]"
    assert cleaned["nested"][0] == {"n": 1}
    assert cleaned["nested"][1][1] == "[secret redacted]"
    assert cleaned["count"] == 3 and cleaned["flag"] is False
    assert cleaned["nothing"] is None
    assert count == 2


def test_redact_data_drops_command_lines():
    payload = {
        "command_line": "app.exe --password hunter2",
        "CommandLine": "other.exe",
        "cmdline": "third.exe",
        "name": "app.exe",
    }
    cleaned, count = redact.redact_data(payload, username="")
    assert cleaned["command_line"] == "[cmdline dropped]"
    assert cleaned["CommandLine"] == "[cmdline dropped]"
    assert cleaned["cmdline"] == "[cmdline dropped]"
    assert cleaned["name"] == "app.exe"
    assert count == 3


def test_redact_data_redacts_but_keeps_arguments():
    payload = {"arguments": "-File sync.ps1 -Token abc123secret"}
    cleaned, count = redact.redact_data(payload, username="")
    assert "abc123secret" not in cleaned["arguments"]
    assert count >= 1


def test_backend_compatible_tokens():
    assert redact.redact_text("a@b.com", username="") == "[email redacted]"
    assert redact.redact_text("CORP\\u1 and EF\\user2", username="") == (
        "[user redacted] and [user redacted]"
    )
    assert redact.redact_text("secret: s3cr3t", username="") == "[secret redacted]"


def test_empty_inputs():
    assert redact.redact_text("", username="") == ""
    cleaned, count = redact.redact_data({}, username="")
    assert cleaned == {} and count == 0
