"""E2E helper: build a validated collector ZIP from a JSON entry spec.

Usage:
    python make_pkg.py --out <pkg.zip> --host-hash <64hex> --entries <spec.json>
        [--package-id <id>] [--created-at <iso>] [--hint <text>]

The spec is a JSON list of {id, category, data, source_suffix?,
tool_name?, tool_args?, error?}. Entries validate through the real
collector manifest/archive path, so imports exercise production checks.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from collector import archive  # noqa: E402
from collector import manifest as colmanifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--host-hash", required=True)
    parser.add_argument("--entries", required=True)
    parser.add_argument("--package-id", default=None)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--hint", default="lens-e2e-pc")
    args = parser.parse_args()

    spec = json.loads(Path(args.entries).read_text(encoding="utf-8"))
    entries = [
        colmanifest.build_entry(
            item["id"],
            item["category"],
            item["data"],
            source_suffix=item.get("source_suffix", "live"),
            tool_name=item.get("tool_name"),
            tool_args=item.get("tool_args"),
            error=item.get("error"),
        )
        for item in spec
    ]
    manifest = colmanifest.build_manifest(
        hostname_hash=args.host_hash,
        os_info={"platform": "win32", "version": "11", "build": "26100"},
        evidence=entries,
        target_hint=args.hint,
        package_id=args.package_id,
        created_at=args.created_at,
    )
    errors, _ = colmanifest.validate_manifest(manifest)
    if errors:
        print(f"manifest invalid: {'; '.join(errors[:8])}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    archive.create_package(manifest, {}, out)
    print(manifest["package_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
