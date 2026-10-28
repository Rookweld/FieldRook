"""Build the committed sample collector packages (deterministic, offline).

Outputs (written next to this script):

- ``sample_basic.zip`` — fixture collection, all categories + one service
  detail, one supplementary note, no chunks;
- ``sample_chunked.zip`` — fixture collection plus a ~30KB application-log
  document pre-chunked per D3a (``chunk_seq``/``chunk_of`` + ``refresh_of``
  chain), two supplementary files.

Run: ``python collector/samples/build_samples.py`` from the repo root.
"""

from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from collector.archive import create_package, extract_and_verify  # noqa: E402
from collector.chunker import chunk_entries, data_size_bytes  # noqa: E402
from collector.collect_windows import (  # noqa: E402
    FIXTURE_HOSTNAME,
    FIXTURE_USERNAME,
    collect_all,
)
from collector.manifest import build_manifest  # noqa: E402
from collector.redact_import import redact_data  # noqa: E402

SAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))
FIXED_CREATED_AT = "2026-10-28T17:00:00Z"
FIXED_DURATION_MS = 1234

BASIC_PACKAGE_ID = "11111111-1111-4111-8111-111111111111"
CHUNKED_PACKAGE_ID = "22222222-2222-4222-8222-222222222222"


def _pin_times(entries: list[dict]) -> None:
    for entry in entries:
        entry["collected_at"] = FIXED_CREATED_AT


def _large_log_text() -> str:
    lines = [
        "# ContosoVPN application log (sample, synthetic) — 2026-10-26",
        "# host: FIELD-PC-042 — support: ops@example.com",
        "",
    ]
    for i in range(1, 421):
        lines.append(
            f"2026-10-26T09:{i // 60:02d}:{i % 60:02d}Z level=Error "
            f"event=1000 app=ContosoVPN.exe module=VPNCore.dll "
            f"code=0xc0000005 offset=0x000{0x1000 + i:04x} "
            f"msg=\"tunnel re-establishment failed (attempt {i}); retrying with backoff\""
        )
    lines.append("2026-10-26T09:59:59Z level=Info event=9000 msg=\"log rotation requested\"")
    return "\n".join(lines) + "\n"


def build_basic() -> tuple[dict, dict[str, bytes]]:
    result = collect_all(
        consent_ack=True,
        fixture=True,
        hostname=FIXTURE_HOSTNAME,
        target_hint="front-desk-pc",
        username=FIXTURE_USERNAME,
        service_name="wuauserv",
    )
    _pin_times(result.entries)
    payloads = {
        "notes/collector-note.md": (
            "# Collector note (sample)\n\n"
            "Technician visited front desk; user reports Windows Update stuck at 0%.\n"
            "Package collected read-only with consent; no command lines included.\n"
        ).encode("utf-8"),
    }
    manifest = build_manifest(
        hostname_hash=result.hostname_hash,
        os_info=result.os_info,
        evidence=result.entries,
        file_hashes={k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()},
        package_id=BASIC_PACKAGE_ID,
        target_hint=result.target_hint,
        duration_ms=FIXED_DURATION_MS,
        warnings=result.warnings,
        created_at=FIXED_CREATED_AT,
    )
    return manifest, payloads


def build_chunked() -> tuple[dict, dict[str, bytes]]:
    result = collect_all(
        consent_ack=True,
        fixture=True,
        hostname=FIXTURE_HOSTNAME,
        target_hint="back-office-pc",
        username=FIXTURE_USERNAME,
    )
    raw_doc = {
        "doc_id": "app-log-sample",
        "title": "ContosoVPN application log (sample)",
        "path": "samples/app.log",
        "log_text": _large_log_text(),
    }
    redacted, count = redact_data(
        raw_doc, FIXTURE_HOSTNAME, "back-office-pc", FIXTURE_USERNAME
    )
    assert isinstance(redacted, dict)
    redacted["provenance"] = {"redaction_count": count}
    assert data_size_bytes(redacted) > 12 * 1024, "sample doc must exceed 12KB"
    # build_entry refuses oversize input by design; assemble then chunk.
    doc_entry = {
        "id": "c-doc",
        "category": "app_crashes",
        "source_suffix": "fixture",
        "collected_at": FIXED_CREATED_AT,
        "data": redacted,
        "sha256": "pending",
        "size": 0,
    }
    _pin_times(result.entries)
    chunked, chunk_warnings = chunk_entries([*result.entries, doc_entry])
    for entry in chunked:
        entry["collected_at"] = FIXED_CREATED_AT
    payloads = {
        "notes/case-note.txt": (
            "Back office PC stalls on VPN connect; see chunked app log.\n"
            "Collected read-only with consent.\n"
        ).encode("utf-8"),
        "files/app-summary.log": (
            "2026-10-26 summary: 420 tunnel failures, 1 rotation request.\n"
        ).encode("utf-8"),
    }
    manifest = build_manifest(
        hostname_hash=result.hostname_hash,
        os_info=result.os_info,
        evidence=chunked,
        file_hashes={k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()},
        package_id=CHUNKED_PACKAGE_ID,
        target_hint=result.target_hint,
        duration_ms=FIXED_DURATION_MS,
        warnings=[*result.warnings, *chunk_warnings],
        created_at=FIXED_CREATED_AT,
    )
    return manifest, payloads


def build_all(out_dir: str = SAMPLES_DIR) -> list[str]:
    outputs: list[str] = []
    for name, builder in (("sample_basic.zip", build_basic), ("sample_chunked.zip", build_chunked)):
        manifest, payloads = builder()
        dest = os.path.join(out_dir, name)
        create_package(manifest, payloads, dest)
        outputs.append(dest)
    return outputs


def main() -> int:
    import shutil
    import tempfile

    outputs = build_all()
    for path in outputs:
        tmp = tempfile.mkdtemp(prefix="fieldrook-sample-check-")
        try:
            _, manifest, warnings = extract_and_verify(path, os.path.join(tmp, "pkg"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print(
            f"built + verified {os.path.basename(path)}: "
            f"{len(manifest['evidence'])} entries, "
            f"{len(manifest['file_hashes'])} files, {len(warnings)} warnings."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
