"""Portable collector CLI (stdlib only, offline).

Collect::

    python -m collector collect --out package.zip --yes [--hint LABEL]
        [--categories services,os,events,network,tasks,procs]
        [--service NAME] [--fixture] [--note PATH] [--log PATH]

Validate::

    python -m collector validate package.zip

``collect`` prints the per-category consent screen and refuses to run
without ``--yes``. ``--note``/``--log`` attach supplementary UTF-8 text
payloads (``.json``/``.txt``/``.md``/``.log`` only) under ``notes/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from .archive import ArchiveError, create_package, extract_and_verify
from .chunker import chunk_entries
from .collect_windows import CATEGORIES, collect_all, format_consent_screen
from .manifest import build_manifest, new_package_id, utc_now_iso

ALLOWED_NOTE_SUFFIXES = frozenset({".json", ".txt", ".md", ".log"})


def _parse_categories(raw: str | None) -> list[str]:
    if not raw:
        return sorted(CATEGORIES)
    keys = [part.strip().lower() for part in raw.split(",") if part.strip()]
    unknown = [k for k in keys if k not in CATEGORIES]
    if unknown:
        raise SystemExit(f"error: unknown categories: {unknown}.")
    if not keys:
        raise SystemExit("error: no categories selected.")
    return keys


def _load_notes(paths: list[str]) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    for raw in paths:
        path = Path(raw)
        if path.suffix.lower() not in ALLOWED_NOTE_SUFFIXES:
            raise SystemExit(
                f"error: note {raw!r} must end .json/.txt/.md/.log."
            )
        try:
            blob = path.read_bytes()
        except OSError as exc:
            raise SystemExit(f"error: cannot read {raw!r}: {exc}.")
        try:
            blob.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise SystemExit(f"error: note {raw!r} is not valid UTF-8.")
        payloads[f"notes/{path.name}"] = blob
    return payloads


def cmd_collect(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="collector collect")
    parser.add_argument("--out", required=True, help="Destination .zip path.")
    parser.add_argument("--yes", action="store_true", help="Acknowledge consent screen.")
    parser.add_argument("--hint", default=None, help="Technician label (never the hostname).")
    parser.add_argument("--categories", default=None, help="Comma-separated subset.")
    parser.add_argument("--service", default="", help="Optional target service for details.")
    parser.add_argument("--fixture", action="store_true", help="Deterministic synthetic data.")
    parser.add_argument("--note", action="append", default=[], help="Attach a text file (repeatable).")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    keys = _parse_categories(args.categories)
    print(format_consent_screen(keys))
    print()
    if not args.yes:
        print("Refusing to collect without --yes (consent not acknowledged).")
        return 2
    try:
        result = collect_all(
            categories=keys,
            consent_ack=True,
            timeout_s=args.timeout,
            fixture=args.fixture,
            target_hint=args.hint,
            service_name=args.service,
        )
    except PermissionError as exc:
        print(f"error: {exc}")
        return 2
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    payloads = _load_notes(args.note)
    chunked, chunk_warnings = chunk_entries(result.entries)
    warnings = list(result.warnings) + chunk_warnings
    file_hashes = {
        rel: hashlib.sha256(blob).hexdigest() for rel, blob in payloads.items()
    }
    manifest = build_manifest(
        hostname_hash=result.hostname_hash,
        os_info=result.os_info,
        evidence=chunked,
        file_hashes=file_hashes,
        package_id=new_package_id(),
        target_hint=result.target_hint,
        duration_ms=result.duration_ms,
        warnings=warnings,
        created_at=utc_now_iso(),
    )
    try:
        dest = create_package(manifest, payloads, args.out)
    except ArchiveError as exc:
        print(f"error: {exc}")
        return 1
    print(f"wrote {dest} ({len(chunked)} evidence entries, {len(payloads)} notes).")
    for warning in warnings:
        print(f"warning: {warning}")
    return 0


def cmd_validate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="collector validate")
    parser.add_argument("package", help="Package .zip path.")
    args = parser.parse_args(argv)
    tmp = Path(tempfile.mkdtemp(prefix="fieldrook-collector-validate-"))
    try:
        dest, manifest, warnings = extract_and_verify(args.package, tmp / "package")
    except ArchiveError as exc:
        print(f"INVALID: {exc}")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print(
        f"VALID: package {manifest.get('package_id')} "
        f"({len(manifest.get('evidence', []))} entries, "
        f"{len(manifest.get('file_hashes', {}))} files)."
    )
    for warning in warnings:
        print(f"warning: {warning}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if args else 2
    command, rest = args[0], args[1:]
    if command == "collect":
        return cmd_collect(rest)
    if command == "validate":
        return cmd_validate(rest)
    print(f"error: unknown command {command!r} (want collect|validate).")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
