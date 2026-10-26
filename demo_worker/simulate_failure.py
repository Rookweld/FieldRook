"""Demo setup helper: put the FieldRook demo worker into failing mode.

This is demo scaffolding run by the technician in a terminal, NOT a FieldRook
corrective action: it creates the incident that FieldRook then diagnoses.
Recovery happens only through FieldRook's approved recovery action.

Run:  python demo_worker/simulate_failure.py
"""

import json
import os
import sys

STATE_DIR = os.environ.get(
    "FIELDROOK_DEMO_STATE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "state"),
)


def main() -> int:
    os.makedirs(STATE_DIR, exist_ok=True)
    control_path = os.path.join(STATE_DIR, "control.json")
    with open(control_path, "w", encoding="utf-8") as handle:
        json.dump({"mode": "failing"}, handle)
    print(f"demo worker failure simulated ({control_path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
